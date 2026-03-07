import pandas as pd
import streamlit as st

from easy_ecom.app.ui.components import require_login
from easy_ecom.app.ui.documents import PdfDependencyError, build_invoice_pdf, build_shipment_pdf
from easy_ecom.app.ui.formatters import format_money
from easy_ecom.core.config import settings
from easy_ecom.core.rbac import can_access_page
from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
    ShipmentsRepo,
)
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.client_service import ClientService
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.product_service import ProductService
from easy_ecom.domain.services.data_reconciliation_service import DataReconciliationService
from easy_ecom.domain.services.sales_service import SalesService

require_login()
roles = st.session_state["user"]["roles"].split(",")
if not can_access_page(roles, "Sales"):
    st.error("Access denied")
    st.stop()

store = CsvStore(settings.data_dir)
seq = SequenceService(SequencesRepo(store))
inv = InventoryService(InventoryTxnRepo(store), seq)
fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
product_repo = ProductsRepo(store)
variants_repo = ProductVariantsRepo(store)
product_svc = ProductService(product_repo, variants_repo)
customer_repo = CustomersRepo(store)
clients_repo = ClientsRepo(store)
client_svc = ClientService(clients_repo)
orders_repo = SalesOrdersRepo(store)
items_repo = SalesOrderItemsRepo(store)
invoices_repo = InvoicesRepo(store)
shipments_repo = ShipmentsRepo(store)
payments_repo = PaymentsRepo(store)
svc = SalesService(
    orders_repo,
    items_repo,
    invoices_repo,
    shipments_repo,
    payments_repo,
    inv,
    seq,
    fin,
    product_repo,
    customer_repo,
    AuditRepo(store),
    variants_repo,
)
recon = DataReconciliationService(
    InventoryTxnRepo(store),
    product_repo,
    variants_repo,
    orders_repo,
    items_repo,
    LedgerRepo(store),
    invoices_repo,
)

user = st.session_state["user"]
client_id = user["client_id"]
user_id = user["user_id"]
currency_code, currency_symbol = client_svc.get_currency(client_id)

st.title("Sales")
if st.button("Refresh"):
    st.rerun()

sell_tab, cart_tab, records_tab = st.tabs(["Sell", "Cart", "Sales Records"])

