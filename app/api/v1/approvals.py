from fastapi import APIRouter, HTTPException, Query

from app.core.utils import verify_confirmation_token

from app.repositories.post_repository import (
    get_post_by_id,
    mark_token_used,
    approve_post,
)

from app.repositories.approval_repository import (
    admin_final_approve,
    admin_final_reject,
    update_hr_approval,
)

from app.schemas.auth import RejectRequest


router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"],
)


# ============================================================
# HR APPROVE
# ============================================================

@router.get("/{post_id}/hr-approve")
def hr_approve(
    post_id: int,
    token: str = Query(...),
):
    post = get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Post is not awaiting HR approval. Current status: {post['status']}",
        )

    if not verify_confirmation_token(
        token,
        post["confirmation_token"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token",
        )

    if post["token_used"]:
        raise HTTPException(
            status_code=400,
            detail="Token already used",
        )

    # Mark HR confirmation token as used
    mark_token_used(post_id)

    # Update HR approval status
    update_hr_approval(
        post_id,
        "approved",
    )

    # Mark post as approved
    # The publishing worker will publish it
    # when scheduled_at is reached.
    approve_post(post_id)

    return {
        "message": (
            "HR approved successfully. "
            "Post will be published at the scheduled time."
        ),
        "post_id": post_id,
        "scheduled_at": post["scheduled_at"],
    }


# ============================================================
# HR REJECT
# ============================================================

@router.post("/{post_id}/hr-reject")
def hr_reject(
    post_id: int,
    req: RejectRequest,
):
    post = get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Post status is: {post['status']}",
        )

    if not verify_confirmation_token(
        req.token,
        post["confirmation_token"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid token",
        )

    if post["token_used"]:
        raise HTTPException(
            status_code=400,
            detail="Token already used",
        )

    # Mark token as used
    mark_token_used(post_id)

    # Update HR status to rejected
    update_hr_approval(
        post_id,
        "rejected",
        req.reason,
    )

    return {
        "message": "HR rejected the post.",
        "post_id": post_id,
        "reason": req.reason,
    }


# ============================================================
# ADMIN APPROVE
# ============================================================
# Kept for compatibility with the existing application.
# It is no longer part of the normal HR approval flow.
# ============================================================

@router.get("/{post_id}/admin-approve")
def admin_approve_email(
    post_id: int,
    token: str = Query(...),
):
    post = get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Post status is: {post['status']}",
        )

    if not verify_confirmation_token(
        token,
        post["admin_token"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token",
        )

    if post["admin_token_used"]:
        raise HTTPException(
            status_code=400,
            detail="Token already used",
        )

    admin_final_approve(post_id)

    return {
        "message": "Admin approved. Post is being published.",
        "post_id": post_id,
    }


# ============================================================
# ADMIN REJECT
# ============================================================

@router.post("/{post_id}/admin-reject")
def admin_reject_email(
    post_id: int,
    req: RejectRequest,
):
    post = get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Post status is: {post['status']}",
        )

    if not verify_confirmation_token(
        req.token,
        post["admin_token"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid token",
        )

    if post["admin_token_used"]:
        raise HTTPException(
            status_code=400,
            detail="Token already used",
        )

    admin_final_reject(
        post_id,
        req.reason,
    )

    return {
        "message": "Admin rejected. Post cancelled.",
        "post_id": post_id,
        "reason": req.reason,
    }