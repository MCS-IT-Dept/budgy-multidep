from datetime import datetime, timezone
from app import db


class BudgetLineItem(db.Model):
    __tablename__ = "budget_line_items"
    __table_args__ = (
        db.UniqueConstraint("department_id", "code", name="uq_dept_line_item_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    is_custom = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    allocations = db.relationship(
        "BudgetAllocation", backref="line_item", lazy="dynamic"
    )
    purchases = db.relationship("Purchase", backref="line_item", lazy="dynamic")

    @property
    def display_label(self):
        if self.code == self.name:
            return self.name
        return f"{self.code}: {self.name}"

    def __repr__(self):
        return f"<BudgetLineItem {self.code}>"
