"""add overlay text size

Revision ID: d3dfa5674ad4
Revises: aa2a0629abe1
Create Date: 2026-10-05 12:28:58.802288
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3dfa5674ad4'
down_revision = 'aa2a0629abe1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "overlay_text_size",
            sa.Integer(),
            server_default="48",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "user_profiles",
        "overlay_text_size",
    )