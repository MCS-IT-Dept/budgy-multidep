from datetime import datetime, timezone
from app import db


class Purchase(db.Model):
    __tablename__ = "purchases"

    STATUSES = ["submitted", "reviewed", "approved", "rejected"]

    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(255), nullable=False, index=True)
    purchase_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    po_number = db.Column(db.String(100), nullable=True)
    invoice_number = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)

    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    budget_line_item_id = db.Column(
        db.Integer, db.ForeignKey("budget_line_items.id"), nullable=False
    )
    custom_account_code = db.Column(db.String(100), nullable=True)
    custom_account_description = db.Column(db.String(255), nullable=True)

    fiscal_year_id = db.Column(
        db.Integer, db.ForeignKey("fiscal_years.id"), nullable=False
    )
    submitted_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    status = db.Column(db.String(20), nullable=False, default="submitted", index=True)
    review_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    documents = db.relationship(
        "Document", backref="purchase", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Purchase {self.id} {self.vendor_name}>"
