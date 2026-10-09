"""allow multiple social accounts

Revision ID: a95eb1149b56
Revises: d3dfa5674ad4
Create Date: 2026-10-09 10:03:08.005615
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a95eb1149b56"
down_revision = "d3dfa5674ad4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Find and remove the existing UNIQUE constraint
    # on (user_id, platform).
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'social_accounts'::regclass
              AND contype = 'u'
              AND pg_get_constraintdef(oid)
                  = 'UNIQUE (user_id, platform)'
            """
        )
    )

    old_constraint = result.scalar_one_or_none()

    if old_constraint:
        op.drop_constraint(
            old_constraint,
            "social_accounts",
            type_="unique",
        )

    # Allow multiple accounts for the same platform,
    # as long as the account/page identity is different.
    op.create_unique_constraint(
        "uq_social_accounts_user_platform_page",
        "social_accounts",
        ["user_id", "platform", "page_id"],
    )


def downgrade() -> None:
    # Remove the new constraint.
    op.drop_constraint(
        "uq_social_accounts_user_platform_page",
        "social_accounts",
        type_="unique",
    )

    # Restore the old constraint.
    op.create_unique_constraint(
        "social_accounts_user_id_platform_key",
        "social_accounts",
        ["user_id", "platform"],
    )