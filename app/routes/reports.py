import io
import csv
from datetime import date, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request,
    g,
    Response,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models.purchase import Purchase
from app.models.budget_line_item import BudgetLineItem
from app.models.fiscal_year import FiscalYear
from app.models.department import Department
from app.utils.decorators import dept_admin_required, global_admin_required, department_access_required
from app.services.report_pdf import generate_dept_report_pdf, generate_global_report_pdf

reports_bp = Blueprint(
    "reports", __name__, template_folder="../templates/reports"
)


def _build_purchase_query(department_id=None, date_from=None, date_to=None,
                          status=None, line_item_id=None, payment_method=None,
                          tax_exempt_status=None):
    """Build a filtered purchase query."""
    query = Purchase.query

    if department_id:
        query = query.filter(Purchase.department_id == department_id)

    if date_from:
        query = query.filter(Purchase.purchase_date >= date_from)
    if date_to:
        query = query.filter(Purchase.purchase_date <= date_to)

    if status:
        query = query.filter(Purchase.status == status)
    else:
        query = query.filter(Purchase.status != "rejected")

    if line_item_id:
        query = query.filter(Purchase.budget_line_item_id == line_item_id)

    if payment_method:
        query = query.filter(Purchase.payment_method == payment_method)

    if tax_exempt_status:
        query = query.filter(Purchase.tax_exempt_status == tax_exempt_status)

    return query


def _compute_report_data(query):
    """Compute summary statistics and breakdowns from a purchase query."""
    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    total_amount = sum(p.amount for p in purchases) if purchases else Decimal("0")
    purchase_count = len(purchases)

    # Breakdown by status
    by_status = {}
    for p in purchases:
        key = p.status or "unknown"
        if key not in by_status:
            by_status[key] = {"count": 0, "total": Decimal("0")}
        by_status[key]["count"] += 1
        by_status[key]["total"] += p.amount

    # Breakdown by line item
    by_line_item = {}
    for p in purchases:
        label = p.line_item.display_label if p.line_item else "N/A"
        if label not in by_line_item:
            by_line_item[label] = {"count": 0, "total": Decimal("0")}
        by_line_item[label]["count"] += 1
        by_line_item[label]["total"] += p.amount

    # Breakdown by payment method
    by_payment = {}
    for p in purchases:
        key = p.payment_method or "Not Specified"
        if key not in by_payment:
            by_payment[key] = {"count": 0, "total": Decimal("0")}
        by_payment[key]["count"] += 1
        by_payment[key]["total"] += p.amount

    # Breakdown by tax exempt status
    tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)
    by_tax_status = {}
    for p in purchases:
        key = tax_labels.get(p.tax_exempt_status, "Not Specified") if p.tax_exempt_status else "Not Specified"
        if key not in by_tax_status:
            by_tax_status[key] = {"count": 0, "total": Decimal("0")}
        by_tax_status[key]["count"] += 1
        by_tax_status[key]["total"] += p.amount

    # Breakdown by vendor (top 15)
    by_vendor = {}
    for p in purchases:
        key = p.vendor_name
        if key not in by_vendor:
            by_vendor[key] = {"count": 0, "total": Decimal("0")}
        by_vendor[key]["count"] += 1
        by_vendor[key]["total"] += p.amount
    by_vendor = dict(sorted(by_vendor.items(), key=lambda x: x[1]["total"], reverse=True)[:15])

    return {
        "purchases": purchases,
        "total_amount": total_amount,
        "purchase_count": purchase_count,
        "by_status": by_status,
        "by_line_item": by_line_item,
        "by_payment": by_payment,
        "by_tax_status": by_tax_status,
        "by_vendor": by_vendor,
    }


def _get_filter_params():
    """Extract filter parameters from request args."""
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    status = request.args.get("status", "")
    line_item_id = request.args.get("line_item", type=int)
    payment_method = request.args.get("payment_method", "")
    tax_exempt_status = request.args.get("tax_exempt_status", "")

    return {
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "line_item_id": line_item_id,
        "payment_method": payment_method,
        "tax_exempt_status": tax_exempt_status,
    }


