from app import db
from app.models.activity_log import ActivityLog


def log_activity(user_id, action, entity_type=None, entity_id=None, details=None, department_id=None):
    entry = ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        department_id=department_id,
    )
    db.session.add(entry)
    db.session.commit()
