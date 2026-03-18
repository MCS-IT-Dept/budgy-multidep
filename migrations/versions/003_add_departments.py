"""Add multi-department support

Revision ID: 003
Revises: 002
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create departments table
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # 2. Create payment_methods table
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("department_id", "name", name="uq_dept_payment_method"),
    )
    op.create_index("ix_payment_methods_department_id", "payment_methods", ["department_id"])

    # 3. Insert default department
    op.execute(
        "INSERT INTO departments (id, name, slug) VALUES (1, 'Default', 'default')"
    )

    # 4. Seed payment methods for default department from old hardcoded list
    payment_methods = [
        "Credit Card - Andy",
        "Credit Card - James",
        "Credit Card - Brady",
        "Credit Card - Danielle",
        "Amazon",
        "Purchase Order",
        "Other",
    ]
    for i, pm in enumerate(payment_methods):
        escaped = pm.replace("'", "''")
        op.execute(
            f"INSERT INTO payment_methods (department_id, name, sort_order) "
            f"VALUES (1, '{escaped}', {i})"
        )

    # 5. Add department_id to users (nullable for global_admin)
    op.add_column("users", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True))
    op.create_index("ix_users_department_id", "users", ["department_id"])
    # Assign existing non-admin users to default department
    op.execute("UPDATE users SET department_id = 1 WHERE role != 'admin'")

    # 6. Convert role values
    op.execute("UPDATE users SET role = 'global_admin' WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'dept_admin' WHERE role = 'manager'")
    op.execute("UPDATE users SET role = 'user' WHERE role = 'staff'")

    # 7. Add department_id to budget_line_items
    op.add_column("budget_line_items", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True))
    op.execute("UPDATE budget_line_items SET department_id = 1")
    op.alter_column("budget_line_items", "department_id", nullable=False)
    op.create_index("ix_budget_line_items_department_id", "budget_line_items", ["department_id"])
    # Drop old unique constraint on code, add composite unique
    op.drop_constraint("budget_line_items_code_key", "budget_line_items", type_="unique")
    op.create_unique_constraint("uq_dept_line_item_code", "budget_line_items", ["department_id", "code"])

    # 8. Add department_id to purchases
    op.add_column("purchases", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True))
    op.execute("UPDATE purchases SET department_id = 1")
    op.alter_column("purchases", "department_id", nullable=False)
    op.create_index("ix_purchases_department_id", "purchases", ["department_id"])

    # 9. Add department_id to activity_logs (nullable - some actions are global)
    op.add_column("activity_logs", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True))
    op.create_index("ix_activity_logs_department_id", "activity_logs", ["department_id"])


def downgrade():
    # Remove department_id from activity_logs
    op.drop_index("ix_activity_logs_department_id", "activity_logs")
    op.drop_column("activity_logs", "department_id")

    # Remove department_id from purchases
    op.drop_index("ix_purchases_department_id", "purchases")
    op.drop_column("purchases", "department_id")

    # Restore budget_line_items
    op.drop_constraint("uq_dept_line_item_code", "budget_line_items", type_="unique")
    op.create_unique_constraint("budget_line_items_code_key", "budget_line_items", ["code"])
    op.drop_index("ix_budget_line_items_department_id", "budget_line_items")
    op.drop_column("budget_line_items", "department_id")

    # Revert role values
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'global_admin'")
    op.execute("UPDATE users SET role = 'manager' WHERE role = 'dept_admin'")
    op.execute("UPDATE users SET role = 'staff' WHERE role = 'user'")

    # Remove department_id from users
    op.drop_index("ix_users_department_id", "users")
    op.drop_column("users", "department_id")

    # Drop payment_methods table
    op.drop_index("ix_payment_methods_department_id", "payment_methods")
    op.drop_table("payment_methods")

    # Drop departments table
    op.drop_table("departments")
