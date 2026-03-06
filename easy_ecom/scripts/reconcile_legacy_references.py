from __future__ import annotations

import argparse

from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import SalesOrderItemsRepo, SalesOrdersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.services.data_reconciliation_service import DataReconciliationService


def run(client_id: str | None = None, apply: bool = False) -> int:
    store = CsvStore(settings.data_dir)
    inv_repo = InventoryTxnRepo(store)
    recon = DataReconciliationService(
        inv_repo,
        ProductsRepo(store),
        ProductVariantsRepo(store),
        SalesOrdersRepo(store),
        SalesOrderItemsRepo(store),
        LedgerRepo(store),
    )

    current = inv_repo.all()
    normalized = recon.normalized_inventory_rows(client_id)
    if normalized.empty:
        print("No inventory rows found.")
        return 0

    scoped = (
        normalized[normalized["client_id"] == client_id].copy() if client_id else normalized.copy()
    )
    fixable = scoped[
        (~scoped["canonical_product_id"].astype(str).str.startswith("UNMAPPED::"))
        & (scoped["product_id"].astype(str) != scoped["canonical_product_id"].astype(str))
    ]

    print(f"dry_run={not apply} client_scope={client_id or 'ALL'}")
    print(f"fixable_inventory_rows={len(fixable)}")
    if not fixable.empty:
        print(
            fixable[
                ["txn_id", "client_id", "product_id", "canonical_product_id", "issue_reason"]
            ].to_string(index=False)
        )

    orphan_ledger = recon.orphan_ledger_earnings(client_id)
    print(f"orphan_ledger_rows={len(orphan_ledger)}")
    if not orphan_ledger.empty:
        print(
            orphan_ledger[
                ["entry_id", "client_id", "source_id", "amount", "issue_reason"]
            ].to_string(index=False)
        )

    if not apply or fixable.empty:
        return int(len(fixable))

    updated = 0
    for _, row in fixable.iterrows():
        txn_id = str(row["txn_id"])
        idx = current[current["txn_id"].astype(str) == txn_id].index
        if len(idx) == 0:
            continue
        current.loc[idx[0], "product_id"] = str(row["canonical_product_id"])
        updated += 1
    inv_repo.save(current)
    print(f"applied_inventory_updates={updated}")
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reconcile legacy inventory references with canonical products."
    )
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--apply", action="store_true", help="Persist updates. Default is dry-run.")
    args = parser.parse_args()
    run(client_id=args.client_id, apply=bool(args.apply))
