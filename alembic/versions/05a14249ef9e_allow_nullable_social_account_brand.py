"""allow nullable social account brand

Revision ID: YOUR_GENERATED_REVISION
Revises: da2aeb18e963
"""

from alembic import op
import sqlalchemy as sa


revision = "YOUR_GENERATED_REVISION"
down_revision = "da2aeb18e963"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "social_accounts",
        "brand_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "social_accounts",
        "brand_id",
        existing_type=sa.Integer(),
        nullable=False,
    )