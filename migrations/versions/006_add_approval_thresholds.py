"""Add approval_thresholds table

Revision ID: 006
Revises: 005
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_thresholds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False, index=True),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("required_role", sa.String(20), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("approval_thresholds")
