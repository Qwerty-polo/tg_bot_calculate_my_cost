"""Store each user's calendar timezone; existing expense timestamps stay UTC."""

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column(
            "timezone", sa.String(64), nullable=False, server_default="Europe/Kyiv"
        ))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("timezone")
