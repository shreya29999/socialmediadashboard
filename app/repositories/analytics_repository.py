from datetime import datetime

from sqlalchemy import select

from app.db.models import PostTemplate, ScheduledPost, User
from app.db.session import SessionLocal


def get_posts_for_calendar(user_id: int, start_date: datetime, end_date: datetime):
    with SessionLocal() as db:
        rows = db.execute(
            select(ScheduledPost, PostTemplate.content_text, PostTemplate.platforms, PostTemplate.media_url)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .where(
                PostTemplate.user_id == user_id,
                ScheduledPost.scheduled_at >= start_date,
                ScheduledPost.scheduled_at <= end_date,
            )
            .order_by(ScheduledPost.scheduled_at.asc())
        ).all()

        result = []
        for post, content_text, platforms, media_url in rows:
            result.append({
                "id": post.id,
                "scheduled_at": post.scheduled_at,
                "status": post.status,
                "content_text": content_text,
                "platforms": platforms,
                "media_url": media_url,
            })
        return result


def get_posts_for_calendar_for_admin(admin_id: int, start_date: datetime, end_date: datetime):
    with SessionLocal() as db:
        rows = db.execute(
            select(ScheduledPost, PostTemplate.content_text, PostTemplate.platforms, PostTemplate.media_url)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .join(User, PostTemplate.user_id == User.id)
            .where(
                User.admin_id == admin_id,
                ScheduledPost.scheduled_at >= start_date,
                ScheduledPost.scheduled_at <= end_date,
            )
            .order_by(ScheduledPost.scheduled_at.asc())
        ).all()

        result = []
        for post, content_text, platforms, media_url in rows:
            result.append({
                "id": post.id,
                "scheduled_at": post.scheduled_at,
                "status": post.status,
                "content_text": content_text,
                "platforms": platforms,
                "media_url": media_url,
            })
        return result
