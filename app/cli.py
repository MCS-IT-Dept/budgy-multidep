import click
import json
import os
from datetime import date, datetime
from flask import current_app
from flask.cli import AppGroup

from app import db
from app.models.department import Department
from app.models.payment_method import PaymentMethod
from app.models.budget_line_item import BudgetLineItem
from app.models.fiscal_year import FiscalYear
from app.models.budget_allocation import BudgetAllocation
from app.services.fiscal_year import compute_fiscal_year_for_date


seed_cli = AppGroup("seed")
backup_cli = AppGroup("backup")

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


@backup_cli.command("run")
@click.option("--keep", default=30, help="Number of recent backups to keep (0 = keep all).")
def backup_run(keep):
    """Export a JSON backup and upload it to R2 (or save locally)."""
    from app.services.backup import export_backup, BackupEncoder

    data = export_backup()
    json_bytes = json.dumps(data, cls=BackupEncoder, indent=2).encode("utf-8")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"budgy_backup_{timestamp}.json"
    object_key = f"backups/{filename}"

    r2_endpoint = current_app.config.get("R2_ENDPOINT_URL")
    r2_bucket = current_app.config.get("R2_BUCKET_NAME")
    r2_key = current_app.config.get("R2_ACCESS_KEY_ID")
    r2_secret = current_app.config.get("R2_SECRET_ACCESS_KEY")

    if r2_endpoint and r2_bucket and r2_key and r2_secret:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=r2_endpoint,
            aws_access_key_id=r2_key,
            aws_secret_access_key=r2_secret,
            region_name="auto",
        )
        client.put_object(
            Bucket=r2_bucket,
            Key=object_key,
            Body=json_bytes,
            ContentType="application/json",
        )
        click.echo(f"Backup uploaded to R2: {r2_bucket}/{object_key} ({len(json_bytes)} bytes)")

        # Prune old backups
        if keep > 0:
            _prune_r2_backups(client, r2_bucket, keep)
    else:
        # Fallback: save locally
        backup_dir = os.path.join(current_app.config.get("LOCAL_UPLOAD_PATH", "uploads"), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        filepath = os.path.join(backup_dir, filename)
        with open(filepath, "wb") as f:
            f.write(json_bytes)
        click.echo(f"Backup saved locally: {filepath} ({len(json_bytes)} bytes)")

        # Prune old local backups
        if keep > 0:
            _prune_local_backups(backup_dir, keep)


@backup_cli.command("prune")
@click.option("--keep", default=30, help="Number of recent backups to keep.")
def backup_prune(keep):
    """Remove old backups, keeping only the N most recent."""
    r2_endpoint = current_app.config.get("R2_ENDPOINT_URL")
    r2_bucket = current_app.config.get("R2_BUCKET_NAME")
    r2_key = current_app.config.get("R2_ACCESS_KEY_ID")
    r2_secret = current_app.config.get("R2_SECRET_ACCESS_KEY")

    if r2_endpoint and r2_bucket and r2_key and r2_secret:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=r2_endpoint,
            aws_access_key_id=r2_key,
            aws_secret_access_key=r2_secret,
            region_name="auto",
        )
        _prune_r2_backups(client, r2_bucket, keep)
    else:
        backup_dir = os.path.join(current_app.config.get("LOCAL_UPLOAD_PATH", "uploads"), "backups")
        if os.path.isdir(backup_dir):
            _prune_local_backups(backup_dir, keep)
        else:
            click.echo("No backup directory found.")


def _prune_r2_backups(client, bucket, keep):
    """List backups/ prefix in R2 and delete all but the most recent `keep`."""
    response = client.list_objects_v2(Bucket=bucket, Prefix="backups/budgy_backup_")
    objects = response.get("Contents", [])
    # Sort by key (timestamp in filename ensures chronological order)
    objects.sort(key=lambda o: o["Key"])

    to_delete = objects[:-keep] if len(objects) > keep else []
    for obj in to_delete:
        client.delete_object(Bucket=bucket, Key=obj["Key"])
        click.echo(f"  Pruned: {obj['Key']}")

    if to_delete:
        click.echo(f"Pruned {len(to_delete)} old backup(s), kept {keep}.")
    else:
        click.echo(f"Nothing to prune ({len(objects)} backup(s), keep={keep}).")


def _prune_local_backups(backup_dir, keep):
    """Delete all but the most recent `keep` local backup files."""
    files = sorted(
        f for f in os.listdir(backup_dir)
        if f.startswith("budgy_backup_") and f.endswith(".json")
    )
    to_delete = files[:-keep] if len(files) > keep else []
    for f in to_delete:
        os.remove(os.path.join(backup_dir, f))
        click.echo(f"  Pruned: {f}")

    if to_delete:
        click.echo(f"Pruned {len(to_delete)} old backup(s), kept {keep}.")
    else:
        click.echo(f"Nothing to prune ({len(files)} backup(s), keep={keep}).")


def register_cli(app):
    app.cli.add_command(seed_cli)
    app.cli.add_command(backup_cli)