with sell_tab:
    for key, default in [
        ("selected_cart_order_id", ""),
        ("sales_selected_customer_id", ""),
        ("sales_selected_customer_label", ""),
        ("sales_last_cart_result", None),
        ("sales_force_new_cart", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    products_df = product_svc.list_by_client(client_id)
    product_options = (
        sorted(products_df["product_name"].dropna().astype(str).unique().tolist())
        if not products_df.empty
        else []
    )
    product_name = st.selectbox(
        "Parent product", product_options, index=None, placeholder="Select product"
    )
    selected_product = product_svc.get_by_name(client_id, product_name) if product_name else None
    variants = (
        product_svc.list_variants(client_id, selected_product["product_id"])
        if selected_product
        else []
    )
    variant_map = {v["variant_name"]: v for v in variants}
    variant_name = (
        st.selectbox("Variant", sorted(variant_map.keys()), index=None) if variants else None
    )
    selected_variant = variant_map.get(variant_name) if variant_name else None
    product_id = (
        selected_variant["variant_id"]
        if selected_variant
        else (selected_product["product_id"] if selected_product else "")
    )

    qty = st.number_input("Qty", min_value=0.01, value=1.0)
    default_price = float(
        (selected_variant or selected_product or {}).get("default_selling_price", 0.01) or 0.01
    )
    max_discount_pct = float(
        (selected_variant or selected_product or {}).get("max_discount_pct", 10.0) or 10.0
    )
    min_price = default_price * (1 - max_discount_pct / 100)
    price = st.number_input("Unit selling price", min_value=0.01, value=default_price)

    if product_id:
        st.caption(f"Available stock: {inv.available_qty(client_id, product_id):,.2f}")
        st.caption(
            f"Minimum allowed price: {format_money(min_price, currency_code, currency_symbol)}"
        )

    st.subheader("Customer")
    customer_name = st.text_input("Customer name")
    matches = (
        customer_repo.find_by_name(client_id, customer_name)
        if customer_name.strip()
        else customer_repo.all().iloc[0:0]
    )
    matched_customer_id = ""
    selected_match = None
    if not matches.empty:
        options = [
            f"{r.customer_id} | {r.full_name} | {r.phone} | {r.email}"
            for r in matches.itertuples(index=False)
        ]
        selected_label = st.selectbox("Matched customers", options, index=0)
        matched_customer_id = selected_label.split(" | ")[0]
        st.session_state["sales_selected_customer_id"] = matched_customer_id
        st.session_state["sales_selected_customer_label"] = selected_label
        selected_match = matches[matches["customer_id"] == matched_customer_id].iloc[0]

    phone = st.text_input(
        "Phone", value=selected_match["phone"] if selected_match is not None else ""
    )
    email = st.text_input(
        "Email", value=selected_match["email"] if selected_match is not None else ""
    )
    address_line1 = st.text_input(
        "Address", value=selected_match["address_line1"] if selected_match is not None else ""
    )
    city = st.text_input("City", value=selected_match["city"] if selected_match is not None else "")

    c1, c2, c3 = st.columns(3)
    if c1.button("Add to Cart", type="primary"):
        try:
            if not product_id:
                raise ValueError("Please select a product")
            if float(price) < min_price:
                raise ValueError(
                    f"Unit price cannot be below {format_money(min_price, currency_code, currency_symbol)}"
                )
            resolved_customer_id = svc.resolve_customer_for_sale(
                client_id,
                {
                    "full_name": customer_name,
                    "phone": phone,
                    "email": email,
                    "address_line1": address_line1,
                    "city": city,
                },
                matched_customer_id=matched_customer_id,
                user_id=user_id,
            )
            draft_id = svc.get_or_create_customer_draft(
                client_id,
                resolved_customer_id,
                force_new=bool(st.session_state.get("sales_force_new_cart", False)),
            )
            svc.add_item_to_draft(
                draft_id,
                client_id,
                SaleItem(product_id=product_id, qty=float(qty), unit_selling_price=float(price)),
            )
            st.session_state["selected_cart_order_id"] = draft_id
            st.session_state["sales_last_cart_result"] = {
                "order_id": draft_id,
                "customer_id": resolved_customer_id,
            }
            st.session_state["sales_force_new_cart"] = False
            st.success(f"Added to draft cart: {draft_id}")
        except Exception as exc:
            st.error(str(exc))

    if c2.button("Start New Cart"):
        st.session_state["sales_force_new_cart"] = True
        st.session_state["selected_cart_order_id"] = ""
        st.info("New cart mode enabled. Next Add to Cart will create a new draft.")

    if c3.button("Go to Cart"):
        st.info("Open the Cart tab to continue editing the selected draft order.")

    with st.expander("Quick confirm sale (legacy flow)", expanded=False):
        if st.button("Confirm sale"):
            try:
                if not product_id:
                    raise ValueError("Please select a product")
                if float(price) < min_price:
                    raise ValueError(
                        f"Unit price cannot be below {format_money(min_price, currency_code, currency_symbol)}"
                    )
                resolved_customer_id = svc.resolve_customer_for_sale(
                    client_id,
                    {
                        "full_name": customer_name,
                        "phone": phone,
                        "email": email,
                        "address_line1": address_line1,
                        "city": city,
                    },
                    matched_customer_id=matched_customer_id,
                    user_id=user_id,
                )
                payload = SaleConfirm(
                    client_id=client_id,
                    customer_id=resolved_customer_id,
                    items=[
                        SaleItem(
                            product_id=product_id, qty=float(qty), unit_selling_price=float(price)
                        )
                    ],
                )
                result = svc.confirm_sale(
                    payload,
                    {"full_name": customer_name, "phone": phone, "address_line1": address_line1},
                    user_id=user_id,
                )
                st.success(f"Order confirmed {result['order_id']}")
            except Exception as exc:
                st.error(str(exc))

with cart_tab:
    st.subheader("Draft cart list")
    search = st.text_input("Search customer name/phone", key="cart_search")
    sort_order = st.selectbox("Sort", ["Newest", "Oldest"], key="cart_sort")
    non_empty_only = st.checkbox("Only carts with items", value=False)

    drafts = svc.list_draft_orders(client_id)
    customers_df = customer_repo.all()
    if not drafts.empty:
        customer_cols = ["customer_id", "full_name", "phone", "email", "address_line1", "city"]
        customer_view = (
            customers_df[customer_cols]
            if not customers_df.empty
            else pd.DataFrame(columns=customer_cols)
        )
        carts = drafts.merge(customer_view, on="customer_id", how="left")
        carts["full_name"] = carts["full_name"].fillna("Unknown")
        carts["phone"] = carts["phone"].fillna("")
        carts["timestamp"] = pd.to_datetime(carts["timestamp"], errors="coerce")

        totals = [
            svc.compute_order_totals(str(row.order_id)) for row in carts.itertuples(index=False)
        ]
        carts["subtotal"] = [t["subtotal"] for t in totals]
        carts["grand_total"] = [t["grand_total"] for t in totals]

        if search.strip():
            token = search.strip().lower()
            carts = carts[
                carts["full_name"].astype(str).str.lower().str.contains(token)
                | carts["phone"].astype(str).str.lower().str.contains(token)
            ]
        if non_empty_only:
            carts = carts[carts["item_count"] > 0]

        carts = carts.sort_values("timestamp", ascending=sort_order == "Oldest")

        for row in carts.itertuples(index=False):
            cols = st.columns([2.4, 1.6, 1.2, 1, 1, 1, 1])
            cols[0].markdown(f"**{row.full_name}**  \n{row.phone}")
            cols[1].write(f"{row.timestamp}")
            cols[2].write(f"Items: {int(row.item_count)}")
            cols[3].write(format_money(float(row.subtotal), currency_code, currency_symbol))
            cols[4].write(format_money(float(row.grand_total), currency_code, currency_symbol))
            if cols[5].button("Open", key=f"open_{row.order_id}"):
                st.session_state["selected_cart_order_id"] = row.order_id
                st.rerun()
            if cols[6].button("Confirm", key=f"confirm_inline_{row.order_id}"):
                try:
                    result = svc.confirm_order(
                        row.order_id, {"client_id": client_id, "user_id": user_id}
                    )
                    st.session_state["sales_last_cart_result"] = {
                        **result,
                        "order_id": row.order_id,
                    }
                    st.success(f"Confirmed: {result['invoice_no']} / {result['shipment_no']}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            caux = st.columns([1, 1, 5])
            if caux[0].button("Cancel", key=f"cancel_{row.order_id}"):
                if svc.cancel_draft_order(row.order_id):
                    st.success("Draft cart cancelled")
                    if st.session_state.get("selected_cart_order_id") == row.order_id:
                        st.session_state["selected_cart_order_id"] = ""
                    st.rerun()
            if caux[1].button("Empty", key=f"empty_{row.order_id}"):
                try:
                    svc.empty_draft_order(row.order_id, client_id)
                    st.success("Draft cart emptied")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            st.divider()
    else:
        st.info("No draft carts found.")

    selected_order_id = st.session_state.get("selected_cart_order_id", "")
    st.subheader("Selected cart workspace")
    if selected_order_id:
        order = svc.get_order(selected_order_id)
        if order and order.get("client_id") == client_id:
            customer = customer_repo.get(order.get("customer_id", "")) or {}
            st.markdown("**Customer**")
            st.write(
                f"{customer.get('full_name', '')} | {customer.get('phone', '')} | {customer.get('email', '')}"
            )
            st.write(f"{customer.get('address_line1', '')} {customer.get('city', '')}")

            p1, p2, p3 = st.columns(3)
            discount = p1.number_input(
                "Discount",
                min_value=0.0,
                value=float(order.get("discount", 0) or 0),
                key=f"discount_{selected_order_id}",
            )
            tax = p2.number_input(
                "Tax",
                min_value=0.0,
                value=float(order.get("tax", 0) or 0),
                key=f"tax_{selected_order_id}",
            )
            delivery_cost = p3.number_input(
                "Delivery cost",
                min_value=0.0,
                value=float(order.get("delivery_cost", 0) or 0),
                key=f"delivery_{selected_order_id}",
            )
            provider = st.text_input(
                "Delivery provider",
                value=order.get("delivery_provider", ""),
                key=f"provider_{selected_order_id}",
            )
            note = st.text_area(
                "Note", value=order.get("note", ""), key=f"note_{selected_order_id}"
            )
            if st.button("Save pricing/meta", key=f"save_pricing_{selected_order_id}"):
                try:
                    svc.update_order_pricing(
                        selected_order_id,
                        client_id,
                        float(discount),
                        float(tax),
                        float(delivery_cost),
                        provider,
                        note,
                    )
                    st.success("Cart pricing/meta updated")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            line_df = svc.resolve_order_items(client_id, selected_order_id)
            if line_df.empty:
                st.info("This draft cart is empty.")
            else:
                for item in line_df.itertuples(index=False):
                    with st.container(border=True):
                        st.write(f"{item.product_display_name}")
                        st.caption(
                            f"Available stock: {item.available_qty:,.2f} | Minimum allowed price: {format_money(float(item.minimum_allowed_price), currency_code, currency_symbol)}"
                        )
                        ec1, ec2, ec3, ec4 = st.columns(4)
                        new_qty = ec1.number_input(
                            "Qty",
                            min_value=0.01,
                            value=float(item.qty),
                            key=f"qty_{item.order_item_id}",
                        )
                        new_price = ec2.number_input(
                            "Unit price",
                            min_value=0.01,
                            value=float(item.unit_selling_price),
                            key=f"price_{item.order_item_id}",
                        )
                        ec3.write(
                            format_money(float(item.line_total), currency_code, currency_symbol)
                        )
                        if ec4.button("Save line", key=f"save_{item.order_item_id}"):
                            try:
                                svc.update_draft_item(
                                    item.order_item_id, float(new_qty), float(new_price), client_id
                                )
                                st.success("Line updated")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                        if st.button("Remove line", key=f"remove_{item.order_item_id}"):
                            try:
                                svc.remove_draft_item(item.order_item_id, client_id)
                                st.success("Line removed")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

            totals = svc.compute_order_totals(selected_order_id)
            st.markdown(
                f"Subtotal: **{format_money(totals['subtotal'], currency_code, currency_symbol)}**"
            )
            st.markdown(
                f"Discount: **{format_money(totals['discount'], currency_code, currency_symbol)}**"
            )
            st.markdown(f"Tax: **{format_money(totals['tax'], currency_code, currency_symbol)}**")
            st.markdown(
                f"Delivery: **{format_money(totals['delivery_cost'], currency_code, currency_symbol)}**"
            )
            st.markdown(
                f"Grand Total: **{format_money(totals['grand_total'], currency_code, currency_symbol)}**"
            )

            if order.get("status") == "draft" and st.button(
                "Confirm Order", key=f"confirm_detail_{selected_order_id}"
            ):
                try:
                    result = svc.confirm_order(
                        selected_order_id, {"client_id": client_id, "user_id": user_id}
                    )
                    st.success(f"Invoice {result['invoice_no']} | Shipment {result['shipment_no']}")
                    st.session_state["sales_last_cart_result"] = {
                        **result,
                        "order_id": selected_order_id,
                    }
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        else:
            st.warning("Selected cart not found for this client.")

    last_confirm = st.session_state.get("sales_last_cart_result")
    if last_confirm and last_confirm.get("invoice_id"):
        order_id = last_confirm["order_id"]
        order = svc.get_order(order_id) or {}
        order_items = svc.get_order_items(order_id)
        customer = customer_repo.get(order.get("customer_id", "")) or {}
        clients = clients_repo.all()
        client = (
            clients[clients["client_id"] == client_id].iloc[0].to_dict()
            if not clients.empty and not clients[clients["client_id"] == client_id].empty
            else {}
        )
        invoices = invoices_repo.all()
        invoice_row = invoices[invoices["invoice_id"] == last_confirm["invoice_id"]]
        invoice = (
            invoice_row.iloc[0].to_dict()
            if not invoice_row.empty
            else {"invoice_no": last_confirm["invoice_no"]}
        )
        shipments = shipments_repo.all()
        shipment_row = shipments[shipments["shipment_id"] == last_confirm["shipment_id"]]
        shipment = (
            shipment_row.iloc[0].to_dict()
            if not shipment_row.empty
            else {"shipment_no": last_confirm["shipment_no"]}
        )

        product_names = (
            product_repo.all()[["product_id", "product_name"]]
            if not product_repo.all().empty
            else pd.DataFrame(columns=["product_id", "product_name"])
        )
        render_items_df = (
            order_items.merge(product_names, on="product_id", how="left")
            if not order_items.empty
            else pd.DataFrame()
        )
        render_items = (
            render_items_df.to_dict(orient="records") if not render_items_df.empty else []
        )

        try:
            invoice_pdf = build_invoice_pdf(client, customer, order, render_items, invoice)
            shipment_pdf = build_shipment_pdf(client, customer, order, render_items, shipment)
            st.download_button(
                "Download Invoice PDF",
                invoice_pdf,
                file_name=f"{last_confirm['invoice_no']}.pdf",
                mime="application/pdf",
            )
            st.download_button(
                "Download Shipping Mark",
                shipment_pdf,
                file_name=f"{last_confirm['shipment_no']}.pdf",
                mime="application/pdf",
            )
        except PdfDependencyError as exc:
            st.warning(str(exc))

with records_tab:
    st.subheader("Sales records")
    records_search = st.text_input("Search invoice/order/customer", key="records_search")
    records_sort_order = st.selectbox("Sort by date", ["Newest", "Oldest"], key="records_sort")

    reconciled_orders = recon.confirmed_sales_with_reconciliation(client_id, latest_limit=50)
    if reconciled_orders.empty:
        st.info("No sales records found.")
    else:
        customers = customer_repo.all()
        invoices = invoices_repo.all()
        payments = payments_repo.all()

        confirmed_orders = reconciled_orders.copy()
        st.caption(
            "Showing the latest 50 confirmed sales for this client (reconciled with ledger)."
        )

        invoice_view_cols = ["invoice_id", "invoice_no", "order_id", "status"]
        invoice_view = (
            invoices[invoice_view_cols]
            if not invoices.empty
            else pd.DataFrame(columns=invoice_view_cols)
        )
        invoice_view = invoice_view.rename(columns={"status": "invoice_status"})
        records = confirmed_orders.merge(invoice_view, on="order_id", how="left")

        customer_cols = ["customer_id", "full_name", "phone"]
        customer_view = (
            customers[customer_cols] if not customers.empty else pd.DataFrame(columns=customer_cols)
        )
        records = records.merge(customer_view, on="customer_id", how="left")

        if not payments.empty and "invoice_id" in records.columns:
            payments["amount_paid"] = payments["amount_paid"].astype(float)
            paid_summary = payments.groupby("invoice_id", as_index=False)["amount_paid"].sum()
            records = records.merge(paid_summary, on="invoice_id", how="left")
        else:
            records["amount_paid"] = 0.0
        records["amount_paid"] = records["amount_paid"].fillna(0.0)

        records["full_name"] = records["full_name"].fillna("Unknown")
        records["phone"] = records["phone"].fillna("")
        records["invoice_no"] = records["invoice_no"].fillna("-")
        records["invoice_status"] = records["invoice_status"].fillna("unpaid")

        if records_search.strip():
            token = records_search.strip().lower()
            records = records[
                records["invoice_no"].astype(str).str.lower().str.contains(token)
                | records["order_id"].astype(str).str.lower().str.contains(token)
                | records["full_name"].astype(str).str.lower().str.contains(token)
                | records["phone"].astype(str).str.lower().str.contains(token)
            ]

        records = records.sort_values("timestamp", ascending=records_sort_order == "Oldest")

        display = records[
            [
                "timestamp",
                "invoice_no",
                "order_id",
                "full_name",
                "phone",
                "grand_total",
                "amount_paid",
                "invoice_status",
                "has_items",
                "has_ledger_earning",
                "ledger_mismatch",
            ]
        ].copy()
        display = display.rename(
            columns={
                "timestamp": "Sale Date",
                "invoice_no": "Invoice No",
                "order_id": "Order ID",
                "full_name": "Customer",
                "phone": "Phone",
                "grand_total": "Total",
                "amount_paid": "Paid",
                "invoice_status": "Invoice Status",
                "has_items": "Has Items",
                "has_ledger_earning": "Ledger Posted",
                "ledger_mismatch": "Ledger Mismatch",
            }
        )
        display["Sale Date"] = display["Sale Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display["Total"] = display["Total"].apply(
            lambda value: format_money(float(value), currency_code, currency_symbol)
        )
        display["Paid"] = display["Paid"].apply(
            lambda value: format_money(float(value), currency_code, currency_symbol)
        )
        st.dataframe(display, use_container_width=True)

        if "SUPER_ADMIN" in roles:
            orphan_ledger = recon.orphan_ledger_earnings(client_id)
            if not orphan_ledger.empty:
                st.warning("Orphan ledger earning entries detected (no matching sales order).")
                st.dataframe(orphan_ledger, use_container_width=True)
