from datetime import datetime, timezone
from app import db


class PaymentMethod(db.Model):
    __tablename__ = "payment_methods"
    __table_args__ = (
        db.UniqueConstraint("department_id", "name", name="uq_dept_payment_method"),
    )

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<PaymentMethod {self.name}>"
