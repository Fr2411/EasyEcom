from __future__ import annotations

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.sales_repo import RefundsRepo, ReturnItemsRepo, ReturnsRepo
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
    ):
        self.returns_repo = returns_repo
        self.return_items_repo = return_items_repo
        self.refunds_repo = refunds_repo
        self.finance_service = finance_service
        self.inventory_service = inventory_service

    def create_request(self, payload: ReturnRequestCreate) -> str:
        return_id = new_uuid()
        self.returns_repo.append(
            {
                "return_id": return_id,
                "client_id": payload.client_id,
                "invoice_id": payload.invoice_id,
                "order_id": payload.order_id,
                "customer_id": payload.customer_id,
                "status": "PENDING",
                "requested_by_user_id": payload.requested_by_user_id,
                "approved_by_user_id": "",
                "requested_at": now_iso(),
                "approved_at": "",
                "reason": payload.reason,
                "note": payload.note,
                "restock": str(payload.restock).lower(),
            }
        )

        for item in payload.items:
            self.return_items_repo.append(
                {
                    "return_item_id": new_uuid(),
                    "return_id": return_id,
                    "product_id": item.product_id,
                    "qty": str(item.qty),
                    "unit_selling_price": str(item.unit_selling_price),
                    "refund_amount": str(item.qty * item.unit_selling_price),
                    "note": item.note,
                }
            )
        return return_id

    def approve_request(self, client_id: str, return_id: str, approver_user_id: str, approver_roles: list[str], approve: bool, note: str = "") -> str:
        if not set(approver_roles).intersection(APPROVER_ROLES):
            raise PermissionError("You are not allowed to approve/reject returns")
        returns_df = self.returns_repo.all()
        idx = returns_df[(returns_df["client_id"] == client_id) & (returns_df["return_id"] == return_id)].index
        if len(idx) == 0:
            raise ValueError("Return request not found")
        i = idx[0]
        status = returns_df.loc[i, "status"]
        if status != "PENDING":
            raise ValueError("Return request already processed")

        if not approve:
            returns_df.loc[i, "status"] = "REJECTED"
            returns_df.loc[i, "approved_by_user_id"] = approver_user_id
            returns_df.loc[i, "approved_at"] = now_iso()
            returns_df.loc[i, "note"] = note or returns_df.loc[i, "note"]
            self.returns_repo.save(returns_df)
            return "REJECTED"

        return_items = self.return_items_repo.all()
        items = return_items[return_items["return_id"] == return_id].copy()
        if items.empty:
            raise ValueError("Return items missing")
        items["refund_amount"] = items["refund_amount"].astype(float)
        refund_amount = float(items["refund_amount"].sum())

        returns_df.loc[i, "status"] = "APPROVED"
        returns_df.loc[i, "approved_by_user_id"] = approver_user_id
        returns_df.loc[i, "approved_at"] = now_iso()
        returns_df.loc[i, "note"] = note or returns_df.loc[i, "note"]
        self.returns_repo.save(returns_df)

        refund_id = new_uuid()
        row = returns_df.loc[i]
        self.refunds_repo.append(
            {
                "refund_id": refund_id,
                "client_id": client_id,
                "return_id": return_id,
                "invoice_id": row["invoice_id"],
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "amount": str(refund_amount),
                "status": "INITIATED",
                "requested_by_user_id": row["requested_by_user_id"],
                "approved_by_user_id": approver_user_id,
                "created_at": now_iso(),
                "processed_at": "",
                "reason": row["reason"],
                "note": row["note"],
            }
        )

        self.finance_service.add_entry(client_id, "expense", "Refunds", refund_amount, "refund", refund_id, f"Refund initiated for return {return_id}", user_id=approver_user_id)

        if str(row.get("restock", "false")).lower() == "true":
            for _, item in items.iterrows():
                self.inventory_service.add_stock(
                    client_id=client_id,
                    product_name=str(item["product_id"]),
                    qty=float(item["qty"]),
                    unit_cost=float(item["unit_selling_price"]),
                    supplier_snapshot="Return restock",
                    note=f"Restocked from return {return_id}",
                    source_type="return",
                    source_id=return_id,
                    user_id=approver_user_id,
                )
        return "APPROVED"
