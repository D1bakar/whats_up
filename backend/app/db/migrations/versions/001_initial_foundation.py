"""Initial foundation schema: admin users, business accounts, phone numbers."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "operator", "viewer", name="admin_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_users_email"), "admin_users", ["email"], unique=True)

    op.create_table(
        "business_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("meta_waba_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_business_accounts_meta_waba_id"),
        "business_accounts",
        ["meta_waba_id"],
        unique=True,
    )

    op.create_table(
        "phone_numbers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_account_id", sa.UUID(), nullable=False),
        sa.Column("meta_phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("display_number", sa.String(length=32), nullable=False),
        sa.Column("verify_token_ref", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["business_account_id"], ["business_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_phone_numbers_business_account_id"),
        "phone_numbers",
        ["business_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_phone_numbers_meta_phone_number_id"),
        "phone_numbers",
        ["meta_phone_number_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_phone_numbers_meta_phone_number_id"), table_name="phone_numbers")
    op.drop_index(op.f("ix_phone_numbers_business_account_id"), table_name="phone_numbers")
    op.drop_table("phone_numbers")
    op.drop_index(op.f("ix_business_accounts_meta_waba_id"), table_name="business_accounts")
    op.drop_table("business_accounts")
    op.drop_index(op.f("ix_admin_users_email"), table_name="admin_users")
    op.drop_table("admin_users")
