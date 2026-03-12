from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.sales_repo import RefundsRepo, ReturnItemsRepo, ReturnsRepo, SalesOrdersRepo
from easy_ecom.domain.models.sales import ReturnRequestCreate
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService

APPROVER_ROLES = {"SUPER_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "FINANCE_ONLY"}


class ReturnsService:
    def __init__(
        self,
        returns_repo: ReturnsRepo,
        return_items_repo: ReturnItemsRepo,
        refunds_repo: RefundsRepo,
        finance_service: FinanceService,
        inventory_service: InventoryService,
        orders_repo: SalesOrdersRepo | None = None,
    ):
        self.returns_repo = returns_repo
        self.return_items_repo = return_items_repo
        self.refunds_repo = refunds_repo
        self.finance_service = finance_service
        self.inventory_service = inventory_service
        self.orders_repo = orders_repo

    def request_return(self, order_id: str, lines: list[dict[str, object]], reason: str, requested_by: dict[str, str]) -> str:
        return_id = new_uuid()
        self.returns_repo.append(
            {
                "return_id": return_id,
                "client_id": requested_by.get("client_id", ""),
                "invoice_id": requested_by.get("invoice_id", ""),
                "order_id": order_id,
                "customer_id": requested_by.get("customer_id", ""),
                "status": "return_requested",
                "requested_by_user_id": requested_by.get("user_id", ""),
                "approved_by_user_id": "",
                "requested_at": now_iso(),
                "approved_at": "",
                "received_at": "",
                "inspected_at": "",
                "reason": reason,
                "note": requested_by.get("note", ""),
                "restock": "false",
            }
        )
        for line in lines:
            qty_requested = float(line.get("qty_requested", line.get("qty", 0)) or 0)
            self.return_items_repo.append(
                {
                    "return_item_id": new_uuid(),
                    "return_id": return_id,
                    "product_id": str(line.get("product_id", "")),
                    "variant_id": str(line.get("variant_id", "")),
                    "qty_ordered": str(float(line.get("qty_ordered", qty_requested))),
                    "qty_requested": str(qty_requested),
                    "qty_approved": str(float(line.get("qty_approved", qty_requested))),
                    "qty_received": str(float(line.get("qty_received", qty_requested))),
                    "qty": str(qty_requested),
                    "unit_selling_price": str(float(line.get("unit_selling_price", 0))),
                    "refund_amount": str(qty_requested * float(line.get("unit_selling_price", 0))),
                    "restock": str(bool(line.get("restock", False))).lower(),
                    "reason": str(line.get("reason", reason)),
                    "condition": "",
                    "note": str(line.get("note", "")),
                }
            )
        return return_id

    def approve_return(self, return_id: str, user_ctx: dict[str, str]) -> None:
        self._transition(return_id, "return_requested", "approved", user_ctx, "approved_at")

    def receive_return(self, return_id: str, received_lines: list[dict[str, object]], condition_note: str, user_ctx: dict[str, str]) -> None:
        self._transition(return_id, "approved", "received", user_ctx, "received_at", condition_note)
        items = self.return_items_repo.all()
        if items.empty:
            return
        for line in received_lines:
            matched = items[(items["return_id"] == return_id) & (items["product_id"] == str(line.get("product_id", "")))]
            if matched.empty:
                continue
            i = matched.index[0]
            items.loc[i, "qty_received"] = str(float(line.get("qty_received", 0)))
            items.loc[i, "condition"] = str(line.get("condition", ""))
        self.return_items_repo.save(items)

    def inspect_return(self, return_id: str, decision: str, note: str, user_ctx: dict[str, str]) -> None:
        target = "inspected" if decision == "approve" else "rejected"
        self._transition(return_id, "received", target, user_ctx, "inspected_at", note)

    def issue_refund(self, return_id: str, amount: float, refund_method: str, restock_lines: bool = True, user_ctx: dict[str, str] | None = None) -> str:
        user_ctx = user_ctx or {}
        returns_df = self.returns_repo.all()
        row = returns_df[returns_df["return_id"] == return_id]
        if row.empty:
            raise ValueError("Return request not found")
        i = row.index[0]
        if returns_df.loc[i, "status"] not in ["inspected", "approved", "refund_approved"]:
            raise ValueError("Return must be inspected/approved before refund")
        refund_id = new_uuid()
        self.refunds_repo.append(
            {
                "refund_id": refund_id,
                "client_id": returns_df.loc[i, "client_id"],
                "return_id": return_id,
                "invoice_id": returns_df.loc[i, "invoice_id"],
                "order_id": returns_df.loc[i, "order_id"],
                "customer_id": returns_df.loc[i, "customer_id"],
                "amount": str(amount),
                "status": "processed",
                "method": refund_method,
                "requested_by_user_id": returns_df.loc[i, "requested_by_user_id"],
                "approved_by_user_id": user_ctx.get("user_id", ""),
                "created_at": now_iso(),
                "processed_at": now_iso(),
                "reason": returns_df.loc[i, "reason"],
                "note": returns_df.loc[i, "note"],
            }
        )
        self.finance_service.add_entry(returns_df.loc[i, "client_id"], "expense", "Refunds", float(amount), "refund", refund_id, f"Refund issued for return {return_id}", user_id=user_ctx.get("user_id", ""))
        returns_df.loc[i, "status"] = "refund_completed"
        self.returns_repo.save(returns_df)

        if restock_lines:
            items = self.return_items_repo.all()
            scoped = items[items["return_id"] == return_id]
            for _, item in scoped.iterrows():
                if str(item.get("restock", "false")).lower() != "true":
                    continue
                variant_id = str(item.get("variant_id", "")).strip()
                if not variant_id:
                    raise ValueError("variant_id is required for restock inventory writes")
                self.inventory_service.add_stock(
                    client_id=returns_df.loc[i, "client_id"],
                    product_id=str(item["product_id"]),
                    variant_id=variant_id,
                    product_name=str(item.get("product_id", "")),
                    qty=float(item.get("qty_received", item.get("qty", 0)) or 0),
                    unit_cost=float(item.get("unit_selling_price", 0) or 0),
                    supplier_snapshot="Return restock",
                    note=f"Restocked from return {return_id}",
                    source_type="return",
                    source_id=return_id,
                    user_id=user_ctx.get("user_id", ""),
                )
        if self.orders_repo is not None:
            orders = self.orders_repo.all()
            order_match = orders[orders["order_id"] == returns_df.loc[i, "order_id"]]
            if not order_match.empty:
                oi = order_match.index[0]
                orders.loc[oi, "return_status"] = "refund_completed"
                orders.loc[oi, "fulfillment_status"] = "returned"
                refunded = float(orders.loc[oi, "amount_refunded"] or 0) + float(amount)
                orders.loc[oi, "amount_refunded"] = str(refunded)
                self.orders_repo.save(orders)
        return refund_id

    def reject_return(self, return_id: str, reason: str, user_ctx: dict[str, str]) -> None:
        self._transition(return_id, "return_requested", "rejected", user_ctx, "approved_at", reason)

    def _transition(self, return_id: str, expected: str, target: str, user_ctx: dict[str, str], ts_col: str, note: str = "") -> None:
        returns_df = self.returns_repo.all()
        matched = returns_df[returns_df["return_id"] == return_id]
        if matched.empty:
            raise ValueError("Return request not found")
        i = matched.index[0]
        if str(returns_df.loc[i, "status"]) != expected:
            raise ValueError(f"Invalid return transition from {returns_df.loc[i, 'status']}")
        returns_df.loc[i, "status"] = target
        if ts_col in returns_df.columns:
            returns_df.loc[i, ts_col] = now_iso()
        if note:
            returns_df.loc[i, "note"] = note
        returns_df.loc[i, "approved_by_user_id"] = user_ctx.get("user_id", "")
        self.returns_repo.save(returns_df)

    # backward compatibility wrappers
    def create_request(self, payload: ReturnRequestCreate) -> str:
        lines = [{"product_id": i.product_id, "qty_requested": i.qty, "unit_selling_price": i.unit_selling_price, "note": i.note, "restock": payload.restock} for i in payload.items]
        return self.request_return(payload.order_id, lines, payload.reason, {"client_id": payload.client_id, "invoice_id": payload.invoice_id, "customer_id": payload.customer_id, "user_id": payload.requested_by_user_id, "note": payload.note})

    def approve_request(self, client_id: str, return_id: str, approver_user_id: str, approver_roles: list[str], approve: bool, note: str = "") -> str:
        if not set(approver_roles).intersection(APPROVER_ROLES):
            raise PermissionError("You are not allowed to approve/reject returns")
        if approve:
            self.approve_return(return_id, {"client_id": client_id, "user_id": approver_user_id})
            return "APPROVED"
        self.reject_return(return_id, note or "Rejected", {"client_id": client_id, "user_id": approver_user_id})
        return "REJECTED"
