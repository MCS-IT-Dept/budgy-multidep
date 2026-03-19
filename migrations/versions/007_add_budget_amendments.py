"""Add budget_amendments table for tracking mid-year allocation changes

Revision ID: 007
Revises: 006
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "budget_amendments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("budget_allocation_id", sa.Integer(), sa.ForeignKey("budget_allocations.id"), nullable=False, index=True),
        sa.Column("previous_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("change_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("board_approval_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("approved_by_name", sa.String(255), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("budget_amendments")
