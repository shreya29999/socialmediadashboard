from datetime import date, datetime, timedelta

from sqlalchemy import delete, select

from app.db.models import EventsCache, TrendsCache
from app.db.session import SessionLocal


def get_cached_events(country_code: str):
    with SessionLocal() as db:
        today = date.today()
        end_date = today + timedelta(days=30)

        rows = db.execute(
            select(EventsCache)
            .where(
                EventsCache.country_code == country_code,
                EventsCache.event_date >= today,
                EventsCache.event_date <= end_date,
            )
            .order_by(EventsCache.event_date.asc())
        ).scalars().all()

        return [
            {
                "id": row.id,
                "country_code": row.country_code,
                "event_name": row.event_name,
                "event_date": row.event_date,
                "event_type": row.event_type,
                "raw_data": row.raw_data,
                "fetched_at": row.fetched_at,
            }
            for row in rows
        ]


def has_fresh_events_cache(country_code: str):
    with SessionLocal() as db:
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())

        row = db.execute(
            select(EventsCache.id)
            .where(
                EventsCache.country_code == country_code,
                EventsCache.fetched_at >= start_of_day,
            )
            .limit(1)
        ).first()

        return row is not None


def delete_events_cache(country_code: str):
    with SessionLocal() as db:
        db.execute(
            delete(EventsCache).where(
                EventsCache.country_code == country_code
            )
        )
        db.commit()


def save_event(
    country_code: str,
    event_name: str,
    event_date,
    event_type: str,
    raw_data: dict,
):
    if isinstance(event_date, str):
        event_date = date.fromisoformat(event_date[:10])

    with SessionLocal() as db:
        event = EventsCache(
            country_code=country_code,
            event_name=event_name,
            event_date=event_date,
            event_type=event_type,
            raw_data=raw_data,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id


def has_fresh_trends_cache(
    country_code: str | None,
    platform: str,
    hours: int,
):
    with SessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = select(TrendsCache.id).where(
            TrendsCache.platform == platform,
            TrendsCache.fetched_at >= cutoff,
        )

        if country_code is not None:
            query = query.where(
                TrendsCache.country_code == country_code
            )

        return db.execute(query.limit(1)).first() is not None


def get_cached_trends(
    country_code: str | None,
    platform: str,
    hours: int | None = None,
):
    with SessionLocal() as db:
        query = select(TrendsCache).where(
            TrendsCache.platform == platform
        )

        if country_code is not None:
            query = query.where(
                TrendsCache.country_code == country_code
            )

        if hours is not None:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            query = query.where(
                TrendsCache.fetched_at >= cutoff
            )

        rows = db.execute(
            query.order_by(TrendsCache.score.desc())
        ).scalars().all()

        return [
            {
                "id": row.id,
                "country_code": row.country_code,
                "platform": row.platform,
                "topic": row.topic,
                "score": row.score,
                "raw_data": row.raw_data,
                "fetched_at": row.fetched_at,
            }
            for row in rows
        ]


def delete_trends_cache(
    platform: str,
    country_code: str | None = None,
):
    with SessionLocal() as db:
        query = delete(TrendsCache).where(
            TrendsCache.platform == platform
        )

        if country_code is not None:
            query = query.where(
                TrendsCache.country_code == country_code
            )

        db.execute(query)
        db.commit()


def save_trend(
    country_code: str,
    platform: str,
    topic: str,
    score: float,
    raw_data: dict | None = None,
):
    with SessionLocal() as db:
        trend = TrendsCache(
            country_code=country_code,
            platform=platform,
            topic=topic,
            score=score,
            raw_data=raw_data,
        )
        db.add(trend)
        db.commit()
        db.refresh(trend)
        return trend.id
