from app import db
from app.models.department import Department
from app.models.payment_method import PaymentMethod


def get_department_or_404(dept_id):
    dept = db.session.get(Department, dept_id)
    if dept is None:
        from flask import abort
        abort(404)
    return dept


def get_active_departments():
    return Department.query.filter_by(is_active=True).order_by(Department.name).all()


def get_all_departments():
    return Department.query.order_by(Department.name).all()


def get_payment_methods_for_department(department_id):
    return (
        PaymentMethod.query
        .filter_by(department_id=department_id, is_active=True)
        .order_by(PaymentMethod.sort_order, PaymentMethod.name)
        .all()
    )
