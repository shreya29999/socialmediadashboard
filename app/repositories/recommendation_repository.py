from datetime import datetime, time

from sqlalchemy import Date, cast, func, select

from app.db.models import PostTemplate, ScheduledPost, SocialAccount
from app.db.session import SessionLocal


def get_connected_platforms(user_id: int) -> list[str]:
    """Return the social platforms connected to a user."""
    with SessionLocal() as db:
        rows = db.execute(
            select(SocialAccount.platform)
            .where(SocialAccount.user_id == user_id)
        ).all()

        return [row[0] for row in rows if row[0]]


def has_duplicate_post_for_trigger(
    user_id: int,
    trigger_name: str,
) -> bool:
    """Preserve the legacy same-day duplicate check using SQLAlchemy."""
    search_text = f"%{(trigger_name or '')[:20]}%"

    with SessionLocal() as db:
        post_id = db.execute(
            select(ScheduledPost.id)
            .join(
                PostTemplate,
                ScheduledPost.template_id == PostTemplate.id,
            )
            .where(
                PostTemplate.user_id == user_id,
                PostTemplate.content_text.ilike(search_text),
                cast(ScheduledPost.created_at, Date) == func.current_date(),
            )
            .limit(1)
        ).scalar_one_or_none()

        return post_id is not None
