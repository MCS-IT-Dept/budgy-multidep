from datetime import datetime, timezone
from app import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    users = db.relationship("User", backref="department", lazy="dynamic")
    budget_line_items = db.relationship(
        "BudgetLineItem", backref="department", lazy="dynamic"
    )
    payment_methods = db.relationship(
        "PaymentMethod", backref="department", lazy="dynamic"
    )
    purchases = db.relationship("Purchase", backref="department", lazy="dynamic")

    def __repr__(self):
        return f"<Department {self.name}>"
