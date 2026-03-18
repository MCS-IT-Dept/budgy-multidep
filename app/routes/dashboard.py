from flask import Blueprint, render_template, request, g
from flask_login import login_required

from app.models.fiscal_year import FiscalYear
from app.models.purchase import Purchase
from app.services.budget import get_budget_summary, get_budget_totals, get_cross_department_summary
from app.services.fiscal_year import get_or_create_fiscal_year, get_all_fiscal_years
from app.utils.decorators import dept_admin_required, global_admin_required, department_access_required
from datetime import date

dashboard_bp = Blueprint(
    "dashboard", __name__, template_folder="../templates/dashboard"
)


@dashboard_bp.route("/")
@login_required
@global_admin_required
def global_overview():
    """Global admin overview showing all departments."""
    fiscal_years = get_all_fiscal_years()

    fy_id = request.args.get("fy", type=int)
    if fy_id:
        fiscal_year = FiscalYear.query.get(fy_id)
    else:
        fiscal_year = get_or_create_fiscal_year(date.today())

    if not fiscal_year:
        fiscal_year = get_or_create_fiscal_year(date.today())

    dept_summaries = get_cross_department_summary(fiscal_year.id)

    # Overall totals across all departments
    from decimal import Decimal
    overall = {
        "total_allocated": sum(d["totals"]["total_allocated"] for d in dept_summaries),
        "total_spent": sum(d["totals"]["total_spent"] for d in dept_summaries),
        "total_pending": sum(d["totals"]["total_pending"] for d in dept_summaries),
        "total_remaining": sum(d["totals"]["total_remaining"] for d in dept_summaries),
    }
    overall["pct_used"] = (
        round((overall["total_spent"] / overall["total_allocated"]) * 100, 1)
        if overall["total_allocated"] > 0
        else Decimal("0")
    )

    recent_purchases = (
        Purchase.query
        .filter_by(fiscal_year_id=fiscal_year.id)
        .filter(Purchase.status != "rejected")
        .order_by(Purchase.created_at.desc())
        .limit(10)
        .all()
    )

    tax_reimbursement_purchases = (
        Purchase.query
        .filter_by(tax_exempt_status="reimbursement_required")
        .filter(Purchase.status != "rejected")
        .order_by(Purchase.created_at.desc())
        .all()
    )

    return render_template(
        "dashboard/global_overview.html",
        fiscal_year=fiscal_year,
        fiscal_years=fiscal_years,
        dept_summaries=dept_summaries,
        overall=overall,
        recent_purchases=recent_purchases,
        tax_reimbursement_purchases=tax_reimbursement_purchases,
    )


@dashboard_bp.route("/dept/<int:dept_id>")
@login_required
@department_access_required
@dept_admin_required
def dept_dashboard(dept_id):
    """Department-specific dashboard."""
    department = g.department
    fiscal_years = get_all_fiscal_years()

    fy_id = request.args.get("fy", type=int)
    if fy_id:
        fiscal_year = FiscalYear.query.get(fy_id)
    else:
        fiscal_year = get_or_create_fiscal_year(date.today())

    if not fiscal_year:
        fiscal_year = get_or_create_fiscal_year(date.today())

    summary = get_budget_summary(fiscal_year.id, department_id=department.id)
    totals = get_budget_totals(summary)

    recent_purchases = (
        Purchase.query
        .filter_by(fiscal_year_id=fiscal_year.id, department_id=department.id)
        .filter(Purchase.status != "rejected")
        .order_by(Purchase.created_at.desc())
        .limit(10)
        .all()
    )

    tax_reimbursement_purchases = (
        Purchase.query
        .filter_by(department_id=department.id, tax_exempt_status="reimbursement_required")
        .filter(Purchase.status != "rejected")
        .order_by(Purchase.created_at.desc())
        .all()
    )

    return render_template(
        "dashboard/index.html",
        fiscal_year=fiscal_year,
        fiscal_years=fiscal_years,
        summary=summary,
        totals=totals,
        recent_purchases=recent_purchases,
        tax_reimbursement_purchases=tax_reimbursement_purchases,
        department=department,
    )
