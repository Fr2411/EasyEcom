from __future__ import annotations

from io import BytesIO


class PdfDependencyError(ImportError):
    """Raised when optional PDF dependencies are not installed."""


def _load_reportlab() -> tuple[object, object]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "PDF generation requires `reportlab`. Install dependencies with `pip install -e .` "
            "(or `pip install reportlab`)."
        ) from exc
    return A4, canvas


def _draw_header(c: object, client: dict[str, str], title: str, number: str) -> None:
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 800, client.get("business_name", "EasyEcom"))
    c.setFont("Helvetica", 10)
    c.drawString(40, 784, f"Phone: {client.get('phone', '')}  Email: {client.get('email', '')}")
    c.drawString(40, 770, str(client.get("address", "")))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 744, f"{title}: {number}")


def build_invoice_pdf(client: dict[str, str], customer: dict[str, str], order: dict[str, str], items: list[dict[str, str]], invoice: dict[str, str]) -> bytes:
    A4, canvas = _load_reportlab()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _draw_header(c, client, "Invoice", invoice.get("invoice_no", ""))

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 720, "Bill To")
    c.setFont("Helvetica", 10)
    c.drawString(40, 705, customer.get("full_name", ""))
    c.drawString(40, 690, customer.get("phone", ""))
    c.drawString(40, 675, customer.get("address_line1", ""))
    c.drawString(40, 660, customer.get("city", ""))

    y = 630
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Product")
    c.drawString(280, y, "Qty")
    c.drawString(340, y, "Unit Price")
    c.drawString(460, y, "Line Total")
    c.setFont("Helvetica", 10)
    y -= 18
    subtotal = 0.0
    for item in items:
        qty = float(item.get("qty", 0) or 0)
        unit_price = float(item.get("unit_selling_price", 0) or 0)
        line_total = qty * unit_price
        subtotal += line_total
        c.drawString(40, y, str(item.get("product_name") or item.get("product_id", ""))[:38])
        c.drawRightString(315, y, f"{qty:.2f}")
        c.drawRightString(420, y, f"{unit_price:,.2f}")
        c.drawRightString(560, y, f"{line_total:,.2f}")
        y -= 16
        if y < 80:
            c.showPage()
            y = 800

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(560, max(y - 12, 60), f"Total: {subtotal:,.2f}")
    c.showPage()
    c.save()
    return buffer.getvalue()


def build_shipment_pdf(client: dict[str, str], customer: dict[str, str], order: dict[str, str], items: list[dict[str, str]], shipment: dict[str, str]) -> bytes:
    A4, canvas = _load_reportlab()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _draw_header(c, client, "Shipment", shipment.get("shipment_no", ""))

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 720, "Ship To")
    c.setFont("Helvetica", 10)
    c.drawString(40, 705, customer.get("full_name", ""))
    c.drawString(40, 690, customer.get("phone", ""))
    c.drawString(40, 675, customer.get("address_line1", ""))
    c.drawString(40, 660, customer.get("city", ""))

    y = 630
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Items")
    c.setFont("Helvetica", 10)
    y -= 18
    for item in items:
        c.drawString(40, y, f"- {item.get('product_name') or item.get('product_id', '')} x {float(item.get('qty', 0) or 0):.2f}")
        y -= 16
        if y < 80:
            c.showPage()
            y = 800

    c.showPage()
    c.save()
    return buffer.getvalue()
