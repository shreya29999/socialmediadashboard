from celery_app import celery_app
import os
from database import execute_query
from database import init_db
from datetime import datetime, timezone
import time
from event_fetcher import run_recommendation_pipeline_sync
from database import (
    get_posts_due_for_confirmation,
    get_expired_awaiting_posts,
    get_post_by_id,
    get_targets_for_post,
    update_post_status,
    update_target_status,
    create_post_targets,
    save_confirmation_token,
    get_post_by_token,
    approve_post,
    reject_post,
    increment_occurrence_count,
    get_template_by_id,
    create_scheduled_post,
    get_user_by_id,
    create_approval_stage,
    update_hr_approval,
    save_admin_token,         
    get_approval_stage,
    update_last_login,
    get_posts_ready_to_publish,
    create_notification
)
from services import (
    send_confirmation_email,
    send_success_email,
    send_failure_email,
    send_expired_email,
    send_admin_approval_email,  
    send_hr_decision_notify_email
)
from utils import (
    generate_confirmation_token,
    hash_token,
    calculate_single_next_date,
    check_and_refresh_token
)
from logger import logger
init_db()
BASE_URL = os.getenv("BASE_URL")

@celery_app.task(name="tasks.send_confirmation_task")
def send_confirmation_task():
    logger.info("Checking for posts due for confirmation")
    posts = get_posts_due_for_confirmation()
    if not posts:
        return
    for post in posts:
        try:
            if post["confirmation_sent_at"]:
                continue
            owner = get_user_by_id(post["user_id"])
            raw_token = generate_confirmation_token()
            hashed    = hash_token(raw_token)
            save_confirmation_token(post["id"], hashed)
            create_approval_stage(post["id"])
            update_post_status(post["id"], "awaiting_hr_approval")
            approve_url = f"{BASE_URL}/approvals/{post['id']}/hr-approve?token={raw_token}"
            reject_url  = f"{BASE_URL}/approvals/{post['id']}/hr-reject?token={raw_token}"
            scheduled_at = post["scheduled_at"].strftime("%B %d, %Y at %I:%M %p UTC")
            send_confirmation_email(
                to_email     = owner["email"],
                post_content = post["content_text"],
                platforms    = post["platforms"],
                scheduled_at = scheduled_at,
                approve_url  = approve_url,
                reject_url   = reject_url
            )
            create_notification(
                user_id = post["user_id"],
                type    = "hr_approval_requested",
                title   = "Post awaiting your approval",
                message = f"Your post scheduled for {scheduled_at} needs approval before it goes live.",
                link    = f"/posts/{post['id']}",
                post_id = post["id"]
            )
            logger.info("HR confirmation sent for post %s", post["id"])
        except Exception:
            logger.exception("Failed to send confirmation for post %s", post["id"])

def _escalate_to_admin(post_id: int, hr_status: str, hr_reason: str = None):
    try:
        post = get_post_by_id(post_id)
        user = get_user_by_id(post["user_id"])
        if not user.get("admin_id"):
            if hr_status == "approved":
                approve_post(post_id)
                publish_post_task.delay(post_id)
                logger.info("Post %s approved (no admin on account) — queued for publishing", post_id)
            else:
                reject_post(post_id, hr_reason)
                logger.info("Post %s rejected (no admin on account) — cancelled", post_id)
            return
        admin = get_user_by_id(user["admin_id"])
        if not admin:
            logger.error("Admin %s not found — cannot escalate post %s", user["admin_id"], post_id)
            return
        raw_token = generate_confirmation_token()
        hashed    = hash_token(raw_token)
        save_admin_token(post_id, hashed)
        update_post_status(post_id, "awaiting_admin_approval")
        scheduled_at = post["scheduled_at"].strftime("%B %d, %Y at %I:%M %p UTC")
        approve_url = f"{BASE_URL}/approvals/{post_id}/admin-approve?token={raw_token}"
        reject_url  = f"{BASE_URL}/approvals/{post_id}/admin-reject?token={raw_token}"

        send_admin_approval_email(
            to_email     = admin["email"],
            post_content = post["content_text"],
            platforms    = post["platforms"],
            scheduled_at = scheduled_at,
            approve_url  = approve_url,
            reject_url   = reject_url,
            hr_status    = hr_status,
            hr_reason    = hr_reason,
            user_email   = user["email"],
            brand_name   = ""
        )
        create_notification(
            user_id = admin["id"],
            type    = "admin_approval_requested",
            title   = "Post awaiting your approval",
            message = f"A post from {user['email']} needs your final review (HR: {hr_status}).",
            link    = f"/admin/pending",
            post_id = post_id
        )
        send_hr_decision_notify_email(
            to_email     = user["email"],
            post_content = post["content_text"],
            hr_status    = hr_status,
            reason       = hr_reason
        )
        create_notification(
            user_id = user["id"],
            type    = "hr_decision",
            title   = "HR reviewed your post" if hr_status == "approved" else "HR rejected your post",
            message = (
                "HR approved your post — it's now with your Admin for final review."
                if hr_status == "approved"
                else f"HR rejected your post{f': {hr_reason}' if hr_reason else ''}. It has been escalated to your Admin."
            ),
            link    = f"/posts/{post_id}",
            post_id = post_id
        )
        logger.info("Post %s escalated to admin %s (HR: %s)", post_id, admin["id"], hr_status)
    except Exception:
        logger.exception("Failed to escalate post %s to admin", post_id)


