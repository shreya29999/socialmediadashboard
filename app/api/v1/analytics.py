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


def normalize_platforms(platforms):
    """
    Convert platform data into a flat list of platform strings.

    Supported examples:

    ["facebook", "instagram"]
    [["facebook", "instagram"]]
    "facebook"

    Result:

    ["facebook", "instagram"]
    """

    if not platforms:
        return []

    if isinstance(platforms, str):
        return [platforms]

    normalized = []

    for platform in platforms:

        if isinstance(platform, list):
            normalized.extend(
                normalize_platforms(platform)
            )

        elif isinstance(platform, str):
            normalized.append(platform)

    return normalized


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

    # ============================================================
    # GET POSTS BY STATUS
    # ============================================================

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

    # ============================================================
    # PLATFORM STATISTICS
    # ============================================================

    platform_stats = {
        "facebook": 0,
        "instagram": 0,
        "linkedin": 0,
    }

    for post in all_posts:

        platforms = normalize_platforms(
            post.get("platforms")
        )

        for platform in platforms:

            platform = platform.lower().strip()

            if platform in platform_stats:
                platform_stats[platform] += 1

    # ============================================================
    # SUMMARY COUNTS
    # ============================================================

    total = len(all_posts)

    posted_count = counts.get("posted", 0)
    failed_count = counts.get("failed", 0)

    scheduled_count = counts.get("scheduled", 0)

    awaiting_hr_approval_count = counts.get(
        "awaiting_hr_approval",
        0,
    )

    awaiting_admin_approval_count = counts.get(
        "awaiting_admin_approval",
        0,
    )

    expired_count = counts.get(
        "expired",
        0,
    )

    cancelled_count = counts.get(
        "cancelled",
        0,
    )

    skipped_count = counts.get(
        "skipped",
        0,
    )

    # ============================================================
    # SUCCESS RATE
    # ============================================================

    total_completed = (
        posted_count + failed_count
    )

    if total_completed > 0:
        success_rate = round(
            (
                posted_count
                / total_completed
            ) * 100,
            1,
        )
    else:
        success_rate = 0.0

    # ============================================================
    # RESPONSE
    # ============================================================

    return {
        "summary": {
            "total": total,

            "posted": posted_count,

            "scheduled": scheduled_count,

            "awaiting_hr_approval": (
                awaiting_hr_approval_count
            ),

            "awaiting_admin_approval": (
                awaiting_admin_approval_count
            ),

            "failed": failed_count,

            "expired": expired_count,

            "cancelled": cancelled_count,

            "skipped": skipped_count,
        },

        "platforms": platform_stats,

        "success_rate": success_rate,
    }