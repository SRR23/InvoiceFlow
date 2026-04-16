"""
Generate invoice PDFs (ReportLab). Used by Celery and email attachments.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value, currency: str = "") -> str:
    try:
        num = f"{float(value):,.2f}"
    except (TypeError, ValueError):
        num = str(value)
    return f"{num} {currency}".strip() if currency else num


def build_invoice_pdf_bytes(invoice, *, status_display: str | None = None) -> bytes:
    """
    Build a PDF byte string for an invoice.

    Expects ``invoice`` with ``client``, ``user``, and ``items`` (prefetched) loaded.

    If ``status_display`` is set (e.g. ``\"Sent\"`` when attaching to a just-sent email),
    that label is used for the Status row instead of ``invoice.get_status_display()``,
    so the PDF matches the sending flow even if the in-memory instance were stale.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="MerchantTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        name="InvHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#134e4a"),
    )
    small = ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

    story = []
    user = invoice.user
    merchant = (user.company_name or "").strip() or user.get_full_name() or user.email
    story.append(Paragraph(merchant.replace("&", "&amp;"), title_style))
    story.append(Paragraph(f"<b>Invoice</b> {invoice.invoice_number}", heading))
    story.append(Spacer(1, 0.15 * inch))

    client = invoice.client
    lines = [f"<b>Bill to:</b> {client.name}"]
    if client.company:
        lines.append(client.company)
    if client.email:
        lines.append(client.email)
    if client.phone:
        lines.append(client.phone)
    if client.address:
        safe_addr = client.address.replace("&", "&amp;").replace("<", "")
        lines.append(safe_addr.replace("\n", "<br/>"))
    for line in lines:
        story.append(Paragraph(line, styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    # Prefer explicit label when caller knows the intended status (e.g. email attachment).
    resolved_status = (
        status_display
        if status_display is not None
        else invoice.get_status_display()
    )
    meta = Table(
        [
            ["Issue date", str(invoice.issue_date)],
            ["Due date", str(invoice.due_date)],
            ["Status", resolved_status],
        ],
        colWidths=[1.4 * inch, 4.2 * inch],
    )
    meta.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 0.2 * inch))

    data = [["Description", "Qty", "Unit", "Tax %", "Line total"]]
    items_qs = list(invoice.items.all())
    for item in items_qs:
        desc = item.title
        if item.description:
            desc = f"{desc} - {item.description[:120]}"
        data.append(
            [
                desc[:100],
                str(item.quantity),
                _money(item.unit_price, invoice.currency),
                f"{item.tax_rate}%",
                _money(item.total_price, invoice.currency),
            ]
        )
    if len(data) == 1:
        data.append(["No line items", "-", "-", "-", "-"])

    table = Table(data, colWidths=[2.6 * inch, 0.65 * inch, 0.95 * inch, 0.55 * inch, 1.1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))

    totals_data = [
        ["Subtotal", _money(invoice.subtotal, invoice.currency)],
        ["Tax", _money(invoice.tax, invoice.currency)],
        ["Discount", _money(invoice.discount, invoice.currency)],
        ["Total due", _money(invoice.total_amount, invoice.currency)],
    ]
    totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.35 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 11),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#0f172a")),
            ]
        )
    )
    story.append(totals_table)

    if invoice.notes:
        story.append(Spacer(1, 0.2 * inch))
        notes_safe = invoice.notes.replace("&", "&amp;").replace("<", "").replace(">", "")
        story.append(Paragraph(f"<b>Notes / terms</b><br/>{notes_safe.replace(chr(10), '<br/>')}", styles["Normal"]))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Generated by InvoiceFlow", small))

    doc.build(story)
    return buffer.getvalue()
