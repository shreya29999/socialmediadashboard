from datetime import datetime
from types import SimpleNamespace


def test_get_approval_stage_returns_stage(monkeypatch):
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
                    id=3,
                    scheduled_post_id=15,
                    hr_status="pending",
                    hr_approved_at=None,
                    hr_rejection_reason=None,
                    superadmin_status="pending",
                    superadmin_approved_at=None,
                    superadmin_rejection_reason=None,
                    admin_status="pending",
                    admin_approved_at=None,
                    admin_rejection_reason=None,
                    created_at=datetime(2026, 1, 1),
                )
            )

    monkeypatch.setattr(
        "app.repositories.approval_repository.SessionLocal",
        lambda: FakeSession(),
    )

    from app.repositories.approval_repository import get_approval_stage

    stage = get_approval_stage(15)

    assert stage is not None
    assert stage["scheduled_post_id"] == 15
    assert stage["hr_status"] == "pending"
    assert stage["admin_status"] == "pending"
