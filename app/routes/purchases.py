import io
import csv
from datetime import date
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    Response,
    g,
)
from flask_login import login_required, current_user

from app import db
from app.models.purchase import Purchase
from app.models.document import Document
from app.models.budget_line_item import BudgetLineItem
from app.models.fiscal_year import FiscalYear
from app.models.user import User
from app.services.fiscal_year import get_or_create_fiscal_year
from app.services.department import get_payment_methods_for_department
from app.services.storage import get_storage_backend, generate_object_key, allowed_file
from app.services.activity import log_activity
from app.utils.forms import PurchaseForm, PurchaseStatusForm
from app.utils.decorators import dept_admin_required, department_access_required

purchases_bp = Blueprint(
    "purchases", __name__, template_folder="../templates/purchases"
)


def _populate_form_choices(form, department_id):
    items = (
        BudgetLineItem.query
        .filter_by(is_active=True, department_id=department_id)
        .order_by(BudgetLineItem.code)
        .all()
    )
    form.budget_line_item_id.choices = [(i.id, i.display_label) for i in items]

    payment_methods = get_payment_methods_for_department(department_id)
    form.payment_method.choices = [("", "— Select —")] + [
        (pm.name, pm.name) for pm in payment_methods
    ]


@purchases_bp.route("/dept/<int:dept_id>/")
@login_required
@department_access_required
def index(dept_id):
    department = g.department
    page = request.args.get("page", 1, type=int)
    per_page = 25

    query = Purchase.query.filter_by(department_id=department.id)

    # Regular users can only see their own purchases
    if current_user.role == "user":
        query = query.filter_by(submitted_by_user_id=current_user.id)

    # Filters
    fy_id = request.args.get("fy", type=int)
    if fy_id:
        query = query.filter_by(fiscal_year_id=fy_id)

    vendor = request.args.get("vendor", "").strip()
    if vendor:
        query = query.filter(Purchase.vendor_name.ilike(f"%{vendor}%"))

    line_item_id = request.args.get("line_item", type=int)
    if line_item_id:
        query = query.filter_by(budget_line_item_id=line_item_id)

    status = request.args.get("status", "").strip()
    if status:
        query = query.filter_by(status=status)

    submitter_id = request.args.get("submitter", type=int)
    if submitter_id and current_user.is_manager:
        query = query.filter_by(submitted_by_user_id=submitter_id)

    date_from = request.args.get("date_from", "")
    if date_from:
        query = query.filter(Purchase.purchase_date >= date_from)
    date_to = request.args.get("date_to", "")
    if date_to:
        query = query.filter(Purchase.purchase_date <= date_to)

    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            db.or_(
                Purchase.vendor_name.ilike(f"%{search}%"),
                Purchase.description.ilike(f"%{search}%"),
                Purchase.po_number.ilike(f"%{search}%"),
                Purchase.invoice_number.ilike(f"%{search}%"),
            )
        )

    sort = request.args.get("sort", "date_desc")
    if sort == "date_asc":
        query = query.order_by(Purchase.purchase_date.asc())
    elif sort == "amount_desc":
        query = query.order_by(Purchase.amount.desc())
    elif sort == "amount_asc":
        query = query.order_by(Purchase.amount.asc())
    elif sort == "vendor":
        query = query.order_by(Purchase.vendor_name.asc())
    else:
        query = query.order_by(Purchase.purchase_date.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    fiscal_years = FiscalYear.query.order_by(FiscalYear.start_date.desc()).all()
    line_items = (
        BudgetLineItem.query
        .filter_by(is_active=True, department_id=department.id)
        .order_by(BudgetLineItem.code)
        .all()
    )
    users = (
        User.query.filter_by(is_active=True, department_id=department.id)
        .order_by(User.display_name).all()
        if current_user.is_manager else []
    )

    return render_template(
        "purchases/index.html",
        purchases=pagination.items,
        pagination=pagination,
        fiscal_years=fiscal_years,
        line_items=line_items,
        users=users,
        statuses=Purchase.STATUSES,
        department=department,
    )


@purchases_bp.route("/dept/<int:dept_id>/new", methods=["GET", "POST"])
@login_required
@department_access_required
def create(dept_id):
    department = g.department
    form = PurchaseForm()
    _populate_form_choices(form, department.id)

    if form.validate_on_submit():
        other_item = BudgetLineItem.query.filter_by(
            code="Other", department_id=department.id
        ).first()
        is_other = other_item and form.budget_line_item_id.data == other_item.id

        if is_other and not form.custom_account_code.data:
            flash("Custom account code is required when 'Other' is selected.", "danger")
            return render_template("purchases/form.html", form=form, edit=False, department=department)

        if is_other and not form.custom_account_description.data:
            flash("Custom account description is required when 'Other' is selected.", "danger")
            return render_template("purchases/form.html", form=form, edit=False, department=department)

        fiscal_year = get_or_create_fiscal_year(form.purchase_date.data)

        purchase = Purchase(
            vendor_name=form.vendor_name.data.strip(),
            purchase_date=form.purchase_date.data,
            amount=form.amount.data,
            description=form.description.data,
            notes=form.notes.data,
            po_number=form.po_number.data,
            invoice_number=form.invoice_number.data,
            payment_method=form.payment_method.data or None,
            tax_exempt_status=form.tax_exempt_status.data or None,
            budget_line_item_id=form.budget_line_item_id.data,
            custom_account_code=form.custom_account_code.data if is_other else None,
            custom_account_description=form.custom_account_description.data if is_other else None,
            fiscal_year_id=fiscal_year.id,
            submitted_by_user_id=current_user.id,
            department_id=department.id,
            status="submitted",
        )
        db.session.add(purchase)
        db.session.flush()

        # Handle file uploads
        files = request.files.getlist("attachments")
        storage = get_storage_backend()
        for f in files:
            if f and f.filename and allowed_file(f.filename):
                object_key = generate_object_key(
                    fiscal_year.label, purchase.id, f.filename
                )
                meta = storage.save(f, object_key, f.content_type or "application/octet-stream")
                doc = Document(
                    purchase_id=purchase.id,
                    original_filename=f.filename,
                    stored_filename=meta["stored_filename"],
                    content_type=f.content_type or "application/octet-stream",
                    file_size=meta["file_size"],
                    storage_backend=meta["storage_backend"],
                    bucket_name=meta.get("bucket_name"),
                    object_key=meta["object_key"],
                    uploaded_by_user_id=current_user.id,
                )
                db.session.add(doc)
            elif f and f.filename:
                flash(f"File '{f.filename}' skipped: invalid type.", "warning")

        db.session.commit()
        log_activity(
            current_user.id, "purchase_created", "purchase", purchase.id,
            f"Vendor: {purchase.vendor_name}, Amount: {purchase.amount}",
            department_id=department.id,
        )
        flash("Purchase created successfully.", "success")
        return redirect(url_for("purchases.detail", dept_id=department.id, id=purchase.id))

    return render_template("purchases/form.html", form=form, edit=False, department=department)


@purchases_bp.route("/dept/<int:dept_id>/<int:id>")
@login_required
@department_access_required
def detail(dept_id, id):
    department = g.department
    purchase = Purchase.query.get_or_404(id)

    if purchase.department_id != department.id:
        abort(404)

    # Regular users can only view their own
    if current_user.role == "user" and purchase.submitted_by_user_id != current_user.id:
        abort(403)

    status_form = PurchaseStatusForm(obj=purchase)
    documents = purchase.documents.all()

    return render_template(
        "purchases/detail.html",
        purchase=purchase,
        documents=documents,
        status_form=status_form,
        department=department,
    )


@purchases_bp.route("/dept/<int:dept_id>/<int:id>/edit", methods=["GET", "POST"])
@login_required
@department_access_required
def edit(dept_id, id):
    department = g.department
    purchase = Purchase.query.get_or_404(id)

    if purchase.department_id != department.id:
        abort(404)

    # Only owner (if submitted) or admin can edit
    if current_user.role == "user" and purchase.submitted_by_user_id != current_user.id:
        abort(403)
    if current_user.role == "user" and purchase.status not in ("submitted",):
        flash("You can only edit purchases in 'submitted' status.", "warning")
        return redirect(url_for("purchases.detail", dept_id=department.id, id=id))

    form = PurchaseForm(obj=purchase)
    _populate_form_choices(form, department.id)

    if form.validate_on_submit():
        other_item = BudgetLineItem.query.filter_by(
            code="Other", department_id=department.id
        ).first()
        is_other = other_item and form.budget_line_item_id.data == other_item.id

        if is_other and not form.custom_account_code.data:
            flash("Custom account code is required when 'Other' is selected.", "danger")
            return render_template("purchases/form.html", form=form, edit=True, purchase=purchase, department=department)

        if is_other and not form.custom_account_description.data:
            flash("Custom account description is required when 'Other' is selected.", "danger")
            return render_template("purchases/form.html", form=form, edit=True, purchase=purchase, department=department)

        fiscal_year = get_or_create_fiscal_year(form.purchase_date.data)

        purchase.vendor_name = form.vendor_name.data.strip()
        purchase.purchase_date = form.purchase_date.data
        purchase.amount = form.amount.data
        purchase.description = form.description.data
        purchase.notes = form.notes.data
        purchase.po_number = form.po_number.data
        purchase.invoice_number = form.invoice_number.data
        purchase.payment_method = form.payment_method.data or None
        purchase.tax_exempt_status = form.tax_exempt_status.data or None
        purchase.budget_line_item_id = form.budget_line_item_id.data
        purchase.custom_account_code = form.custom_account_code.data if is_other else None
        purchase.custom_account_description = form.custom_account_description.data if is_other else None
        purchase.fiscal_year_id = fiscal_year.id

        # Handle new file uploads
        files = request.files.getlist("attachments")
        storage = get_storage_backend()
        for f in files:
            if f and f.filename and allowed_file(f.filename):
                object_key = generate_object_key(
                    fiscal_year.label, purchase.id, f.filename
                )
                meta = storage.save(f, object_key, f.content_type or "application/octet-stream")
                doc = Document(
                    purchase_id=purchase.id,
                    original_filename=f.filename,
                    stored_filename=meta["stored_filename"],
                    content_type=f.content_type or "application/octet-stream",
                    file_size=meta["file_size"],
                    storage_backend=meta["storage_backend"],
                    bucket_name=meta.get("bucket_name"),
                    object_key=meta["object_key"],
                    uploaded_by_user_id=current_user.id,
                )
                db.session.add(doc)

        db.session.commit()
        log_activity(
            current_user.id, "purchase_updated", "purchase", purchase.id,
            department_id=department.id,
        )
        flash("Purchase updated.", "success")
        return redirect(url_for("purchases.detail", dept_id=department.id, id=purchase.id))

    return render_template("purchases/form.html", form=form, edit=True, purchase=purchase, department=department)


@purchases_bp.route("/dept/<int:dept_id>/<int:id>/status", methods=["POST"])
@login_required
@department_access_required
@dept_admin_required
def update_status(dept_id, id):
    department = g.department
    purchase = Purchase.query.get_or_404(id)

    if purchase.department_id != department.id:
        abort(404)

    form = PurchaseStatusForm()

    if form.validate_on_submit():
        old_status = purchase.status
        purchase.status = form.status.data
        purchase.review_notes = form.review_notes.data
        db.session.commit()
        log_activity(
            current_user.id, "purchase_status_changed", "purchase", purchase.id,
            f"{old_status} -> {purchase.status}",
            department_id=department.id,
        )
        flash(f"Status updated to {purchase.status}.", "success")
    else:
        flash("Invalid status update.", "danger")

    return redirect(url_for("purchases.detail", dept_id=department.id, id=id))


@purchases_bp.route("/dept/<int:dept_id>/export")
@login_required
@department_access_required
@dept_admin_required
def export_csv(dept_id):
    department = g.department
    query = Purchase.query.filter_by(department_id=department.id)

    fy_id = request.args.get("fy", type=int)
    if fy_id:
        query = query.filter_by(fiscal_year_id=fy_id)

    purchases = query.order_by(Purchase.purchase_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Vendor", "Date", "Amount", "Status", "Payment Method", "Tax Exempt Status",
        "Line Item", "Custom Code", "Description", "PO #", "Invoice #",
        "Submitted By", "Fiscal Year", "Created At",
    ])

    for p in purchases:
        writer.writerow([
            p.id,
            p.vendor_name,
            p.purchase_date.isoformat(),
            str(p.amount),
            p.status,
            p.payment_method or "",
            dict(Purchase.TAX_EXEMPT_CHOICES).get(p.tax_exempt_status, "") if p.tax_exempt_status else "",
            p.line_item.display_label if p.line_item else "",
            p.custom_account_code or "",
            p.description or "",
            p.po_number or "",
            p.invoice_number or "",
            p.submitter.display_name if p.submitter else "",
            p.fiscal_year.label if p.fiscal_year else "",
            p.created_at.isoformat() if p.created_at else "",
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={department.slug}_purchases_export.csv"},
    )


@purchases_bp.route("/dept/<int:dept_id>/vendors.json")
@login_required
@department_access_required
def vendor_autocomplete(dept_id):
    department = g.department
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return {"results": []}

    vendors = (
        db.session.query(Purchase.vendor_name)
        .filter(
            Purchase.vendor_name.ilike(f"%{q}%"),
            Purchase.department_id == department.id,
        )
        .distinct()
        .order_by(Purchase.vendor_name)
        .limit(10)
        .all()
    )
    return {"results": [v[0] for v in vendors]}
