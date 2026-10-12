"""add brand_id to social_accounts unique constraint

Revision ID: 4a255124e4f3
Revises: fd3268337be6
Create Date: 2026-10-12 17:16:52.023401
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a255124e4f3'
down_revision = 'fd3268337be6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Update social_accounts unique constraint:
    - OLD: (user_id, platform, page_id)
    - NEW: (user_id, brand_id, platform, page_id)

    Why: Allow same social account to be connected to
    multiple brands (or user-scoped + brand-scoped).
    """
    # Drop old constraint
    op.drop_constraint(
        'uq_social_accounts_user_platform_page',
        'social_accounts',
        type_='unique',
    )

    # Add new constraint with brand_id
    op.create_unique_constraint(
        'uq_social_accounts_user_brand_platform_page',
        'social_accounts',
        ['user_id', 'brand_id', 'platform', 'page_id'],
    )


def downgrade() -> None:
    """
    Revert back to old constraint.
    """
    # Drop new constraint
    op.drop_constraint(
        'uq_social_accounts_user_brand_platform_page',
        'social_accounts',
        type_='unique',
    )

    # Recreate old constraint
    op.create_unique_constraint(
        'uq_social_accounts_user_platform_page',
        'social_accounts',
        ['user_id', 'platform', 'page_id'],
    )