import csv
import io
import json
from datetime import date, datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    g,
    current_app,
    Response,
)
from flask_login import login_required, current_user

from app import db
from app.models.user import User
from app.models.department import Department
from app.models.payment_method import PaymentMethod
from app.models.budget_line_item import BudgetLineItem
from app.models.budget_allocation import BudgetAllocation
from app.models.fiscal_year import FiscalYear
from app.models.purchase import Purchase
from app.models.document import Document
from app.models.activity_log import ActivityLog
from app.models.organization_settings import OrganizationSettings
from app.models.approval_threshold import ApprovalThreshold
from app.services.activity import log_activity
from app.services.storage import get_storage_backend
from app.services.department import get_all_departments
from app.utils.decorators import global_admin_required, dept_admin_required, department_access_required
from app.utils.forms import (
    BudgetAllocationForm,
    FiscalYearForm,
    BudgetLineItemForm,
    UserEditForm,
    PurchaseStatusForm,
    DepartmentForm,
    PaymentMethodForm,
    ApprovalThresholdForm,
    BrandingForm,
)

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


# ══════════════════════════════════════════════════════════════
# GLOBAL ADMIN routes (require global_admin role)
# ══════════════════════════════════════════════════════════════

@admin_bp.route("/")
@login_required
@global_admin_required
def index():
    user_count = User.query.count()
    purchase_count = Purchase.query.count()
    dept_count = Department.query.count()
    fy_count = FiscalYear.query.count()
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    return render_template(
        "admin/index.html",
        user_count=user_count,
        purchase_count=purchase_count,
        dept_count=dept_count,
        fy_count=fy_count,
        recent_logs=recent_logs,
    )


# ── Departments ───────────────────────────────────────────────
@admin_bp.route("/departments")
@login_required
@global_admin_required
def departments():
    depts = Department.query.order_by(Department.name).all()
    return render_template("admin/departments.html", departments=depts)


@admin_bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@global_admin_required
def department_create():
    form = DepartmentForm()
    if form.validate_on_submit():
        dept = Department(name=form.name.data, slug=form.slug.data)
        db.session.add(dept)
        db.session.commit()
        log_activity(current_user.id, "department_created", "department", dept.id)
        flash("Department created.", "success")
        return redirect(url_for("admin.departments"))
    return render_template("admin/department_form.html", form=form, edit=False)


@admin_bp.route("/departments/<int:id>/edit", methods=["GET", "POST"])
@login_required
@global_admin_required
def department_edit(id):
    dept = Department.query.get_or_404(id)
    form = DepartmentForm(obj=dept)
    if form.validate_on_submit():
        dept.name = form.name.data
        dept.slug = form.slug.data
        db.session.commit()
        log_activity(current_user.id, "department_updated", "department", dept.id)
        flash("Department updated.", "success")
        return redirect(url_for("admin.departments"))
    return render_template("admin/department_form.html", form=form, edit=True, dept=dept)


# ── Users (global admin only) ────────────────────────────────
@admin_bp.route("/users")
@login_required
@global_admin_required
def users():
    all_users = User.query.order_by(User.display_name).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/<int:id>/edit", methods=["GET", "POST"])
@login_required
@global_admin_required
def user_edit(id):
    user = User.query.get_or_404(id)
    form = UserEditForm(obj=user)

    # Populate department choices
    depts = get_all_departments()
    form.department_id.choices = [(0, "— None (Global Admin) —")] + [
        (d.id, d.name) for d in depts
    ]

    if request.method == "GET":
        form.is_active.data = "1" if user.is_active else "0"
        form.department_id.data = user.department_id or 0

    if form.validate_on_submit():
        user.display_name = form.display_name.data
        user.role = form.role.data
        user.is_active = form.is_active.data == "1"
        dept_val = form.department_id.data
        user.department_id = dept_val if dept_val and dept_val != 0 else None
        db.session.commit()
        log_activity(current_user.id, "user_updated", "user", user.id)
        flash(f"User {user.email} updated.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit.html", form=form, user=user)


# ── Fiscal Years (global, shared across departments) ─────────
@admin_bp.route("/fiscal-years")
@login_required
@global_admin_required
def fiscal_years():
    fys = FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    return render_template("admin/fiscal_years.html", fiscal_years=fys)


