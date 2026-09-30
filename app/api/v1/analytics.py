from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import (
    get_current_user,
    get_actor_user,
)
from app.core.config import STATUS_LIST
from app.repositories.post_repository import (
    get_posts_by_status,
    get_posts_by_status_for_admin,
)
router = APIRouter(
    tags=["Analytics"],
)

@router.get("/analytics")
def get_analytics(
    current_user: dict = Depends(get_current_user),
):
    actor = get_actor_user(current_user)

    if not actor:
        raise HTTPException(
            status_code=403,
            detail="User information not found",
        )

    counts = {}
    all_posts = []

    if actor.get("role") == "admin":
        for status in STATUS_LIST:
            posts = get_posts_by_status_for_admin(
                actor["id"],
                status,
            ) or []

            counts[status] = len(posts)
            all_posts.extend(posts)

    else:
        user_id = current_user["user_id"]

        for status in STATUS_LIST:
            posts = get_posts_by_status(
                user_id,
                status,
            ) or []

            counts[status] = len(posts)
            all_posts.extend(posts)

    platform_stats = {
        "facebook": 0,
        "instagram": 0,
        "linkedin": 0,
    }

    for post in all_posts:
        for platform in post.get("platforms") or []:
            if platform in platform_stats:
                platform_stats[platform] += 1

    total = len(all_posts)

    posted_count = counts.get("posted", 0)
    failed_count = counts.get("failed", 0)

    success_rate = round(
        (
            posted_count
            / max(posted_count + failed_count, 1)
        ) * 100,
        1,
    )

    return {
        "summary": {
            "total": total,
            "posted": posted_count,
            "scheduled": counts.get("scheduled", 0),
            "awaiting_hr_approval": counts.get(
                "awaiting_hr_approval",
                0,
            ),
            "awaiting_admin_approval": counts.get(
                "awaiting_admin_approval",
                0,
            ),
            "failed": failed_count,
            "expired": counts.get("expired", 0),
            "cancelled": counts.get("cancelled", 0),
            "skipped": counts.get("skipped", 0),
        },
        "platforms": platform_stats,
        "success_rate": success_rate,
    }