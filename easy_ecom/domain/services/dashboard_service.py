from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.errors import ApiException
from easy_ecom.core.time_utils import ensure_utc, now_utc
from easy_ecom.data.store.postgres_models import (
    ClientModel,
    InventoryLedgerModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.commerce_service import (
    CommerceBaseService,
    ZERO,
    as_decimal,
    as_optional_decimal,
    build_variant_label,
)


MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")
DEFAULT_TIMEZONE = "UTC"
FINANCIAL_ROLES = {"SUPER_ADMIN", "CLIENT_OWNER", "FINANCE_STAFF"}


@dataclass(frozen=True)
class DashboardRange:
    range_key: str
    label: str
    timezone: str
    from_date: date
    to_date: date
    previous_from_date: date
    previous_to_date: date
    bucket: str
    days: int
    start_utc: datetime
    end_exclusive_utc: datetime
    previous_start_utc: datetime
    previous_end_exclusive_utc: datetime


@dataclass
class ProductStockAggregate:
    product_id: str
    product_name: str
    on_hand_qty: Decimal = ZERO
    available_qty: Decimal = ZERO
    inventory_cost_value: Decimal = ZERO
    inventory_cost_complete: bool = True
    active_variants: int = 0


@dataclass
class ProductSalesAggregate:
    product_id: str
    product_name: str
    units_sold: Decimal = ZERO
    revenue: Decimal = ZERO
    estimated_cost: Decimal = ZERO
    cost_complete: bool = True


@dataclass
class SalesAggregation:
    completed_orders_count: int = 0
    units_sold: Decimal = ZERO
    revenue_total: Decimal = ZERO
    estimated_cost_total: Decimal = ZERO
    cost_complete: bool = True
    revenue_by_bucket: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    gross_profit_by_bucket: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    incomplete_profit_buckets: set[str] = field(default_factory=set)
    products: dict[str, ProductSalesAggregate] = field(default_factory=dict)


@dataclass
class ReturnsAggregation:
    returns_count: int = 0
    refund_total: Decimal = ZERO
    count_by_bucket: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    amount_by_bucket: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))


