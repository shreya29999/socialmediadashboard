from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import aliased
from datetime import datetime, timezone, timedelta
from app.db.models import (
    PostApprovalStage,
    PostTarget,
    PostTemplate,
    ScheduledPost,
    User,
)
from app.db.session import SessionLocal


def _post_dict(post, template):
    return {
        "id": post.id,
        "template_id": post.template_id,
        "scheduled_at": post.scheduled_at,
        "confirmation_sent_at": post.confirmation_sent_at,
        "confirmation_token": post.confirmation_token,
        "superadmin_token": post.superadmin_token,
        "token_used": post.token_used,
        "superadmin_token_used": post.superadmin_token_used,
        "status": post.status,
        "approved_at": post.approved_at,
        "rejection_reason": post.rejection_reason,
        "ai_generated": post.ai_generated,
        "trigger_type": post.trigger_type,
        "trigger_name": post.trigger_name,
        "reposted_from_id": post.reposted_from_id,
        "created_at": post.created_at,
        "user_id": template.user_id,
        "content_text": template.content_text,
        "media_url": template.media_url,
        "platforms": template.platforms,
    }


def get_posts_due_for_confirmation():
    """
    Get scheduled posts that have not yet received
    an HR approval request.
    """
    with SessionLocal() as db:
        stmt = (
            select(ScheduledPost, PostTemplate)
            .join(
                PostTemplate,
                ScheduledPost.template_id == PostTemplate.id,
            )
            .join(
                User,
                PostTemplate.user_id == User.id,
            )
            .where(
                ScheduledPost.status == "scheduled",
                PostTemplate.status == "active",
                User.admin_id.is_not(None),
                ScheduledPost.confirmation_sent_at.is_(None),
            )
        )

        rows = db.execute(stmt).all()

        return [
            _post_dict(post, template)
            for post, template in rows
        ]

def get_expired_awaiting_posts():
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Post expires 30 minutes after its scheduled time
        expiration_time = now - timedelta(minutes=30)

        stmt = select(ScheduledPost).where(
            ScheduledPost.status.in_(
                ["awaiting_hr_approval", "awaiting_admin_approval"]
            ),
            ScheduledPost.scheduled_at <= expiration_time,
        )

        posts = db.execute(stmt).scalars().all()

        return posts


def get_post_by_id(post_id: int):
    with SessionLocal() as db:
        stmt = (
            select(ScheduledPost, PostTemplate)
            .join(
                PostTemplate,
                ScheduledPost.template_id == PostTemplate.id,
            )
            .where(ScheduledPost.id == post_id)
        )

        row = db.execute(stmt).first()

        if not row:
            return None

        post, template = row
        return _post_dict(post, template)


def get_posts_ready_to_publish():
    """
    Get posts whose scheduled time has arrived and which
    have been explicitly approved.
    """
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)

        stmt = (
            select(ScheduledPost, PostTemplate)
            .join(
                PostTemplate,
                ScheduledPost.template_id == PostTemplate.id,
            )
            .where(
                PostTemplate.status == "active",
                ScheduledPost.scheduled_at <= now,
                ScheduledPost.status == "approved",
            )
        )

        rows = db.execute(stmt).all()

        return [
            _post_dict(post, template)
            for post, template in rows
        ]

def update_post_status(post_id: int, status: str):
    with SessionLocal() as db:
        stmt = (
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(status=status)
        )

        db.execute(stmt)
        db.commit()


def get_targets_for_post(scheduled_post_id: int):
    with SessionLocal() as db:
        stmt = select(PostTarget).where(
            PostTarget.scheduled_post_id == scheduled_post_id
        )

        targets = db.execute(stmt).scalars().all()

        return [
            {
                "id": target.id,
                "scheduled_post_id": target.scheduled_post_id,
                "platform": target.platform,
                "status": target.status,
                "error_message": target.error_message,
                "posted_at": target.posted_at,
            }
            for target in targets
        ]


