from datetime import datetime
from types import SimpleNamespace


def test_get_notifications_returns_list(monkeypatch):
    class FakeResult:
     def __init__(self, value):
        self._value = value

     def scalars(self):
        return self

     def all(self):
        return self._value

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            return FakeResult([
                SimpleNamespace(
                    id=1,
                    user_id=8,
                    type="hr_approval_requested",
                    title="Post awaiting your approval",
                    message="Please review",
                    link="/posts/1",
                    post_id=1,
                    is_read=False,
                    created_at=datetime(2026, 1, 1),
                )
            ])

    monkeypatch.setattr(
        "app.repositories.notification_repository.SessionLocal",
        lambda: FakeSession(),
    )

    from app.repositories.notification_repository import get_notifications

    items = get_notifications(8)

    assert len(items) == 1
    assert items[0]["user_id"] == 8
    assert items[0]["type"] == "hr_approval_requested"
