from datetime import datetime
from types import SimpleNamespace


def test_get_post_by_id_returns_dict(monkeypatch):
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, post_id):
            model_name = getattr(model, "__name__", "")

            if model_name == "ScheduledPost":
                return SimpleNamespace(
                    id=12,
                    template_id=5,
                    status="scheduled",
                    scheduled_at=datetime(2026, 1, 1, 12, 0, 0),
                    confirmation_sent_at=None,
                    confirmation_token=None,
                    superadmin_token=None,
                    token_used=False,
                    superadmin_token_used=False,
                    approved_at=None,
                    rejection_reason=None,
                    ai_generated=False,
                    trigger_type=None,
                    trigger_name=None,
                    reposted_from_id=None,
                )

            if model_name == "PostTemplate":
                return SimpleNamespace(
                    id=5,
                    user_id=2,
                    content_text="Hello world",
                    media_url="https://example.com/image.png",
                    platforms=["facebook"],
                )

            return None

    monkeypatch.setattr(
        "app.repositories.post_repository.SessionLocal",
        lambda: FakeSession(),
    )

    from app.repositories.post_repository import get_post_by_id

    post = get_post_by_id(12)

    assert post is not None
    assert post["id"] == 12
    assert post["template_id"] == 5
    assert post["user_id"] == 2
    assert post["status"] == "scheduled"
    assert post["content_text"] == "Hello world"
    assert post["media_url"] == "https://example.com/image.png"
    assert post["platforms"] == ["facebook"]