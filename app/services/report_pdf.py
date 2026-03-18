"""PDF report generation using fpdf2."""
import io
from datetime import date
from decimal import Decimal

from fpdf import FPDF


class ReportPDF(FPDF):
    """Custom PDF class with header/footer for purchase reports."""

    def __init__(self, title, org_name=None, **kwargs):
        super().__init__(orientation="L", unit="mm", format="A4", **kwargs)
        self.report_title = title
        self.org_name = org_name or "Budgy"
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, self.org_name, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, self.report_title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, f"Generated: {date.today().strftime('%m/%d/%Y')}", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def _section_title(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(52, 58, 64)
        self.set_text_color(255, 255, 255)
        self.cell(0, 7, f"  {text}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def _table_header(self, col_widths, headers):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(233, 236, 239)
        for w, h in zip(col_widths, headers):
            align = "R" if h in ("Amount", "Count", "Total") else "L"
            self.cell(w, 6, h, border=1, fill=True, align=align)
        self.ln()

    def _table_row(self, col_widths, values, aligns=None):
        self.set_font("Helvetica", "", 7)
        if aligns is None:
            aligns = ["L"] * len(values)
        for w, v, a in zip(col_widths, values, aligns):
            self.cell(w, 5, str(v)[:60], border=1, align=a)
        self.ln()

    def _fmt_money(self, val):
        return f"${val:,.2f}"


def _build_date_range_label(params):
    parts = []
    if params.get("date_from"):
        parts.append(f"From: {params['date_from']}")
    if params.get("date_to"):
        parts.append(f"To: {params['date_to']}")
    return " | ".join(parts) if parts else "All Dates"


def generate_dept_report_pdf(department, report, params, org_name=None):
    """Generate a PDF for a department purchase report."""
    title = f"Purchase Report - {department.name}"
    pdf = ReportPDF(title, org_name)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Date range & filter summary
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Date Range: {_build_date_range_label(params)}", new_x="LMARGIN", new_y="NEXT")

    filters = []
    if params.get("status"):
        filters.append(f"Status: {params['status'].title()}")
    if params.get("payment_method"):
        filters.append(f"Payment: {params['payment_method']}")
    if params.get("tax_exempt_status"):
        from app.models.purchase import Purchase
        tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)
        filters.append(f"Tax Status: {tax_labels.get(params['tax_exempt_status'], params['tax_exempt_status'])}")
    if filters:
        pdf.cell(0, 5, "Filters: " + " | ".join(filters), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)

    # Summary box
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(70, 7, f"Total Purchases: {report['purchase_count']}", border=1)
    pdf.cell(70, 7, f"Total Amount: {pdf._fmt_money(report['total_amount'])}", border=1)
    pdf.ln(10)

    # Breakdown tables side by side approach -do them sequentially for simplicity

    # By Status
    if report["by_status"]:
        pdf._section_title("Breakdown by Status")
        widths = [60, 30, 50]
        pdf._table_header(widths, ["Status", "Count", "Total"])
        for status, data in report["by_status"].items():
            pdf._table_row(widths, [status.title(), str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Line Item
    if report["by_line_item"]:
        pdf._section_title("Breakdown by Line Item")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Line Item", "Count", "Total"])
        for item, data in report["by_line_item"].items():
            pdf._table_row(widths, [item[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Payment Method
    if report["by_payment"]:
        pdf._section_title("Breakdown by Payment Method")
        widths = [80, 30, 50]
        pdf._table_header(widths, ["Payment Method", "Count", "Total"])
        for method, data in report["by_payment"].items():
            pdf._table_row(widths, [method, str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Tax Status
    if report["by_tax_status"]:
        pdf._section_title("Breakdown by Tax Exempt Status")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Tax Status", "Count", "Total"])
        for status, data in report["by_tax_status"].items():
            pdf._table_row(widths, [status[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # Top Vendors
    if report["by_vendor"]:
        pdf._section_title("Top Vendors")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Vendor", "Count", "Total"])
        for vendor, data in report["by_vendor"].items():
            pdf._table_row(widths, [vendor[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # Purchase Details
    pdf.add_page()
    pdf._section_title(f"Purchase Details ({report['purchase_count']} records)")
    widths = [22, 55, 50, 30, 22, 35, 60]
    pdf._table_header(widths, ["Date", "Vendor", "Line Item", "Amount", "Status", "Payment", "Submitted By"])

    from app.models.purchase import Purchase
    tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)

    for p in report["purchases"]:
        pdf._table_row(
            widths,
            [
                p.purchase_date.strftime("%m/%d/%Y"),
                p.vendor_name[:30],
                (p.line_item.code if p.line_item else "N/A")[:25],
                pdf._fmt_money(p.amount),
                p.status,
                (p.payment_method or "-")[:18],
                (p.submitter.display_name if p.submitter else "N/A")[:30],
            ],
            ["L", "L", "L", "R", "L", "L", "L"],
        )

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf.getvalue()


def generate_global_report_pdf(report, params, org_name=None, selected_dept_name=None):
    """Generate a PDF for the global purchase report."""
    title = "Global Purchase Report"
    if selected_dept_name:
        title += f" - {selected_dept_name}"
    pdf = ReportPDF(title, org_name)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Date range & filter summary
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Date Range: {_build_date_range_label(params)}", new_x="LMARGIN", new_y="NEXT")

    filters = []
    if selected_dept_name:
        filters.append(f"Department: {selected_dept_name}")
    if params.get("status"):
        filters.append(f"Status: {params['status'].title()}")
    if params.get("payment_method"):
        filters.append(f"Payment: {params['payment_method']}")
    if params.get("tax_exempt_status"):
        from app.models.purchase import Purchase
        tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)
        filters.append(f"Tax Status: {tax_labels.get(params['tax_exempt_status'], params['tax_exempt_status'])}")
    if filters:
        pdf.cell(0, 5, "Filters: " + " | ".join(filters), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)

    # Summary box
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(70, 7, f"Total Purchases: {report['purchase_count']}", border=1)
    pdf.cell(70, 7, f"Total Amount: {pdf._fmt_money(report['total_amount'])}", border=1)
    pdf.ln(10)

    # By Department
    if report.get("by_department"):
        pdf._section_title("Breakdown by Department")
        widths = [80, 30, 50]
        pdf._table_header(widths, ["Department", "Count", "Total"])
        for dept, data in report["by_department"].items():
            pdf._table_row(widths, [dept[:40], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Status
    if report["by_status"]:
        pdf._section_title("Breakdown by Status")
        widths = [60, 30, 50]
        pdf._table_header(widths, ["Status", "Count", "Total"])
        for status, data in report["by_status"].items():
            pdf._table_row(widths, [status.title(), str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Line Item
    if report["by_line_item"]:
        pdf._section_title("Breakdown by Line Item")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Line Item", "Count", "Total"])
        for item, data in report["by_line_item"].items():
            pdf._table_row(widths, [item[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Payment Method
    if report["by_payment"]:
        pdf._section_title("Breakdown by Payment Method")
        widths = [80, 30, 50]
        pdf._table_header(widths, ["Payment Method", "Count", "Total"])
        for method, data in report["by_payment"].items():
            pdf._table_row(widths, [method, str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # By Tax Status
    if report["by_tax_status"]:
        pdf._section_title("Breakdown by Tax Exempt Status")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Tax Status", "Count", "Total"])
        for status, data in report["by_tax_status"].items():
            pdf._table_row(widths, [status[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # Top Vendors
    if report["by_vendor"]:
        pdf._section_title("Top Vendors")
        widths = [100, 30, 50]
        pdf._table_header(widths, ["Vendor", "Count", "Total"])
        for vendor, data in report["by_vendor"].items():
            pdf._table_row(widths, [vendor[:55], str(data["count"]), pdf._fmt_money(data["total"])],
                           ["L", "R", "R"])
        pdf.ln(3)

    # Purchase Details
    pdf.add_page()
    pdf._section_title(f"Purchase Details ({report['purchase_count']} records)")
    widths = [22, 40, 45, 40, 28, 22, 32, 45]
    pdf._table_header(widths, ["Date", "Department", "Vendor", "Line Item", "Amount", "Status", "Payment", "Submitted By"])

    for p in report["purchases"]:
        pdf._table_row(
            widths,
            [
                p.purchase_date.strftime("%m/%d/%Y"),
                (p.department.name if p.department else "N/A")[:22],
                p.vendor_name[:24],
                (p.line_item.code if p.line_item else "N/A")[:22],
                pdf._fmt_money(p.amount),
                p.status,
                (p.payment_method or "-")[:16],
                (p.submitter.display_name if p.submitter else "N/A")[:24],
            ],
            ["L", "L", "L", "L", "R", "L", "L", "L"],
        )

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf.getvalue()
