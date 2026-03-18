import io

from flask import Blueprint, redirect, url_for, abort, send_file
from flask_login import current_user

from app.models.organization_settings import OrganizationSettings
from app.services.storage import get_storage_backend

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_global_admin:
            return redirect(url_for("dashboard.global_overview"))
        if current_user.department_id:
            if current_user.is_dept_admin:
                return redirect(url_for("dashboard.dept_dashboard", dept_id=current_user.department_id))
            return redirect(url_for("purchases.index", dept_id=current_user.department_id))
    return redirect(url_for("auth.login"))


@main_bp.route("/branding/logo")
def org_logo():
    """Serve the organization logo from storage."""
    settings = OrganizationSettings.get()
    if not settings.logo_object_key:
        abort(404)

    storage = get_storage_backend()
    file_data, _ = storage.get(settings.logo_object_key)

    return send_file(
        io.BytesIO(file_data),
        mimetype=settings.logo_content_type or "image/png",
        as_attachment=False,
        download_name=settings.logo_filename,
    )
