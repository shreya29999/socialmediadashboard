"""add brands and user brand memberships

Revision ID: feb659ef10b1
Revises: a95eb1149b56
Create Date: 2026-10-09 16:51:08.762978
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "feb659ef10b1"
down_revision = "a95eb1149b56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # Create brands table
    # ---------------------------------------------------------
    op.create_table(
        "brands",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            index=True,
        ),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "slug",
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "logo_url",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "slug",
            name="uq_brands_slug",
        ),
    )

    # ---------------------------------------------------------
    # Create user_brands table
    # ---------------------------------------------------------
    op.create_table(
        "user_brands",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            sa.Integer(),
            sa.ForeignKey(
                "brands.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
            server_default="owner",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "brand_id",
            name="uq_user_brand",
        ),
    )

    # ---------------------------------------------------------
    # Ensure only one default brand per user
    # ---------------------------------------------------------
    op.create_index(
        "uq_user_brands_one_default",
        "user_brands",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_default = true"
        ),
    )


def downgrade() -> None:
    # ---------------------------------------------------------
    # Remove one-default-brand constraint
    # ---------------------------------------------------------
    op.drop_index(
        "uq_user_brands_one_default",
        table_name="user_brands",
    )

    # ---------------------------------------------------------
    # Remove user-brand relationships
    # ---------------------------------------------------------
    op.drop_table("user_brands")

    # ---------------------------------------------------------
    # Remove brands
    # ---------------------------------------------------------
    op.drop_table("brands")