@reports_bp.route("/dept/<int:dept_id>/")
@login_required
@department_access_required
@dept_admin_required
def dept_report(dept_id):
    """Department purchase report with date range and filters."""
    department = g.department
    params = _get_filter_params()

    query = _build_purchase_query(
        department_id=department.id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    report = _compute_report_data(query)

    line_items = (
        BudgetLineItem.query
        .filter_by(is_active=True, department_id=department.id)
        .order_by(BudgetLineItem.code)
        .all()
    )

    # Get distinct payment methods used
    payment_methods = [
        r[0] for r in
        db.session.query(Purchase.payment_method)
        .filter(Purchase.department_id == department.id, Purchase.payment_method.isnot(None))
        .distinct().order_by(Purchase.payment_method).all()
    ]

    return render_template(
        "reports/dept_report.html",
        department=department,
        report=report,
        params=params,
        line_items=line_items,
        payment_methods=payment_methods,
        statuses=Purchase.STATUSES,
        tax_exempt_choices=Purchase.TAX_EXEMPT_CHOICES,
    )


@reports_bp.route("/dept/<int:dept_id>/export")
@login_required
@department_access_required
@dept_admin_required
def dept_report_export(dept_id):
    """Export department report as CSV."""
    department = g.department
    params = _get_filter_params()

    query = _build_purchase_query(
        department_id=department.id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Vendor", "Date", "Amount", "Status", "Payment Method",
        "Tax Exempt Status", "Line Item", "Custom Code", "Description",
        "PO #", "Invoice #", "Submitted By", "Fiscal Year", "Notes",
    ])

    for p in purchases:
        writer.writerow([
            p.id,
            p.vendor_name,
            p.purchase_date.isoformat(),
            str(p.amount),
            p.status,
            p.payment_method or "",
            tax_labels.get(p.tax_exempt_status, "") if p.tax_exempt_status else "",
            p.line_item.display_label if p.line_item else "",
            p.custom_account_code or "",
            p.description or "",
            p.po_number or "",
            p.invoice_number or "",
            p.submitter.display_name if p.submitter else "",
            p.fiscal_year.label if p.fiscal_year else "",
            p.notes or "",
        ])

    output.seek(0)
    date_suffix = ""
    if params["date_from"]:
        date_suffix += f"_from_{params['date_from']}"
    if params["date_to"]:
        date_suffix += f"_to_{params['date_to']}"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={department.slug}_report{date_suffix}.csv"},
    )


@reports_bp.route("/dept/<int:dept_id>/pdf")
@login_required
@department_access_required
@dept_admin_required
def dept_report_pdf(dept_id):
    """Export department report as PDF."""
    department = g.department
    params = _get_filter_params()

    query = _build_purchase_query(
        department_id=department.id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    report = _compute_report_data(query)

    from flask import current_app
    from app.models.organization_settings import OrganizationSettings
    try:
        org_name = OrganizationSettings.get().organization_name
    except Exception:
        org_name = None

    pdf_bytes = generate_dept_report_pdf(department, report, params, org_name=org_name)

    date_suffix = ""
    if params["date_from"]:
        date_suffix += f"_from_{params['date_from']}"
    if params["date_to"]:
        date_suffix += f"_to_{params['date_to']}"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={department.slug}_report{date_suffix}.pdf"},
    )


