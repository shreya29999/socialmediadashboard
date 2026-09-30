from sqlalchemy import delete, select

from app.db.models import (
    EventsCache,
    PostTemplate,
    RagChatHistory,
    TrendsCache,
    UserProfile,
)
from app.db.session import SessionLocal


def get_rag_profile(user_id: int):
    with SessionLocal() as db:
        profile = db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).scalar_one_or_none()

        if not profile:
            return None

        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "persona": profile.persona,
            "industry": profile.industry,
            "brand_name": profile.brand_name,
            "tone": profile.tone,
            "audience": profile.audience,
            "country_code": profile.country_code,
            "language": profile.language,
            "posts_per_week": profile.posts_per_week,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }


def get_recent_posts_for_rag(user_id: int, limit: int = 8):
    with SessionLocal() as db:
        rows = db.execute(
            select(
                PostTemplate.content_text,
                PostTemplate.platforms,
                PostTemplate.created_at,
            )
            .where(PostTemplate.user_id == user_id)
            .order_by(PostTemplate.created_at.desc())
            .limit(limit)
        ).all()

        return [
            {
                "content_text": row.content_text,
                "platforms": row.platforms,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def get_events_for_rag(country_code: str, limit: int = 8):
    with SessionLocal() as db:
        rows = db.execute(
            select(
                EventsCache.event_name,
                EventsCache.event_date,
                EventsCache.event_type,
            )
            .where(EventsCache.country_code == country_code)
            .order_by(EventsCache.event_date.asc())
            .limit(limit)
        ).all()

        return [
            {
                "event_name": row.event_name,
                "event_date": row.event_date,
                "event_type": row.event_type,
            }
            for row in rows
        ]


def get_trends_for_rag(country_code: str, limit: int = 8):
    with SessionLocal() as db:
        rows = db.execute(
            select(TrendsCache.topic)
            .where(TrendsCache.country_code == country_code)
            .order_by(TrendsCache.score.desc())
            .limit(limit)
        ).all()

        return [{"topic": row.topic} for row in rows]


def get_chat_history(user_id: int, limit: int = 6):
    with SessionLocal() as db:
        rows = db.execute(
            select(
                RagChatHistory.role,
                RagChatHistory.content,
            )
            .where(RagChatHistory.user_id == user_id)
            .order_by(RagChatHistory.created_at.desc())
            .limit(limit)
        ).all()

        return [
            {"role": row.role, "content": row.content}
            for row in reversed(rows)
        ]


def save_chat_turn(user_id: int, role: str, content: str):
    with SessionLocal() as db:
        chat = RagChatHistory(
            user_id=user_id,
            role=role,
            content=content,
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat.id


def clear_rag_history(user_id: int):
    with SessionLocal() as db:
        db.execute(
            delete(RagChatHistory).where(
                RagChatHistory.user_id == user_id
            )
        )
        db.commit()
