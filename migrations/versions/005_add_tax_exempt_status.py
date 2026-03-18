"""Add tax_exempt_status to purchases

Revision ID: 005
Revises: 004
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchases", sa.Column("tax_exempt_status", sa.String(30), nullable=True))


def downgrade():
    op.drop_column("purchases", "tax_exempt_status")