@admin_bp.route("/fiscal-years/new", methods=["GET", "POST"])
@login_required
@global_admin_required
def fiscal_year_create():
    form = FiscalYearForm()
    if form.validate_on_submit():
        fy = FiscalYear(
            label=form.label.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
        )
        db.session.add(fy)
        db.session.commit()
        log_activity(current_user.id, "fiscal_year_created", "fiscal_year", fy.id)
        flash("Fiscal year created.", "success")
        return redirect(url_for("admin.fiscal_years"))
    return render_template("admin/fiscal_year_form.html", form=form, edit=False)


@admin_bp.route("/fiscal-years/<int:id>/edit", methods=["GET", "POST"])
@login_required
@global_admin_required
def fiscal_year_edit(id):
    fy = FiscalYear.query.get_or_404(id)
    form = FiscalYearForm(obj=fy)
    if form.validate_on_submit():
        fy.label = form.label.data
        fy.start_date = form.start_date.data
        fy.end_date = form.end_date.data
        db.session.commit()
        log_activity(current_user.id, "fiscal_year_updated", "fiscal_year", fy.id)
        flash("Fiscal year updated.", "success")
        return redirect(url_for("admin.fiscal_years"))
    return render_template("admin/fiscal_year_form.html", form=form, edit=True, fy=fy)


# ── Activity Log (global admin) ──────────────────────────────
@admin_bp.route("/activity")
@login_required
@global_admin_required
def activity():
    page = request.args.get("page", 1, type=int)
    pagination = ActivityLog.query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("admin/activity.html", logs=pagination.items, pagination=pagination)


# ── Branding (global admin) ───────────────────────────────────
@admin_bp.route("/branding", methods=["GET", "POST"])
@login_required
@global_admin_required
def branding():
    settings = OrganizationSettings.get()
    form = BrandingForm(obj=settings)

    if form.validate_on_submit():
        settings.organization_name = form.organization_name.data or None

        logo_file = form.logo.data
        if logo_file and hasattr(logo_file, "filename") and logo_file.filename:
            from werkzeug.utils import secure_filename
            import uuid

            filename = secure_filename(logo_file.filename)
            unique_id = uuid.uuid4().hex[:12]
            object_key = f"branding/{unique_id}_{filename}"

            # Delete old logo if exists
            if settings.logo_object_key:
                storage = get_storage_backend()
                try:
                    storage.delete(settings.logo_object_key)
                except Exception:
                    pass

            storage = get_storage_backend()
            storage.save(logo_file, object_key, logo_file.content_type or "image/png")

            settings.logo_filename = filename
            settings.logo_object_key = object_key
            settings.logo_content_type = logo_file.content_type or "image/png"
            settings.logo_storage_backend = current_app.config["STORAGE_BACKEND"]

        db.session.commit()
        log_activity(current_user.id, "branding_updated", "organization_settings", settings.id)
        flash("Branding settings updated.", "success")
        return redirect(url_for("admin.branding"))

    return render_template("admin/branding.html", form=form, settings=settings)


@admin_bp.route("/branding/remove-logo", methods=["POST"])
@login_required
@global_admin_required
def branding_remove_logo():
    settings = OrganizationSettings.get()
    if settings.logo_object_key:
        storage = get_storage_backend()
        try:
            storage.delete(settings.logo_object_key)
        except Exception:
            pass
        settings.logo_filename = None
        settings.logo_object_key = None
        settings.logo_content_type = None
        settings.logo_storage_backend = None
        db.session.commit()
        log_activity(current_user.id, "branding_logo_removed", "organization_settings", settings.id)
        flash("Logo removed.", "success")
    return redirect(url_for("admin.branding"))


# ── Backup & Restore (global admin) ──────────────────────────
@admin_bp.route("/backup")
@login_required
@global_admin_required
def backup():
    return render_template("admin/backup.html")


@admin_bp.route("/backup/export")
@login_required
@global_admin_required
def backup_export():
    from app.services.backup import export_backup, BackupEncoder

    data = export_backup()
    json_str = json.dumps(data, cls=BackupEncoder, indent=2)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"budgy_backup_{timestamp}.json"

    log_activity(current_user.id, "backup_exported", "system", None)

    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route("/backup/import", methods=["POST"])
