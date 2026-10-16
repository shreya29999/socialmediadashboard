"""add branding fields to user_profiles

Revision ID: 558a1d64c37c
Revises: 46ec2c316048
Create Date: 2026-10-15 XX:XX:XX.XXXXXX
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '558a1d64c37c'
down_revision = '46ec2c316048'         # ⭐ Adjust to your previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add branding fields to user_profiles:
      - Logo size + position
      - Footer size + position
      - Overlay text color
    """

    # ⭐ Logo size + position
    op.add_column(
        'user_profiles',
        sa.Column(
            'logo_size',
            sa.Integer(),
            nullable=True,
            server_default='60',
        ),
    )
    op.add_column(
        'user_profiles',
        sa.Column(
            'logo_position_x',
            sa.Integer(),
            nullable=True,
            server_default='4',
        ),
    )
    op.add_column(
        'user_profiles',
        sa.Column(
            'logo_position_y',
            sa.Integer(),
            nullable=True,
            server_default='4',
        ),
    )

    # ⭐ Footer size + position
    op.add_column(
        'user_profiles',
        sa.Column(
            'footer_height',
            sa.Integer(),
            nullable=True,
            server_default='60',
        ),
    )
    op.add_column(
        'user_profiles',
        sa.Column(
            'footer_width',
            sa.Integer(),
            nullable=True,
            server_default='100',
        ),
    )
    op.add_column(
        'user_profiles',
        sa.Column(
            'footer_position_x',
            sa.Integer(),
            nullable=True,
            server_default='0',
        ),
    )
    op.add_column(
        'user_profiles',
        sa.Column(
            'footer_position_y',
            sa.Integer(),
            nullable=True,
            server_default='0',
        ),
    )

    # ⭐ Overlay text color
    op.add_column(
        'user_profiles',
        sa.Column(
            'overlay_color',
            sa.String(length=20),
            nullable=True,
            server_default='#ffffff',
        ),
    )


def downgrade() -> None:
    """Remove branding fields from user_profiles."""

    op.drop_column('user_profiles', 'overlay_color')
    op.drop_column('user_profiles', 'footer_position_y')
    op.drop_column('user_profiles', 'footer_position_x')
    op.drop_column('user_profiles', 'footer_width')
    op.drop_column('user_profiles', 'footer_height')
    op.drop_column('user_profiles', 'logo_position_y')
    op.drop_column('user_profiles', 'logo_position_x')
    op.drop_column('user_profiles', 'logo_size')