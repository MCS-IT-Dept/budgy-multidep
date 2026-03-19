from datetime import datetime, timezone
from app import db


class BudgetAmendment(db.Model):
    __tablename__ = "budget_amendments"

    id = db.Column(db.Integer, primary_key=True)
    budget_allocation_id = db.Column(
        db.Integer, db.ForeignKey("budget_allocations.id"), nullable=False, index=True
    )
    previous_amount = db.Column(db.Numeric(12, 2), nullable=False)
    new_amount = db.Column(db.Numeric(12, 2), nullable=False)
    change_amount = db.Column(db.Numeric(12, 2), nullable=False)
    board_approval_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(500), nullable=False)
    approved_by_name = db.Column(db.String(255), nullable=True)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    allocation = db.relationship("BudgetAllocation", backref=db.backref("amendments", lazy="dynamic", order_by="BudgetAmendment.created_at.desc()"))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])

    @property
    def change_display(self):
        if self.change_amount > 0:
            return f"+${self.change_amount:,.2f}"
        return f"-${abs(self.change_amount):,.2f}"

    def __repr__(self):
        return f"<BudgetAmendment {self.id} alloc:{self.budget_allocation_id} {self.change_display}>"
