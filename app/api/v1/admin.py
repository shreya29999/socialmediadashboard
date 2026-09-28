from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_current_admin,
    get_actor_user,
    require_owning_admin,
)
from app.core.helpers import normalize_email
from app.core.utils import hash_password
from app.db.database import (
    admin_final_approve,
    admin_final_reject,
    create_user,
    get_all_users,
    get_post_by_id,
    get_posts_awaiting_admin_approval,
    get_user_by_email,
    get_user_by_id,
    get_users_for_admin,
)
from app.schemas.admin import CreateManagedUserRequest
from app.schemas.auth import RejectRequest

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/users")
def admin_create_user(req: CreateManagedUserRequest, current_user: dict = Depends(get_current_admin)):
    actor = get_actor_user(current_user)
    if not actor or actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    email = normalize_email(req.email)
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    user = create_user(email, hashed, role="user", admin_id=actor["id"])
    return {
        "message": "User created successfully ✅",
        "user_id": user["id"],
        "email": user["email"],
        "password": req.password,
        "admin_id": actor["id"]
    }


@router.get("/users")
def admin_get_users(current_user: dict = Depends(get_current_admin)):
    user = get_user_by_id(current_user["user_id"])
    if user and user["role"] == "superadmin":
        users = get_all_users()
    else:
        users = get_users_for_admin(user["id"])
    return {"users": users, "total": len(users) if users else 0}


@router.get("/pending")
def admin_get_pending(current_user: dict = Depends(get_current_admin)):
    actor = get_actor_user(current_user)
    if actor["role"] == "superadmin":
        posts = get_posts_awaiting_admin_approval()          
    else:
        posts = get_posts_awaiting_admin_approval(actor["id"])  
    return {"pending": posts, "count": len(posts) if posts else 0}


@router.post("/posts/{post_id}/approve")
def admin_approve_dashboard(post_id: int, current_user: dict = Depends(get_current_admin)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    require_owning_admin(post, current_user)
    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    admin_final_approve(post_id)
    return {"message": f"Post {post_id} approved and queued for publishing ✅"}


@router.post("/posts/{post_id}/reject")
def admin_reject_dashboard(post_id: int, req: RejectRequest, current_user: dict = Depends(get_current_admin)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    require_owning_admin(post, current_user)
    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    admin_final_reject(post_id, req.reason)
    return {"message": f"Post {post_id} rejected ❌", "reason": req.reason}
