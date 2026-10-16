"""widen persona/industry/tone/audience to Text

Revision ID: 46ec2c316048
Revises: 4a255124e4f3
Create Date: 2026-10-15 XX:XX:XX.XXXXXX
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46ec2c316048'
down_revision = '4a255124e4f3'         # ⭐ Adjust to your previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Widen persona/industry/tone/audience to Text
    to support multi-select comma-separated values.
    """
    op.alter_column(
        'user_profiles',
        'persona',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'industry',
        existing_type=sa.VARCHAR(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'tone',
        existing_type=sa.VARCHAR(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'audience',
        existing_type=sa.VARCHAR(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert back to VARCHAR."""
    op.alter_column(
        'user_profiles',
        'persona',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'industry',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'tone',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        'user_profiles',
        'audience',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=100),
        existing_nullable=True,
    )