@login_required
@global_admin_required
def backup_import():
    from app.services.backup import import_backup

    file = request.files.get("backup_file")
    if not file or not file.filename:
        flash("Please select a backup JSON file.", "danger")
        return redirect(url_for("admin.backup"))

    if not file.filename.endswith(".json"):
        flash("Only JSON files are accepted.", "danger")
        return redirect(url_for("admin.backup"))

    try:
        raw = file.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        flash("Invalid JSON file.", "danger")
        return redirect(url_for("admin.backup"))

    try:
        stats = import_backup(data)
    except ValueError as e:
        flash(f"Import error: {e}", "danger")
        return redirect(url_for("admin.backup"))
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {e}", "danger")
        return redirect(url_for("admin.backup"))

    log_activity(current_user.id, "backup_imported", "system", None,
                 details=json.dumps(stats))

    parts = []
    for key, count in stats.items():
        if count > 0:
            parts.append(f"{count} {key}")
    summary = ", ".join(parts) if parts else "no new records"
    flash(f"Import complete: {summary}.", "success")
    return redirect(url_for("admin.backup"))


# ══════════════════════════════════════════════════════════════
# DEPARTMENT-SCOPED ADMIN routes (dept_admin or global_admin)
# ══════════════════════════════════════════════════════════════

# ── Payment Methods ───────────────────────────────────────────
@admin_bp.route("/dept/<int:dept_id>/payment-methods")
@login_required
@department_access_required
@dept_admin_required
def payment_methods(dept_id):
    department = g.department
    methods = (
        PaymentMethod.query
        .filter_by(department_id=department.id)
        .order_by(PaymentMethod.sort_order, PaymentMethod.name)
        .all()
    )
    return render_template("admin/payment_methods.html", methods=methods, department=department)