@celery_app.task(name="tasks.expiry_checker_task")
def expiry_checker_task():
    logger.info("Checking for expired posts")
    posts = get_expired_awaiting_posts()
    if not posts:
        logger.info("No expired posts found")
        return
    for post in posts:
        try:
            update_post_status(post["id"], "expired")
            full_post = get_post_by_id(post["id"])
            user      = get_user_by_id(full_post["user_id"])
            scheduled_at = post["scheduled_at"].strftime("%B %d, %Y at %I:%M %p UTC")
            send_expired_email(
                to_email     = user["email"],
                post_content = full_post["content_text"],
                scheduled_at = scheduled_at
            )
            create_notification(
                user_id = full_post["user_id"],
                type    = "post_expired",
                title   = "Post expired without approval",
                message = f"Your post scheduled for {scheduled_at} was not approved in time and has been cancelled.",
                link    = f"/posts/{post['id']}",
                post_id = post["id"]
            )
            logger.warning("Post %s marked as expired", post["id"])

        except Exception as e:
            logger.exception("Failed to process expired post %s", post["id"])

@celery_app.task(name="tasks.publish_due_posts_task")
def publish_due_posts_task():
    logger.info("Checking for posts due for publishing")
    posts = get_posts_ready_to_publish()
    if not posts:
        return
    for post in posts:
        try:
            if post["status"] == "scheduled":
                approve_post(post["id"])
            publish_post_task.delay(post["id"])
            logger.info("Post %s queued for publishing (scheduled_at reached)", post["id"])
        except Exception:
            logger.exception("Failed to queue due post %s", post["id"])


