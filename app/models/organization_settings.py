from app import db
from datetime import datetime, timezone


class OrganizationSettings(db.Model):
    """Singleton model for organization-wide settings like branding."""

    __tablename__ = "organization_settings"

    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(255), nullable=True)
    logo_filename = db.Column(db.String(255), nullable=True)
    logo_object_key = db.Column(db.String(500), nullable=True)
    logo_content_type = db.Column(db.String(100), nullable=True)
    logo_storage_backend = db.Column(db.String(20), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def get(cls):
        """Return the singleton settings row, creating it if needed."""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
