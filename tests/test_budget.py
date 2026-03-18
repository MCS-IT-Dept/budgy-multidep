from datetime import date
from decimal import Decimal
from app.models.budget_allocation import BudgetAllocation
from app.models.purchase import Purchase
from app.services.budget import get_budget_summary, get_budget_totals


class TestBudgetCalculations:
    def test_remaining_balance(self, app, db, default_department, sample_line_items, sample_fiscal_year, admin_user):
        with app.app_context():
            li = sample_line_items[0]  # 72250 336

            # Allocate 10000
            alloc = BudgetAllocation(
                fiscal_year_id=sample_fiscal_year.id,
                budget_line_item_id=li.id,
                allocated_amount=Decimal("10000.00"),
            )
            db.session.add(alloc)

            # Add approved purchase of 3000
            p1 = Purchase(
                vendor_name="Vendor A",
                purchase_date=date(2025, 9, 1),
                amount=Decimal("3000.00"),
                budget_line_item_id=li.id,
                fiscal_year_id=sample_fiscal_year.id,
                submitted_by_user_id=admin_user.id,
                department_id=default_department.id,
                status="approved",
            )
            db.session.add(p1)

            # Add submitted (pending) purchase of 2000
            p2 = Purchase(
                vendor_name="Vendor B",
                purchase_date=date(2025, 10, 1),
                amount=Decimal("2000.00"),
                budget_line_item_id=li.id,
                fiscal_year_id=sample_fiscal_year.id,
                submitted_by_user_id=admin_user.id,
                department_id=default_department.id,
                status="submitted",
            )
            db.session.add(p2)
            db.session.commit()

            summary = get_budget_summary(sample_fiscal_year.id, department_id=default_department.id)
            assert len(summary) == 1
            s = summary[0]
            assert s["allocated"] == Decimal("10000.00")
            assert s["spent"] == Decimal("3000.00")
            assert s["pending"] == Decimal("2000.00")
            assert s["remaining"] == Decimal("7000.00")
            assert s["purchase_count"] == 2  # non-rejected

    def test_rejected_not_counted_in_spend(self, app, db, default_department, sample_line_items, sample_fiscal_year, admin_user):
        with app.app_context():
            li = sample_line_items[0]

            alloc = BudgetAllocation(
                fiscal_year_id=sample_fiscal_year.id,
                budget_line_item_id=li.id,
                allocated_amount=Decimal("5000.00"),
            )
            db.session.add(alloc)

            p = Purchase(
                vendor_name="Vendor C",
                purchase_date=date(2025, 8, 1),
                amount=Decimal("1500.00"),
                budget_line_item_id=li.id,
                fiscal_year_id=sample_fiscal_year.id,
                submitted_by_user_id=admin_user.id,
                department_id=default_department.id,
                status="rejected",
            )
            db.session.add(p)
            db.session.commit()

            summary = get_budget_summary(sample_fiscal_year.id, department_id=default_department.id)
            s = summary[0]
            assert s["spent"] == Decimal("0")
            assert s["pending"] == Decimal("0")
            assert s["remaining"] == Decimal("5000.00")
            assert s["purchase_count"] == 0  # rejected excluded

    def test_totals(self, app, db, default_department, sample_line_items, sample_fiscal_year, admin_user):
        with app.app_context():
            for i, li in enumerate(sample_line_items):
                alloc = BudgetAllocation(
                    fiscal_year_id=sample_fiscal_year.id,
                    budget_line_item_id=li.id,
                    allocated_amount=Decimal("1000.00"),
                )
                db.session.add(alloc)
            db.session.commit()

            summary = get_budget_summary(sample_fiscal_year.id, department_id=default_department.id)
            totals = get_budget_totals(summary)
            assert totals["total_allocated"] == Decimal("3000.00")
            assert totals["total_spent"] == Decimal("0")
            assert totals["total_remaining"] == Decimal("3000.00")
