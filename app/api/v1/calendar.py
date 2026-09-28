from datetime import datetime, timezone
import calendar

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user
from app.db.database import get_posts_for_calendar

router = APIRouter(tags=["Calendar"])


@router.get("/calendar")
def get_calendar(month: str = Query(..., description="Format: YYYY-MM"), current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    try:
        year, mon  = map(int, month.split("-"))
        start_date = datetime(year, mon, 1, tzinfo=timezone.utc)
        import calendar
        last_day   = calendar.monthrange(year, mon)[1]
        end_date   = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    posts = get_posts_for_calendar(user_id, start_date, end_date)
    calendar_data = {}
    for post in (posts or []):
        date_key = post["scheduled_at"].strftime("%Y-%m-%d")
        if date_key not in calendar_data:
            calendar_data[date_key] = []
        calendar_data[date_key].append({
            "post_id"      : post["id"],
            "scheduled_at" : post["scheduled_at"].isoformat(),
            "content"      : post["content_text"][:50] + "...",
            "platforms"    : post["platforms"],
            "status"       : post["status"]
        })

    return {"month": month, "calendar": calendar_data, "total": len(posts) if posts else 0}
