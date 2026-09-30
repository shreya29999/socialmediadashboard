from datetime import datetime , timezone
from typing  import Optional
from app.repositories.post_repository import (
    create_post_template,
    create_scheduled_post,
)
from app.repositories.user_repository import get_user_profile
from app.ai.event_fetcher import(
    generate_post_content_from_title,
    generate_media_url,
)
from app.core.logging import logger
class PostService:
    @staticmethod
    async def generate_and_store(
        user_id:int,
        title:str,
        platform:str,
        generate_image:bool = True,
        scheduled_at: Optional[datetime] = None,
    ):
        logger.info(
            "Starting AI post generation | user_id=%s | title=%s | platform=%s",
            user_id,
            title,
            platform,
        )

        profile = get_user_profile(user_id)
        if not profile:
            raise RuntimeError("User profile not found.")

        content = generate_post_content_from_title(
            profile=profile,
            title=title,
            platform=platform,
        )
        caption = (content.get("caption") or "").strip()
        image_prompt = (content.get("image_prompt") or "").strip()

                
        if not caption:
            raise RuntimeError(
                "AI failed to generate caption."
            )

        if not image_prompt:
            raise RuntimeError(
                "AI failed to generate image prompt."
            )

        image_url = None

        if generate_image:
            image_url = await generate_media_url(
                image_prompt=image_prompt,
                profile=profile,
            )

            if not image_url:
                logger.warning(
                    "Image generation failed | user_id=%s",
                    user_id,
                ) 

        if scheduled_at is None:
            scheduled_at = datetime.now(timezone.utc) 

        template = create_post_template(
            user_id=user_id,
            content_text=caption,
            media_url=image_url,
            platforms=[platform],
            recurrence_type="ONE_TIME",
            interval_days=1,
            start_date=scheduled_at,
            end_date=None,
            max_occurrences=1,
            timezone="UTC",
        )


        post = create_scheduled_post(
            template["id"],
            scheduled_at,
        )

        post_id = post["id"]

        logger.info(
            "AI post saved | user_id=%s | post_id=%s | template_id=%s",
            user_id,
            post_id,
            template["id"],
        )

        logger.info(
            "AI post generation completed | user_id=%s | post_id=%s",
            user_id,
            post_id,
        )

        return {
            "post_id": post_id,
            "title": title,
            "platform": platform,
            "caption": caption,
            "image_prompt": image_prompt,
            "image_url": image_url,
            "status": "generated",
            "scheduled_at": scheduled_at.isoformat(),
        }
              
            