def create_post_targets(scheduled_post_id: int, platforms: list[str]):
    with SessionLocal() as db:
        for platform in platforms:
            target = PostTarget(
                scheduled_post_id=scheduled_post_id,
                platform=platform,
            )
            db.add(target)

        db.commit()


def update_target_status(
    scheduled_post_id: int,
    platform: str,
    status: str,
    error_message: str | None = None,
):
    with SessionLocal() as db:
        stmt = (
            update(PostTarget)
            .where(
                PostTarget.scheduled_post_id == scheduled_post_id,
                PostTarget.platform == platform,
            )
            .values(
                status=status,
                error_message=error_message,
                posted_at=(
                    datetime.now(timezone.utc)
                    if status == "posted"
                    else None
                ),
            )
        )

        db.execute(stmt)
        db.commit()


def save_confirmation_token(post_id: int, token: str):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)

        if not post:
            return False

        post.confirmation_token = token
        post.confirmation_sent_at = datetime.now(timezone.utc)
        post.token_used = False

        db.commit()
        return True


def save_admin_token(post_id: int, token: str):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)

        if not post:
            return False

        post.superadmin_token = token
        post.superadmin_token_used = False

        db.commit()
        return True


def get_post_by_token(token: str):
    with SessionLocal() as db:
        stmt = (
            select(ScheduledPost, PostTemplate)
            .join(
                PostTemplate,
                ScheduledPost.template_id == PostTemplate.id,
            )
            .where(
                ScheduledPost.confirmation_token == token,
                ScheduledPost.token_used.is_(False),
            )
        )

        row = db.execute(stmt).first()

        if not row:
            return None

        post, template = row
        return _post_dict(post, template)


def approve_post(post_id: int):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)

        if not post:
            return False

        post.status = "approved"
        post.approved_at = datetime.now(timezone.utc)
        post.token_used = True

        db.commit()
        return True


def reject_post(post_id: int, reason: str | None = None):
    with SessionLocal() as db:
        post = db.get(ScheduledPost, post_id)

        if not post:
            return False

        post.status = "cancelled"
        post.rejection_reason = reason
        post.token_used = True

        db.commit()
        return True


def create_approval_stage(post_id: int):
    with SessionLocal() as db:
        existing = db.execute(
            select(PostApprovalStage).where(
                PostApprovalStage.scheduled_post_id == post_id
            )
        ).scalar_one_or_none()

        if existing:
            return existing.id

        stage = PostApprovalStage(
            scheduled_post_id=post_id,
            hr_status="pending",
            admin_status="pending",
        )

        db.add(stage)
        db.commit()
        db.refresh(stage)

        return stage.id


def get_approval_stage(post_id: int):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(
                PostApprovalStage.scheduled_post_id == post_id
            )
        ).scalar_one_or_none()

        if not stage:
            return None

        return {
            "id": stage.id,
            "scheduled_post_id": stage.scheduled_post_id,
            "hr_status": stage.hr_status,
            "hr_approved_at": stage.hr_approved_at,
            "hr_rejection_reason": stage.hr_rejection_reason,
            "admin_status": stage.admin_status,
            "admin_approved_at": stage.admin_approved_at,
            "admin_rejection_reason": stage.admin_rejection_reason,
            "created_at": stage.created_at,
        }


def update_hr_approval(
    post_id: int,
    status: str,
    reason: str | None = None,
):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(
                PostApprovalStage.scheduled_post_id == post_id
            )
        ).scalar_one_or_none()

        if not stage:
            return False

        stage.hr_status = status
        stage.hr_rejection_reason = reason

        if status == "approved":
            stage.hr_approved_at = datetime.now(timezone.utc)
        else:
            stage.hr_approved_at = None

        db.commit()
        return True


def increment_occurrence_count(template_id: int):
    with SessionLocal() as db:
        template = db.get(PostTemplate, template_id)

        if not template:
            return False

        template.occurrence_count += 1
        db.commit()

        return True


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
            "occurrence_count": template.occurrence_count,
            "timezone": template.timezone,
            "status": template.status,
        }


def create_scheduled_post(
    template_id: int,
    scheduled_at,
    reposted_from_id: int | None = None,
):
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
        }