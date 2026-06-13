"""simplify: drop expenses.category and the analytics table

Revision ID: b1c2d3e4f5a6
Revises: baa5b1247f5f
Create Date: 2026-06-08 14:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "baa5b1247f5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_expenses_category"))
        batch_op.drop_column("category")
        batch_op.drop_column("description")

    op.drop_table("analytics")


def downgrade() -> None:
    op.create_table(
        "analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("insight_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("analytics", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_analytics_user_id"), ["user_id"], unique=False
        )

    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("description", sa.String(length=512), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "category",
                sa.Enum(
                    "FOOD",
                    "TRANSPORT",
                    "SHOPPING",
                    "ENTERTAINMENT",
                    "SUBSCRIPTIONS",
                    "CAFES",
                    "HEALTH",
                    "UTILITIES",
                    "OTHER",
                    name="expensecategory",
                    native_enum=False,
                    length=32,
                ),
                nullable=False,
                server_default="OTHER",
            )
        )
        batch_op.create_index(
            batch_op.f("ix_expenses_category"), ["category"], unique=False
        )
