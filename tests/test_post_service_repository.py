import asyncio
from datetime import datetime, timezone


def test_generate_and_store_uses_repository_layer(monkeypatch):
    calls = {}

    def fake_profile(user_id):
        calls["profile"] = user_id
        return {
            "persona": "creator",
            "industry": "tech",
            "brand_name": "Acme",
            "tone": "friendly",
            "audience": "startup founders",
            "country_code": "US",
            "language": "en",
            "posts_per_week": 3,
        }

    def fake_template(**kwargs):
        calls["template"] = kwargs
        return {"id": 11, "user_id": kwargs["user_id"]}

    def fake_post(template_id, scheduled_at, reposted_from_id=None):
        calls["post"] = {
            "template_id": template_id,
            "scheduled_at": scheduled_at,
            "reposted_from_id": reposted_from_id,
        }
        return {"id": 77}

    def fake_content(profile, title, platform):
        calls["content"] = {"title": title, "platform": platform}
        return {"caption": "Test caption", "image_prompt": "Test prompt"}

    async def fake_media(image_prompt, profile):
        calls["media"] = {"prompt": image_prompt, "profile": profile["brand_name"]}
        return "https://example.com/image.png"

    monkeypatch.setattr("app.repositories.user_repository.get_user_profile", fake_profile)
    monkeypatch.setattr("app.repositories.post_repository.create_post_template", fake_template)
    monkeypatch.setattr("app.repositories.post_repository.create_scheduled_post", fake_post)
    monkeypatch.setattr("app.ai.event_fetcher.generate_post_content_from_title", fake_content)
    monkeypatch.setattr("app.ai.event_fetcher.generate_media_url", fake_media)

    import app.services.post_service as post_service_module

    result = asyncio.run(
        post_service_module.PostService.generate_and_store(
            user_id=2,
            title="Launch update",
            platform="linkedin",
            generate_image=True,
            scheduled_at=datetime(2026, 1, 10, 15, 0, tzinfo=timezone.utc),
        )
    )

    assert calls["profile"] == 2
    assert calls["template"]["user_id"] == 2
    assert calls["post"]["template_id"] == 11
    assert result["post_id"] == 77
    assert result["caption"] == "Test caption"
