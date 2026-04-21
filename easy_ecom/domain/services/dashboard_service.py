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
    CategoryModel,
    ClientModel,
    InventoryLedgerModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnModel,
    SalesReturnItemModel,
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
    discount_total: Decimal = ZERO
    gross_before_discount: Decimal = ZERO
    cost_complete: bool = True


@dataclass
class SalesAggregation:
    completed_orders_count: int = 0
    units_sold: Decimal = ZERO
    revenue_total: Decimal = ZERO
    estimated_cost_total: Decimal = ZERO
    discount_total: Decimal = ZERO
    gross_before_discount_total: Decimal = ZERO
    cost_complete: bool = True
    revenue_by_bucket: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    orders_by_bucket: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    discount_by_bucket: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
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
            on_hand_at_range_start = self._stock_map_until(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                end_exclusive_utc=range_ctx.start_utc,
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
            product_dimensions = self._product_dimension_map(
                session=session,
                client_id=user.client_id,
                product_ids=set(current_sales.products.keys()) | set(previous_sales.products.keys()) | set(product_stock.keys()),
            )
            conversion_funnel = self._conversion_funnel(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
            )
            returns_intelligence = self._returns_intelligence(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                range_ctx=range_ctx,
                returns_agg=current_returns,
                orders_by_bucket=current_sales.orders_by_bucket,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            inventory_aging = self._inventory_aging_waterfall(
                session=session,
                client_id=user.client_id,
                location_ids=selected_location_ids,
                on_hand_map=on_hand_map,
                start_on_hand_map=on_hand_at_range_start,
                as_of_date=range_ctx.to_date,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            sell_through_cover = self._sell_through_cover_matrix(
                product_stock=product_stock,
                current_sales=current_sales,
                range_days=range_ctx.days,
            )
            reorder_priority = self._reorder_priority_scoreboard(
                current_sales=current_sales,
                product_stock=product_stock,
                range_days=range_ctx.days,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            price_discount_impact = self._price_discount_impact(
                current_sales=current_sales,
                previous_sales=previous_sales,
                range_days=range_ctx.days,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            product_performance_quadrant = self._product_performance_quadrant(
                current_sales=current_sales,
                product_stock=product_stock,
                range_days=range_ctx.days,
                can_view_financial_metrics=can_view_financial_metrics,
            )
            category_brand_mix = self._category_brand_profit_mix(
                current_sales=current_sales,
                product_dimensions=product_dimensions,
                can_view_financial_metrics=can_view_financial_metrics,
                unavailable_reason=revenue_unavailable_reason,
            )

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
                    "revenue_orders_aov_trend": {
                        "items": self._revenue_orders_aov_points(range_ctx=range_ctx, sales=current_sales),
                    },
                    "gross_profit_margin_trend": {
                        "items": self._gross_profit_margin_points(
                            range_ctx=range_ctx,
                            sales=current_sales,
                            can_view_financial_metrics=can_view_financial_metrics,
                        ),
                        "unavailable_reason": revenue_unavailable_reason,
                    },
                    "conversion_funnel": conversion_funnel,
                    "product_performance_quadrant": {
                        "items": product_performance_quadrant
                        if can_view_financial_metrics and current_sales.cost_complete
                        else [],
                        "unavailable_reason": revenue_unavailable_reason,
                    },
                    "category_brand_profit_mix": category_brand_mix,
                    "returns_intelligence": returns_intelligence,
                    "inventory_aging_waterfall": {
                        "buckets": inventory_aging,
                        "unavailable_reason": None if can_view_financial_metrics else "Financial metrics are hidden for your role.",
                    },
                    "sell_through_cover_matrix": {
                        "items": sell_through_cover,
                    },
                    "reorder_priority_scoreboard": {
                        "items": reorder_priority,
                    },
                    "price_discount_impact": {
                        "items": price_discount_impact if can_view_financial_metrics and current_sales.cost_complete else [],
                        "unavailable_reason": revenue_unavailable_reason,
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

    def _stock_map_until(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        end_exclusive_utc: datetime,
    ) -> dict[str, Decimal]:
        return {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    InventoryLedgerModel.variant_id,
                    func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO),
                )
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id.in_(location_ids),
                    InventoryLedgerModel.created_at < end_exclusive_utc,
                )
                .group_by(InventoryLedgerModel.variant_id)
            ).all()
        }

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
                SalesOrderItemModel.discount_amount,
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
        seen_orders_per_bucket: set[tuple[str, str]] = set()
        for event_at, order_id, line_id, product_id, product_name, quantity, quantity_fulfilled, quantity_cancelled, line_total, discount_amount in rows:
            line_key = str(line_id)
            sold_quantity = as_decimal(quantity_fulfilled)
            if sold_quantity <= ZERO:
                sold_quantity = max(ZERO, as_decimal(quantity) - as_decimal(quantity_cancelled))
            if sold_quantity <= ZERO:
                continue

            event_local = ensure_utc(event_at).astimezone(zone)
            bucket = self._bucket_label(range_ctx, event_local.date())
            revenue = as_decimal(line_total)
            discount = as_decimal(discount_amount)
            gross_before_discount = revenue + discount

            order_bucket_key = (bucket, str(order_id))
            if order_bucket_key not in seen_orders_per_bucket:
                seen_orders_per_bucket.add(order_bucket_key)
                aggregation.orders_by_bucket[bucket] += 1

            aggregation.units_sold += sold_quantity
            aggregation.revenue_total += revenue
            aggregation.revenue_by_bucket[bucket] += revenue
            aggregation.discount_total += discount
            aggregation.gross_before_discount_total += gross_before_discount
            aggregation.discount_by_bucket[bucket] += discount

            product_key = str(product_id)
            product_agg = aggregation.products.setdefault(
                product_key,
                ProductSalesAggregate(product_id=product_key, product_name=product_name),
            )
            product_agg.units_sold += sold_quantity
            product_agg.revenue += revenue
            product_agg.discount_total += discount
            product_agg.gross_before_discount += gross_before_discount

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

    def _revenue_orders_aov_points(self, *, range_ctx: DashboardRange, sales: SalesAggregation) -> list[dict[str, object]]:
        buckets = self._bucket_labels(range_ctx)
        revenues = [sales.revenue_by_bucket.get(bucket, ZERO) for bucket in buckets]
        revenue_avg = (sum(revenues, ZERO) / Decimal(str(len(revenues)))) if revenues else ZERO
        anomaly_threshold_high = revenue_avg * Decimal("1.50")
        anomaly_threshold_low = revenue_avg * Decimal("0.50")

        points: list[dict[str, object]] = []
        for bucket in buckets:
            revenue = sales.revenue_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
            orders = sales.orders_by_bucket.get(bucket, 0)
            aov = (revenue / Decimal(str(orders))).quantize(MONEY_QUANTUM) if orders > 0 else ZERO
            anomaly_flag = bool(
                len(buckets) >= 6
                and revenue_avg > ZERO
                and (revenue >= anomaly_threshold_high or revenue <= anomaly_threshold_low)
            )
            points.append(
                {
                    "period": bucket,
                    "revenue": revenue,
                    "orders": orders,
                    "aov": aov,
                    "anomaly_flag": anomaly_flag,
                }
            )
        return points

    def _gross_profit_margin_points(
        self,
        *,
        range_ctx: DashboardRange,
        sales: SalesAggregation,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        points: list[dict[str, object]] = []
        for bucket in self._bucket_labels(range_ctx):
            revenue = sales.revenue_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
            estimated_gross_profit = None
            margin_percent = None
            if can_view_financial_metrics and bucket not in sales.incomplete_profit_buckets:
                profit = sales.gross_profit_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
                estimated_gross_profit = profit
                if revenue > ZERO:
                    margin_percent = ((profit / revenue) * Decimal("100")).quantize(PERCENT_QUANTUM)
            points.append(
                {
                    "period": bucket,
                    "revenue": revenue,
                    "estimated_gross_profit": estimated_gross_profit,
                    "margin_percent": margin_percent,
                }
            )
        return points

    def _conversion_funnel(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        range_ctx: DashboardRange,
    ) -> dict[str, object]:
        rows = session.execute(
            select(SalesOrderModel.status, func.count())
            .where(
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.location_id.in_(location_ids),
                SalesOrderModel.created_at >= range_ctx.start_utc,
                SalesOrderModel.created_at < range_ctx.end_exclusive_utc,
            )
            .group_by(SalesOrderModel.status)
        ).all()

        status_counts: dict[str, int] = {str(status): int(count or 0) for status, count in rows}
        inquiry_count = sum(status_counts.values())
        draft_count = status_counts.get("draft", 0)
        reserved_count = status_counts.get("confirmed", 0)
        completed_count = status_counts.get("completed", 0)

        raw_stages = [
            ("inquiry", "Inquiry", inquiry_count),
            ("draft", "Draft", draft_count),
            ("reserved", "Reserved", reserved_count),
            ("completed", "Completed", completed_count),
        ]
        stages: list[dict[str, object]] = []
        previous_count: int | None = None
        for stage_key, label, count in raw_stages:
            conversion_percent = None
            drop_off = None
            if previous_count is not None and previous_count > 0:
                conversion_percent = ((Decimal(str(count)) / Decimal(str(previous_count))) * Decimal("100")).quantize(
                    PERCENT_QUANTUM
                )
                drop_off = max(previous_count - count, 0)
            stages.append(
                {
                    "stage": stage_key,
                    "label": label,
                    "count": count,
                    "conversion_percent_from_previous": conversion_percent,
                    "drop_off_from_previous": drop_off,
                }
            )
            previous_count = count

        drop_off_reasons = [
            {"reason": self._humanize_status(status), "count": count}
            for status, count in sorted(status_counts.items(), key=lambda item: item[1], reverse=True)
            if status not in {"draft", "confirmed", "completed"}
        ]

        return {
            "stages": stages,
            "drop_off_reasons": drop_off_reasons[:6],
        }

    def _product_dimension_map(
        self,
        *,
        session: Session,
        client_id: str,
        product_ids: set[str],
    ) -> dict[str, dict[str, str]]:
        if not product_ids:
            return {}
        rows = session.execute(
            select(ProductModel.product_id, ProductModel.brand, CategoryModel.name)
            .outerjoin(CategoryModel, CategoryModel.category_id == ProductModel.category_id)
            .where(
                ProductModel.client_id == client_id,
                ProductModel.product_id.in_(list(product_ids)),
            )
        ).all()
        return {
            str(product_id): {
                "brand": (brand or "").strip() or "Unbranded",
                "category": (category_name or "").strip() or "Uncategorized",
            }
            for product_id, brand, category_name in rows
        }

    def _product_performance_quadrant(
        self,
        *,
        current_sales: SalesAggregation,
        product_stock: dict[str, ProductStockAggregate],
        range_days: int,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        if not can_view_financial_metrics:
            return []

        divisor = Decimal(str(max(range_days, 1)))
        velocity_values: list[Decimal] = []
        prepared: list[dict[str, object]] = []
        for product in current_sales.products.values():
            if product.revenue <= ZERO:
                continue
            velocity = (product.units_sold / divisor).quantize(PERCENT_QUANTUM)
            velocity_values.append(velocity)
            margin_percent = None
            if product.cost_complete and product.revenue > ZERO:
                margin_percent = (((product.revenue - product.estimated_cost) / product.revenue) * Decimal("100")).quantize(
                    PERCENT_QUANTUM
                )
            stock = product_stock.get(product.product_id)
            available = stock.available_qty if stock else ZERO
            days_cover = None
            if velocity > ZERO and available > ZERO:
                days_cover = (available / velocity).quantize(PERCENT_QUANTUM)
            prepared.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "sales_velocity": velocity,
                    "estimated_margin_percent": margin_percent,
                    "revenue": product.revenue.quantize(MONEY_QUANTUM),
                    "days_cover": days_cover,
                    "quadrant": "laggard",
                }
            )

        velocity_threshold = self._decimal_median(velocity_values)
        margin_threshold = Decimal("25.00")
        for point in prepared:
            margin = as_optional_decimal(point["estimated_margin_percent"])
            velocity = as_decimal(point["sales_velocity"])
            if margin is None:
                point["quadrant"] = "watch"
            elif velocity >= velocity_threshold and margin >= margin_threshold:
                point["quadrant"] = "star"
            elif velocity >= velocity_threshold and margin < margin_threshold:
                point["quadrant"] = "margin_killer"
            elif velocity < velocity_threshold and margin >= margin_threshold:
                point["quadrant"] = "sleeper"
            else:
                point["quadrant"] = "laggard"

        prepared.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
        return prepared[:30]

    def _category_brand_profit_mix(
        self,
        *,
        current_sales: SalesAggregation,
        product_dimensions: dict[str, dict[str, str]],
        can_view_financial_metrics: bool,
        unavailable_reason: str | None,
    ) -> dict[str, object]:
        if not can_view_financial_metrics:
            return {"categories": [], "unavailable_reason": "Financial metrics are hidden for your role."}

        category_accumulator: dict[str, dict[str, object]] = {}
        for product in current_sales.products.values():
            if product.revenue <= ZERO:
                continue
            dims = product_dimensions.get(product.product_id, {})
            category = dims.get("category") or "Uncategorized"
            brand = dims.get("brand") or "Unbranded"
            category_bucket = category_accumulator.setdefault(
                category,
                {
                    "revenue": ZERO,
                    "estimated_gross_profit": ZERO,
                    "cost_complete": True,
                    "brands": {},
                },
            )
            category_bucket["revenue"] = as_decimal(category_bucket["revenue"]) + product.revenue
            if product.cost_complete:
                category_bucket["estimated_gross_profit"] = as_decimal(category_bucket["estimated_gross_profit"]) + (
                    product.revenue - product.estimated_cost
                )
            else:
                category_bucket["cost_complete"] = False

            brand_map: dict[str, dict[str, object]] = category_bucket["brands"]  # type: ignore[assignment]
            brand_bucket = brand_map.setdefault(
                brand,
                {
                    "revenue": ZERO,
                    "estimated_gross_profit": ZERO,
                    "cost_complete": True,
                    "products": set(),
                },
            )
            brand_bucket["revenue"] = as_decimal(brand_bucket["revenue"]) + product.revenue
            if product.cost_complete:
                brand_bucket["estimated_gross_profit"] = as_decimal(brand_bucket["estimated_gross_profit"]) + (
                    product.revenue - product.estimated_cost
                )
            else:
                brand_bucket["cost_complete"] = False
            casted_products: set[str] = brand_bucket["products"]  # type: ignore[assignment]
            casted_products.add(product.product_id)

        categories: list[dict[str, object]] = []
        for category, values in category_accumulator.items():
            category_revenue = as_decimal(values["revenue"]).quantize(MONEY_QUANTUM)
            category_profit = (
                as_decimal(values["estimated_gross_profit"]).quantize(MONEY_QUANTUM) if values.get("cost_complete", False) else None
            )
            category_margin = (
                ((category_profit / category_revenue) * Decimal("100")).quantize(PERCENT_QUANTUM)
                if category_profit is not None and category_revenue > ZERO
                else None
            )

            brands_payload: list[dict[str, object]] = []
            brand_map: dict[str, dict[str, object]] = values["brands"]  # type: ignore[assignment]
            for brand, brand_values in brand_map.items():
                brand_revenue = as_decimal(brand_values["revenue"]).quantize(MONEY_QUANTUM)
                brand_profit = (
                    as_decimal(brand_values["estimated_gross_profit"]).quantize(MONEY_QUANTUM)
                    if brand_values.get("cost_complete", False)
                    else None
                )
                brand_margin = (
                    ((brand_profit / brand_revenue) * Decimal("100")).quantize(PERCENT_QUANTUM)
                    if brand_profit is not None and brand_revenue > ZERO
                    else None
                )
                brands_payload.append(
                    {
                        "brand": brand,
                        "revenue": brand_revenue,
                        "estimated_gross_profit": brand_profit,
                        "margin_percent": brand_margin,
                        "product_count": len(brand_values["products"]),
                    }
                )
            brands_payload.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
            categories.append(
                {
                    "category": category,
                    "revenue": category_revenue,
                    "estimated_gross_profit": category_profit,
                    "margin_percent": category_margin,
                    "brands": brands_payload[:10],
                }
            )

        categories.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
        return {
            "categories": categories[:12],
            "unavailable_reason": unavailable_reason if not current_sales.cost_complete else None,
        }

    def _returns_intelligence(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        range_ctx: DashboardRange,
        returns_agg: ReturnsAggregation,
        orders_by_bucket: dict[str, int],
        can_view_financial_metrics: bool,
    ) -> dict[str, object]:
        event_expr = func.coalesce(SalesReturnModel.received_at, SalesReturnModel.requested_at, SalesReturnModel.created_at)
        rows = session.execute(
            select(
                event_expr,
                ProductModel.product_id,
                ProductModel.name,
                SalesReturnItemModel.disposition,
                SalesReturnItemModel.quantity,
                SalesReturnItemModel.unit_refund_amount,
            )
            .join(SalesReturnModel, SalesReturnModel.sales_return_id == SalesReturnItemModel.sales_return_id)
            .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesReturnModel.sales_order_id)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesReturnItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesReturnItemModel.client_id == client_id,
                SalesReturnModel.client_id == client_id,
                SalesOrderModel.client_id == client_id,
                ProductVariantModel.client_id == client_id,
                ProductModel.client_id == client_id,
                SalesOrderModel.location_id.in_(location_ids),
                event_expr >= range_ctx.start_utc,
                event_expr < range_ctx.end_exclusive_utc,
            )
        ).all()

        heatmap: dict[tuple[str, str], dict[str, object]] = {}
        reason_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for _event_at, product_id, product_name, disposition, quantity, unit_refund_amount in rows:
            reason = (str(disposition or "").strip().replace("_", " ") or "other").title()
            key = (str(product_id), reason)
            quantity_value = as_decimal(quantity)
            refund_amount = (quantity_value * as_decimal(unit_refund_amount)).quantize(MONEY_QUANTUM)
            entry = heatmap.setdefault(
                key,
                {
                    "product_id": str(product_id),
                    "product_name": product_name,
                    "reason": reason,
                    "returns_qty": ZERO,
                    "refund_amount": ZERO,
                },
            )
            entry["returns_qty"] = as_decimal(entry["returns_qty"]) + quantity_value
            entry["refund_amount"] = as_decimal(entry["refund_amount"]) + refund_amount
            reason_totals[reason] += quantity_value

        heatmap_rows = list(heatmap.values())
        heatmap_rows.sort(key=lambda item: (as_decimal(item["returns_qty"]), item["product_name"]), reverse=True)
        top_reasons = [
            {"reason": reason, "returns_qty": quantity.quantize(PERCENT_QUANTUM)}
            for reason, quantity in sorted(reason_totals.items(), key=lambda item: item[1], reverse=True)
        ]

        trend = []
        for bucket in self._bucket_labels(range_ctx):
            returns_count = returns_agg.count_by_bucket.get(bucket, 0)
            completed_orders = max(orders_by_bucket.get(bucket, 0), 0)
            return_rate_percent = (
                ((Decimal(str(returns_count)) / Decimal(str(completed_orders))) * Decimal("100")).quantize(PERCENT_QUANTUM)
                if completed_orders > 0
                else ZERO
            )
            trend.append(
                {
                    "period": bucket,
                    "returns_count": returns_count,
                    "return_rate_percent": return_rate_percent,
                    "refund_amount": (
                        returns_agg.amount_by_bucket.get(bucket, ZERO).quantize(MONEY_QUANTUM)
                        if can_view_financial_metrics
                        else None
                    ),
                }
            )

        serialized_heatmap = [
            {
                **row,
                "returns_qty": as_decimal(row["returns_qty"]).quantize(PERCENT_QUANTUM),
                "refund_amount": as_decimal(row["refund_amount"]).quantize(MONEY_QUANTUM)
                if can_view_financial_metrics
                else None,
            }
            for row in heatmap_rows[:40]
        ]
        return {
            "heatmap": serialized_heatmap,
            "top_reasons": top_reasons[:8],
            "trend": trend,
        }

    def _inventory_aging_waterfall(
        self,
        *,
        session: Session,
        client_id: str,
        location_ids: list[str],
        on_hand_map: dict[str, Decimal],
        start_on_hand_map: dict[str, Decimal],
        as_of_date: date,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        rows = session.execute(
            select(
                ProductVariantModel.variant_id,
                ProductVariantModel.cost_amount,
                ProductVariantModel.created_at,
            )
            .where(ProductVariantModel.client_id == client_id)
        ).all()
        last_received_map = {
            str(variant_id): ensure_utc(last_received_at)
            for variant_id, last_received_at in session.execute(
                select(InventoryLedgerModel.variant_id, func.max(InventoryLedgerModel.created_at))
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id.in_(location_ids),
                    InventoryLedgerModel.movement_type == "stock_received",
                )
                .group_by(InventoryLedgerModel.variant_id)
            ).all()
            if last_received_at is not None
        }

        bucket_order = ("0-30", "31-60", "61-90", "90+")
        buckets: dict[str, dict[str, Decimal]] = {
            label: {
                "on_hand_qty": ZERO,
                "inventory_value": ZERO,
                "net_qty_change": ZERO,
                "net_value_change": ZERO,
            }
            for label in bucket_order
        }

        for variant_id, cost_amount, created_at in rows:
            variant_key = str(variant_id)
            on_hand_qty = on_hand_map.get(variant_key, ZERO)
            if on_hand_qty <= ZERO:
                continue
            start_qty = start_on_hand_map.get(variant_key, ZERO)
            net_qty_change = on_hand_qty - start_qty
            anchor = last_received_map.get(variant_key, ensure_utc(created_at))
            age_days = max((as_of_date - anchor.date()).days, 0)
            bucket_label = self._inventory_age_bucket(age_days)
            bucket = buckets[bucket_label]
            bucket["on_hand_qty"] += on_hand_qty
            bucket["net_qty_change"] += net_qty_change
            if can_view_financial_metrics:
                cost_decimal = as_optional_decimal(cost_amount)
                if cost_decimal is not None:
                    bucket["inventory_value"] += (on_hand_qty * cost_decimal).quantize(MONEY_QUANTUM)
                    bucket["net_value_change"] += (net_qty_change * cost_decimal).quantize(MONEY_QUANTUM)

        return [
            {
                "bucket": label,
                "on_hand_qty": buckets[label]["on_hand_qty"].quantize(PERCENT_QUANTUM),
                "inventory_value": buckets[label]["inventory_value"].quantize(MONEY_QUANTUM)
                if can_view_financial_metrics
                else None,
                "net_qty_change": buckets[label]["net_qty_change"].quantize(PERCENT_QUANTUM),
                "net_value_change": buckets[label]["net_value_change"].quantize(MONEY_QUANTUM)
                if can_view_financial_metrics
                else None,
            }
            for label in bucket_order
        ]

    def _sell_through_cover_matrix(
        self,
        *,
        product_stock: dict[str, ProductStockAggregate],
        current_sales: SalesAggregation,
        range_days: int,
    ) -> list[dict[str, object]]:
        product_ids = set(product_stock.keys()) | set(current_sales.products.keys())
        divisor = Decimal(str(max(range_days, 1)))
        rows: list[dict[str, object]] = []

        for product_id in product_ids:
            stock = product_stock.get(product_id)
            sales = current_sales.products.get(product_id)
            product_name = sales.product_name if sales else (stock.product_name if stock else "Unknown product")
            units_sold = sales.units_sold if sales else ZERO
            revenue = sales.revenue if sales else ZERO
            on_hand = stock.on_hand_qty if stock else ZERO
            available = stock.available_qty if stock else ZERO
            denominator = units_sold + max(on_hand, ZERO)
            sell_through_percent = (
                ((units_sold / denominator) * Decimal("100")).quantize(PERCENT_QUANTUM) if denominator > ZERO else ZERO
            )
            sales_velocity = (units_sold / divisor).quantize(PERCENT_QUANTUM)
            days_cover = (available / sales_velocity).quantize(PERCENT_QUANTUM) if sales_velocity > ZERO and available > ZERO else None

            zone = "watch"
            if sales_velocity >= Decimal("0.50") and (days_cover is None or days_cover <= Decimal("14")):
                zone = "low_cover_high_velocity"
            elif sales_velocity <= Decimal("0.20") and days_cover is not None and days_cover >= Decimal("45"):
                zone = "high_cover_low_velocity"
            elif sales_velocity >= Decimal("0.50") and days_cover is not None and days_cover <= Decimal("45"):
                zone = "healthy"

            rows.append(
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "sell_through_percent": sell_through_percent,
                    "days_cover": days_cover,
                    "sales_velocity": sales_velocity,
                    "zone": zone,
                    "revenue": revenue.quantize(MONEY_QUANTUM),
                }
            )

        rows.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
        return rows[:40]

    def _reorder_priority_scoreboard(
        self,
        *,
        current_sales: SalesAggregation,
        product_stock: dict[str, ProductStockAggregate],
        range_days: int,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        divisor = Decimal(str(max(range_days, 1)))
        rows: list[dict[str, object]] = []
        for product in current_sales.products.values():
            sales_velocity = (product.units_sold / divisor).quantize(PERCENT_QUANTUM)
            if sales_velocity <= ZERO:
                continue
            stock = product_stock.get(product.product_id)
            available = stock.available_qty if stock else ZERO
            days_cover = (available / sales_velocity).quantize(PERCENT_QUANTUM) if available > ZERO else None
            margin_percent = None
            if can_view_financial_metrics and product.cost_complete and product.revenue > ZERO:
                margin_percent = (((product.revenue - product.estimated_cost) / product.revenue) * Decimal("100")).quantize(
                    PERCENT_QUANTUM
                )

            if days_cover is None:
                stockout_risk = Decimal("2.2")
            elif days_cover <= Decimal("7"):
                stockout_risk = Decimal("3.0")
            elif days_cover <= Decimal("14"):
                stockout_risk = Decimal("2.0")
            elif days_cover <= Decimal("30"):
                stockout_risk = Decimal("1.2")
            else:
                stockout_risk = Decimal("0.6")

            margin_factor = Decimal("1.0")
            if margin_percent is not None:
                margin_factor = max(Decimal("0.5"), min(Decimal("2.5"), margin_percent / Decimal("20")))
            score = (sales_velocity * margin_factor * stockout_risk * Decimal("100")).quantize(PERCENT_QUANTUM)

            recommended_action = "Monitor"
            if stockout_risk >= Decimal("2.0"):
                recommended_action = "Reorder now"
            elif stockout_risk >= Decimal("1.2"):
                recommended_action = "Plan reorder"

            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "priority_score": score,
                    "sales_velocity": sales_velocity,
                    "days_cover": days_cover,
                    "estimated_margin_percent": margin_percent,
                    "revenue": product.revenue.quantize(MONEY_QUANTUM),
                    "recommended_action": recommended_action,
                }
            )

        rows.sort(key=lambda item: as_decimal(item["priority_score"]), reverse=True)
        return rows[:20]

    def _price_discount_impact(
        self,
        *,
        current_sales: SalesAggregation,
        previous_sales: SalesAggregation,
        range_days: int,
        can_view_financial_metrics: bool,
    ) -> list[dict[str, object]]:
        if not can_view_financial_metrics:
            return []
        divisor = Decimal(str(max(range_days, 1)))
        rows: list[dict[str, object]] = []
        for product in current_sales.products.values():
            if product.revenue <= ZERO:
                continue
            discount_percent = (
                ((product.discount_total / product.gross_before_discount) * Decimal("100")).quantize(PERCENT_QUANTUM)
                if product.gross_before_discount > ZERO
                else ZERO
            )
            current_velocity = (product.units_sold / divisor).quantize(PERCENT_QUANTUM)
            previous = previous_sales.products.get(product.product_id)
            previous_velocity = (previous.units_sold / divisor).quantize(PERCENT_QUANTUM) if previous else ZERO
            if previous_velocity > ZERO:
                unit_lift = (((current_velocity - previous_velocity) / previous_velocity) * Decimal("100")).quantize(PERCENT_QUANTUM)
            elif current_velocity > ZERO:
                unit_lift = Decimal("100.00")
            else:
                unit_lift = ZERO

            net_margin_percent = None
            if product.cost_complete and product.revenue > ZERO:
                net_margin_percent = (((product.revenue - product.estimated_cost) / product.revenue) * Decimal("100")).quantize(
                    PERCENT_QUANTUM
                )

            recommendation: str = "keep"
            if discount_percent >= Decimal("8.00") and (net_margin_percent is None or net_margin_percent < Decimal("15.00")):
                recommendation = "raise"
            elif unit_lift >= Decimal("12.00") and (net_margin_percent is None or net_margin_percent >= Decimal("20.00")):
                recommendation = "discount"

            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "discount_percent": discount_percent,
                    "unit_lift_percent": unit_lift,
                    "net_margin_percent": net_margin_percent,
                    "revenue": product.revenue.quantize(MONEY_QUANTUM),
                    "recommendation": recommendation,
                }
            )

        rows.sort(key=lambda item: as_decimal(item["revenue"]), reverse=True)
        return rows[:30]

    def _decimal_median(self, values: list[Decimal]) -> Decimal:
        if not values:
            return ZERO
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return ((ordered[middle - 1] + ordered[middle]) / Decimal("2")).quantize(PERCENT_QUANTUM)

    def _inventory_age_bucket(self, age_days: int) -> str:
        if age_days <= 30:
            return "0-30"
        if age_days <= 60:
            return "31-60"
        if age_days <= 90:
            return "61-90"
        return "90+"

    def _humanize_status(self, value: str) -> str:
        return value.replace("_", " ").strip().title()

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