@reports_bp.route("/")
@login_required
@global_admin_required
def global_report():
    """Global purchase report across all departments."""
    params = _get_filter_params()
    dept_id = request.args.get("department", type=int)

    query = _build_purchase_query(
        department_id=dept_id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    report = _compute_report_data(query)

    # Breakdown by department
    by_department = {}
    for p in report["purchases"]:
        dept_name = p.department.name if p.department else "N/A"
        if dept_name not in by_department:
            by_department[dept_name] = {"count": 0, "total": Decimal("0")}
        by_department[dept_name]["count"] += 1
        by_department[dept_name]["total"] += p.amount
    report["by_department"] = by_department

    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    # Get all active line items (optionally filtered by dept)
    li_query = BudgetLineItem.query.filter_by(is_active=True)
    if dept_id:
        li_query = li_query.filter_by(department_id=dept_id)
    line_items = li_query.order_by(BudgetLineItem.code).all()

    # Get distinct payment methods
    pm_query = db.session.query(Purchase.payment_method).filter(Purchase.payment_method.isnot(None)).distinct()
    if dept_id:
        pm_query = pm_query.filter(Purchase.department_id == dept_id)
    payment_methods = [r[0] for r in pm_query.order_by(Purchase.payment_method).all()]

    return render_template(
        "reports/global_report.html",
        report=report,
        params=params,
        departments=departments,
        selected_dept_id=dept_id,
        line_items=line_items,
        payment_methods=payment_methods,
        statuses=Purchase.STATUSES,
        tax_exempt_choices=Purchase.TAX_EXEMPT_CHOICES,
    )


@reports_bp.route("/export")
@login_required
@global_admin_required
def global_report_export():
    """Export global report as CSV."""
    params = _get_filter_params()
    dept_id = request.args.get("department", type=int)

    query = _build_purchase_query(
        department_id=dept_id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    tax_labels = dict(Purchase.TAX_EXEMPT_CHOICES)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Department", "Vendor", "Date", "Amount", "Status",
        "Payment Method", "Tax Exempt Status", "Line Item", "Custom Code",
        "Description", "PO #", "Invoice #", "Submitted By", "Fiscal Year", "Notes",
    ])

    for p in purchases:
        writer.writerow([
            p.id,
            p.department.name if p.department else "",
            p.vendor_name,
            p.purchase_date.isoformat(),
            str(p.amount),
            p.status,
            p.payment_method or "",
            tax_labels.get(p.tax_exempt_status, "") if p.tax_exempt_status else "",
            p.line_item.display_label if p.line_item else "",
            p.custom_account_code or "",
            p.description or "",
            p.po_number or "",
            p.invoice_number or "",
            p.submitter.display_name if p.submitter else "",
            p.fiscal_year.label if p.fiscal_year else "",
            p.notes or "",
        ])

    output.seek(0)
    date_suffix = ""
    if params["date_from"]:
        date_suffix += f"_from_{params['date_from']}"
    if params["date_to"]:
        date_suffix += f"_to_{params['date_to']}"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=global_report{date_suffix}.csv"},
    )


@reports_bp.route("/pdf")
@login_required
@global_admin_required
def global_report_pdf():
    """Export global report as PDF."""
    params = _get_filter_params()
    dept_id = request.args.get("department", type=int)

    query = _build_purchase_query(
        department_id=dept_id,
        date_from=params["date_from"] or None,
        date_to=params["date_to"] or None,
        status=params["status"] or None,
        line_item_id=params["line_item_id"],
        payment_method=params["payment_method"] or None,
        tax_exempt_status=params["tax_exempt_status"] or None,
    )

    report = _compute_report_data(query)

    # Breakdown by department
    by_department = {}
    for p in report["purchases"]:
        dept_name = p.department.name if p.department else "N/A"
        if dept_name not in by_department:
            by_department[dept_name] = {"count": 0, "total": Decimal("0")}
        by_department[dept_name]["count"] += 1
        by_department[dept_name]["total"] += p.amount
    report["by_department"] = by_department

    selected_dept_name = None
    if dept_id:
        dept = Department.query.get(dept_id)
        if dept:
            selected_dept_name = dept.name

    from app.models.organization_settings import OrganizationSettings
    try:
        org_name = OrganizationSettings.get().organization_name
    except Exception:
        org_name = None

    pdf_bytes = generate_global_report_pdf(
        report, params, org_name=org_name, selected_dept_name=selected_dept_name
    )

    date_suffix = ""
    if params["date_from"]:
        date_suffix += f"_from_{params['date_from']}"
    if params["date_to"]:
        date_suffix += f"_to_{params['date_to']}"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=global_report{date_suffix}.pdf"},
    )
