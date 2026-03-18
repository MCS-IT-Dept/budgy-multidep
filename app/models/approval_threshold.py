from datetime import datetime, timezone
from app import db


class ApprovalThreshold(db.Model):
    """Configurable approval tiers per department.

    Each row defines a ceiling: purchases up to `max_amount` can be
    approved by users with the specified `required_role` (or higher).
    Rows are evaluated from lowest max_amount upward.

    Example rows for a department:
        max_amount=500,   required_role=dept_admin   -> dept admin can approve up to $500
        max_amount=5000,  required_role=director      -> director can approve up to $5,000
        max_amount=None,  required_role=global_admin   -> global admin required above $5,000
    """
    __tablename__ = "approval_thresholds"

    # Role hierarchy: higher index = more authority
    ROLE_HIERARCHY = ["dept_admin", "director", "global_admin"]

    ROLE_LABELS = {
        "dept_admin": "Department Admin",
        "director": "Director / Assistant Superintendent",
        "global_admin": "Superintendent / Board",
    }

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    max_amount = db.Column(db.Numeric(12, 2), nullable=True)  # NULL = unlimited
    required_role = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(255), nullable=True)  # Optional description
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def get_required_role(cls, department_id, amount):
        """Return the minimum role required to approve a given amount.

        Thresholds are checked from lowest max_amount upward.
        If no thresholds are configured, returns 'dept_admin' (default behavior).
        """
        thresholds = (
            cls.query
            .filter_by(department_id=department_id)
            .order_by(cls.max_amount.asc().nullslast())
            .all()
        )

        if not thresholds:
            return "dept_admin"

        for t in thresholds:
            if t.max_amount is None or amount <= t.max_amount:
                return t.required_role

        # If amount exceeds all defined thresholds, require the highest role
        return thresholds[-1].required_role

    @classmethod
    def can_approve(cls, department_id, amount, user_role):
        """Check if a user with the given role can approve the amount."""
        required = cls.get_required_role(department_id, amount)
        required_level = cls.ROLE_HIERARCHY.index(required) if required in cls.ROLE_HIERARCHY else 0
        user_level = cls.ROLE_HIERARCHY.index(user_role) if user_role in cls.ROLE_HIERARCHY else -1
        return user_level >= required_level

    @classmethod
    def get_thresholds_for_department(cls, department_id):
        """Get all thresholds for a department, ordered by max_amount."""
        return (
            cls.query
            .filter_by(department_id=department_id)
            .order_by(cls.max_amount.asc().nullslast())
            .all()
        )

    def __repr__(self):
        return f"<ApprovalThreshold dept={self.department_id} max={self.max_amount} role={self.required_role}>"
