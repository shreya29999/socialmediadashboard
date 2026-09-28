from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_actor_user
from app.core.config import STATUS_LIST
from app.db.database import (
    get_posts_by_status,
    get_posts_by_status_for_admin,
)

router = APIRouter(tags=["Analytics"])


@router.get("/analytics")
def get_analytics(current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    counts       = {}
    all_posts    = []

    if actor and actor.get("role") == "admin":
        for s in STATUS_LIST:
            posts       = get_posts_by_status_for_admin(actor["id"], s) or []
            counts[s]   = len(posts)
            all_posts.extend(posts)
    else:
        user_id = current_user["user_id"]
        for s in STATUS_LIST:
            posts       = get_posts_by_status(user_id, s) or []
            counts[s]   = len(posts)
            all_posts.extend(posts)

    platform_stats = {"facebook": 0, "instagram": 0, "linkedin": 0}
    for post in all_posts:
        for plat in (post.get("platforms") or []):
            if plat in platform_stats:
                platform_stats[plat] += 1

    total = len(all_posts)

    return {
        "summary": {
            "total"                        : total,
            "posted"                       : counts.get("posted", 0),
            "scheduled"                    : counts.get("scheduled", 0),
            "awaiting_hr_approval"         : counts.get("awaiting_hr_approval", 0),
            "awaiting_admin_approval" : counts.get("awaiting_admin_approval", 0),
            "failed"                       : counts.get("failed", 0),
            "expired"                      : counts.get("expired", 0),
            "cancelled"                    : counts.get("cancelled", 0),
            "skipped"                      : counts.get("skipped", 0),
        },
        "platforms": platform_stats,
        "success_rate": round(
            (counts.get("posted", 0) / max(counts.get("posted", 0) + counts.get("failed", 0), 1)) * 100, 1
        )
    }