@celery_app.task(
    name="tasks.publish_post_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)

def publish_post_task(self, post_id: int):
    logger.info("Publishing post %s...", post_id)

    try:
        post = get_post_by_id(post_id)
        if not post:
            logger.warning("Post %s not found", post_id)
            return
        if post["status"] == "posted":
            logger.info("Post %s already published", post_id)
            return
        update_post_status(post_id, "posting")
        existing_targets = get_targets_for_post(post_id)
        if not existing_targets:
            create_post_targets(post_id, post["platforms"])
        success_platforms = []
        failed_platforms  = []
        logger.info("Platforms to publish: %s", post['platforms'])
        for platform in post["platforms"]:
            logger.info("Attempting publish for %s", platform)
            try:
                access_token = check_and_refresh_token(post["user_id"], platform)
                if not access_token:
                    raise Exception(f"No valid token for {platform}")
                if platform == "facebook":
                    result = _publish_to_facebook(post, access_token)
                elif platform == "instagram":
                    result = _publish_to_instagram(post, access_token)
                elif platform == "linkedin":
                    result = _publish_to_linkedin(post, access_token)
                else:
                    raise Exception(f"Unknown platform: {platform}")
                if result["success"]:
                    update_target_status(post_id, platform, "posted")
                    success_platforms.append(platform)
                    logger.info("Posted to %s", platform)
                else:
                    raise Exception(result.get("error", "Unknown error"))
            except Exception as platform_error:
                update_target_status(post_id, platform, "failed", str(platform_error))
                failed_platforms.append(platform)
                logger.error("Failed to post to %s: %s", platform, platform_error)
        user = get_user_by_id(post["user_id"])
        published_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")
        if success_platforms and not failed_platforms:
            update_post_status(post_id, "posted")
            send_success_email(
                to_email     = user["email"],
                post_content = post["content_text"],
                platforms    = success_platforms,
                published_at = published_at
            )
            create_notification(
                user_id = post["user_id"],
                type    = "post_published",
                title   = "Your post is live!",
                message = f"Published on {', '.join(success_platforms)} at {published_at}.",
                link    = f"/posts/{post_id}",
                post_id = post_id
            )
            logger.info("Post %s published successfully on: %s", post_id, success_platforms)
        elif success_platforms and failed_platforms:
            update_post_status(post_id, "posted")
            send_success_email(
                to_email     = user["email"],
                post_content = post["content_text"],
                platforms    = success_platforms,
                published_at = published_at
            )
            create_notification(
                user_id = post["user_id"],
                type    = "post_published",
                title   = "Your post is live (partially)",
                message = f"Published on {', '.join(success_platforms)}, but failed on {', '.join(failed_platforms)}.",
                link    = f"/posts/{post_id}",
                post_id = post_id
            )
            logger.warning("Post %s partially published. Success: %s, Failed: %s", post_id, success_platforms, failed_platforms)
        else:
            update_post_status(post_id, "failed")
            send_failure_email(
                to_email         = user["email"],
                post_content     = post["content_text"],
                failed_platforms = failed_platforms,
                error            = "All platforms failed to publish"
            )
            create_notification(
                user_id = post["user_id"],
                type    = "post_failed",
                title   = "Post publishing failed",
                message = f"Failed to publish on {', '.join(failed_platforms)}. Please check your connected accounts.",
                link    = f"/posts/{post_id}",
                post_id = post_id
            )
            logger.error("Post %s failed on all platforms: %s", post_id, failed_platforms)
        _generate_next_occurrence(post)
    except Exception as e:
        logger.exception("publish_post_task failed for post %s", post_id)
        update_post_status(post_id, "failed")
        raise self.retry(exc=e)

def _publish_to_facebook(post: dict, access_token: str) -> dict:
    import httpx
    from database import get_social_account
    account = get_social_account(post["user_id"], "facebook")
    page_id = account["page_id"]
    media_url = post.get("media_url")
    is_video  = _is_video_url(media_url)
    for attempt in range(3):
        try:
            if media_url and is_video:
                logger.info("Facebook: posting video")
                response = httpx.post(
                    f"https://graph.facebook.com/v18.0/{page_id}/videos",
                    data={
                        "file_url"     : media_url,
                        "description"  : post["content_text"],
                        "access_token" : access_token
                    },
                    timeout=60.0   
                )
            elif media_url:
                logger.info("Facebook: posting image")
                response = httpx.post(
                    f"https://graph.facebook.com/v18.0/{page_id}/photos",
                    data={
                        "url"          : media_url,
                        "caption"      : post["content_text"],
                        "access_token" : access_token
                    },
                    timeout=30.0
                )
            else:
                logger.info("Facebook: posting text only")
                response = httpx.post(
                    f"https://graph.facebook.com/v18.0/{page_id}/feed",
                    data={
                        "message"      : post["content_text"],
                        "access_token" : access_token
                    },
                    timeout=30.0
                )
            data = response.json()
            if "id" in data:
                return {"success": True, "post_id": data["id"]}
            logger.error("Facebook publish failed: %s", data)
            return {
                "success": False,
                "error"  : data.get("error", {}).get("message", "Unknown Facebook error")
            }

        except httpx.TimeoutException:
            logger.warning("Facebook timeout attempt %s/3", attempt + 1)
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return {"success": False, "error": "Facebook API timed out after 3 attempts"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Facebook: max retries exceeded"}


def _publish_to_instagram(post: dict, access_token: str) -> dict:
    import httpx
    from database import get_social_account

    account = get_social_account(post["user_id"], "instagram")
    if not account:
        return {"success": False, "error": "Instagram account not connected"}

    ig_user_id = account["page_id"]
    media_url  = post.get("media_url")
    is_video   = _is_video_url(media_url)

    if not media_url:
        return {"success": False, "error": "Instagram requires an image or video URL"}

    for attempt in range(3):
        try:
            if is_video:
                logger.info("Instagram attempt %s/3 - creating video container...", attempt + 1)
                container_data = {
                    "caption"      : post["content_text"],
                    "video_url"    : media_url,
                    "media_type"   : "REELS",         
                    "share_to_feed": "true",
                    "access_token" : access_token
                }
            else:
                logger.info("Instagram attempt %s/3 - creating image container...", attempt + 1)
                container_data = {
                    "caption"      : post["content_text"],
                    "image_url"    : media_url,
                    "media_type"   : "IMAGE",
                    "access_token" : access_token
                }

            container_response = httpx.post(
                f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
                data=container_data,
                timeout=60.0
            )
            container = container_response.json()
            logger.debug("Instagram container response: %s %s", container_response.status_code, container)

            if "id" not in container:
                return {
                    "success": False,
                    "error": container.get("error", {}).get("message", "Container creation failed")
                }
            creation_id = container["id"]
            if is_video:
                logger.info("Instagram: waiting for video processing...")
                for poll_attempt in range(15):   
                    time.sleep(5)
                    status_resp = httpx.get(
                        f"https://graph.facebook.com/v18.0/{creation_id}",
                        params={
                            "fields"       : "status_code",
                            "access_token" : access_token
                        },
                        timeout=15.0
                    )
                    status_data = status_resp.json()
                    status_code = status_data.get("status_code")
                    logger.debug("Instagram video status: %s (poll %s/15)", status_code, poll_attempt + 1)
                    if status_code == "FINISHED":
                        break
                    elif status_code == "ERROR":
                        return {"success": False, "error": "Instagram video processing failed"}
                    elif status_code == "EXPIRED":
                        return {"success": False, "error": "Instagram video container expired"}
                else:
                    return {"success": False, "error": "Instagram video processing timed out"}

            publish_response = httpx.post(
                f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
                data={
                    "creation_id"  : creation_id,
                    "access_token" : access_token
                },
                timeout=30.0
            )
            publish_data = publish_response.json()
            logger.debug("Instagram publish response: %s %s", publish_response.status_code, publish_data)
            if "id" in publish_data:
                return {"success": True, "post_id": publish_data["id"]}
            return {
                "success": False,
                "error": publish_data.get("error", {}).get("message", "Instagram publish failed")
            }
        except httpx.TimeoutException:
            logger.warning("Instagram timeout attempt %s/3", attempt + 1)
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return {"success": False, "error": "Instagram API timed out after 3 attempts"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Instagram: max retries exceeded"}

def _upload_linkedin_image(image_url: str, access_token: str, owner: str) -> dict:
    import httpx

    headers = {
        "Authorization"             : f"Bearer {access_token}",
        "Content-Type"              : "application/json",
        "X-Restli-Protocol-Version" : "2.0.0"
    }
    register_payload = {
        "registerUploadRequest": {
            "owner": owner,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {
                    "identifier": "urn:li:userGeneratedContent",
                    "relationshipType": "OWNER"
                }
            ],
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
        }
    }
    reg_response = httpx.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        json=register_payload,
        headers=headers,
        timeout=30.0
    )
    reg_data = reg_response.json()
    asset = reg_data.get("value", {}).get("asset")
    upload_mechanism = reg_data.get("value", {}).get("uploadMechanism", {})
    upload_url = upload_mechanism.get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}).get("uploadUrl")

    if not asset or not upload_url:
        logger.error("LinkedIn asset registration failed: %s", reg_data)
        return {
            "success": False,
            "error": reg_data.get("message", "LinkedIn asset registration failed")
        }
    image_response = httpx.get(image_url, timeout=30.0)
    if image_response.status_code != 200:
        return {"success": False, "error": "Failed to fetch image for LinkedIn upload"}
    content_type = image_response.headers.get("content-type", "image/jpeg")
    upload_headers = {"Content-Type": content_type}
    put_response = httpx.put(upload_url, content=image_response.content, headers=upload_headers, timeout=60.0)
    if put_response.status_code not in (200, 201, 202):
        logger.error("LinkedIn upload failed: %s %s", put_response.status_code, put_response.text)
        return {"success": False, "error": "LinkedIn image upload failed"}
    return {"success": True, "asset": asset}

