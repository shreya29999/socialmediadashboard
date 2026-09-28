from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user, get_actor_user
from app.core.config import BASE_URL, STATUS_LIST
from app.core.utils import (
    calculate_next_dates as calc_dates,
    generate_confirmation_token,
    generate_post_preview,
    hash_token,
)
from app.db.database import (
    approve_post,
    create_approval_stage,
    create_notification,
    create_post_template,
    create_scheduled_post,
    execute_query,
    get_post_by_id,
    get_posts_by_status,
    get_posts_by_status_for_admin,
    get_template_by_id,
    get_user_by_id,
    pause_template,
    resume_template,
    save_confirmation_token,
    update_post_status,
)
from app.schemas.posts import CreatePostRequest, UpdatePostRequest
from app.services.email import send_confirmation_email
from app.workers.tasks import publish_post_task

router = APIRouter(tags=["Posts"])


@router.post("/posts/")
def create_post(req: CreatePostRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    start   = datetime.fromisoformat(req.start_date.replace('Z', '+00:00'))
    end     = datetime.fromisoformat(req.end_date.replace('Z', '+00:00')) if req.end_date else None
    template = create_post_template(
        user_id         = user_id,
        content_text    = req.content_text,
        media_url       = req.media_url,
        platforms       = req.platforms,
        recurrence_type = req.recurrence_type,
        interval_days   = req.interval_days,
        start_date      = start,
        end_date        = end,
        max_occurrences = req.max_occurrences,
        timezone        = req.timezone
    )
    template_id = template["id"]
    dates = calc_dates(
        recurrence_type = req.recurrence_type,
        start_date      = start,
        interval_days   = req.interval_days,
        count           = 30,
        end_date        = end,
        max_occurrences = req.max_occurrences
    )
    created_posts = []
    for date in dates:
        post = create_scheduled_post(template_id, date)
        created_posts.append({"post_id": post["id"], "scheduled_at": date.isoformat()})

    return {
        "message"         : "Post scheduled successfully ✅",
        "template_id"     : template_id,
        "total_scheduled" : len(created_posts),
        "upcoming_posts"  : created_posts[:5]
    }


@router.get("/posts/")
def list_posts(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    if actor and actor.get("role") == "admin":
        if status:
            posts = get_posts_by_status_for_admin(actor["id"], status)
        else:
            posts = []
            for s in STATUS_LIST:
                posts.extend(get_posts_by_status_for_admin(actor["id"], s) or [])
        return {"posts": posts, "total": len(posts)}
    user_id = current_user["user_id"]
    if status:
        posts = get_posts_by_status(user_id, status)
    else:
        posts = []
        for s in STATUS_LIST:
            posts.extend(get_posts_by_status(user_id, s) or [])
    return {"posts": posts, "total": len(posts)}


@router.get("/posts/upcoming")
def get_upcoming_posts(current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    if actor and actor.get("role") == "admin":
        posts = get_posts_by_status_for_admin(actor["id"], "scheduled")
    else:
        posts = get_posts_by_status(current_user["user_id"], "scheduled")
    upcoming = []
    for post in (posts or []):
        scheduled_at = post.get("scheduled_at")
        if hasattr(scheduled_at, "isoformat"):
            scheduled_at = scheduled_at.isoformat()
        content = (post.get("content_text") or "")
        if len(content) > 50:
            content = content[:50].rstrip() + "..."
        upcoming.append({
            "post_id": post.get("id"),
            "scheduled_at": scheduled_at,
            "content": content
        })
    return {"upcoming": upcoming, "total": len(posts) if posts else 0}


@router.get("/posts/{post_id}")
def get_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    return post


@router.put("/posts/{post_id}")
def edit_post(post_id: int, req: UpdatePostRequest, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] not in ("scheduled", "awaiting_hr_approval"):
        raise HTTPException(status_code=400, detail=f"Cannot edit post with status: {post['status']}")

    updates = []
    params  = []

    if req.content_text is not None:
        updates.append("content_text = %s")
        params.append(req.content_text)
        execute_query(
            "UPDATE post_templates SET content_text = %s WHERE id = %s",
            (req.content_text, post["template_id"])
        )

    if req.media_url is not None:
        updates.append("media_url = %s")
        params.append(req.media_url)
        execute_query(
            "UPDATE post_templates SET media_url = %s WHERE id = %s",
            (req.media_url, post["template_id"])
        )

    if req.platforms is not None:
        updates.append("platforms = %s")
        params.append(req.platforms)
        execute_query(
            "UPDATE post_templates SET platforms = %s WHERE id = %s",
            (req.platforms, post["template_id"])
        )

    if req.scheduled_at is not None:
        new_dt = datetime.fromisoformat(req.scheduled_at.replace('Z', '+00:00'))
        updates.append("scheduled_at = %s")
        params.append(new_dt)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("status = %s")
    params.append("scheduled")
    updates.append("confirmation_token = NULL")
    updates.append("confirmation_sent_at = NULL")
    updates.append("token_used = FALSE")
    params.append(post_id)
    execute_query(
        f"UPDATE scheduled_posts SET {', '.join(updates)} WHERE id = %s",
        tuple(params)
    )
    return {"message": f"Post {post_id} updated ✅", "post_id": post_id}


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] == "posted":
        raise HTTPException(status_code=400, detail="Cannot delete an already published post")
    execute_query("DELETE FROM post_targets WHERE scheduled_post_id = %s", (post_id,))
    execute_query("DELETE FROM scheduled_posts WHERE id = %s",     (post_id,))

    return {"message": f"Post {post_id} deleted ✅"}


@router.post("/posts/{post_id}/publish")
def publish_now(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post.get("reposted_from_id"):
        raise HTTPException(
            status_code=400,
            detail="Reposts can only be approved via the confirmation link emailed to you, not published directly."
        )
    if post["status"] == "posted":
        raise HTTPException(status_code=400, detail="Post already published")
    if post["status"] == "posting":
        raise HTTPException(status_code=400, detail="Post is currently being published")
    approve_post(post_id)
    publish_post_task.delay(post_id)
    return {"message": f"Post {post_id} queued for immediate publishing ✅", "post_id": post_id}


@router.patch("/posts/{post_id}/skip")
def skip_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] != "scheduled":
        raise HTTPException(status_code=400, detail=f"Cannot skip post with status: {post['status']}")
    update_post_status(post_id, "skipped")
    return {"message": f"Post {post_id} skipped ✅"}


@router.patch("/posts/{post_id}/retry")
def retry_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] not in ("failed", "expired"):
        raise HTTPException(status_code=400, detail=f"Can only retry failed/expired posts")
    approve_post(post_id)
    publish_post_task.delay(post_id)
    return {"message": f"Post {post_id} queued for retry ✅"}


@router.patch("/templates/{template_id}/pause")
def pause_automation(template_id: int, current_user: dict = Depends(get_current_user)):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your template")
    pause_template(template_id)
    return {"message": "Automation paused ⏸️"}


@router.patch("/templates/{template_id}/resume")
def resume_automation(template_id: int, current_user: dict = Depends(get_current_user)):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your template")
    resume_template(template_id)
    return {"message": "Automation resumed ▶️"}


@router.get("/posts/{post_id}/preview")
def preview_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    preview = generate_post_preview(post)
    return {"post_id": post_id, "preview": preview}


@router.post("/posts/{post_id}/repost")
def repost(post_id: int, req: CreatePostRequest, current_user: dict = Depends(get_current_user)):
    original = get_post_by_id(post_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original post not found")
    if original["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if original["status"] != "posted":
        raise HTTPException(status_code=400, detail="Can only repost published posts")
    user_id = current_user["user_id"]
    start   = datetime.fromisoformat(req.start_date.replace('Z', '+00:00'))
    end     = datetime.fromisoformat(req.end_date.replace('Z', '+00:00')) if req.end_date else None
    template = create_post_template(
        user_id         = user_id,
        content_text    = req.content_text,
        media_url       = req.media_url,
        platforms       = req.platforms,
        recurrence_type = req.recurrence_type,
        interval_days   = req.interval_days,
        start_date      = start,
        end_date        = end,
        max_occurrences = req.max_occurrences,
        timezone        = req.timezone
    )
    post = create_scheduled_post(
        template["id"], start, reposted_from_id=post_id
    )
    new_post_id = post["id"]
    create_approval_stage(new_post_id)
    owner     = get_user_by_id(user_id)
    raw_token = generate_confirmation_token()
    hashed    = hash_token(raw_token)
    save_confirmation_token(new_post_id, hashed)
    update_post_status(new_post_id, "awaiting_hr_approval")
    approve_url  = f"{BASE_URL}/approvals/{new_post_id}/hr-approve?token={raw_token}"
    reject_url   = f"{BASE_URL}/approvals/{new_post_id}/hr-reject?token={raw_token}"
    scheduled_str = start.strftime("%B %d, %Y at %I:%M %p UTC")

    send_confirmation_email(
        to_email     = owner["email"],
        post_content = req.content_text,
        platforms    = req.platforms,
        scheduled_at = scheduled_str,
        approve_url  = approve_url,
        reject_url   = reject_url
    )
    create_notification(
        user_id = user_id,
        type    = "hr_approval_requested",
        title   = "Repost awaiting your approval",
        message = f"Your repost scheduled for {scheduled_str} needs approval before it goes live.",
        link    = f"/posts/{new_post_id}",
        post_id = new_post_id
    )

    return {
        "message"         : "Repost created ✅ Check your email (or the Pending Approval section) to approve it.",
        "new_post_id"     : new_post_id,
        "reposted_from"   : post_id,
        "scheduled_at"    : start.isoformat()
    }
