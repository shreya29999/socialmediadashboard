from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.utils import verify_access_token
from app.db.database import get_user_by_id


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return payload


def get_current_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user = get_user_by_id(payload["user_id"])

    if not user or user["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="SuperAdmin access required",
        )

    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    user = get_user_by_id(payload["user_id"])

    if not user or user["role"] not in {"admin", "superadmin"}:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return payload


def get_actor_user(current_user: dict):
    return get_user_by_id(current_user["user_id"])


def require_owning_admin(post: dict, current_user: dict):
    actor = get_actor_user(current_user)

    if not actor:
        raise HTTPException(status_code=403, detail="Not authorized")

    if actor["role"] == "superadmin":
        raise HTTPException(
            status_code=403,
            detail=(
                "SuperAdmin has view-only oversight and cannot "
                "approve or reject posts"
            ),
        )

    owner = get_user_by_id(post["user_id"])

    if (
        actor["role"] != "admin"
        or not owner
        or owner.get("admin_id") != actor["id"]
    ):
        raise HTTPException(
            status_code=403,
            detail="Not your team's post",
        )


def can_access_resource(resource_user_id: int, current_user: dict) -> bool:
    actor = get_actor_user(current_user)

    if not actor:
        return False

    if actor["role"] == "superadmin":
        return True

    if actor["role"] == "admin":
        owner = get_user_by_id(resource_user_id)
        return bool(owner and owner.get("admin_id") == actor["id"])

    return resource_user_id == current_user["user_id"]
