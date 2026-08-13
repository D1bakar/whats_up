"""Bot engine entities: contacts, conversations, messages, sessions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_bot_conversations_messages"
down_revision: Union[str, None] = "002_webhook_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("phone_number_id", sa.UUID(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("whatsapp", name="channel", native_enum=False),
            nullable=False,
        ),
        sa.Column("channel_user_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["phone_number_id"], ["phone_numbers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "phone_number_id",
            "channel",
            "channel_user_id",
            name="uq_contacts_phone_channel_user",
        ),
    )
    op.create_index(
        op.f("ix_contacts_channel_user_id"), "contacts", ["channel_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_contacts_phone_number_id"), "contacts", ["phone_number_id"], unique=False
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("phone_number_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "paused", "closed", name="conversation_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phone_number_id"], ["phone_numbers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "phone_number_id",
            "contact_id",
            name="uq_conversations_phone_contact",
        ),
    )
    op.create_index(
        op.f("ix_conversations_contact_id"),
        "conversations",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_last_message_at"),
        "conversations",
        ["last_message_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversations_phone_number_id"),
        "conversations",
        ["phone_number_id"],
        unique=False,
    )

    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("current_state", sa.String(length=64), nullable=False),
        sa.Column("state_data", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_sessions_conversation_id"),
        "conversation_sessions",
        ["conversation_id"],
        unique=True,
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("wamid", sa.String(length=128), nullable=True),
        sa.Column(
            "direction",
            sa.Enum("inbound", "outbound", name="message_direction", native_enum=False),
            nullable=False,
        ),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum(
                "received",
                "processing",
                "processed",
                "failed",
                "ignored",
                name="message_processing_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "delivery_status",
            sa.Enum(
                "pending",
                "sent",
                "delivered",
                "failed",
                name="message_delivery_status",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_messages_wamid"), "messages", ["wamid"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_wamid"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(
        op.f("ix_conversation_sessions_conversation_id"), table_name="conversation_sessions"
    )
    op.drop_table("conversation_sessions")
    op.drop_index(op.f("ix_conversations_phone_number_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_last_message_at"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_contact_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_contacts_phone_number_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_channel_user_id"), table_name="contacts")
    op.drop_table("contacts")