def _upload_linkedin_video(video_url: str, access_token: str, owner: str) -> dict:
    import httpx

    headers = {
        "Authorization"             : f"Bearer {access_token}",
        "Content-Type"              : "application/json",
        "X-Restli-Protocol-Version" : "2.0.0"
    }
    register_payload = {
        "registerUploadRequest": {
            "owner": owner,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "serviceRelationships": [
                {
                    "identifier"      : "urn:li:userGeneratedContent",
                    "relationshipType": "OWNER"
                }
            ],
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
        }
    }
    reg_response = httpx.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        json=register_payload,
        headers=headers,
        timeout=30.0
    )
    reg_data = reg_response.json()
    asset      = reg_data.get("value", {}).get("asset")
    upload_url = reg_data.get("value", {}).get("uploadMechanism", {}).get(
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}
    ).get("uploadUrl")
    if not asset or not upload_url:
        logger.error("LinkedIn video registration failed: %s", reg_data)
        return {"success": False, "error": "LinkedIn video asset registration failed"}
    video_response = httpx.get(video_url, timeout=60.0)
    if video_response.status_code != 200:
        return {"success": False, "error": "Failed to fetch video for LinkedIn upload"}
    put_response = httpx.put(
        upload_url,
        content=video_response.content,
        headers={"Content-Type": "video/mp4"},
        timeout=120.0   
    )
    if put_response.status_code not in (200, 201, 202):
        logger.error("LinkedIn video upload failed: %s", put_response.status_code)
        return {"success": False, "error": "LinkedIn video upload failed"}
    return {"success": True, "asset": asset}

