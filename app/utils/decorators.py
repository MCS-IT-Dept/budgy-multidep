from functools import wraps
from flask import flash, redirect, url_for, abort, g
from flask_login import current_user

from app import db
from app.models.department import Department


def role_required(*roles):
    """Decorator that requires the current user to have one of the given roles."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in.", "warning")
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def global_admin_required(f):
    return role_required("global_admin")(f)


def dept_admin_required(f):
    return role_required("global_admin", "dept_admin")(f)


def department_access_required(f):
    """Decorator for routes with a dept_id parameter.

    Verifies the user is a global_admin or belongs to the specified department.
    Sets g.department to the resolved Department object.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in.", "warning")
            return redirect(url_for("auth.login"))

        dept_id = kwargs.get("dept_id")
        if dept_id is None:
            abort(400)

        department = db.session.get(Department, dept_id)
        if department is None or not department.is_active:
            abort(404)

        # Global admins can access any department
        if current_user.is_global_admin:
            g.department = department
            return f(*args, **kwargs)

        # Other users must belong to this department
        if current_user.department_id != dept_id:
            abort(403)

        g.department = department
        return f(*args, **kwargs)

    return decorated_function
