from datetime import datetime

from sqlalchemy import select

from app.db.models import PostApprovalStage, PostTemplate, ScheduledPost, User, UserProfile
from app.db.session import SessionLocal


def create_approval_stage(post_id: int):
    with SessionLocal() as db:
        existing = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "scheduled_post_id": post_id}

        stage = PostApprovalStage(scheduled_post_id=post_id)
        db.add(stage)
        db.commit()
        db.refresh(stage)
        return {"id": stage.id, "scheduled_post_id": stage.scheduled_post_id}


def get_approval_stage(post_id: int):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if not stage:
            return None
        return {
            "id": stage.id,
            "scheduled_post_id": stage.scheduled_post_id,
            "hr_status": stage.hr_status,
            "hr_approved_at": stage.hr_approved_at,
            "hr_rejection_reason": stage.hr_rejection_reason,
            "superadmin_status": stage.superadmin_status,
            "superadmin_approved_at": stage.superadmin_approved_at,
            "superadmin_rejection_reason": stage.superadmin_rejection_reason,
            "admin_status": stage.admin_status,
            "admin_approved_at": stage.admin_approved_at,
            "admin_rejection_reason": stage.admin_rejection_reason,
            "created_at": stage.created_at,
        }


def update_hr_approval(post_id: int, status: str, reason: str | None = None):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if not stage:
            return None
        stage.hr_status = status
        stage.hr_approved_at = datetime.utcnow() if status == "approved" else None
        stage.hr_rejection_reason = reason
        db.commit()
        return {"id": stage.id, "scheduled_post_id": stage.scheduled_post_id, "hr_status": stage.hr_status}


def update_admin_approval(post_id: int, status: str, reason: str | None = None):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if not stage:
            return None
        stage.admin_status = status
        stage.admin_approved_at = datetime.utcnow() if status == "approved" else None
        stage.admin_rejection_reason = reason
        db.commit()
        return {"id": stage.id, "scheduled_post_id": stage.scheduled_post_id, "admin_status": stage.admin_status}


def get_posts_awaiting_admin_approval(admin_id: int | None = None):
    with SessionLocal() as db:
        stmt = (
            select(ScheduledPost, PostTemplate.content_text, PostTemplate.media_url, PostTemplate.platforms, PostTemplate.user_id, User.email, UserProfile.brand_name, UserProfile.persona, PostApprovalStage.hr_status, PostApprovalStage.admin_status)
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .join(User, PostTemplate.user_id == User.id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .join(PostApprovalStage, PostApprovalStage.scheduled_post_id == ScheduledPost.id)
            .where(ScheduledPost.status == "awaiting_admin_approval", PostApprovalStage.admin_status == "pending")
            .order_by(ScheduledPost.scheduled_at.asc())
        )
        if admin_id is not None:
            stmt = stmt.where(User.admin_id == admin_id)

        rows = db.execute(stmt).all()
        result = []
        for row in rows:
            post = row[0]
            result.append({
                "id": post.id,
                "template_id": post.template_id,
                "user_id": row[4],
                "status": post.status,
                "scheduled_at": post.scheduled_at,
                "content_text": row[1],
                "media_url": row[2],
                "platforms": row[3],
                "user_email": row[5],
                "brand_name": row[6],
                "persona": row[7],
                "hr_status": row[8],
                "admin_status": row[9],
            })
        return result


def admin_final_approve(post_id: int):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if stage:
            stage.admin_status = "approved"
            stage.admin_approved_at = datetime.utcnow()
        post = db.get(ScheduledPost, post_id)
        if post:
            post.status = "approved"
            post.approved_at = datetime.utcnow()
        db.commit()
        return {"id": post_id, "status": "approved"}


def admin_final_reject(post_id: int, reason: str | None = None):
    with SessionLocal() as db:
        stage = db.execute(
            select(PostApprovalStage).where(PostApprovalStage.scheduled_post_id == post_id)
        ).scalar_one_or_none()
        if stage:
            stage.admin_status = "rejected"
            stage.admin_rejection_reason = reason
        post = db.get(ScheduledPost, post_id)
        if post:
            post.status = "cancelled"
            post.rejection_reason = reason
        db.commit()
        return {"id": post_id, "status": "cancelled"}