def _publish_to_linkedin(post: dict, access_token: str) -> dict:
    import httpx
    from database import get_social_account
    account   = get_social_account(post["user_id"], "linkedin")
    user_urn  = account["page_id"]
    media_url = post.get("media_url")
    is_video  = _is_video_url(media_url)
    headers = {
        "Authorization"             : f"Bearer {access_token}",
        "Content-Type"              : "application/json",
        "X-Restli-Protocol-Version" : "2.0.0"
    }
    if media_url and is_video:
        logger.info("LinkedIn: uploading video...")
        upload_result = _upload_linkedin_video(media_url, access_token, user_urn)
        if not upload_result["success"]:
            return upload_result
        specific_content = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary"   : {"text": post["content_text"]},
                "shareMediaCategory": "VIDEO",
                "media": [
                    {
                        "status"     : "READY",
                        "media"      : upload_result["asset"],
                        "title"      : {"text": "Video"},
                        "description": {"text": post["content_text"]}
                    }
                ]
            }
        }
    elif media_url:
        logger.info("LinkedIn: uploading image...")
        upload_result = _upload_linkedin_image(media_url, access_token, user_urn)
        if not upload_result["success"]:
            return upload_result
        specific_content = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary"   : {"text": post["content_text"]},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status"     : "READY",
                        "media"      : upload_result["asset"],
                        "title"      : {"text": "Image"},
                        "description": {"text": post["content_text"]}
                    }
                ]
            }
        }
    else:
        logger.info("LinkedIn: posting text only...")
        specific_content = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary"   : {"text": post["content_text"]},
                "shareMediaCategory": "NONE"
            }
        }
    payload = {
        "author"         : user_urn,
        "lifecycleState" : "PUBLISHED",
        "specificContent": specific_content,
        "visibility"     : {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    try:
        response = httpx.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        if response.status_code == 201:
            return {"success": True, "post_id": response.headers.get("x-restli-id")}
        logger.error("LinkedIn ugcPosts failed: %s %s", response.status_code, response.text)
        return {
            "success": False,
            "error"  : response.json().get("message", "LinkedIn post failed")
        }
    except httpx.TimeoutException:
        return {"success": False, "error": "LinkedIn API timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    

def _generate_next_occurrence(post: dict):
    try:
        template = get_template_by_id(post["template_id"])
        if not template:
            return
        if template["recurrence_type"] == "ONE_TIME":
            logger.info("One time post, no next occurrence")
            return
        if template["status"] != "active":
            logger.info("Template %s is %s, skipping", template["id"], template["status"])
            return
        next_date = calculate_single_next_date(
            recurrence_type  = template["recurrence_type"],
            last_date        = post["scheduled_at"],
            interval_days    = template["interval_days"],
            end_date         = template["end_date"],
            max_occurrences  = template["max_occurrences"],
            occurrence_count = template["occurrence_count"]
        )
        if not next_date:
            logger.info("Template %s has completed all occurrences", template["id"])
            from database import execute_query
            execute_query(
                "UPDATE post_templates SET status = 'completed' WHERE id = %s",
                (template["id"],)
            )
            return
        new_post = create_scheduled_post(template["id"], next_date)
        increment_occurrence_count(template["id"])
        logger.info("Next occurrence created: %s (post id: %s)", next_date, new_post["id"])
    except Exception as e:
        logger.exception("Failed to generate next occurrence")


@celery_app.task(name="tasks.generate_ai_posts_task")
def generate_ai_posts_task(user_id: int):
    logger.info("Running AI post generation for user %s...", user_id)
    try:
        posts = run_recommendation_pipeline_sync(user_id)
        if not posts:
            logger.warning("No posts generated for user %s", user_id)
            return
        user = get_user_by_id(user_id)
        if not user:
            logger.error("User %s not found", user_id)
            return
        created_count = 0
        for post_data in posts:
            try:
                duplicate = execute_query("""
                    SELECT sp.id FROM scheduled_posts sp
                    WHERE sp.trigger_name = %s
                    AND sp.ai_generated = TRUE
                    AND sp.created_at::date = CURRENT_DATE
                    AND EXISTS (
                        SELECT 1 FROM post_templates pt
                        WHERE pt.id = sp.template_id
                        AND pt.user_id = %s
                    )
                    LIMIT 1
                """, (post_data.get("trigger_name"), user_id), fetch="one")
                if duplicate:
                    logger.info("Duplicate skipped: %s", post_data.get('trigger_name'))
                    continue
                template = execute_query("""
                    INSERT INTO post_templates
                        (user_id, content_text, media_url, platforms,
                         recurrence_type, interval_days, start_date, timezone)
                    VALUES (%s, %s, %s, %s, 'ONE_TIME', 1, %s, 'UTC')
                    RETURNING id
                """, (
                    user_id,
                    post_data["content_text"],
                    post_data.get("media_url"),
                    post_data["platforms"],
                    post_data["scheduled_at"]
                ), fetch="one")
                if not template:
                    continue
                template_id = template["id"]
                post = execute_query("""
                    INSERT INTO scheduled_posts
                        (template_id, scheduled_at, status, ai_generated, trigger_type, trigger_name)
                    VALUES (%s, %s, 'scheduled', TRUE, %s, %s)
                    RETURNING id
                """, (
                    template_id,
                    post_data["scheduled_at"],
                    post_data.get("trigger_type"),
                    post_data.get("trigger_name")
                ), fetch="one")
                if not post:
                    continue
                created_count += 1
                logger.info(
                    "AI post created (id: %s) | %s: %s | platforms: %s",
                    post["id"],
                    post_data["trigger_type"],
                    post_data["trigger_name"],
                    post_data["platforms"]
                )
            except Exception:
                logger.exception("Failed to save AI post for user %s", user_id)
                continue
        logger.info("AI generation done for user %s — %s posts queued", user_id, created_count)
    except Exception:
        logger.exception("generate_ai_posts_task failed for user %s", user_id)


@celery_app.task(name="tasks.generate_ai_posts_for_all_users")
def generate_ai_posts_for_all_users():
    users = execute_query("""
        SELECT user_id FROM user_profiles
        WHERE persona IS NOT NULL
        AND industry IS NOT NULL
        AND brand_name IS NOT NULL
        AND tone IS NOT NULL
        AND country_code IS NOT NULL
    """, fetch="all")
    if not users:
        logger.warning("No users with completed profiles found")
        return
    logger.info("Triggering AI generation for %s users...", len(users))
    for user in users:
        generate_ai_posts_task.delay(user["user_id"])
        logger.info("Queued AI generation for user %s", user["user_id"])


def _is_video_url(url: str) -> bool:
    if not url:
        return False
    video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')
    url_lower = url.lower().split('?')[0] 
    return any(url_lower.endswith(ext) for ext in video_extensions)