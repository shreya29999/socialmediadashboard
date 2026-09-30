from types import SimpleNamespace


def test_get_social_account_returns_dict(monkeypatch):
    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt):
            return FakeResult(
                SimpleNamespace(
                    id=9,
                    user_id=1,
                    platform="facebook",
                    access_token="abc",
                    refresh_token="ref",
                    token_expires_at="2026-01-01T00:00:00",
                    page_id="page_123",
                    account_name="Page Name",
                    account_email="page@example.com",
                    created_at="2026-01-01T00:00:00",
                )
            )

    monkeypatch.setattr(
        "app.repositories.social_account_repository.SessionLocal",
        lambda: FakeSession(),
    )

    from app.repositories.social_account_repository import get_social_account

    account = get_social_account(1, "facebook")

    assert account is not None
    assert account["id"] == 9
    assert account["platform"] == "facebook"
    assert account["access_token"] == "abc"
