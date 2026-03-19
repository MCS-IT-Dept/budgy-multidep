"""Add submitted_to_finance flag to purchases

Revision ID: 008
Revises: 007
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "purchases",
        sa.Column("submitted_to_finance", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade():
    op.drop_column("purchases", "submitted_to_finance")
