"""Add approval_thresholds table and purchase approval tracking columns

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

    with op.batch_alter_table("purchases") as batch_op:
        batch_op.add_column(sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
        batch_op.add_column(sa.Column("approval_flag", sa.String(255), nullable=True))


def downgrade():
    with op.batch_alter_table("purchases") as batch_op:
        batch_op.drop_column("approval_flag")
        batch_op.drop_column("approved_by_user_id")
    op.drop_table("approval_thresholds")
