# Section 2: Send Confirmation Task (runs every minute via Beat)
# Section 3: Expiry Checker Task (runs every minute via Beat)
# Section 4: Publish Post Task (triggered on approval)

from celery_app import celery_app
import os
from database import execute_query
from database import init_db
from datetime import datetime, timezone
import asyncio
from event_fetcher import run_recommendation_pipeline
import time
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
    increment_occurrence_count,
    get_template_by_id,
    create_scheduled_post,
    get_user_by_id
)
from services import (
    send_confirmation_email,
    send_success_email,
    send_failure_email,
    send_expired_email
)
from utils import (
    generate_confirmation_token,
    hash_token,
    calculate_single_next_date,
    check_and_refresh_token
)


init_db()

BASE_URL = "http://localhost:8001"

@celery_app.task(name="tasks.send_confirmation_task")
def send_confirmation_task():
    print("🔍 Checking for posts due for confirmation...")
    posts = get_posts_due_for_confirmation()
    if not posts:
        print("✅ No posts due for confirmation")
        return
    for post in posts:
        try:
            if post["confirmation_sent_at"]:
                print(f"⏭️ Post {post['id']} confirmation already sent")
                continue
            raw_token    = generate_confirmation_token()
            hashed       = hash_token(raw_token)
            save_confirmation_token(post["id"], hashed)
            update_post_status(post["id"], "awaiting_approval")
            approve_url = f"{BASE_URL}/approvals/{post['id']}/approve?token={raw_token}"
            reject_url  = f"{BASE_URL}/approvals/{post['id']}/reject?token={raw_token}"
            user = get_user_by_id(post["user_id"])
            scheduled_at = post["scheduled_at"].strftime("%B %d, %Y at %I:%M %p UTC")
            send_confirmation_email(
                to_email     = user["email"],
                post_content = post["content_text"],
                platforms    = post["platforms"],
                scheduled_at = scheduled_at,
                approve_url  = approve_url,
                reject_url   = reject_url
            )
            print(f"✅ Confirmation sent for post {post['id']} to {user['email']}")

        except Exception as e:
            print(f"❌ Failed to send confirmation for post {post['id']}: {e}")


@celery_app.task(name="tasks.expiry_checker_task")
def expiry_checker_task():
    print("🔍 Checking for expired posts...")
    posts = get_expired_awaiting_posts()
    if not posts:
        print("✅ No expired posts found")
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
            print(f"⚠️ Post {post['id']} marked as expired")

        except Exception as e:
            print(f"❌ Failed to process expired post {post['id']}: {e}")

