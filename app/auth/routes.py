import uuid
import logging

import msal
from flask import (
    Blueprint,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    request,
)
from flask_login import login_user, logout_user, current_user

from app import db
from app.models.user import User
from app.models.department import Department
from app.services.activity import log_activity

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


def _build_msal_app():
    return msal.ConfidentialClientApplication(
        current_app.config["AZURE_CLIENT_ID"],
        authority=current_app.config["AZURE_AUTHORITY"],
        client_credential=current_app.config["AZURE_CLIENT_SECRET"],
    )


def _get_redirect_uri():
    return current_app.config["AZURE_REDIRECT_URI"]


def _get_default_department():
    """Get or create the default department for new user assignment."""
    dept = Department.query.filter_by(slug="default").first()
    if dept is None:
        dept = Department(name="Default", slug="default")
        db.session.add(dept)
        db.session.commit()
    return dept


def _redirect_after_login(user):
    """Redirect user to the appropriate page after login."""
    if user.is_global_admin:
        return redirect(url_for("dashboard.global_overview"))
    if user.department_id:
        if user.is_dept_admin:
            return redirect(url_for("dashboard.dept_dashboard", dept_id=user.department_id))
        return redirect(url_for("purchases.index", dept_id=user.department_id))
    # User has no department assignment — shouldn't happen but fallback
    return redirect(url_for("auth.login"))


@auth_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)

    # If Azure AD is not configured, use dev login
    if not current_app.config["AZURE_CLIENT_ID"]:
        from flask import render_template

        return render_template("auth/dev_login.html")

    app_msal = _build_msal_app()
    state = str(uuid.uuid4())
    session["auth_state"] = state
    auth_url = app_msal.get_authorization_request_url(
        scopes=["User.Read"],
        state=state,
        redirect_uri=_get_redirect_uri(),
    )
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    if request.args.get("state") != session.get("auth_state"):
        flash("Authentication state mismatch.", "danger")
        return redirect(url_for("auth.login"))

    if "error" in request.args:
        flash(f"Authentication error: {request.args.get('error_description', 'Unknown error')}", "danger")
        return redirect(url_for("auth.login"))

    app_msal = _build_msal_app()
    result = app_msal.acquire_token_by_authorization_code(
        request.args["code"],
        scopes=["User.Read"],
        redirect_uri=_get_redirect_uri(),
    )

    if "error" in result:
        flash(f"Token error: {result.get('error_description', '')}", "danger")
        return redirect(url_for("auth.login"))

    claims = result.get("id_token_claims", {})
    email = claims.get("preferred_username", claims.get("email", "")).lower().strip()
    display_name = claims.get("name", email)
    oid = claims.get("oid", "")

    if not email:
        flash("Could not determine your email from the identity provider.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if user is None:
        # Determine role
        if email in current_app.config["ADMIN_EMAILS"]:
            role = "global_admin"
            department_id = None
        else:
            role = "user"
            department_id = _get_default_department().id

        user = User(
            email=email,
            display_name=display_name,
            role=role,
            auth_provider="azure_ad",
            azure_oid=oid,
            department_id=department_id,
        )
        db.session.add(user)
        db.session.commit()
        log_activity(user.id, "user_created", "user", user.id, f"New user: {email}")
    else:
        # Update display name if changed
        if user.display_name != display_name:
            user.display_name = display_name
            db.session.commit()
        # Bootstrap global_admin if listed in ADMIN_EMAILS
        if email in current_app.config["ADMIN_EMAILS"] and user.role != "global_admin":
            user.role = "global_admin"
            user.department_id = None
            db.session.commit()

    if not user.is_active:
        flash("Your account has been deactivated. Contact an administrator.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    session.pop("auth_state", None)
    log_activity(user.id, "user_login", "user", user.id)
    flash(f"Welcome, {user.display_name}!", "success")
    return _redirect_after_login(user)


@auth_bp.route("/dev-login", methods=["POST"])
def dev_login():
    """Development-only login that bypasses Azure AD."""
    if current_app.config["AZURE_CLIENT_ID"]:
        flash("Dev login is disabled when Azure AD is configured.", "danger")
        return redirect(url_for("auth.login"))

    from flask import request as req

    email = req.form.get("email", "").lower().strip()
    display_name = req.form.get("display_name", email)

    if not email:
        flash("Email is required.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if user is None:
        if email in current_app.config["ADMIN_EMAILS"]:
            role = "global_admin"
            department_id = None
        else:
            role = "user"
            department_id = _get_default_department().id

        user = User(
            email=email,
            display_name=display_name,
            role=role,
            auth_provider="dev",
            department_id=department_id,
        )
        db.session.add(user)
        db.session.commit()

    if not user.is_active:
        flash("Account deactivated.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    flash(f"Welcome, {user.display_name}! (Dev mode)", "success")
    return _redirect_after_login(user)


@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        log_activity(current_user.id, "user_logout", "user", current_user.id)
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
