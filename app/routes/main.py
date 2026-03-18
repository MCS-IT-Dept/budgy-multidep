from flask import Blueprint, redirect, url_for
from flask_login import current_user

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