@admin_bp.route("/dept/<int:dept_id>/payment-methods/new", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def payment_method_create(dept_id):
    department = g.department
    form = PaymentMethodForm()
    if form.validate_on_submit():
        pm = PaymentMethod(
            department_id=department.id,
            name=form.name.data,
            sort_order=form.sort_order.data or 0,
        )
        db.session.add(pm)
        db.session.commit()
        log_activity(
            current_user.id, "payment_method_created", "payment_method", pm.id,
            department_id=department.id,
        )
        flash("Payment method created.", "success")
        return redirect(url_for("admin.payment_methods", dept_id=department.id))
    return render_template("admin/payment_method_form.html", form=form, edit=False, department=department)


@admin_bp.route("/dept/<int:dept_id>/payment-methods/<int:id>/edit", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def payment_method_edit(dept_id, id):
    department = g.department
    pm = PaymentMethod.query.get_or_404(id)
    if pm.department_id != department.id:
        abort(404)

    form = PaymentMethodForm(obj=pm)
    if form.validate_on_submit():
        pm.name = form.name.data
        pm.sort_order = form.sort_order.data or 0
        db.session.commit()
        log_activity(
            current_user.id, "payment_method_updated", "payment_method", pm.id,
            department_id=department.id,
        )
        flash("Payment method updated.", "success")
        return redirect(url_for("admin.payment_methods", dept_id=department.id))
    return render_template("admin/payment_method_form.html", form=form, edit=True, pm=pm, department=department)


# ── Budget Line Items (department-scoped) ─────────────────────
@admin_bp.route("/dept/<int:dept_id>/line-items")
@login_required
@department_access_required
@dept_admin_required
def line_items(dept_id):
    department = g.department
    items = (
        BudgetLineItem.query
        .filter_by(department_id=department.id)
        .order_by(BudgetLineItem.code)
        .all()
    )
    return render_template("admin/line_items.html", items=items, department=department)


@admin_bp.route("/dept/<int:dept_id>/line-items/new", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def line_item_create(dept_id):
    department = g.department
    form = BudgetLineItemForm()
    if form.validate_on_submit():
        item = BudgetLineItem(
            code=form.code.data,
            name=form.name.data,
            department_id=department.id,
        )
        db.session.add(item)
        db.session.commit()
        log_activity(
            current_user.id, "line_item_created", "budget_line_item", item.id,
            department_id=department.id,
        )
        flash("Line item created.", "success")
        return redirect(url_for("admin.line_items", dept_id=department.id))
    return render_template("admin/line_item_form.html", form=form, edit=False, department=department)


@admin_bp.route("/dept/<int:dept_id>/line-items/<int:id>/edit", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def line_item_edit(dept_id, id):
    department = g.department
    item = BudgetLineItem.query.get_or_404(id)
    if item.department_id != department.id:
        abort(404)

    form = BudgetLineItemForm(obj=item)
    if form.validate_on_submit():
        item.code = form.code.data
        item.name = form.name.data
        db.session.commit()
        log_activity(
            current_user.id, "line_item_updated", "budget_line_item", item.id,
            department_id=department.id,
        )
        flash("Line item updated.", "success")
        return redirect(url_for("admin.line_items", dept_id=department.id))
    return render_template("admin/line_item_form.html", form=form, edit=True, item=item, department=department)


# ── Budget Allocations (department-scoped) ────────────────────
@admin_bp.route("/dept/<int:dept_id>/allocations")
@login_required
@department_access_required
@dept_admin_required
def allocations(dept_id):
    department = g.department
    fy_id = request.args.get("fy", type=int)

    query = (
        BudgetAllocation.query
        .join(BudgetLineItem)
        .filter(BudgetLineItem.department_id == department.id)
    )

    if fy_id:
        query = query.filter(BudgetAllocation.fiscal_year_id == fy_id)

    allocs = (
        query.join(FiscalYear)
        .order_by(FiscalYear.start_date.desc(), BudgetLineItem.code)
        .all()
    )
    fiscal_years = FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    return render_template(
        "admin/allocations.html",
        allocations=allocs,
        fiscal_years=fiscal_years,
        department=department,
    )


@admin_bp.route("/dept/<int:dept_id>/allocations/new", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def allocation_create(dept_id):
    department = g.department
    form = BudgetAllocationForm()
    form.fiscal_year_id.choices = [
        (fy.id, fy.label)
        for fy in FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    ]
    form.budget_line_item_id.choices = [
        (i.id, i.display_label)
        for i in BudgetLineItem.query.filter_by(
            is_active=True, department_id=department.id
        ).order_by(BudgetLineItem.code).all()
    ]

    if form.validate_on_submit():
        existing = BudgetAllocation.query.filter_by(
            fiscal_year_id=form.fiscal_year_id.data,
            budget_line_item_id=form.budget_line_item_id.data,
        ).first()
        if existing:
            flash("An allocation for this line item and fiscal year already exists. Edit it instead.", "warning")
            return redirect(url_for("admin.allocation_edit", dept_id=department.id, id=existing.id))

        alloc = BudgetAllocation(
            fiscal_year_id=form.fiscal_year_id.data,
            budget_line_item_id=form.budget_line_item_id.data,
            allocated_amount=form.allocated_amount.data,
        )
        db.session.add(alloc)
        db.session.commit()
        log_activity(
            current_user.id, "allocation_created", "budget_allocation", alloc.id,
            department_id=department.id,
        )
        flash("Budget allocation created.", "success")
        return redirect(url_for("admin.allocations", dept_id=department.id))

    return render_template("admin/allocation_form.html", form=form, edit=False, department=department)


@admin_bp.route("/dept/<int:dept_id>/allocations/<int:id>/edit", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def allocation_edit(dept_id, id):
    department = g.department
    alloc = BudgetAllocation.query.get_or_404(id)

    # Verify this allocation belongs to this department
    if alloc.line_item.department_id != department.id:
        abort(404)

    form = BudgetAllocationForm(obj=alloc)
    form.fiscal_year_id.choices = [
        (fy.id, fy.label)
        for fy in FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    ]
    form.budget_line_item_id.choices = [
        (i.id, i.display_label)
        for i in BudgetLineItem.query.filter_by(
            is_active=True, department_id=department.id
        ).order_by(BudgetLineItem.code).all()
    ]

    if form.validate_on_submit():
        alloc.fiscal_year_id = form.fiscal_year_id.data
        alloc.budget_line_item_id = form.budget_line_item_id.data
        alloc.allocated_amount = form.allocated_amount.data
        db.session.commit()
        log_activity(
            current_user.id, "allocation_updated", "budget_allocation", alloc.id,
            department_id=department.id,
        )
        flash("Budget allocation updated.", "success")
        return redirect(url_for("admin.allocations", dept_id=department.id))

    return render_template("admin/allocation_form.html", form=form, edit=True, alloc=alloc, department=department)


# ── Allocation CSV Import (department-scoped) ─────────────────
@admin_bp.route("/dept/<int:dept_id>/allocations/import", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def allocation_import(dept_id):
    department = g.department

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a CSV file.", "danger")
            return redirect(url_for("admin.allocation_import", dept_id=department.id))

        fy_id = request.form.get("fiscal_year_id", type=int)
        if not fy_id:
            flash("Please select a fiscal year.", "danger")
            return redirect(url_for("admin.allocation_import", dept_id=department.id))

        reader = csv.DictReader(io.TextIOWrapper(file, encoding="utf-8-sig"))
        count = 0
        for row in reader:
            code = row.get("code", "").strip()
            amount = row.get("amount", "0").strip().replace(",", "")
            if not code or not amount:
                continue

            item = BudgetLineItem.query.filter_by(
                code=code, department_id=department.id
            ).first()
            if not item:
                flash(f"Line item code '{code}' not found in this department, skipping.", "warning")
                continue

            try:
                amount_val = float(amount)
            except ValueError:
                flash(f"Invalid amount for code '{code}', skipping.", "warning")
                continue

            existing = BudgetAllocation.query.filter_by(
                fiscal_year_id=fy_id, budget_line_item_id=item.id
            ).first()
            if existing:
                existing.allocated_amount = amount_val
            else:
                alloc = BudgetAllocation(
                    fiscal_year_id=fy_id,
                    budget_line_item_id=item.id,
                    allocated_amount=amount_val,
                )
                db.session.add(alloc)
            count += 1

        db.session.commit()
        flash(f"Imported/updated {count} allocations.", "success")
        return redirect(url_for("admin.allocations", dept_id=department.id))

    fiscal_years = FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    return render_template("admin/allocation_import.html", fiscal_years=fiscal_years, department=department)


# ── Purchases Admin (department-scoped) ───────────────────────
@admin_bp.route("/dept/<int:dept_id>/purchases")
@login_required
@department_access_required
@dept_admin_required
def purchases(dept_id):
    department = g.department
    page = request.args.get("page", 1, type=int)
    query = (
        Purchase.query
        .filter_by(department_id=department.id)
        .order_by(Purchase.created_at.desc())
    )
    pagination = query.paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "admin/purchases.html",
        purchases=pagination.items,
        pagination=pagination,
        department=department,
    )


@admin_bp.route("/dept/<int:dept_id>/purchases/<int:id>/delete", methods=["POST"])
@login_required
@department_access_required
@dept_admin_required
def purchase_delete(dept_id, id):
    department = g.department
    purchase = Purchase.query.get_or_404(id)

    if purchase.department_id != department.id:
        abort(404)

    # Delete associated documents from storage
    storage = get_storage_backend()
    for doc in purchase.documents.all():
        try:
            storage.delete(doc.object_key)
        except Exception:
            pass

    db.session.delete(purchase)
    db.session.commit()
    log_activity(
        current_user.id, "purchase_deleted", "purchase", id,
        department_id=department.id,
    )
    flash("Purchase deleted.", "success")
    return redirect(url_for("admin.purchases", dept_id=department.id))


# ── Documents Admin (department-scoped) ───────────────────────
@admin_bp.route("/dept/<int:dept_id>/documents")
@login_required
@department_access_required
@dept_admin_required
def documents(dept_id):
    department = g.department
    page = request.args.get("page", 1, type=int)
    pagination = (
        Document.query
        .join(Purchase)
        .filter(Purchase.department_id == department.id)
        .order_by(Document.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template(
        "admin/documents.html",
        documents=pagination.items,
        pagination=pagination,
        department=department,
    )


@admin_bp.route("/dept/<int:dept_id>/documents/<int:id>/delete", methods=["POST"])
@login_required
@department_access_required
@dept_admin_required
def document_delete(dept_id, id):
    department = g.department
    doc = Document.query.get_or_404(id)
    purchase = Purchase.query.get_or_404(doc.purchase_id)

    if purchase.department_id != department.id:
        abort(404)

    storage = get_storage_backend()
    try:
        storage.delete(doc.object_key)
    except Exception:
        pass
    db.session.delete(doc)
    db.session.commit()
    log_activity(
        current_user.id, "document_deleted", "document", id,
        department_id=department.id,
    )
    flash("Document deleted.", "success")
    return redirect(url_for("admin.documents", dept_id=department.id))


# ── Approval Thresholds (department-scoped) ────────────────
@admin_bp.route("/dept/<int:dept_id>/approval-thresholds")
@login_required
@department_access_required
@dept_admin_required
def approval_thresholds(dept_id):
    department = g.department
    thresholds = ApprovalThreshold.get_thresholds_for_department(department.id)
    return render_template(
        "admin/approval_thresholds.html",
        thresholds=thresholds,
        department=department,
        role_labels=ApprovalThreshold.ROLE_LABELS,
    )


@admin_bp.route("/dept/<int:dept_id>/approval-thresholds/new", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def approval_threshold_create(dept_id):
    department = g.department
    form = ApprovalThresholdForm()

    if form.validate_on_submit():
        threshold = ApprovalThreshold(
            department_id=department.id,
            max_amount=form.max_amount.data if form.max_amount.data is not None else None,
            required_role=form.required_role.data,
            label=form.label.data or None,
        )
        db.session.add(threshold)
        db.session.commit()
        log_activity(
            current_user.id, "approval_threshold_created", "approval_threshold", threshold.id,
            department_id=department.id,
        )
        flash("Approval threshold created.", "success")
        return redirect(url_for("admin.approval_thresholds", dept_id=department.id))

    return render_template(
        "admin/approval_threshold_form.html", form=form, edit=False, department=department
    )


@admin_bp.route("/dept/<int:dept_id>/approval-thresholds/<int:id>/edit", methods=["GET", "POST"])
@login_required
@department_access_required
@dept_admin_required
def approval_threshold_edit(dept_id, id):
    department = g.department
    threshold = ApprovalThreshold.query.get_or_404(id)
    if threshold.department_id != department.id:
        abort(404)

    form = ApprovalThresholdForm(obj=threshold)

    if form.validate_on_submit():
        threshold.max_amount = form.max_amount.data if form.max_amount.data is not None else None
        threshold.required_role = form.required_role.data
        threshold.label = form.label.data or None
        db.session.commit()
        log_activity(
            current_user.id, "approval_threshold_updated", "approval_threshold", threshold.id,
            department_id=department.id,
        )
        flash("Approval threshold updated.", "success")
        return redirect(url_for("admin.approval_thresholds", dept_id=department.id))

    return render_template(
        "admin/approval_threshold_form.html", form=form, edit=True, threshold=threshold, department=department
    )


@admin_bp.route("/dept/<int:dept_id>/approval-thresholds/<int:id>/delete", methods=["POST"])
@login_required
@department_access_required
@dept_admin_required
def approval_threshold_delete(dept_id, id):
    department = g.department
    threshold = ApprovalThreshold.query.get_or_404(id)
    if threshold.department_id != department.id:
        abort(404)

    db.session.delete(threshold)
    db.session.commit()
    log_activity(
        current_user.id, "approval_threshold_deleted", "approval_threshold", id,
        department_id=department.id,
    )
    flash("Approval threshold deleted.", "success")
    return redirect(url_for("admin.approval_thresholds", dept_id=department.id))


# ── Department Activity Log ───────────────────────────────────
@admin_bp.route("/dept/<int:dept_id>/activity")
@login_required
@department_access_required
@dept_admin_required
def dept_activity(dept_id):
    department = g.department
    page = request.args.get("page", 1, type=int)
    pagination = (
        ActivityLog.query
        .filter_by(department_id=department.id)
        .order_by(ActivityLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template(
        "admin/activity.html",
        logs=pagination.items,
        pagination=pagination,
        department=department,
    )
