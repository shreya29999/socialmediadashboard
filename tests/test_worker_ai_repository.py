from datetime import datetime, timezone


def test_generate_ai_posts_task_uses_repository_for_duplicate_and_creation(monkeypatch):
    from app.workers import tasks

    calls = {}
    post_data = {
        "content_text": "A useful update",
        "media_url": None,
        "platforms": ["linkedin"],
        "scheduled_at": datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
        "trigger_type": "event",
        "trigger_name": "Launch day",
    }

    monkeypatch.setattr(
        tasks,
        "run_recommendation_pipeline_sync",
        lambda user_id: [post_data],
    )
    monkeypatch.setattr(tasks, "get_user_by_id", lambda user_id: {"id": user_id})
    monkeypatch.setattr(
        tasks,
        "has_ai_generated_post_for_trigger_today",
        lambda user_id, trigger_name: calls.setdefault("duplicate_check", (user_id, trigger_name)) and False,
    )

    def create_post(**kwargs):
        calls["create"] = kwargs
        return {"id": 91}

    monkeypatch.setattr(tasks, "create_ai_generated_post", create_post)

    tasks.generate_ai_posts_task.run(user_id=4)

    assert calls["duplicate_check"] == (4, "Launch day")
    assert calls["create"]["user_id"] == 4
    assert calls["create"]["content_text"] == "A useful update"