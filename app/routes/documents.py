from flask import Blueprint, abort, send_file, current_app
from flask_login import login_required, current_user
import io

from app.models.document import Document
from app.models.purchase import Purchase
from app.services.storage import get_storage_backend

documents_bp = Blueprint("documents", __name__)


def _check_document_access(purchase):
    """Check that the current user can access documents for this purchase."""
    if current_user.is_global_admin:
        return

    # Dept admins can access documents in their department
    if current_user.is_dept_admin and current_user.department_id == purchase.department_id:
        return

    # Regular users can only access their own purchase documents
    if current_user.role == "user":
        if (current_user.department_id == purchase.department_id
                and purchase.submitted_by_user_id == current_user.id):
            return

    abort(403)


@documents_bp.route("/<int:id>/download")
@login_required
def download(id):
    doc = Document.query.get_or_404(id)
    purchase = Purchase.query.get_or_404(doc.purchase_id)

    _check_document_access(purchase)

    storage = get_storage_backend()
    file_data, content_type = storage.get(doc.object_key)

    return send_file(
        io.BytesIO(file_data),
        mimetype=doc.content_type,
        as_attachment=True,
        download_name=doc.original_filename,
    )


@documents_bp.route("/<int:id>/view")
@login_required
def view(id):
    doc = Document.query.get_or_404(id)
    purchase = Purchase.query.get_or_404(doc.purchase_id)

    _check_document_access(purchase)

    storage = get_storage_backend()
    file_data, _ = storage.get(doc.object_key)

    return send_file(
        io.BytesIO(file_data),
        mimetype=doc.content_type,
        as_attachment=False,
        download_name=doc.original_filename,
    )
