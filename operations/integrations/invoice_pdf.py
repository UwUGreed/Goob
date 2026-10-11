"""Printable invoice built from a saved, authorized snapshot; no remote assets."""
from html import escape
from io import BytesIO
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def render(invoice):
    s = invoice.snapshot
    d = s["draft"]
    out = BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#442d43")
    def p(value, style="BodyText"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])
    def money(value):
        return "Unresolved" if value is None else ("-" if value < 0 else "") + f"${Decimal(abs(value))/100:,.2f}"
    company = s["configuration"]["company"]
    story = [p(company["name"] or "Company details require review", "Title"), p(company["address"]), p(company["contact"]), Spacer(1, 20),
        p("Invoice " + invoice.number, "Heading1"), p(invoice.status.upper() + (" — NOT FINAL" if invoice.status != "finalized" else "")),
        p(f"Invoice date: {d['invoice_date']}    Due: {d['due_date']}    Service date: {d['service_date']}"), Spacer(1, 12),
        p("Bill to: " + s["customer"]["name"], "Heading2"), p(s["property"]["address"]),
        p(s["customer"]["email"] or s["customer"]["phone"]), Spacer(1, 14), p(d["title"], "Heading2"), p(d["description"]), Spacer(1, 16)]
    rows = [[p("Description"), p("Qty"), p("Unit price"), p("Discount"), p("Amount")]]
    for line in s["lines"]:
        rows.append([p(line["description"]), p(line["quantity"]), p("Unresolved" if line["unit_price"] is None else money(int(Decimal(line["unit_price"])*100))), p(money(line["discount_cents"])), p(money(line["total_cents"]))])
    table = Table(rows, colWidths=[2.8*inch, .45*inch, .85*inch, .85*inch, .95*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f5eee9")), ("VALIGN", (0,0),(-1,-1),"TOP"),
        ("LINEBELOW",(0,0),(-1,-1),.4,colors.HexColor("#ded4da")), ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    story += [table, Spacer(1, 14), p("Subtotal: " + money(s["subtotal_cents"])), p("Membership adjustments: −" + money(s["discount_cents"])),
        p("Tax: " + money(s["tax_cents"])), p("Total" + (" (partial)" if s["partial"] else "") + ": " + money(s["total_cents"]), "Heading2")]
    for line in s["lines"]:
        if line["discount_cents"]:
            story.append(p(line["description"]+": "+line["discount_reason"]))
    if invoice.status != "finalized":
        story += [p("Review required", "Heading2")] + [p(x) for x in s["issues"]]
    SimpleDocTemplate(out, pagesize=(612,792), leftMargin=42, rightMargin=42, topMargin=40, bottomMargin=40,
        title="Invoice "+invoice.number).build(story)
    return out.getvalue()
