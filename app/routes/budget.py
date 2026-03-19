import io
import csv
from datetime import date

from flask import Blueprint, render_template, request, Response, g
from flask_login import login_required

from app.models.fiscal_year import FiscalYear
from app.models.budget_amendment import BudgetAmendment
from app.models.budget_allocation import BudgetAllocation
from app.models.budget_line_item import BudgetLineItem
from app.services.budget import get_budget_summary, get_budget_totals
from app.services.fiscal_year import get_or_create_fiscal_year, get_all_fiscal_years
from app.utils.decorators import dept_admin_required, department_access_required

budget_bp = Blueprint("budget", __name__, template_folder="../templates/budget")


@budget_bp.route("/dept/<int:dept_id>/")
@login_required
@department_access_required
@dept_admin_required
def index(dept_id):
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

    amendments = (
        BudgetAmendment.query
        .join(BudgetAllocation)
        .join(BudgetLineItem)
        .filter(
            BudgetAllocation.fiscal_year_id == fiscal_year.id,
            BudgetLineItem.department_id == department.id,
        )
        .order_by(BudgetAmendment.created_at.desc())
        .all()
    )

    return render_template(
        "budget/index.html",
        fiscal_year=fiscal_year,
        fiscal_years=fiscal_years,
        summary=summary,
        totals=totals,
        department=department,
        amendments=amendments,
    )


@budget_bp.route("/dept/<int:dept_id>/export")
@login_required
@department_access_required
@dept_admin_required
def export_csv(dept_id):
    department = g.department
    fy_id = request.args.get("fy", type=int)
    if fy_id:
        fiscal_year = FiscalYear.query.get_or_404(fy_id)
    else:
        fiscal_year = get_or_create_fiscal_year(date.today())

    summary = get_budget_summary(fiscal_year.id, department_id=department.id)
    totals = get_budget_totals(summary)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Line Item Code", "Line Item Name", "Allocated", "Approved Spent",
        "Pending", "Remaining", "% Used", "Purchase Count",
    ])

    for s in summary:
        writer.writerow([
            s["line_item"].code,
            s["line_item"].name,
            str(s["allocated"]),
            str(s["spent"]),
            str(s["pending"]),
            str(s["remaining"]),
            str(s["pct_used"]),
            s["purchase_count"],
        ])

    writer.writerow([])
    writer.writerow([
        "TOTALS", "",
        str(totals["total_allocated"]),
        str(totals["total_spent"]),
        str(totals["total_pending"]),
        str(totals["total_remaining"]),
        str(totals["pct_used"]),
        "",
    ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=budget_{department.slug}_{fiscal_year.label}.csv"
        },
    )