class DashboardAnalyticsService(CommerceBaseService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(session_factory)

    def analytics(
        self,
        user: AuthenticatedUser,
        *,
        range_key: str = "mtd",
        from_date: date | None = None,
        to_date: date | None = None,
        location_id: str | None = None,
    ) -> dict[str, object]:
        self._require_dashboard_access(user)

        with self._session_factory() as session:
            client = session.execute(
                select(ClientModel).where(ClientModel.client_id == user.client_id)
            ).scalar_one_or_none()
            if client is None:
                raise ApiException(status_code=404, code="CLIENT_NOT_FOUND", message="Tenant not found")

            timezone_name = client.timezone or DEFAULT_TIMEZONE
            range_ctx = self._resolve_range(
                timezone_name=timezone_name,
                range_key=range_key,
                custom_from=from_date,
                custom_to=to_date,
            )

            active_locations = self._active_locations(session, user.client_id)
            if not active_locations:
                raise ApiException(status_code=400, code="LOCATION_REQUIRED", message="No active location is configured for this tenant")

            selected_location_id = None
            if location_id:
                matched = next((item for item in active_locations if str(item.location_id) == location_id), None)
                if matched is None:
                    raise ApiException(status_code=404, code="LOCATION_NOT_FOUND", message="Requested location was not found")
                selected_location_id = str(matched.location_id)
                selected_location_ids = [selected_location_id]
            else:
                selected_location_ids = [str(item.location_id) for item in active_locations]

            can_view_financial_metrics = any(role in FINANCIAL_ROLES for role in user.roles)
            settings = self._client_settings(session, user.client_id)
            default_threshold = as_decimal(settings.low_stock_threshold) if settings else ZERO
            on_hand_map, reserved_map = self._stock_maps_for_locations(session, user.client_id, selected_location_ids)
            product_stock, low_stock_variants = self._build_stock_snapshot(
                session=session,
                client_id=user.client_id,
                on_hand_map=on_hand_map,
                reserved_map=reserved_map,
                default_threshold=default_threshold,
                can_view_financial_metrics=can_view_financial_metrics,
            )

            current_sales = self._sales_aggregation(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
                use_previous=False,
            )
            previous_sales = self._sales_aggregation(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
                use_previous=True,
            )
            current_returns = self._returns_aggregation(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
                use_previous=False,
            )
            previous_returns = self._returns_aggregation(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
                use_previous=True,
            )
            stock_movement = self._stock_movement_aggregation(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
            )
            previous_stock_received = self._stock_received_total(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                start_utc=range_ctx.previous_start_utc,
                end_exclusive_utc=range_ctx.previous_end_exclusive_utc,
            )
            open_confirmed_orders = self._open_confirmed_orders(session, user.client_id, selected_location_ids)
            recent_activity = self._recent_activity(session, user.client_id, selected_location_ids)

            stock_on_hand_units = sum((row.on_hand_qty for row in product_stock.values()), ZERO)
            available_units = sum((row.available_qty for row in product_stock.values()), ZERO)
            low_stock_count = len(low_stock_variants)

            revenue_unavailable_reason = None
            if not can_view_financial_metrics:
                revenue_unavailable_reason = "Financial metrics are hidden for your role."
            elif not current_sales.cost_complete:
                revenue_unavailable_reason = "Not enough cost data to estimate gross profit."

            opportunity_unavailable_reason = revenue_unavailable_reason

            kpis = self._build_kpis(
                can_view_financial_metrics=can_view_financial_metrics,
                current_sales=current_sales,
                previous_sales=previous_sales,
                current_returns=current_returns,
                previous_returns=previous_returns,
                stock_on_hand_units=stock_on_hand_units,
                low_stock_count=low_stock_count,
                open_confirmed_orders=open_confirmed_orders,
                stock_received_units=stock_movement["stock_received_total"],
                previous_stock_received=previous_stock_received,
                gross_profit_unavailable_reason=revenue_unavailable_reason if can_view_financial_metrics else None,
            )

            top_products_by_units = self._top_products_by_units(current_sales)
            top_products_by_revenue = self._top_products_by_revenue(current_sales, can_view_financial_metrics)
            top_products_by_profit = self._top_products_by_profit(
                current_sales,
                can_view_financial_metrics,
                unavailable_reason=revenue_unavailable_reason,
            )
            opportunity_points = self._product_opportunity_points(
                current_sales=current_sales,
                product_stock=product_stock,
                range_days=range_ctx.days,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            insight_cards = self._build_insight_cards(
                product_stock=product_stock,
                current_sales=current_sales,
                opportunity_points=opportunity_points,
                can_view_financial_metrics=can_view_financial_metrics,
                gross_profit_unavailable_reason=revenue_unavailable_reason,
            )
            slow_movers = self._slow_movers(product_stock, current_sales, can_view_financial_metrics)

            return {
                "generated_at": now_utc().isoformat(),
                "has_multiple_locations": len(active_locations) > 1,
                "selected_location_id": selected_location_id,
                "locations": [
                    {
                        "location_id": str(location.location_id),
                        "name": location.name,
                        "is_default": bool(location.is_default),
                    }
                    for location in active_locations
                ],
                "applied_range": {
                    "range_key": range_ctx.range_key,
                    "label": range_ctx.label,
                    "timezone": range_ctx.timezone,
                    "from_date": range_ctx.from_date.isoformat(),
                    "to_date": range_ctx.to_date.isoformat(),
                    "previous_from_date": range_ctx.previous_from_date.isoformat(),
                    "previous_to_date": range_ctx.previous_to_date.isoformat(),
                    "bucket": range_ctx.bucket,
                    "days": range_ctx.days,
                },
                "visibility": {
                    "can_view_financial_metrics": can_view_financial_metrics,
                },
                "kpis": kpis,
                "insight_cards": insight_cards,
                "charts": {
                    "revenue_profit_trend": {
                        "items": self._revenue_profit_points(
                            range_ctx=range_ctx,
                            sales=current_sales,
                            can_view_financial_metrics=can_view_financial_metrics,
                        ),
                        "unavailable_reason": revenue_unavailable_reason,
                    },
                    "stock_movement_trend": self._stock_movement_points(range_ctx=range_ctx, movement=stock_movement["by_bucket"]),
                    "returns_trend": {
                        "items": self._returns_points(
                            range_ctx=range_ctx,
                            returns_agg=current_returns,
                            can_view_financial_metrics=can_view_financial_metrics,
                        ),
                    },
                    "product_opportunity_matrix": {
                        "items": opportunity_points if can_view_financial_metrics and current_sales.cost_complete else [],
                        "unavailable_reason": opportunity_unavailable_reason,
                    },
                },
                "tables": {
                    "stock_investment_by_product": self._stock_investment_rows(product_stock, can_view_financial_metrics),
                    "low_stock_variants": low_stock_variants[:8],
                    "top_products_by_units_sold": top_products_by_units,
                    "top_products_by_revenue": {
                        "items": top_products_by_revenue if can_view_financial_metrics else [],
                        "unavailable_reason": None if can_view_financial_metrics else "Financial metrics are hidden for your role.",
                    },
                    "top_products_by_estimated_gross_profit": {
                        "items": top_products_by_profit if can_view_financial_metrics and current_sales.cost_complete else [],
                        "unavailable_reason": revenue_unavailable_reason,
                    },
                    "slow_movers": slow_movers,
                    "recent_activity": recent_activity,
                },
            }

    def _require_dashboard_access(self, user: AuthenticatedUser) -> None:
        if "Dashboard" not in user.allowed_pages and "SUPER_ADMIN" not in user.roles:
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Access denied for Dashboard")

    def _resolve_range(
        self,
        *,
        timezone_name: str,
        range_key: str,
        custom_from: date | None,
        custom_to: date | None,
    ) -> DashboardRange:
        zone = self._zoneinfo(timezone_name)
        today_local = now_utc().astimezone(zone).date()

        normalized = (range_key or "mtd").strip().lower()
        label = "Month to date"
        if normalized == "mtd":
            start_date = today_local.replace(day=1)
            end_date = today_local
        elif normalized == "last_7_days":
            start_date = today_local - timedelta(days=6)
            end_date = today_local
            label = "Last 7 days"
        elif normalized == "last_30_days":
            start_date = today_local - timedelta(days=29)
            end_date = today_local
            label = "Last 30 days"
        elif normalized == "last_90_days":
            start_date = today_local - timedelta(days=89)
            end_date = today_local
            label = "Last 90 days"
        elif normalized == "custom":
            if custom_from is None or custom_to is None:
                raise ApiException(status_code=400, code="INVALID_RANGE", message="Custom range requires both from_date and to_date")
            start_date = custom_from
            end_date = custom_to
            label = "Custom range"
        else:
            raise ApiException(status_code=400, code="INVALID_RANGE", message="Unsupported dashboard range")

        if end_date < start_date:
            raise ApiException(status_code=400, code="INVALID_RANGE", message="to_date cannot be earlier than from_date")

        days = (end_date - start_date).days + 1
        if days > 366:
            raise ApiException(status_code=400, code="INVALID_RANGE", message="Dashboard range cannot exceed 366 days")

        previous_end_date = start_date - timedelta(days=1)
        previous_start_date = previous_end_date - timedelta(days=days - 1)
        bucket = "day" if days <= 31 else "week"

        start_utc = self._local_start_of_day(start_date, zone)
        end_exclusive_utc = self._local_start_of_day(end_date + timedelta(days=1), zone)
        previous_start_utc = self._local_start_of_day(previous_start_date, zone)
        previous_end_exclusive_utc = self._local_start_of_day(previous_end_date + timedelta(days=1), zone)

        return DashboardRange(
            range_key=normalized,
            label=label,
            timezone=zone.key,
            from_date=start_date,
            to_date=end_date,
            previous_from_date=previous_start_date,
            previous_to_date=previous_end_date,
            bucket=bucket,
            days=days,
            start_utc=start_utc,
            end_exclusive_utc=end_exclusive_utc,
            previous_start_utc=previous_start_utc,
            previous_end_exclusive_utc=previous_end_exclusive_utc,
        )

    def _zoneinfo(self, timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo(DEFAULT_TIMEZONE)

    def _local_start_of_day(self, value: date, zone: ZoneInfo) -> datetime:
        return datetime.combine(value, time.min, tzinfo=zone).astimezone(ZoneInfo("UTC"))

    def _stock_maps_for_locations(
        self,
        session: Session,
        client_id: str,
        location_ids: list[str],
    ) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
        on_hand = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    InventoryLedgerModel.variant_id,
                    func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO),
                )
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id.in_(location_ids),
                )
                .group_by(InventoryLedgerModel.variant_id)
            ).all()
        }

        reserved = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    SalesOrderItemModel.variant_id,
                    func.coalesce(
                        func.sum(
                            SalesOrderItemModel.quantity
                            - SalesOrderItemModel.quantity_fulfilled
                            - SalesOrderItemModel.quantity_cancelled
                        ),
                        ZERO,
                    ),
                )
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    SalesOrderItemModel.client_id == client_id,
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.location_id.in_(location_ids),
                    SalesOrderModel.status == "confirmed",
                )
                .group_by(SalesOrderItemModel.variant_id)
            ).all()
        }
        return on_hand, reserved

    def _build_stock_snapshot(
        self,
        *,
        session: Session,
        client_id: str,
        on_hand_map: dict[str, Decimal],
        reserved_map: dict[str, Decimal],
        default_threshold: Decimal,
        can_view_financial_metrics: bool,
    ) -> tuple[dict[str, ProductStockAggregate], list[dict[str, object]]]:
        product_stock: dict[str, ProductStockAggregate] = {}
        low_stock_variants: list[dict[str, object]] = []

        for product, variant, _supplier, _category in session.execute(self._base_variant_stmt(client_id)).all():
            variant_id = str(variant.variant_id)
            product_id = str(product.product_id)
            on_hand = on_hand_map.get(variant_id, ZERO)
            reserved = reserved_map.get(variant_id, ZERO)
            available = on_hand - reserved
            threshold = as_decimal(variant.reorder_level) if as_decimal(variant.reorder_level) > ZERO else default_threshold
            cost_amount = as_optional_decimal(variant.cost_amount)
            inventory_cost_value = None
            if can_view_financial_metrics and on_hand > ZERO and cost_amount is not None:
                inventory_cost_value = (on_hand * cost_amount).quantize(MONEY_QUANTUM)

            aggregate = product_stock.setdefault(
                product_id,
                ProductStockAggregate(
                    product_id=product_id,
                    product_name=product.name,
                ),
            )
            aggregate.on_hand_qty += on_hand
            aggregate.available_qty += available
            if variant.status == "active":
                aggregate.active_variants += 1
            if on_hand > ZERO:
                if cost_amount is None:
                    aggregate.inventory_cost_complete = False
                elif can_view_financial_metrics:
                    aggregate.inventory_cost_value += inventory_cost_value or ZERO

            if threshold > ZERO and available <= threshold:
                low_stock_variants.append(
                    {
                        "variant_id": variant_id,
                        "product_id": product_id,
                        "product_name": product.name,
                        "label": build_variant_label(product.name, variant.title),
                        "on_hand_qty": on_hand,
                        "reserved_qty": reserved,
                        "available_qty": available,
                        "reorder_level": threshold,
                        "inventory_cost_value": inventory_cost_value if can_view_financial_metrics else None,
                    }
                )

        low_stock_variants.sort(key=lambda item: (as_decimal(item["available_qty"]), item["product_name"], item["label"]))
        return product_stock, low_stock_variants

    def _sales_aggregation(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        range_ctx: DashboardRange,
        use_previous: bool,
    ) -> SalesAggregation:
        start_utc = range_ctx.previous_start_utc if use_previous else range_ctx.start_utc
        end_exclusive_utc = range_ctx.previous_end_exclusive_utc if use_previous else range_ctx.end_exclusive_utc
        event_expr = func.coalesce(
            SalesOrderModel.confirmed_at,
            SalesOrderModel.ordered_at,
            SalesOrderModel.created_at,
        )

        rows = session.execute(
            select(
                event_expr,
                SalesOrderModel.sales_order_id,
                SalesOrderItemModel.sales_order_item_id,
                ProductModel.product_id,
                ProductModel.name,
                SalesOrderItemModel.quantity,
                SalesOrderItemModel.quantity_fulfilled,
                SalesOrderItemModel.quantity_cancelled,
                SalesOrderItemModel.line_total_amount,
            )
            .join(SalesOrderItemModel, SalesOrderItemModel.sales_order_id == SalesOrderModel.sales_order_id)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesOrderModel.client_id == client_id,
                SalesOrderItemModel.client_id == client_id,
                ProductVariantModel.client_id == client_id,
                ProductModel.client_id == client_id,
                SalesOrderModel.status == "completed",
                SalesOrderModel.location_id.in_(location_ids),
                event_expr >= start_utc,
                event_expr < end_exclusive_utc,
            )
        ).all()

        aggregation = SalesAggregation()
        if not rows:
            return aggregation

        order_ids = {str(order_id) for _event_at, order_id, *_rest in rows}
        aggregation.completed_orders_count = len(order_ids)

        line_ids = [str(line_id) for _event_at, _order_id, line_id, *_rest in rows]
        cost_lookup: dict[str, Decimal] = defaultdict(lambda: ZERO)
        missing_cost_lines: set[str] = set(line_ids)
        if line_ids:
            for line_id, quantity_delta, unit_cost_amount in session.execute(
                select(
                    InventoryLedgerModel.reference_line_id,
                    InventoryLedgerModel.quantity_delta,
                    InventoryLedgerModel.unit_cost_amount,
                )
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.reference_type == "sales_order",
                    InventoryLedgerModel.movement_type == "sale_fulfilled",
                    InventoryLedgerModel.reference_line_id.in_(line_ids),
                )
            ).all():
                line_key = str(line_id)
                if unit_cost_amount is None:
                    continue
                cost_lookup[line_key] += (abs(as_decimal(quantity_delta)) * as_decimal(unit_cost_amount)).quantize(MONEY_QUANTUM)
                missing_cost_lines.discard(line_key)

        zone = self._zoneinfo(range_ctx.timezone)
        for event_at, _order_id, line_id, product_id, product_name, quantity, quantity_fulfilled, quantity_cancelled, line_total in rows:
            line_key = str(line_id)
            sold_quantity = as_decimal(quantity_fulfilled)
            if sold_quantity <= ZERO:
                sold_quantity = max(ZERO, as_decimal(quantity) - as_decimal(quantity_cancelled))
            if sold_quantity <= ZERO:
                continue

            event_local = ensure_utc(event_at).astimezone(zone)
            bucket = self._bucket_label(range_ctx, event_local.date())
            revenue = as_decimal(line_total)

            aggregation.units_sold += sold_quantity
            aggregation.revenue_total += revenue
            aggregation.revenue_by_bucket[bucket] += revenue

            product_key = str(product_id)
            product_agg = aggregation.products.setdefault(
                product_key,
                ProductSalesAggregate(product_id=product_key, product_name=product_name),
            )
            product_agg.units_sold += sold_quantity
            product_agg.revenue += revenue

            if line_key in missing_cost_lines:
                aggregation.cost_complete = False
                aggregation.incomplete_profit_buckets.add(bucket)
                product_agg.cost_complete = False
                continue

            line_cost = cost_lookup.get(line_key, ZERO)
            aggregation.estimated_cost_total += line_cost
            aggregation.gross_profit_by_bucket[bucket] += revenue - line_cost
            product_agg.estimated_cost += line_cost

        return aggregation

    def _returns_aggregation(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        range_ctx: DashboardRange,
        use_previous: bool,
    ) -> ReturnsAggregation:
        start_utc = range_ctx.previous_start_utc if use_previous else range_ctx.start_utc
        end_exclusive_utc = range_ctx.previous_end_exclusive_utc if use_previous else range_ctx.end_exclusive_utc
        event_expr = func.coalesce(SalesReturnModel.received_at, SalesReturnModel.requested_at, SalesReturnModel.created_at)
        rows = session.execute(
            select(
                event_expr,
                SalesReturnModel.refund_amount,
            )
            .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesReturnModel.sales_order_id)
            .where(
                SalesReturnModel.client_id == client_id,
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.location_id.in_(location_ids),
                event_expr >= start_utc,
                event_expr < end_exclusive_utc,
            )
        ).all()

        aggregation = ReturnsAggregation()
        if not rows:
            return aggregation

        zone = self._zoneinfo(range_ctx.timezone)
        for event_at, refund_amount in rows:
            event_local = ensure_utc(event_at).astimezone(zone)
            bucket = self._bucket_label(range_ctx, event_local.date())
            refund_total = as_decimal(refund_amount)
            aggregation.returns_count += 1
            aggregation.refund_total += refund_total
            aggregation.count_by_bucket[bucket] += 1
            aggregation.amount_by_bucket[bucket] += refund_total
        return aggregation

    def _stock_movement_aggregation(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        range_ctx: DashboardRange,
    ) -> dict[str, object]:
        rows = session.execute(
            select(
                InventoryLedgerModel.created_at,
                InventoryLedgerModel.movement_type,
                InventoryLedgerModel.quantity_delta,
            )
            .where(
                InventoryLedgerModel.client_id == client_id,
                InventoryLedgerModel.location_id.in_(location_ids),
                InventoryLedgerModel.created_at >= range_ctx.start_utc,
                InventoryLedgerModel.created_at < range_ctx.end_exclusive_utc,
                InventoryLedgerModel.movement_type.in_(
                    ("stock_received", "sale_fulfilled", "sales_return_restock", "adjustment")
                ),
            )
        ).all()

        zone = self._zoneinfo(range_ctx.timezone)
        by_bucket: dict[str, dict[str, Decimal]] = {
            label: {
                "stock_received": ZERO,
                "sale_fulfilled": ZERO,
                "sales_return_restock": ZERO,
                "adjustment": ZERO,
            }
            for label in self._bucket_labels(range_ctx)
        }
        stock_received_total = ZERO
        for created_at, movement_type, quantity_delta in rows:
            bucket = self._bucket_label(range_ctx, ensure_utc(created_at).astimezone(zone).date())
            movement_qty = abs(as_decimal(quantity_delta))
            by_bucket[bucket][str(movement_type)] += movement_qty
            if movement_type == "stock_received":
                stock_received_total += movement_qty

        return {
            "by_bucket": by_bucket,
            "stock_received_total": stock_received_total,
        }

    def _stock_received_total(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        start_utc: datetime,
        end_exclusive_utc: datetime,
    ) -> Decimal:
        return as_decimal(
            session.execute(
                select(func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO))
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id.in_(location_ids),
                    InventoryLedgerModel.movement_type == "stock_received",
                    InventoryLedgerModel.created_at >= start_utc,
                    InventoryLedgerModel.created_at < end_exclusive_utc,
                )
            ).scalar_one()
        )

    def _open_confirmed_orders(self, session: Session, client_id: str, location_ids: list[str]) -> int:
        return int(
            session.execute(
                select(func.count())
                .select_from(SalesOrderModel)
                .where(
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.location_id.in_(location_ids),
                    SalesOrderModel.status == "confirmed",
                )
            ).scalar_one()
            or 0
        )

    def _recent_activity(self, session: Session, client_id: str, location_ids: list[str]) -> list[dict[str, object]]:
        rows = session.execute(
            select(
                InventoryLedgerModel.created_at,
                InventoryLedgerModel.movement_type,
                InventoryLedgerModel.quantity_delta,
                InventoryLedgerModel.reason,
                ProductModel.name,
                ProductVariantModel.title,
            )
            .join(ProductVariantModel, ProductVariantModel.variant_id == InventoryLedgerModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                InventoryLedgerModel.client_id == client_id,
                InventoryLedgerModel.location_id.in_(location_ids),
            )
            .order_by(InventoryLedgerModel.created_at.desc())
            .limit(10)
        ).all()

        event_labels = {
            "stock_received": "Stock received",
            "sale_fulfilled": "Sale fulfilled",
            "sales_return_restock": "Return restocked",
            "adjustment": "Stock adjusted",
        }
        return [
            {
                "timestamp": ensure_utc(created_at).isoformat(),
                "event_type": event_labels.get(str(movement_type), str(movement_type).replace("_", " ").title()),
                "product_name": product_name,
                "label": build_variant_label(product_name, variant_title),
                "quantity": abs(as_decimal(quantity_delta)),
                "note": reason or None,
            }
            for created_at, movement_type, quantity_delta, reason, product_name, variant_title in rows
        ]

    def _build_kpis(
        self,
        *,
        can_view_financial_metrics: bool,
        current_sales: SalesAggregation,
        previous_sales: SalesAggregation,
        current_returns: ReturnsAggregation,
        previous_returns: ReturnsAggregation,
        stock_on_hand_units: Decimal,
        low_stock_count: int,
        open_confirmed_orders: int,
        stock_received_units: Decimal,
        previous_stock_received: Decimal,
        gross_profit_unavailable_reason: str | None,
    ) -> list[dict[str, object]]:
        kpis: list[dict[str, object]] = []

        if can_view_financial_metrics:
            kpis.extend(
                [
                    self._metric(
                        "completed_sales_revenue",
                        "Completed Sales",
                        current_sales.revenue_total.quantize(MONEY_QUANTUM),
                        "money",
                        delta_value=(current_sales.revenue_total - previous_sales.revenue_total).quantize(MONEY_QUANTUM),
                    ),
                    self._metric(
                        "estimated_gross_profit",
                        "Estimated Gross Profit",
                        (current_sales.revenue_total - current_sales.estimated_cost_total).quantize(MONEY_QUANTUM)
                        if current_sales.cost_complete
                        else None,
                        "money",
                        delta_value=(
                            (current_sales.revenue_total - current_sales.estimated_cost_total)
                            - (previous_sales.revenue_total - previous_sales.estimated_cost_total)
                        ).quantize(MONEY_QUANTUM)
                        if current_sales.cost_complete and previous_sales.cost_complete
                        else None,
                        is_estimated=True,
                        unavailable_reason=gross_profit_unavailable_reason,
                    ),
                ]
            )

        kpis.extend(
            [
                self._metric(
                    "completed_orders",
                    "Completed Orders",
                    current_sales.completed_orders_count,
                    "count",
                    delta_value=current_sales.completed_orders_count - previous_sales.completed_orders_count,
                ),
                self._metric(
                    "units_sold",
                    "Units Sold",
                    current_sales.units_sold,
                    "quantity",
                    delta_value=current_sales.units_sold - previous_sales.units_sold,
                ),
            ]
        )

        if not can_view_financial_metrics:
            kpis.append(
                self._metric(
                    "stock_received_units",
                    "Stock Received",
                    stock_received_units,
                    "quantity",
                    delta_value=stock_received_units - previous_stock_received,
                )
            )
            kpis.append(
                self._metric(
                    "open_confirmed_orders",
                    "Open Confirmed Orders",
                    open_confirmed_orders,
                    "count",
                    help_text="Orders currently reserved and awaiting fulfillment.",
                )
            )

        kpis.extend(
            [
                self._metric(
                    "stock_on_hand_units",
                    "Stock On Hand",
                    stock_on_hand_units,
                    "quantity",
                    help_text="Current available quantity across the selected locations.",
                ),
                self._metric(
                    "low_stock_variants",
                    "Low Stock Variants",
                    low_stock_count,
                    "count",
                    help_text="Variants at or below their reorder threshold.",
                ),
            ]
        )
        return kpis

    def _metric(
        self,
        metric_id: str,
        label: str,
        value: Decimal | int | None,
        unit: str,
        *,
        delta_value: Decimal | int | None = None,
        help_text: str | None = None,
        is_estimated: bool = False,
        unavailable_reason: str | None = None,
    ) -> dict[str, object]:
        direction = None
        if delta_value is not None:
            if isinstance(delta_value, Decimal):
                if delta_value > ZERO:
                    direction = "up"
                elif delta_value < ZERO:
                    direction = "down"
                else:
                    direction = "flat"
            else:
                if delta_value > 0:
                    direction = "up"
                elif delta_value < 0:
                    direction = "down"
                else:
                    direction = "flat"
        return {
            "id": metric_id,
            "label": label,
            "value": value,
            "unit": unit,
            "delta_value": delta_value,
            "delta_direction": direction,
            "help_text": help_text,
            "is_estimated": is_estimated,
            "unavailable_reason": unavailable_reason,
        }

    def _revenue_profit_points(
        self,
        *,
        range_ctx: DashboardRange,
        sales: SalesAggregation,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        points: list[dict[str, object]] = []
        for bucket in self._bucket_labels(range_ctx):
            points.append(
                {
                    "period": bucket,
                    "revenue": sales.revenue_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM),
                    "estimated_gross_profit": (
                        sales.gross_profit_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
                        if can_view_financial_metrics and bucket not in sales.incomplete_profit_buckets
                        else None
                    ),
                }
            )
        return points

    def _stock_movement_points(
        self,
        *,
        range_ctx: DashboardRange,
        movement: dict[str, dict[str, Decimal]],
    ) -> list[dict[str, object]]:
        return [
            {
                "period": bucket,
                "stock_received": values["stock_received"],
                "sale_fulfilled": values["sale_fulfilled"],
                "sales_return_restock": values["sales_return_restock"],
                "adjustment": values["adjustment"],
            }
            for bucket, values in ((bucket, movement[bucket]) for bucket in self._bucket_labels(range_ctx))
        ]

    def _returns_points(
        self,
        *,
        range_ctx: DashboardRange,
        returns_agg: ReturnsAggregation,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        return [
            {
                "period": bucket,
                "returns_count": returns_agg.count_by_bucket.get(bucket, 0),
                "refund_amount": returns_agg.amount_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
                if can_view_financial_metrics
                else None,
            }
            for bucket in self._bucket_labels(range_ctx)
        ]

    def _stock_investment_rows(
        self,
        product_stock: dict[str, ProductStockAggregate],
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        rows = []
        for item in product_stock.values():
            if item.on_hand_qty <= ZERO and item.available_qty <= ZERO:
                continue
            rows.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "on_hand_qty": item.on_hand_qty,
                    "available_qty": item.available_qty,
                    "inventory_cost_value": (
                        item.inventory_cost_value.quantize(MONEY_QUANTUM)
                        if can_view_financial_metrics and item.inventory_cost_complete
                        else None
                    ),
                    "active_variants": item.active_variants,
                }
            )
        rows.sort(
            key=lambda item: (
                as_decimal(item["inventory_cost_value"]) if item["inventory_cost_value"] is not None else ZERO,
                as_decimal(item["on_hand_qty"]),
            ),
            reverse=True,
        )
        return rows[:10]

    def _top_products_by_units(self, sales: SalesAggregation) -> list[dict[str, object]]:
        rows = self._leaderboard_rows(sales)
        rows.sort(key=lambda item: (as_decimal(item["units_sold"]), as_decimal(item["revenue"])), reverse=True)
        return rows[:8]

    def _leaderboard_rows(self, sales: SalesAggregation) -> list[dict[str, object]]:
        rows = []
        for item in sales.products.values():
            rows.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "units_sold": item.units_sold,
                    "revenue": item.revenue.quantize(MONEY_QUANTUM),
                    "estimated_gross_profit": (
                        (item.revenue - item.estimated_cost).quantize(MONEY_QUANTUM) if item.cost_complete else None
                    ),
                    "estimated_margin_percent": (
                        (((item.revenue - item.estimated_cost) / item.revenue) * Decimal("100")).quantize(PERCENT_QUANTUM)
                        if item.cost_complete and item.revenue > ZERO
                        else None
                    ),
                }
            )
        return rows

    def _top_products_by_revenue(self, sales: SalesAggregation, can_view_financial_metrics: bool) -> list[dict[str, object]]:
        if not can_view_financial_metrics:
            return []
        rows = self._leaderboard_rows(sales)
        rows.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
        return rows[:8]

    def _top_products_by_profit(
        self,
        sales: SalesAggregation,
        can_view_financial_metrics: bool,
        *,
        unavailable_reason: str | None,
    ) -> list[dict[str, object]]:
        if not can_view_financial_metrics or unavailable_reason:
            return []
        rows = [row for row in self._leaderboard_rows(sales) if row["estimated_gross_profit"] is not None]
        rows.sort(key=lambda item: as_decimal(item["estimated_gross_profit"]), reverse=True)
        return rows[:8]

    def _product_opportunity_points(
        self,
        *,
        current_sales: SalesAggregation,
        product_stock: dict[str, ProductStockAggregate],
        range_days: int,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        if not can_view_financial_metrics or not current_sales.cost_complete:
            return []

        points: list[dict[str, object]] = []
        divisor = Decimal(str(range_days))
        for item in current_sales.products.values():
            stock = product_stock.get(item.product_id)
            available_qty = stock.available_qty if stock else ZERO
            units_per_day = (item.units_sold / divisor).quantize(PERCENT_QUANTUM) if divisor > ZERO else ZERO
            estimated_gross_profit = item.revenue - item.estimated_cost
            margin_percent = (
                ((estimated_gross_profit / item.revenue) * Decimal("100")).quantize(PERCENT_QUANTUM)
                if item.revenue > ZERO and item.cost_complete
                else None
            )
            days_cover = None
            if units_per_day > ZERO and available_qty > ZERO:
                days_cover = (available_qty / units_per_day).quantize(PERCENT_QUANTUM)

            points.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "units_sold": item.units_sold,
                    "sales_qty_per_day": units_per_day,
                    "estimated_margin_percent": margin_percent,
                    "inventory_cost_value": (
                        stock.inventory_cost_value.quantize(MONEY_QUANTUM)
                        if stock and stock.inventory_cost_complete
                        else None
                    ),
                    "revenue": item.revenue.quantize(MONEY_QUANTUM),
                    "estimated_gross_profit": estimated_gross_profit.quantize(MONEY_QUANTUM),
                    "available_qty": available_qty,
                    "days_cover": days_cover,
                }
            )
        points.sort(key=lambda item: (as_decimal(item["units_sold"]), as_decimal(item["revenue"])), reverse=True)
        return points[:20]

    def _build_insight_cards(
        self,
        *,
        product_stock: dict[str, ProductStockAggregate],
        current_sales: SalesAggregation,
        opportunity_points: list[dict[str, object]],
        can_view_financial_metrics: bool,
        gross_profit_unavailable_reason: str | None,
    ) -> list[dict[str, object]]:
        cards: list[dict[str, object]] = []

        replenish = [
            point
            for point in opportunity_points
            if as_decimal(point["sales_qty_per_day"]) > ZERO
            and point["days_cover"] is not None
            and as_decimal(point["days_cover"]) <= Decimal("14")
        ]
        replenish.sort(key=lambda item: (as_decimal(item["sales_qty_per_day"]), -as_decimal(item["days_cover"])), reverse=True)
        cards.append(
            {
                "id": "replenish_winners",
                "title": "Replenish Winners",
                "summary": "Products moving quickly with limited days of cover.",
                "metric_label": "Products under 14 days cover",
                "metric_value": str(len(replenish)),
                "tone": "warning" if replenish else "positive",
                "entity_name": replenish[0]["product_name"] if replenish else None,
                "path": "/inventory?tab=low-stock",
                "unavailable_reason": None,
            }
        )

        products_without_sales = [
            stock
            for stock in product_stock.values()
            if stock.available_qty > ZERO and (
                stock.product_id not in current_sales.products or current_sales.products[stock.product_id].units_sold <= ZERO
            )
        ]
        products_without_sales.sort(key=lambda item: (item.inventory_cost_value, item.available_qty), reverse=True)
        cards.append(
            {
                "id": "capital_trapped",
                "title": "Capital Trapped",
                "summary": "Current stock with no completed sales in the selected period.",
                "metric_label": "Products with no sales",
                "metric_value": str(len(products_without_sales)),
                "tone": "critical" if products_without_sales else "positive",
                "entity_name": products_without_sales[0].product_name if products_without_sales else None,
                "path": "/inventory",
                "unavailable_reason": None,
            }
        )

        if can_view_financial_metrics:
            if gross_profit_unavailable_reason:
                cards.extend(
                    [
                        {
                            "id": "margin_leaders",
                            "title": "Margin Leaders",
                            "summary": "High-velocity products with healthy estimated margin.",
                            "metric_label": "Status",
                            "metric_value": "Unavailable",
                            "tone": "info",
                            "entity_name": None,
                            "path": "/sales",
                            "unavailable_reason": gross_profit_unavailable_reason,
                        },
                        {
                            "id": "price_test_candidates",
                            "title": "Price-Test Candidates",
                            "summary": "High-margin products with room to test lower pricing for more volume.",
                            "metric_label": "Status",
                            "metric_value": "Unavailable",
                            "tone": "info",
                            "entity_name": None,
                            "path": "/catalog",
                            "unavailable_reason": gross_profit_unavailable_reason,
                        },
                        {
                            "id": "margin_leak",
                            "title": "Margin Leak",
                            "summary": "Products selling through while returning weak estimated margin.",
                            "metric_label": "Status",
                            "metric_value": "Unavailable",
                            "tone": "info",
                            "entity_name": None,
                            "path": "/sales",
                            "unavailable_reason": gross_profit_unavailable_reason,
                        },
                    ]
                )
                return cards

            margin_leaders = [
                point
                for point in opportunity_points
                if point["estimated_margin_percent"] is not None
                and as_decimal(point["estimated_margin_percent"]) >= Decimal("30")
                and as_decimal(point["sales_qty_per_day"]) > ZERO
            ]
            margin_leaders.sort(
                key=lambda item: (as_decimal(item["estimated_gross_profit"]), as_decimal(item["sales_qty_per_day"])),
                reverse=True,
            )
            cards.append(
                {
                    "id": "margin_leaders",
                    "title": "Margin Leaders",
                    "summary": "Products combining strong movement with healthy estimated margin.",
                    "metric_label": "Products above 30% margin",
                    "metric_value": str(len(margin_leaders)),
                    "tone": "positive",
                    "entity_name": margin_leaders[0]["product_name"] if margin_leaders else None,
                    "path": "/sales",
                    "unavailable_reason": None,
                }
            )

            price_test_candidates = [
                point
                for point in opportunity_points
                if point["estimated_margin_percent"] is not None
                and as_decimal(point["estimated_margin_percent"]) >= Decimal("35")
                and point["days_cover"] is not None
                and as_decimal(point["days_cover"]) >= Decimal("30")
            ]
            price_test_candidates.sort(
                key=lambda item: (
                    as_decimal(item["estimated_margin_percent"]),
                    as_decimal(item["inventory_cost_value"]) if item["inventory_cost_value"] is not None else ZERO,
                ),
                reverse=True,
            )
            cards.append(
                {
                    "id": "price_test_candidates",
                    "title": "Price-Test Candidates",
                    "summary": "High-margin products with enough cover to test a lower price for more demand.",
                    "metric_label": "Products above 35% margin with 30+ days cover",
                    "metric_value": str(len(price_test_candidates)),
                    "tone": "info",
                    "entity_name": price_test_candidates[0]["product_name"] if price_test_candidates else None,
                    "path": "/catalog",
                    "unavailable_reason": None,
                }
            )

            margin_leak = [
                point
                for point in opportunity_points
                if point["estimated_margin_percent"] is not None
                and as_decimal(point["estimated_margin_percent"]) <= Decimal("15")
                and as_decimal(point["units_sold"]) > ZERO
            ]
            margin_leak.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
            cards.append(
                {
                    "id": "margin_leak",
                    "title": "Margin Leak",
                    "summary": "Products driving sales without much estimated margin left.",
                    "metric_label": "Products at or below 15% margin",
                    "metric_value": str(len(margin_leak)),
                    "tone": "warning" if margin_leak else "positive",
                    "entity_name": margin_leak[0]["product_name"] if margin_leak else None,
                    "path": "/sales",
                    "unavailable_reason": None,
                }
            )

        return cards

    def _slow_movers(
        self,
        product_stock: dict[str, ProductStockAggregate],
        current_sales: SalesAggregation,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for stock in product_stock.values():
            if stock.available_qty <= ZERO:
                continue
            sold = current_sales.products.get(stock.product_id)
            sold_qty = sold.units_sold if sold else ZERO
            if sold_qty > ZERO:
                continue
            rows.append(
                {
                    "product_id": stock.product_id,
                    "product_name": stock.product_name,
                    "available_qty": stock.available_qty,
                    "inventory_cost_value": (
                        stock.inventory_cost_value.quantize(MONEY_QUANTUM)
                        if can_view_financial_metrics and stock.inventory_cost_complete
                        else None
                    ),
                    "units_sold_in_range": ZERO,
                }
            )
        rows.sort(
            key=lambda item: (
                as_decimal(item["inventory_cost_value"]) if item["inventory_cost_value"] is not None else ZERO,
                as_decimal(item["available_qty"]),
            ),
            reverse=True,
        )
        return rows[:8]

    def _bucket_labels(self, range_ctx: DashboardRange) -> list[str]:
        labels: list[str] = []
        cursor = range_ctx.from_date
        if range_ctx.bucket == "day":
            while cursor <= range_ctx.to_date:
                labels.append(cursor.strftime("%b %d"))
                cursor += timedelta(days=1)
            return labels

        while cursor <= range_ctx.to_date:
            end = min(cursor + timedelta(days=6), range_ctx.to_date)
            labels.append(f"{cursor.strftime('%b %d')}-{end.strftime('%d')}")
            cursor = end + timedelta(days=1)
        return labels

    def _bucket_label(self, range_ctx: DashboardRange, value: date) -> str:
        if range_ctx.bucket == "day":
            return value.strftime("%b %d")
        offset = (value - range_ctx.from_date).days
        start = range_ctx.from_date + timedelta(days=(offset // 7) * 7)
        end = min(start + timedelta(days=6), range_ctx.to_date)
        return f"{start.strftime('%b %d')}-{end.strftime('%d')}"
