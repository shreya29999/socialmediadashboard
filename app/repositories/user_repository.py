from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, UserProfile
from app.db.session import SessionLocal

def create_user(
    email: str,
    password_hash: str,
    role: str = "user",
    admin_id: int | None = None,
    invite_code: str | None = None,
    org_name: str | None = None,
    address: str | None = None,
):
    with SessionLocal() as db:
        user = User(
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
            admin_id=admin_id,
            invite_code=invite_code,
            org_name=org_name,
            address=address,
        )

        db.add(user)
        db.flush()

        profile = UserProfile(
            user_id=user.id,
        )

        db.add(profile)
        db.commit()

        db.refresh(user)
        db.refresh(profile)

        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "admin_id": user.admin_id,
            "invite_code": user.invite_code,
            "org_name": user.org_name,
            "address": user.address,
        }


def get_user_by_email(email: str):
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.email == email.strip().lower())
        ).scalar_one_or_none()
        if not user:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "timezone": user.timezone,
            "role": user.role,
            "admin_id": user.admin_id,
            "invite_code": user.invite_code,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "org_name": user.org_name,
            "address": user.address,
        }


def get_user_by_id(user_id: int):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "timezone": user.timezone,
            "role": user.role,
            "admin_id": user.admin_id,
            "invite_code": user.invite_code,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }


def get_user_profile(user_id: int):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()
        if not profile:
            return None
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "persona": profile.persona,
            "industry": profile.industry,
            "brand_name": profile.brand_name,
            "logo_url": profile.logo_url,
            "footer_enabled": profile.footer_enabled,
            "footer_text": profile.footer_text,
            "footer_url": profile.footer_url,
            "overlay_text": profile.overlay_text,
            "overlay_position": profile.overlay_position,
            "overlay_text_size": profile.overlay_text_size,
            "tone": profile.tone,
            "audience": profile.audience,
            "country_code": profile.country_code,
            "language": profile.language,
            "posts_per_week": profile.posts_per_week,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }


def get_users_with_complete_profiles():
    with SessionLocal() as db:
        user_ids = db.execute(
            select(UserProfile.user_id).where(
                UserProfile.persona.is_not(None),
                UserProfile.industry.is_not(None),
                UserProfile.brand_name.is_not(None),
                UserProfile.tone.is_not(None),
                UserProfile.country_code.is_not(None),
            )
        ).scalars().all()
        return [{"user_id": user_id} for user_id in user_ids]


def update_last_login(user_id: int):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        user.last_login_at = datetime.utcnow()
        db.commit()
        return {"id": user.id, "last_login_at": user.last_login_at}



def get_admins():
    with SessionLocal() as db:
        admins = db.execute(
            select(User).where(User.role == "admin")
        ).scalars().all()

        return [
            {
                "id": admin.id,
                "email": admin.email,
                "role": admin.role,
                "admin_id": admin.admin_id,
                "invite_code": admin.invite_code,
                "org_name": admin.org_name,
                "address": admin.address,
            }
            for admin in admins
        ]

def save_user_profile(
    user_id: int,
    persona: str | None,
    industry: str | None,
    brand_name: str | None,
    logo_url: str | None,
    tone: str | None,
    audience: str | None,
    country_code: str | None,
    language: str | None,
    posts_per_week: int,
):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id
            )
        ).scalar_one_or_none()

        if profile:
            profile.persona = persona
            profile.industry = industry
            profile.brand_name = brand_name
            profile.logo_url = logo_url
            profile.tone = tone
            profile.audience = audience
            profile.country_code = country_code
            profile.language = language
            profile.posts_per_week = posts_per_week
        else:
            profile = UserProfile(
                user_id=user_id,
                persona=persona,
                industry=industry,
                brand_name=brand_name,
                logo_url=logo_url,
                tone=tone,
                audience=audience,
                country_code=country_code,
                language=language,
                posts_per_week=posts_per_week,
            )
            db.add(profile)

        db.commit()
        db.refresh(profile)

        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "persona": profile.persona,
            "industry": profile.industry,
            "brand_name": profile.brand_name,
            "logo_url": profile.logo_url,
            "footer_enabled": profile.footer_enabled,
            "footer_text": profile.footer_text,
            "footer_url": profile.footer_url,
            "tone": profile.tone,
            "audience": profile.audience,
            "country_code": profile.country_code,
            "language": profile.language,
            "posts_per_week": profile.posts_per_week,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }  

def update_user_logo(user_id: int, logo_url: str):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id
            )
        ).scalar_one_or_none()

        if not profile:
            return None

        profile.logo_url = logo_url

        db.commit()
        db.refresh(profile)

        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "logo_url": profile.logo_url,
        }

def update_user_footer(user_id: int, footer_url: str):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id
            )
        ).scalar_one_or_none()

        if not profile:
            return None

        profile.footer_url = footer_url
        profile.footer_enabled = True

        db.commit()
        db.refresh(profile)

        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "footer_enabled": profile.footer_enabled,
            "footer_url": profile.footer_url,
        }

def update_user_overlay(
    user_id: int,
    overlay_text: str | None,
    overlay_position: str,
    overlay_text_size: int,
):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id
            )
        ).scalar_one_or_none()

        if not profile:
            return None

        profile.overlay_text = overlay_text
        profile.overlay_position = overlay_position
        profile.overlay_text_size = overlay_text_size

        db.commit()
        db.refresh(profile)

        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "overlay_text": profile.overlay_text,
            "overlay_position": profile.overlay_position,
            "overlay_text_size": profile.overlay_text_size,
        }

def get_superadmin():
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.role == "superadmin")
        ).scalar_one_or_none()

        if not user:
            return None

        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "admin_id": user.admin_id,
            "invite_code": user.invite_code,
            "org_name": user.org_name,
            "address": user.address,
            "created_at": user.created_at,
        }