@celery_app.task(
    name="tasks.publish_post_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)


def publish_post_task(self, post_id: int):
    print(f"🚀 Publishing post {post_id}...")

    try:
        post = get_post_by_id(post_id)
        if not post:
            print(f"❌ Post {post_id} not found")
            return

        if post["status"] == "posted":
            print(f"⏭️ Post {post_id} already published")
            return

        update_post_status(post_id, "posting")

        existing_targets = get_targets_for_post(post_id)
        if not existing_targets:
            create_post_targets(post_id, post["platforms"])

        success_platforms = []
        failed_platforms  = []

        print(f"🎯 Platforms to publish: {post['platforms']}")

        for platform in post["platforms"]:
            print(f"📤 Attempting: {platform}")
            try:
                access_token = asyncio.run(
                    check_and_refresh_token(post["user_id"], platform)
                )

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
                    print(f"✅ Posted to {platform}")
                else:
                    raise Exception(result.get("error", "Unknown error"))

            except Exception as platform_error:
                update_target_status(post_id, platform, "failed", str(platform_error))
                failed_platforms.append(platform)
                print(f"❌ Failed to post to {platform}: {platform_error}")

        user         = get_user_by_id(post["user_id"])
        published_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

        if success_platforms and not failed_platforms:
            update_post_status(post_id, "posted")
            send_success_email(
                to_email     = user["email"],
                post_content = post["content_text"],
                platforms    = success_platforms,
                published_at = published_at
            )
            print(f"✅ Post {post_id} published successfully on: {success_platforms}")

        elif success_platforms and failed_platforms:
            update_post_status(post_id, "posted")
            send_success_email(
                to_email     = user["email"],
                post_content = post["content_text"],
                platforms    = success_platforms,
                published_at = published_at
            )
            print(f"⚠️ Post {post_id} partially published.")
            print(f"   ✅ Success: {success_platforms}")
            print(f"   ❌ Failed:  {failed_platforms}")

        else:
            update_post_status(post_id, "failed")
            send_failure_email(
                to_email         = user["email"],
                post_content     = post["content_text"],
                failed_platforms = failed_platforms,
                error            = "All platforms failed to publish"
            )
            print(f"❌ Post {post_id} failed on all platforms: {failed_platforms}")

        _generate_next_occurrence(post)

    except Exception as e:
        print(f"❌ publish_post_task failed for post {post_id}: {e}")
        update_post_status(post_id, "failed")
        raise self.retry(exc=e)


def _publish_to_facebook(post: dict, access_token: str) -> dict:
    import httpx
    from database import get_social_account

    account = get_social_account(post["user_id"], "facebook")
    page_id = account["page_id"]

    for attempt in range(3):
        try:
            if post.get("media_url"):
                response = httpx.post(
                    f"https://graph.facebook.com/v18.0/{page_id}/photos",
                    data={
                        "url"          : post["media_url"],
                        "caption"      : post["content_text"],
                        "access_token" : access_token
                    },
                    timeout=30.0
                )
            else:
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
            print(f"❌ Facebook publish failed response: {data}")
            return {
                "success": False,
                "error"  : data.get("error", {}).get("message", "Unknown Facebook error")
            }

        except httpx.TimeoutException:
            print(f"⏳ Facebook timeout attempt {attempt + 1}/3")
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
        print("❌ Instagram: no account found in database")
        return {"success": False, "error": "Instagram account not connected"}

    ig_user_id = account["page_id"]

    if not post.get("media_url"):
        print("⚠️ Instagram skipped: no image URL provided")
        return {"success": False, "error": "Instagram requires an image or video URL"}

    for attempt in range(3):  
        try:
            print(f"📸 Instagram attempt {attempt + 1}/3 - creating container...")
            container_response = httpx.post(
                f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
                data={
                    "caption"      : post["content_text"],
                    "image_url"    : post["media_url"],
                    "media_type"   : "IMAGE",
                    "access_token" : access_token
                },
                timeout=30.0
            )
            container = container_response.json()
            print(f"📸 Container response: {container_response.status_code} {container}")

            if "id" not in container:
                return {
                    "success": False,
                    "error": container.get("error", {}).get("message", "Container creation failed")
                }

            publish_response = httpx.post(
                f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
                data={
                    "creation_id"  : container["id"],
                    "access_token" : access_token
                },
                timeout=30.0
            )
            publish_data = publish_response.json()
            print(f"📸 Publish response: {publish_response.status_code} {publish_data}")

            if "id" in publish_data:
                return {"success": True, "post_id": publish_data["id"]}
            return {
                "success": False,
                "error": publish_data.get("error", {}).get("message", "Instagram publish failed")
            }

        except httpx.TimeoutException:
            print(f"⏳ Instagram timeout attempt {attempt + 1}/3")
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
        print(f"❌ LinkedIn asset registration failed: {reg_data}")
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
        print(f"❌ LinkedIn upload failed: {put_response.status_code} {put_response.text}")
        return {"success": False, "error": "LinkedIn image upload failed"}

    return {"success": True, "asset": asset}


def _publish_to_linkedin(post: dict, access_token: str) -> dict:
    import httpx
    from database import get_social_account

    account  = get_social_account(post["user_id"], "linkedin")
    user_urn = account["page_id"]

    headers = {
        "Authorization"              : f"Bearer {access_token}",
        "Content-Type"               : "application/json",
        "X-Restli-Protocol-Version"  : "2.0.0"
    }

    if post.get("media_url"):
        upload_result = _upload_linkedin_image(post["media_url"], access_token, user_urn)
        if not upload_result["success"]:
            return upload_result
        media_payload = [
            {
                "status": "READY",
                "description": {"text": post["content_text"]},
                "media": upload_result["asset"],
                "title": {"text": "Image"}
            }
        ]
        specific_content = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post["content_text"]},
                "shareMediaCategory": "IMAGE",
                "media": media_payload
            }
        }
    else:
        specific_content = {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post["content_text"]},
                "shareMediaCategory": "NONE"
            }
        }

    payload = {
        "author"         : user_urn,
        "lifecycleState" : "PUBLISHED",
        "specificContent": specific_content,
        "visibility": {
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
        print(f"❌ LinkedIn ugcPosts failed: {response.status_code} {response.text}")
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
            print(f"⏭️ One time post, no next occurrence")
            return

        if template["status"] != "active":
            print(f"⏭️ Template {template['id']} is {template['status']}, skipping")
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
            print(f"✅ Template {template['id']} has completed all occurrences")
            from database import execute_query
            execute_query(
                "UPDATE post_templates SET status = 'completed' WHERE id = %s",
                (template["id"],)
            )
            return

        new_post = create_scheduled_post(template["id"], next_date)
        increment_occurrence_count(template["id"])
        print(f"✅ Next occurrence created: {next_date} (post id: {new_post['id']})")

    except Exception as e:
        print(f"❌ Failed to generate next occurrence: {e}")

# ================================================================
# SECTION 5 — AI RECOMMENDATION TASK
# ================================================================

import asyncio
from event_fetcher import run_recommendation_pipeline

@celery_app.task(name="tasks.generate_ai_posts_task")
def generate_ai_posts_task(user_id: int):
    print(f"🤖 Running AI post generation for user {user_id}...")
    try:
        posts = asyncio.run(run_recommendation_pipeline(user_id))
        if not posts:
            print(f"⚠️ No posts generated for user {user_id}")
            return
        user = get_user_by_id(user_id)
        if not user:
            print(f"❌ User {user_id} not found")
            return

        for post_data in posts:
            try:
                template = execute_query("""
                    INSERT INTO post_templates
                        (user_id, content_text, media_url, platforms,
                         recurrence_type, interval_days, start_date, timezone)
                    VALUES (%s, %s, NULL, %s, 'ONE_TIME', 1, %s, 'UTC')
                    RETURNING id
                """, (
                    user_id,
                    post_data["content_text"],
                    post_data["platforms"],
                    post_data["scheduled_at"]
                ), fetch="one")

                if not template:
                    continue

                template_id = template["id"]
                post = execute_query("""
                    INSERT INTO scheduled_posts
                        (template_id, scheduled_at, status)
                    VALUES (%s, %s, 'awaiting_approval')
                    RETURNING id
                """, (template_id, post_data["scheduled_at"]), fetch="one")

                if not post:
                    continue

                post_id = post["id"]
                from utils import generate_confirmation_token, hash_token
                raw_token = generate_confirmation_token()
                hashed    = hash_token(raw_token)
                save_confirmation_token(post_id, hashed)
                from services import send_confirmation_email
                BASE_URL    = os.getenv("BASE_URL", "http://localhost:8001")
                approve_url = f"{BASE_URL}/approvals/{post_id}/approve?token={raw_token}"
                reject_url  = f"{BASE_URL}/approvals/{post_id}/reject?token={raw_token}"

                scheduled_str = post_data["scheduled_at"].strftime("%B %d, %Y at %I:%M %p UTC")

                send_confirmation_email(
                    to_email     = user["email"],
                    post_content = post_data["content_text"],
                    platforms    = post_data["platforms"],
                    scheduled_at = scheduled_str,
                    approve_url  = approve_url,
                    reject_url   = reject_url
                )

                print(f"✅ AI post created (id: {post_id}) | {post_data['trigger_type']}: {post_data['trigger_name']}")

            except Exception as e:
                print(f"❌ Failed to save post for user {user_id}: {e}")
                continue

        print(f"✅ AI generation done for user {user_id} — {len(posts)} posts queued")

    except Exception as e:
        print(f"❌ generate_ai_posts_task failed for user {user_id}: {e}")


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
        print("⚠️ No users with completed profiles found")
        return

    print(f"🤖 Triggering AI generation for {len(users)} users...")
    for user in users:
        generate_ai_posts_task.delay(user["user_id"])
        print(f"✅ Queued AI generation for user {user['user_id']}")