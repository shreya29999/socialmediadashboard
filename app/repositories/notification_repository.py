from datetime import datetime

from sqlalchemy import select

from app.db.models import Notification
from app.db.session import SessionLocal


def create_notification(
    user_id: int,
    type: str,
    title: str,
    message: str | None = None,
    link: str | None = None,
    post_id: int | None = None,
):
    if not user_id:
        return None

    with SessionLocal() as db:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            link=link,
            post_id=post_id,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return {
            "id": notification.id,
            "user_id": notification.user_id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "link": notification.link,
            "post_id": notification.post_id,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
        }


def get_notifications(user_id: int, unread_only: bool = False, limit: int = 50):
    with SessionLocal() as db:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "type": row.type,
                "title": row.title,
                "message": row.message,
                "link": row.link,
                "post_id": row.post_id,
                "is_read": row.is_read,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def get_unread_notification_count(user_id: int):
    with SessionLocal() as db:
        count = db.execute(
            select(__import__("sqlalchemy").func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalar() or 0
        return count


def mark_notification_read(notification_id: int, user_id: int):
    with SessionLocal() as db:
        item = db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        ).scalar_one_or_none()
        if item:
            item.is_read = True
            db.commit()
        return {"id": notification_id, "is_read": True}


def mark_all_notifications_read(user_id: int):
    with SessionLocal() as db:
        rows = db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ).scalars().all()
        for row in rows:
            row.is_read = True
        db.commit()
        return {"user_id": user_id, "updated": len(rows)}


def delete_notification(notification_id: int, user_id: int):
    with SessionLocal() as db:
        item = db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        ).scalar_one_or_none()
        if item:
            db.delete(item)
            db.commit()
        return {"id": notification_id, "deleted": item is not None}
