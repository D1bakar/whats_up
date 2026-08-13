"""Initial foundation schema: admin users, business accounts, phone numbers."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_webhook_events"
down_revision: Union[str, None] = "001_initial_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("wamid", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum(
                "pending",
                "processed",
                "duplicate",
                "unsupported",
                "failed",
                name="webhook_processing_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_events_event_id"), "webhook_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_webhook_events_wamid"), "webhook_events", ["wamid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_events_wamid"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_event_id"), table_name="webhook_events")
    op.drop_table("webhook_events")
