"""enable existing user footers

Revision ID: aa2a0629abe1
Revises: fa2418e7ca63
Create Date: 2026-10-05 11:23:17.900910
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aa2a0629abe1'
down_revision = 'fa2418e7ca63'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        UPDATE user_profiles
        SET footer_enabled = TRUE
        WHERE footer_url IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE user_profiles
        SET footer_enabled = FALSE
        WHERE footer_url IS NOT NULL;
    """)