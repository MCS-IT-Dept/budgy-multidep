import click
from datetime import date
from flask.cli import AppGroup

from app import db
from app.models.department import Department
from app.models.payment_method import PaymentMethod
from app.models.budget_line_item import BudgetLineItem
from app.models.fiscal_year import FiscalYear
from app.models.budget_allocation import BudgetAllocation
from app.services.fiscal_year import compute_fiscal_year_for_date


seed_cli = AppGroup("seed")

DEFAULT_LINE_ITEMS = [
    ("72250 336", "Maintenance and Repair"),
    ("72250 470", "Cabling"),
    ("72250 471", "Software"),
    ("72250 499", "Other Supplies"),
    ("72250 524", "Staff Development"),
    ("72250 599", "Other Charges"),
    ("72250 790", "Equipment"),
    ("Telecom", "Telecom"),
    ("Other", "Other"),
]

DEFAULT_PAYMENT_METHODS = [
    "Credit Card - Andy",
    "Credit Card - James",
    "Credit Card - Brady",
    "Credit Card - Danielle",
    "Amazon",
    "Purchase Order",
    "Other",
]


@seed_cli.command("run")
def seed_run():
    """Seed the database with default data."""
    dept = _seed_default_department()
    _seed_line_items(dept)
    _seed_payment_methods(dept)
    _seed_fiscal_year(dept)
    click.echo("Seed complete.")


def _seed_default_department():
    dept = Department.query.filter_by(slug="default").first()
    if not dept:
        dept = Department(name="Default", slug="default")
        db.session.add(dept)
        db.session.commit()
        click.echo(f"  Created department: {dept.name}")
    else:
        click.echo(f"  Department '{dept.name}' already exists.")
    return dept


def _seed_line_items(department):
    for code, name in DEFAULT_LINE_ITEMS:
        existing = BudgetLineItem.query.filter_by(
            code=code, department_id=department.id
        ).first()
        if not existing:
            is_custom = code == "Other"
            item = BudgetLineItem(
                code=code,
                name=name,
                is_custom=is_custom,
                department_id=department.id,
            )
            db.session.add(item)
            click.echo(f"  Created line item: {code} - {name}")
    db.session.commit()


def _seed_payment_methods(department):
    for i, name in enumerate(DEFAULT_PAYMENT_METHODS):
        existing = PaymentMethod.query.filter_by(
            name=name, department_id=department.id
        ).first()
        if not existing:
            pm = PaymentMethod(
                department_id=department.id,
                name=name,
                sort_order=i,
            )
            db.session.add(pm)
            click.echo(f"  Created payment method: {name}")
    db.session.commit()


def _seed_fiscal_year(department):
    today = date.today()
    label = compute_fiscal_year_for_date(today)
    existing = FiscalYear.query.filter_by(label=label).first()
    if not existing:
        if today.month >= 7:
            start = date(today.year, 7, 1)
            end = date(today.year + 1, 6, 30)
        else:
            start = date(today.year - 1, 7, 1)
            end = date(today.year, 6, 30)
        fy = FiscalYear(label=label, start_date=start, end_date=end)
        db.session.add(fy)
        db.session.commit()
        click.echo(f"  Created fiscal year: {label}")

        # Create zero-amount allocations for this department's line items
        items = BudgetLineItem.query.filter_by(department_id=department.id).all()
        for item in items:
            alloc = BudgetAllocation(
                fiscal_year_id=fy.id,
                budget_line_item_id=item.id,
                allocated_amount=0,
            )
            db.session.add(alloc)
        db.session.commit()
        click.echo(f"  Created {len(items)} budget allocations for {label}")
    else:
        click.echo(f"  Fiscal year {label} already exists.")


def register_cli(app):
    app.cli.add_command(seed_cli)
