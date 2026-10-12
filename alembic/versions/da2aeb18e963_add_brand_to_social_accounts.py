"""add brand to social accounts

Revision ID: da2aeb18e963
Revises: feb659ef10b1
"""

from alembic import op
import sqlalchemy as sa


revision = "da2aeb18e963"
down_revision = "feb659ef10b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add brand_id as nullable first.
    op.add_column(
        "social_accounts",
        sa.Column(
            "brand_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Add foreign key.
    op.create_foreign_key(
        "fk_social_accounts_brand_id",
        "social_accounts",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ---------------------------------------------------------
    # 1. Create a default/legacy brand for users who have
    #    social accounts but currently have no brand.
    # ---------------------------------------------------------
    op.execute(
        """
        INSERT INTO brands (
            name,
            slug,
            description,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            'Default Brand',
            'default-brand-' || sa.user_id,
            'Automatically created for existing social accounts',
            true,
            NOW(),
            NOW()
        FROM social_accounts sa
        WHERE NOT EXISTS (
            SELECT 1
            FROM user_brands ub
            WHERE ub.user_id = sa.user_id
        )
        GROUP BY sa.user_id
        """
    )

    # ---------------------------------------------------------
    # 2. Create user-brand memberships for those new brands.
    # ---------------------------------------------------------
    op.execute(
        """
        INSERT INTO user_brands (
            user_id,
            brand_id,
            role,
            is_default,
            created_at
        )
        SELECT
            sa.user_id,
            b.id,
            'owner',
            true,
            NOW()
        FROM social_accounts sa
        JOIN brands b
            ON b.slug = 'default-brand-' || sa.user_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM user_brands ub
            WHERE ub.user_id = sa.user_id
        )
        GROUP BY sa.user_id, b.id
        """
    )

    # ---------------------------------------------------------
    # 3. Assign every existing social account to the user's
    #    default brand.
    # ---------------------------------------------------------
    op.execute(
        """
        UPDATE social_accounts sa
        SET brand_id = ub.brand_id
        FROM user_brands ub
        WHERE ub.user_id = sa.user_id
          AND ub.is_default = true
        """
    )

    # ---------------------------------------------------------
    # 4. Now that every account has a brand, make brand_id
    #    mandatory.
    # ---------------------------------------------------------
    op.alter_column(
        "social_accounts",
        "brand_id",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_social_accounts_brand_id",
        "social_accounts",
        type_="foreignkey",
    )

    op.drop_column(
        "social_accounts",
        "brand_id",
    )