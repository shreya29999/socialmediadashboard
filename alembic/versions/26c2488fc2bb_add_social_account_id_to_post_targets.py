"""add social_account_id to post_targets

Revision ID: 26c2488fc2bb
Revises: 
Create Date: 2026-10-12 16:42:16.565577
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26c2488fc2bb'
down_revision = None       # ⭐ Adjust to your previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─────────────────────────────────────────────
    # 1. Add social_account_id to post_targets
    #    (nullable=True because existing rows don't have values)
    # ─────────────────────────────────────────────
    op.add_column(
        'post_targets',
        sa.Column(
            'social_account_id',
            sa.Integer(),
            nullable=True,        # ⭐ Changed from False
        )
    )

    # ─────────────────────────────────────────────
    # 2. Add named foreign key (not None)
    # ─────────────────────────────────────────────
    op.create_foreign_key(
        'fk_post_targets_social_account',    # ⭐ Named constraint
        'post_targets',
        'social_accounts',
        ['social_account_id'],
        ['id'],
        ondelete='SET NULL',                 # ⭐ SET NULL, not CASCADE
    )


def downgrade() -> None:
    # Drop named foreign key
    op.drop_constraint(
        'fk_post_targets_social_account',    # ⭐ Named constraint
        'post_targets',
        type_='foreignkey',
    )

    # Drop column
    op.drop_column('post_targets', 'social_account_id')