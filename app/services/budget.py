from decimal import Decimal
from sqlalchemy import func
from app import db
from app.models.budget_allocation import BudgetAllocation
from app.models.budget_line_item import BudgetLineItem
from app.models.purchase import Purchase
from app.models.fiscal_year import FiscalYear


def get_budget_summary(fiscal_year_id: int, department_id: int = None) -> list[dict]:
    """Get budget summary for a fiscal year, optionally filtered by department.

    Returns a list of dicts with line item info, allocated amount,
    approved spend, pending spend, remaining, and percentage used.
    """
    alloc_query = (
        db.session.query(BudgetAllocation, BudgetLineItem)
        .join(BudgetLineItem, BudgetAllocation.budget_line_item_id == BudgetLineItem.id)
        .filter(BudgetAllocation.fiscal_year_id == fiscal_year_id)
    )
    if department_id is not None:
        alloc_query = alloc_query.filter(BudgetLineItem.department_id == department_id)

    allocations = alloc_query.order_by(BudgetLineItem.code).all()

    # Get approved spend per line item
    approved_query = (
        db.session.query(
            Purchase.budget_line_item_id,
            func.coalesce(func.sum(Purchase.amount), Decimal("0")),
        )
        .filter(
            Purchase.fiscal_year_id == fiscal_year_id,
            Purchase.status == "approved",
        )
    )
    if department_id is not None:
        approved_query = approved_query.filter(Purchase.department_id == department_id)
    approved_spend = dict(approved_query.group_by(Purchase.budget_line_item_id).all())

    # Get pending (submitted + reviewed) spend per line item
    pending_query = (
        db.session.query(
            Purchase.budget_line_item_id,
            func.coalesce(func.sum(Purchase.amount), Decimal("0")),
        )
        .filter(
            Purchase.fiscal_year_id == fiscal_year_id,
            Purchase.status.in_(["submitted", "reviewed"]),
        )
    )
    if department_id is not None:
        pending_query = pending_query.filter(Purchase.department_id == department_id)
    pending_spend = dict(pending_query.group_by(Purchase.budget_line_item_id).all())

    # Purchase count per line item
    count_query = (
        db.session.query(
            Purchase.budget_line_item_id,
            func.count(Purchase.id),
        )
        .filter(
            Purchase.fiscal_year_id == fiscal_year_id,
            Purchase.status != "rejected",
        )
    )
    if department_id is not None:
        count_query = count_query.filter(Purchase.department_id == department_id)
    purchase_counts = dict(count_query.group_by(Purchase.budget_line_item_id).all())

    results = []
    for alloc, item in allocations:
        allocated = Decimal(str(alloc.allocated_amount))
        spent = Decimal(str(approved_spend.get(item.id, Decimal("0"))))
        pending = Decimal(str(pending_spend.get(item.id, Decimal("0"))))
        remaining = allocated - spent
        pct_used = (
            round((spent / allocated) * 100, 1) if allocated > 0 else Decimal("0")
        )
        results.append(
            {
                "line_item": item,
                "allocation": alloc,
                "allocated": allocated,
                "spent": spent,
                "pending": pending,
                "remaining": remaining,
                "pct_used": pct_used,
                "purchase_count": purchase_counts.get(item.id, 0),
            }
        )

    return results


def get_budget_totals(summary: list[dict]) -> dict:
    """Calculate totals across all line items."""
    total_allocated = sum(s["allocated"] for s in summary)
    total_spent = sum(s["spent"] for s in summary)
    total_pending = sum(s["pending"] for s in summary)
    total_remaining = total_allocated - total_spent
    pct_used = (
        round((total_spent / total_allocated) * 100, 1)
        if total_allocated > 0
        else Decimal("0")
    )
    return {
        "total_allocated": total_allocated,
        "total_spent": total_spent,
        "total_pending": total_pending,
        "total_remaining": total_remaining,
        "pct_used": pct_used,
    }


def get_cross_department_summary(fiscal_year_id: int) -> list[dict]:
    """Get a per-department budget roll-up for the global admin overview."""
    from app.models.department import Department

    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    results = []
    for dept in departments:
        summary = get_budget_summary(fiscal_year_id, department_id=dept.id)
        totals = get_budget_totals(summary)
        results.append({
            "department": dept,
            "totals": totals,
        })
    return results
