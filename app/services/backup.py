import json
from datetime import date, datetime
from decimal import Decimal

from app import db
from app.models.department import Department
from app.models.user import User
from app.models.fiscal_year import FiscalYear
from app.models.budget_line_item import BudgetLineItem
from app.models.budget_allocation import BudgetAllocation
from app.models.payment_method import PaymentMethod
from app.models.purchase import Purchase
from app.models.document import Document
from app.models.organization_settings import OrganizationSettings


class BackupEncoder(json.JSONEncoder):
    """Handle date, datetime, and Decimal serialization."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def export_backup():
    """Export all application data as a JSON-serializable dict."""

    org = OrganizationSettings.query.first()

    data = {
        "backup_version": 1,
        "exported_at": datetime.utcnow().isoformat(),
        "organization_settings": {
            "organization_name": org.organization_name if org else None,
        },
        "departments": [],
        "users": [],
        "fiscal_years": [],
        "budget_line_items": [],
        "budget_allocations": [],
        "payment_methods": [],
        "purchases": [],
        "documents": [],
    }

    # Departments
    for d in Department.query.order_by(Department.id).all():
        data["departments"].append({
            "id": d.id,
            "name": d.name,
            "slug": d.slug,
            "is_active": d.is_active,
        })

    # Users
    for u in User.query.order_by(User.id).all():
        data["users"].append({
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "auth_provider": u.auth_provider,
            "azure_oid": u.azure_oid,
            "is_active": u.is_active,
            "department_id": u.department_id,
        })

    # Fiscal years
    for fy in FiscalYear.query.order_by(FiscalYear.id).all():
        data["fiscal_years"].append({
            "id": fy.id,
            "label": fy.label,
            "start_date": fy.start_date,
            "end_date": fy.end_date,
            "is_active": fy.is_active,
        })

    # Budget line items
    for item in BudgetLineItem.query.order_by(BudgetLineItem.id).all():
        data["budget_line_items"].append({
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "is_custom": item.is_custom,
            "is_active": item.is_active,
            "department_id": item.department_id,
        })

    # Budget allocations
    for a in BudgetAllocation.query.order_by(BudgetAllocation.id).all():
        data["budget_allocations"].append({
            "id": a.id,
            "fiscal_year_id": a.fiscal_year_id,
            "budget_line_item_id": a.budget_line_item_id,
            "allocated_amount": a.allocated_amount,
        })

    # Payment methods
    for pm in PaymentMethod.query.order_by(PaymentMethod.id).all():
        data["payment_methods"].append({
            "id": pm.id,
            "department_id": pm.department_id,
            "name": pm.name,
            "is_active": pm.is_active,
            "sort_order": pm.sort_order,
        })

    # Purchases
    for p in Purchase.query.order_by(Purchase.id).all():
        data["purchases"].append({
            "id": p.id,
            "vendor_name": p.vendor_name,
            "purchase_date": p.purchase_date,
            "amount": p.amount,
            "description": p.description,
            "notes": p.notes,
            "po_number": p.po_number,
            "invoice_number": p.invoice_number,
            "payment_method": p.payment_method,
            "department_id": p.department_id,
            "budget_line_item_id": p.budget_line_item_id,
            "custom_account_code": p.custom_account_code,
            "custom_account_description": p.custom_account_description,
            "fiscal_year_id": p.fiscal_year_id,
            "submitted_by_user_id": p.submitted_by_user_id,
            "status": p.status,
            "review_notes": p.review_notes,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    # Documents (metadata only - actual files stay in storage)
    for doc in Document.query.order_by(Document.id).all():
        data["documents"].append({
            "id": doc.id,
            "purchase_id": doc.purchase_id,
            "original_filename": doc.original_filename,
            "stored_filename": doc.stored_filename,
            "content_type": doc.content_type,
            "file_size": doc.file_size,
            "storage_backend": doc.storage_backend,
            "bucket_name": doc.bucket_name,
            "object_key": doc.object_key,
            "uploaded_by_user_id": doc.uploaded_by_user_id,
            "created_at": doc.created_at,
        })

    return data


def import_backup(data):
    """Import data from a backup JSON dict. Returns a summary of what was imported.

    Uses an ID-mapping approach: records are inserted with new IDs and
    foreign key references are remapped accordingly.
    """
    if data.get("backup_version") != 1:
        raise ValueError("Unsupported backup version.")

    stats = {
        "departments": 0,
        "users": 0,
        "fiscal_years": 0,
        "budget_line_items": 0,
        "budget_allocations": 0,
        "payment_methods": 0,
        "purchases": 0,
        "documents": 0,
    }

    # ID mapping: old_id -> new_id for each entity type
    dept_map = {}
    user_map = {}
    fy_map = {}
    line_item_map = {}
    purchase_map = {}

    # Organization settings
    org_data = data.get("organization_settings", {})
    if org_data and org_data.get("organization_name"):
        org = OrganizationSettings.get()
        org.organization_name = org_data["organization_name"]
        db.session.flush()

    # Departments - match by slug
    for row in data.get("departments", []):
        old_id = row["id"]
        existing = Department.query.filter_by(slug=row["slug"]).first()
        if existing:
            existing.name = row["name"]
            existing.is_active = row.get("is_active", True)
            dept_map[old_id] = existing.id
        else:
            dept = Department(
                name=row["name"],
                slug=row["slug"],
                is_active=row.get("is_active", True),
            )
            db.session.add(dept)
            db.session.flush()
            dept_map[old_id] = dept.id
            stats["departments"] += 1

    # Users - match by email
    for row in data.get("users", []):
        old_id = row["id"]
        existing = User.query.filter_by(email=row["email"]).first()
        if existing:
            existing.display_name = row["display_name"]
            existing.role = row["role"]
            existing.is_active = row.get("is_active", True)
            existing.department_id = dept_map.get(row.get("department_id"))
            user_map[old_id] = existing.id
        else:
            user = User(
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                auth_provider=row.get("auth_provider", "azure_ad"),
                azure_oid=row.get("azure_oid"),
                is_active=row.get("is_active", True),
                department_id=dept_map.get(row.get("department_id")),
            )
            db.session.add(user)
            db.session.flush()
            user_map[old_id] = user.id
            stats["users"] += 1

    # Fiscal years - match by label
    for row in data.get("fiscal_years", []):
        old_id = row["id"]
        existing = FiscalYear.query.filter_by(label=row["label"]).first()
        if existing:
            existing.start_date = _parse_date(row["start_date"])
            existing.end_date = _parse_date(row["end_date"])
            existing.is_active = row.get("is_active", True)
            fy_map[old_id] = existing.id
        else:
            fy = FiscalYear(
                label=row["label"],
                start_date=_parse_date(row["start_date"]),
                end_date=_parse_date(row["end_date"]),
                is_active=row.get("is_active", True),
            )
            db.session.add(fy)
            db.session.flush()
            fy_map[old_id] = fy.id
            stats["fiscal_years"] += 1

    # Budget line items - match by (department, code)
    for row in data.get("budget_line_items", []):
        old_id = row["id"]
        new_dept_id = dept_map.get(row["department_id"])
        if not new_dept_id:
            continue
        existing = BudgetLineItem.query.filter_by(
            department_id=new_dept_id, code=row["code"]
        ).first()
        if existing:
            existing.name = row["name"]
            existing.is_custom = row.get("is_custom", False)
            existing.is_active = row.get("is_active", True)
            line_item_map[old_id] = existing.id
        else:
            item = BudgetLineItem(
                code=row["code"],
                name=row["name"],
                is_custom=row.get("is_custom", False),
                is_active=row.get("is_active", True),
                department_id=new_dept_id,
            )
            db.session.add(item)
            db.session.flush()
            line_item_map[old_id] = item.id
            stats["budget_line_items"] += 1

    # Budget allocations - match by (fiscal_year, line_item)
    for row in data.get("budget_allocations", []):
        new_fy_id = fy_map.get(row["fiscal_year_id"])
        new_li_id = line_item_map.get(row["budget_line_item_id"])
        if not new_fy_id or not new_li_id:
            continue
        existing = BudgetAllocation.query.filter_by(
            fiscal_year_id=new_fy_id, budget_line_item_id=new_li_id
        ).first()
        if existing:
            existing.allocated_amount = Decimal(str(row["allocated_amount"]))
        else:
            alloc = BudgetAllocation(
                fiscal_year_id=new_fy_id,
                budget_line_item_id=new_li_id,
                allocated_amount=Decimal(str(row["allocated_amount"])),
            )
            db.session.add(alloc)
            db.session.flush()
            stats["budget_allocations"] += 1

    # Payment methods - match by (department, name)
    for row in data.get("payment_methods", []):
        new_dept_id = dept_map.get(row["department_id"])
        if not new_dept_id:
            continue
        existing = PaymentMethod.query.filter_by(
            department_id=new_dept_id, name=row["name"]
        ).first()
        if existing:
            existing.is_active = row.get("is_active", True)
            existing.sort_order = row.get("sort_order", 0)
        else:
            pm = PaymentMethod(
                department_id=new_dept_id,
                name=row["name"],
                is_active=row.get("is_active", True),
                sort_order=row.get("sort_order", 0),
            )
            db.session.add(pm)
            db.session.flush()
            stats["payment_methods"] += 1

    # Purchases - matched by (vendor_name, purchase_date, amount, department, fiscal_year)
    for row in data.get("purchases", []):
        new_dept_id = dept_map.get(row["department_id"])
        new_fy_id = fy_map.get(row["fiscal_year_id"])
        new_li_id = line_item_map.get(row["budget_line_item_id"])
        new_user_id = user_map.get(row["submitted_by_user_id"])
        if not all([new_dept_id, new_fy_id, new_li_id, new_user_id]):
            continue

        purchase_date = _parse_date(row["purchase_date"])
        amount = Decimal(str(row["amount"]))

        existing = Purchase.query.filter_by(
            vendor_name=row["vendor_name"],
            purchase_date=purchase_date,
            amount=amount,
            department_id=new_dept_id,
            fiscal_year_id=new_fy_id,
        ).first()

        old_id = row["id"]
        if existing:
            purchase_map[old_id] = existing.id
        else:
            p = Purchase(
                vendor_name=row["vendor_name"],
                purchase_date=purchase_date,
                amount=amount,
                description=row.get("description"),
                notes=row.get("notes"),
                po_number=row.get("po_number"),
                invoice_number=row.get("invoice_number"),
                payment_method=row.get("payment_method"),
                department_id=new_dept_id,
                budget_line_item_id=new_li_id,
                custom_account_code=row.get("custom_account_code"),
                custom_account_description=row.get("custom_account_description"),
                fiscal_year_id=new_fy_id,
                submitted_by_user_id=new_user_id,
                status=row.get("status", "submitted"),
                review_notes=row.get("review_notes"),
            )
            db.session.add(p)
            db.session.flush()
            purchase_map[old_id] = p.id
            stats["purchases"] += 1

    # Documents (metadata only) - match by (purchase, object_key)
    for row in data.get("documents", []):
        new_purchase_id = purchase_map.get(row["purchase_id"])
        new_user_id = user_map.get(row["uploaded_by_user_id"])
        if not new_purchase_id or not new_user_id:
            continue

        existing = Document.query.filter_by(
            purchase_id=new_purchase_id, object_key=row.get("object_key")
        ).first()
        if not existing:
            doc = Document(
                purchase_id=new_purchase_id,
                original_filename=row["original_filename"],
                stored_filename=row["stored_filename"],
                content_type=row["content_type"],
                file_size=row["file_size"],
                storage_backend=row.get("storage_backend", "local"),
                bucket_name=row.get("bucket_name"),
                object_key=row.get("object_key"),
                uploaded_by_user_id=new_user_id,
            )
            db.session.add(doc)
            db.session.flush()
            stats["documents"] += 1

    db.session.commit()
    return stats


def _parse_date(value):
    """Parse a date string or return as-is if already a date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value
