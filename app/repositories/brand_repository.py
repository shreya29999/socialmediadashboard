from sqlalchemy import select

from app.db.models import Brand, UserBrand
from app.db.session import SessionLocal


def create_brand(
    user_id: int,
    name: str,
    slug: str,
    description: str | None = None,
    logo_url: str | None = None,
):
    with SessionLocal() as db:
        # Check whether the user already has a brand.
        existing_membership = db.execute(
            select(UserBrand).where(
                UserBrand.user_id == user_id
            )
        ).scalars().first()

        # The first brand created by the user
        # automatically becomes the default brand.
        is_default = existing_membership is None

        brand = Brand(
            name=name,
            slug=slug,
            description=description,
            logo_url=logo_url,
            is_active=True,
        )

        db.add(brand)
        db.flush()

        membership = UserBrand(
            user_id=user_id,
            brand_id=brand.id,
            role="owner",
            is_default=is_default,
        )

        db.add(membership)

        db.commit()
        db.refresh(brand)

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "description": brand.description,
            "logo_url": brand.logo_url,
            "is_active": brand.is_active,
            "role": membership.role,
            "is_default": membership.is_default,
            "created_at": brand.created_at,
            "updated_at": brand.updated_at,
        }


def get_brands(user_id: int):
    with SessionLocal() as db:
        stmt = (
            select(Brand, UserBrand)
            .join(
                UserBrand,
                UserBrand.brand_id == Brand.id,
            )
            .where(
                UserBrand.user_id == user_id,
                Brand.is_active.is_(True),
            )
            .order_by(
                UserBrand.is_default.desc(),
                Brand.created_at.asc(),
            )
        )

        rows = db.execute(stmt).all()

        return [
            {
                "id": brand.id,
                "name": brand.name,
                "slug": brand.slug,
                "description": brand.description,
                "logo_url": brand.logo_url,
                "is_active": brand.is_active,
                "role": membership.role,
                "is_default": membership.is_default,
                "created_at": brand.created_at,
                "updated_at": brand.updated_at,
            }
            for brand, membership in rows
        ]


def get_brand_by_id(
    user_id: int,
    brand_id: int,
):
    with SessionLocal() as db:
        stmt = (
            select(Brand, UserBrand)
            .join(
                UserBrand,
                UserBrand.brand_id == Brand.id,
            )
            .where(
                UserBrand.user_id == user_id,
                UserBrand.brand_id == brand_id,
                Brand.is_active.is_(True),
            )
        )

        row = db.execute(stmt).first()

        if row is None:
            return None

        brand, membership = row

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "description": brand.description,
            "logo_url": brand.logo_url,
            "is_active": brand.is_active,
            "role": membership.role,
            "is_default": membership.is_default,
            "created_at": brand.created_at,
            "updated_at": brand.updated_at,
        }


def get_default_brand(user_id: int):
    with SessionLocal() as db:
        stmt = (
            select(Brand, UserBrand)
            .join(
                UserBrand,
                UserBrand.brand_id == Brand.id,
            )
            .where(
                UserBrand.user_id == user_id,
                UserBrand.is_default.is_(True),
                Brand.is_active.is_(True),
            )
        )

        row = db.execute(stmt).first()

        if row is None:
            return None

        brand, membership = row

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "description": brand.description,
            "logo_url": brand.logo_url,
            "is_active": brand.is_active,
            "role": membership.role,
            "is_default": membership.is_default,
            "created_at": brand.created_at,
            "updated_at": brand.updated_at,
        }


def set_default_brand(
    user_id: int,
    brand_id: int,
):
    with SessionLocal() as db:
        membership = db.execute(
            select(UserBrand).where(
                UserBrand.user_id == user_id,
                UserBrand.brand_id == brand_id,
            )
        ).scalar_one_or_none()

        if membership is None:
            return None

        # Remove default status from all user's brands.
        user_memberships = db.execute(
            select(UserBrand).where(
                UserBrand.user_id == user_id
            )
        ).scalars().all()

        for item in user_memberships:
            item.is_default = False

        # Set the selected brand as default.
        membership.is_default = True

        db.commit()

        brand = db.get(Brand, brand_id)

        if brand is None:
            return None

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "description": brand.description,
            "logo_url": brand.logo_url,
            "is_active": brand.is_active,
            "role": membership.role,
            "is_default": membership.is_default,
            "created_at": brand.created_at,
            "updated_at": brand.updated_at,
        }


def update_brand(
    user_id: int,
    brand_id: int,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    logo_url: str | None = None,
):
    with SessionLocal() as db:
        stmt = (
            select(Brand)
            .join(
                UserBrand,
                UserBrand.brand_id == Brand.id,
            )
            .where(
                UserBrand.user_id == user_id,
                UserBrand.brand_id == brand_id,
                Brand.is_active.is_(True),
            )
        )

        brand = db.execute(stmt).scalar_one_or_none()

        if brand is None:
            return None

        if name is not None:
            brand.name = name

        if slug is not None:
            brand.slug = slug

        if description is not None:
            brand.description = description

        if logo_url is not None:
            brand.logo_url = logo_url

        db.commit()
        db.refresh(brand)

        membership = db.execute(
            select(UserBrand).where(
                UserBrand.user_id == user_id,
                UserBrand.brand_id == brand_id,
            )
        ).scalar_one()

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "description": brand.description,
            "logo_url": brand.logo_url,
            "is_active": brand.is_active,
            "role": membership.role,
            "is_default": membership.is_default,
            "created_at": brand.created_at,
            "updated_at": brand.updated_at,
        }


def delete_brand(
    user_id: int,
    brand_id: int,
):
    with SessionLocal() as db:
        membership = db.execute(
            select(UserBrand).where(
                UserBrand.user_id == user_id,
                UserBrand.brand_id == brand_id,
            )
        ).scalar_one_or_none()

        if membership is None:
            return None

        brand = db.get(Brand, brand_id)

        if brand is None:
            return None

        was_default = membership.is_default

        db.delete(brand)
        db.flush()

        # If the deleted brand was the default,
        # make another available brand the default.
        if was_default:
            remaining_membership = db.execute(
                select(UserBrand)
                .where(
                    UserBrand.user_id == user_id
                )
                .order_by(
                    UserBrand.created_at.asc()
                )
            ).scalars().first()

            if remaining_membership:
                remaining_membership.is_default = True

        db.commit()

        return {
            "id": brand_id,
            "deleted": True,
        }