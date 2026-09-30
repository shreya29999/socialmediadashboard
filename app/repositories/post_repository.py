from datetime import datetime

from sqlalchemy import Date, cast, delete, func, select

from app.db.models import PostApprovalStage, PostTarget, PostTemplate, ScheduledPost, User, UserProfile
from app.db.session import SessionLocal


def create_post_template(
    user_id: int,
    content_text: str,
    media_url: str | None,
    platforms: list[str],
    recurrence_type: str,
    interval_days: int,
    start_date: datetime,
    end_date: datetime | None = None,
    max_occurrences: int | None = None,
    timezone: str = "UTC",
):
    with SessionLocal() as db:
        template = PostTemplate(
            user_id=user_id,
            content_text=content_text,
            media_url=media_url,
            platforms=list(platforms or []),
            recurrence_type=recurrence_type,
            interval_days=interval_days,
            start_date=start_date,
            end_date=end_date,
            max_occurrences=max_occurrences,
            timezone=timezone,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return {
            "id": template.id,
            "user_id": template.user_id,
            "content_text": template.content_text,
            "media_url": template.media_url,
            "platforms": template.platforms,
            "recurrence_type": template.recurrence_type,
            "interval_days": template.interval_days,
            "start_date": template.start_date,
            "end_date": template.end_date,
            "max_occurrences": template.max_occurrences,
            "timezone": template.timezone,
            "status": template.status,
        }


def get_template_by_id(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if not template:
            return None
        return {
            "id": template.id,
            "user_id": template.user_id,
            "content_text": template.content_text,
            "media_url": template.media_url,
            "platforms": template.platforms,
            "recurrence_type": template.recurrence_type,
            "interval_days": template.interval_days,
            "start_date": template.start_date,
            "end_date": template.end_date,
            "max_occurrences": template.max_occurrences,
            "timezone": template.timezone,
            "status": template.status,
            "created_at": template.created_at,
        }


def pause_template(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if template:
            template.status = "paused"
            db.commit()
        return {"id": template_id, "status": "paused"} if template else None


def resume_template(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if template:
            template.status = "active"
            db.commit()
        return {"id": template_id, "status": "active"} if template else None


def increment_occurrence_count(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if not template:
            return None
        template.occurrence_count = (template.occurrence_count or 0) + 1
        db.commit()
        return {"id": template.id, "occurrence_count": template.occurrence_count}


def mark_template_completed(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if not template:
            return None
        template.status = "completed"
        db.commit()
        return {"id": template.id, "status": template.status}


def has_ai_generated_post_for_trigger_today(user_id: int, trigger_name: str | None):
    with SessionLocal() as db:
        post_id = db.execute(
            select(ScheduledPost.id)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .where(
                ScheduledPost.trigger_name == trigger_name,
                ScheduledPost.ai_generated.is_(True),
                cast(ScheduledPost.created_at, Date) == func.current_date(),
                PostTemplate.user_id == user_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        return post_id is not None


def create_ai_generated_post(
    user_id: int,
    content_text: str,
    media_url: str | None,
    platforms: list[str],
    scheduled_at: datetime,
    trigger_type: str | None,
    trigger_name: str | None,
):
    with SessionLocal() as db:
        template = PostTemplate(
            user_id=user_id,
            content_text=content_text,
            media_url=media_url,
            platforms=list(platforms or []),
            recurrence_type="ONE_TIME",
            interval_days=1,
            start_date=scheduled_at,
            timezone="UTC",
        )
        db.add(template)
        db.flush()

        post = ScheduledPost(
            template_id=template.id,
            scheduled_at=scheduled_at,
            status="scheduled",
            ai_generated=True,
            trigger_type=trigger_type,
            trigger_name=trigger_name,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return {"id": post.id, "template_id": template.id}


def save_confirmation_token(post_id: int, token: str):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None
        post.confirmation_token = token
        post.confirmation_sent_at = datetime.utcnow()
        post.token_used = False
        db.commit()
        return {
            "id": post.id,
            "confirmation_token": post.confirmation_token,
            "confirmation_sent_at": post.confirmation_sent_at,
            "token_used": post.token_used,
        }


def approve_post(post_id: int):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None
        post.status = "approved"
        post.approved_at = datetime.utcnow()
        post.token_used = True
        db.commit()
        return {"id": post.id, "status": post.status, "approved_at": post.approved_at}


def create_scheduled_post(template_id: int, scheduled_at: datetime, reposted_from_id: int | None = None):
    with SessionLocal() as db:
        post = ScheduledPost(
            template_id=template_id,
            scheduled_at=scheduled_at,
            reposted_from_id=reposted_from_id,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return {
            "id": post.id,
            "template_id": post.template_id,
            "scheduled_at": post.scheduled_at,
            "status": post.status,
            "reposted_from_id": post.reposted_from_id,
            "ai_generated": post.ai_generated,
            "trigger_type": post.trigger_type,
            "trigger_name": post.trigger_name,
        }


def get_post_by_id(post_id: int):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None
        template = db.get(PostTemplate, post.template_id)
        if not template:
            return None
        return {
            "id": post.id,
            "template_id": post.template_id,
            "user_id": template.user_id,
            "status": post.status,
            "scheduled_at": post.scheduled_at,
            "confirmation_sent_at": post.confirmation_sent_at,
            "confirmation_token": post.confirmation_token,
            "superadmin_token": post.superadmin_token,
            "token_used": post.token_used,
            "superadmin_token_used": post.superadmin_token_used,
            "approved_at": post.approved_at,
            "rejection_reason": post.rejection_reason,
            "ai_generated": post.ai_generated,
            "trigger_type": post.trigger_type,
            "trigger_name": post.trigger_name,
            "reposted_from_id": post.reposted_from_id,
            "content_text": template.content_text,
            "media_url": template.media_url,
            "platforms": template.platforms,
        }


def update_post_template(template_id: int, **kwargs):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)
        if not template:
            return None

        if "content_text" in kwargs and kwargs["content_text"] is not None:
            template.content_text = kwargs["content_text"]
        if "media_url" in kwargs and kwargs["media_url"] is not None:
            template.media_url = kwargs["media_url"]
        if "platforms" in kwargs and kwargs["platforms"] is not None:
            template.platforms = list(kwargs["platforms"])

        db.commit()
        return {
            "id": template.id,
            "content_text": template.content_text,
            "media_url": template.media_url,
            "platforms": template.platforms,
        }


def update_post(post_id: int, **kwargs):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None

        if "scheduled_at" in kwargs and kwargs["scheduled_at"] is not None:
            post.scheduled_at = kwargs["scheduled_at"]
        if "status" in kwargs and kwargs["status"] is not None:
            post.status = kwargs["status"]
        if kwargs.get("clear_confirmation"):
            post.confirmation_token = None
            post.confirmation_sent_at = None
            post.token_used = False

        template = db.get(PostTemplate, post.template_id)
        if template:
            if "content_text" in kwargs and kwargs["content_text"] is not None:
                template.content_text = kwargs["content_text"]
            if "media_url" in kwargs and kwargs["media_url"] is not None:
                template.media_url = kwargs["media_url"]
            if "platforms" in kwargs and kwargs["platforms"] is not None:
                template.platforms = list(kwargs["platforms"])

        db.commit()
        return {
            "id": post.id,
            "template_id": post.template_id,
            "status": post.status,
            "scheduled_at": post.scheduled_at,
        }


def delete_post(post_id: int):
    with SessionLocal() as db:
        db.execute(delete(PostTarget).where(PostTarget.scheduled_post_id == post_id))
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None
        db.delete(post)
        db.commit()
        return {"id": post_id, "deleted": True}


def get_posts_by_status(user_id: int, status: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(ScheduledPost)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .where(PostTemplate.user_id == user_id, ScheduledPost.status == status)
            .order_by(ScheduledPost.scheduled_at.asc())
        ).scalars().all()

        result = []
        for post in rows:
            template = db.get(PostTemplate, post.template_id)
            result.append({
                "id": post.id,
                "template_id": post.template_id,
                "user_id": template.user_id,
                "status": post.status,
                "scheduled_at": post.scheduled_at,
                "content_text": template.content_text,
                "media_url": template.media_url,
                "platforms": template.platforms,
                "ai_generated": post.ai_generated,
                "trigger_type": post.trigger_type,
                "trigger_name": post.trigger_name,
                "reposted_from_id": post.reposted_from_id,
            })
        return result


def get_posts_by_status_for_admin(admin_id: int, status: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(ScheduledPost)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .join(User, PostTemplate.user_id == User.id)
            .where(User.admin_id == admin_id, ScheduledPost.status == status)
            .order_by(ScheduledPost.scheduled_at.asc())
        ).scalars().all()

        result = []
        for post in rows:
            template = db.get(PostTemplate, post.template_id)
            result.append({
                "id": post.id,
                "template_id": post.template_id,
                "user_id": template.user_id,
                "status": post.status,
                "scheduled_at": post.scheduled_at,
                "content_text": template.content_text,
                "media_url": template.media_url,
                "platforms": template.platforms,
                "ai_generated": post.ai_generated,
                "trigger_type": post.trigger_type,
                "trigger_name": post.trigger_name,
                "reposted_from_id": post.reposted_from_id,
            })
        return result


def get_all_posts_for_superadmin(status_filter: str | None = None):
    with SessionLocal() as db:
        stmt = (
            select(ScheduledPost)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .join(User, PostTemplate.user_id == User.id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .outerjoin(PostApprovalStage, PostApprovalStage.scheduled_post_id == ScheduledPost.id)
            .where(ScheduledPost.status != "scheduled")
        )
        if status_filter:
            stmt = stmt.where(ScheduledPost.status == status_filter)
        stmt = stmt.order_by(ScheduledPost.created_at.desc())

        rows = db.execute(stmt).scalars().all()
        result = []
        for post in rows:
            template = db.get(PostTemplate, post.template_id)
            user = db.get(User, template.user_id)
            result.append({
                "id": post.id,
                "template_id": post.template_id,
                "user_id": template.user_id,
                "status": post.status,
                "scheduled_at": post.scheduled_at,
                "created_at": post.created_at,
                "content_text": template.content_text,
                "media_url": template.media_url,
                "platforms": template.platforms,
                "user_email": user.email if user else None,
                "brand_name": None,
                "persona": None,
                "ai_generated": post.ai_generated,
                "trigger_type": post.trigger_type,
                "trigger_name": post.trigger_name,
                "reposted_from_id": post.reposted_from_id,
            })
        return result


def update_post_status(post_id: int, status: str):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)
        if not post:
            return None
        post.status = status
        db.commit()
        return {"id": post.id, "status": post.status}


def mark_token_used(post_id: int):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)

        if not post:
            return False

        post.token_used = True
        db.commit()

        return True