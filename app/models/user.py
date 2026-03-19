from datetime import datetime, timezone
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="user"
    )  # global_admin, director, dept_admin, user
    auth_provider = db.Column(db.String(50), default="azure_ad")
    azure_oid = db.Column(db.String(255), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=True, index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    purchases = db.relationship(
        "Purchase", foreign_keys="[Purchase.submitted_by_user_id]",
        backref="submitter", lazy="dynamic"
    )
    documents = db.relationship("Document", backref="uploader", lazy="dynamic")

    @property
    def is_global_admin(self):
        return self.role == "global_admin"

    @property
    def is_dept_admin(self):
        return self.role == "dept_admin"

    @property
    def is_director(self):
        return self.role == "director"

    @property
    def is_admin(self):
        return self.role == "global_admin"

    @property
    def is_manager(self):
        return self.role in ("global_admin", "director", "dept_admin")

    def __repr__(self):
        return f"<User {self.email}>"
