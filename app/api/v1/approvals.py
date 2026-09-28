from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import (
    get_current_admin,
    get_current_user,
    require_owning_admin,
)
from app.core.utils import verify_confirmation_token
from app.db.database import (
    admin_final_approve,
    admin_final_reject,
    execute_query,
    get_post_by_id,
    get_posts_awaiting_admin_approval,
    update_hr_approval,
)
from app.schemas.auth import RejectRequest
from app.workers.tasks import _escalate_to_admin

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("/{post_id}/hr-approve")
def hr_approve(post_id: int, token: str = Query(...)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    execute_query("UPDATE scheduled_posts SET token_used = TRUE WHERE id = %s", (post_id,))
    update_hr_approval(post_id, "approved")
    _escalate_to_admin(post_id, hr_status="approved")
    return {"message": "HR approved ✅ Post sent to Admin for final review.", "post_id": post_id}


@router.post("/{post_id}/hr-reject")
def hr_reject(post_id: int, req: RejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(req.token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    execute_query("UPDATE scheduled_posts SET token_used = TRUE WHERE id = %s", (post_id,))
    update_hr_approval(post_id, "rejected", req.reason)
    _escalate_to_admin(post_id, hr_status="rejected", hr_reason=req.reason)
    return {"message": "HR rejected. Escalated to Admin for final decision.", "post_id": post_id}


@router.get("/{post_id}/admin-approve")
def admin_approve_email(post_id: int, token: str = Query(...)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(token, post["admin_token"]):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if post["admin_token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    admin_final_approve(post_id)
    return {"message": "Admin approved ✅ Post is being published!", "post_id": post_id}


@router.post("/{post_id}/admin-reject")
def admin_reject_email(post_id: int, req: RejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_admin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(req.token, post["admin_token"]):
        raise HTTPException(status_code=400, detail="Invalid token")
    if post["admin_token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    admin_final_reject(post_id, req.reason)
    return {"message": "Admin rejected ❌ Post cancelled.", "post_id": post_id}
