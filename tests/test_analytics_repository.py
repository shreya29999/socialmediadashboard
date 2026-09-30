from datetime import datetime
from types import SimpleNamespace


def test_get_posts_for_calendar_returns_records(monkeypatch):
    class FakeResult:
        def __init__(self, value):
            self._value = value

        def all(self):
            return self._value

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            return FakeResult([
                (
                    SimpleNamespace(
                        id=7,
                        template_id=5,
                        scheduled_at=datetime(2026, 1, 10, 12, 0),
                        status="scheduled",
                    ),
                    "Hello",
                    ["facebook"],
                    "https://example.com/image.png",
                )
            ])

    monkeypatch.setattr(
        "app.repositories.analytics_repository.SessionLocal",
        lambda: FakeSession(),
    )

    from app.repositories.analytics_repository import get_posts_for_calendar

    posts = get_posts_for_calendar(1, datetime(2026, 1, 1), datetime(2026, 1, 31))

    assert len(posts) == 1
    assert posts[0]["id"] == 7
    assert posts[0]["content_text"] == "Hello"
    assert posts[0]["platforms"] == ["facebook"]
