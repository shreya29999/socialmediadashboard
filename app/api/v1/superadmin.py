from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_superadmin
from app.core.helpers import normalize_email
from app.core.utils import create_access_token, hash_password
from app.repositories.admin_repository import (
    get_admin_overview_detail,
    get_admins_overview,
    get_all_users,
)
from app.repositories.post_repository import get_all_posts_for_superadmin
from app.repositories.user_repository import (
    create_user,
    get_superadmin,
    get_user_by_email,
)
from app.schemas.auth import RegisterRequest
from app.schemas.superadmin import CreateAdminRequest


router = APIRouter(
    prefix="/superadmin",
    tags=["SuperAdmin"],
)


@router.post("/admins")
def create_admin_account(
    req: CreateAdminRequest,
    current_user: dict = Depends(get_current_superadmin),
):
    email = normalize_email(req.email)

    existing = get_user_by_email(email)

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    org_name = req.org_name.strip()

    if not org_name:
        raise HTTPException(
            status_code=400,
            detail="Organization name is required",
        )

    hashed = hash_password(req.password)

    user = create_user(
        email,
        hashed,
        role="admin",
        invite_code=req.invite_code,
        org_name=org_name,
        address=req.address,
    )

    return {
        "message": "Admin created successfully ✅",
        "user_id": user["id"],
        "email": user["email"],
        "invite_code": req.invite_code,
        "org_name": user["org_name"],
    }


@router.get("/organizations")
def superadmin_organizations(
    current_user: dict = Depends(get_current_superadmin),
):
    orgs = get_admins_overview()

    platform_totals = {}

    for org in orgs:
        for platform, count in (
            org["social_accounts"] or {}
        ).items():
            platform_totals[platform] = (
                platform_totals.get(platform, 0) + count
            )

    return {
        "organizations": orgs,
        "social_totals": platform_totals,
    }


@router.get("/organizations/{admin_id}")
def superadmin_organization_detail(
    admin_id: int,
    current_user: dict = Depends(get_current_superadmin),
):
    detail = get_admin_overview_detail(admin_id)

    if not detail:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return detail


@router.post("/create")
def create_superadmin_account(
    req: RegisterRequest,
):
    email = normalize_email(req.email)

    existing = get_superadmin()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="SuperAdmin already exists",
        )

    hashed = hash_password(req.password)

    user = create_user(
        email,
        hashed,
        role="superadmin",
    )

    token = create_access_token(
        user["id"],
        user["email"],
    )

    return {
        "message": "SuperAdmin created ✅",
        "access_token": token,
        "role": "superadmin",
    }


@router.get("/users")
def superadmin_get_users(
    current_user: dict = Depends(get_current_superadmin),
):
    users = get_all_users()

    return {
        "users": users,
        "total": len(users) if users else 0,
    }


@router.get("/posts")
def superadmin_get_all_posts(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_superadmin),
):
    posts = get_all_posts_for_superadmin(
        status_filter=status,
    )

    return {
        "posts": posts,
        "total": len(posts) if posts else 0,
    }