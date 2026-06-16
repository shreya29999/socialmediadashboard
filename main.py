# Section 1: Imports + App Init
# Section 2: Startup + Shutdown
# Section 3: Auth Routes (register, login)
# Section 4: Platform Routes (connect FB, IG, LI + account details)
# Section 5: Post Routes (create, list, get, edit, delete, skip, publish now)
# Section 6: Media Upload Route (Cloudinary)
# Section 7: Approval Routes (approve, reject)
# Section 8: Analytics Route
# Section 9: Calendar Routes

from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import httpx
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

from database import (
    init_db,
    create_user,
    get_user_by_email,
    execute_query,
    get_user_by_id,
    save_social_account,
    get_social_account,
    create_post_template,
    get_template_by_id,
    get_active_templates,
    pause_template,
    resume_template,
    create_scheduled_post,
    get_post_by_id,
    get_posts_by_status,
    get_posts_for_calendar,
    update_post_status,
    get_post_by_token,
    approve_post,
    reject_post,
    create_post_targets
)
from utils import (
    create_access_token,
    verify_access_token,
    hash_password,
    verify_password,
    verify_confirmation_token,
    calculate_next_dates as calc_dates
)
from tasks import publish_post_task

# ── SECTION 1 — APP INIT ────────────────────────────────

app = FastAPI(
    title="Social Media Dashboard",
    description="Automate your social media posts",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

META_APP_ID            = os.getenv("META_APP_ID")
META_APP_SECRET        = os.getenv("META_APP_SECRET")
META_REDIRECT_URI      = os.getenv("META_REDIRECT_URI")
LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI  = os.getenv("LINKEDIN_REDIRECT_URI")

CLOUDINARY_CLOUD_NAME  = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY     = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET  = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name = CLOUDINARY_CLOUD_NAME,
    api_key    = CLOUDINARY_API_KEY,
    api_secret = CLOUDINARY_API_SECRET,
    secure     = True
)


# ── SECTION 2 — STARTUP + SHUTDOWN ──────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    print("✅ App started, DB ready")


@app.on_event("shutdown")
async def shutdown():
    print("👋 App shutting down")


@app.get("/")
def root():
    return {"message": "Social Media Dashboard API v2 ✅"}


# ── SECTION 3 — AUTH ROUTES ─────────────────────────────

class RegisterRequest(BaseModel):
    email    : str
    password : str
    timezone : Optional[str] = "UTC"

class LoginRequest(BaseModel):
    email    : str
    password : str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token   = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@app.post("/auth/register")
def register(req: RegisterRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    user   = create_user(req.email, hashed)
    token  = create_access_token(user["id"], user["email"])
    return {
        "message"      : "Registered successfully",
        "access_token" : token,
        "user_id"      : user["id"],
        "email"        : user["email"]
    }


@app.post("/auth/login")
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return {
        "message"      : "Login successful",
        "access_token" : token,
        "user_id"      : user["id"],
        "email"        : user["email"]
    }


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── SECTION 4 — PLATFORM ROUTES ─────────────────────────

# ── Facebook ──

@app.get("/auth/facebook/connect")
def facebook_connect(current_user: dict = Depends(get_current_user)):
    user_id  = current_user["user_id"]
    existing = get_social_account(user_id, "facebook")
    if existing:
        return {
            "already_connected": True,
            "message"          : "Facebook already connected ✅",
            "page_id"          : existing["page_id"]
        }
    url = (
        f"https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={META_APP_ID}"
        f"&redirect_uri={META_REDIRECT_URI}"
        f"&scope=pages_manage_posts,pages_read_engagement,"
        f"pages_show_list,instagram_basic,"
        f"instagram_content_publish,business_management"
        f"&response_type=code"
        f"&state={current_user['user_id']}"
    )
    return {"already_connected": False, "oauth_url": url}


@app.get("/auth/facebook/callback")
async def facebook_callback(code: str = Query(...), state: str = Query(...)):
    user_id = int(state)
    async with httpx.AsyncClient() as client:
        token_response = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id"     : META_APP_ID,
                "client_secret" : META_APP_SECRET,
                "redirect_uri"  : META_REDIRECT_URI,
                "code"          : code
            }
        )
        token_data        = token_response.json()
        short_lived_token = token_data.get("access_token")
        if not short_lived_token:
            raise HTTPException(status_code=400, detail=f"Facebook token error: {token_data}")

        long_response    = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type"        : "fb_exchange_token",
                "client_id"         : META_APP_ID,
                "client_secret"     : META_APP_SECRET,
                "fb_exchange_token" : short_lived_token
            }
        )
        long_data        = long_response.json()
        long_lived_token = long_data.get("access_token", short_lived_token)
        expires_in       = long_data.get("expires_in", 5184000)

        from datetime import timedelta
        expires_at     = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        pages_response = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={
                "access_token" : long_lived_token,
                "fields"       : "id,name,access_token,instagram_business_account",
                "limit"        : 100
            }
        )
        pages      = pages_response.json().get("data", [])
        ig_account = None

        if pages:
            page       = pages[0]
            page_id    = page["id"]
            page_token = page.get("access_token", long_lived_token)
            ig_resp    = await client.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={"fields": "instagram_business_account", "access_token": page_token}
            )
            ig_account = ig_resp.json().get("instagram_business_account")
        else:
            me_data    = (await client.get(
                "https://graph.facebook.com/v18.0/me",
                params={"access_token": long_lived_token, "fields": "id,name"}
            )).json()
            page_id    = me_data.get("id")
            page_token = long_lived_token

        save_social_account(
            user_id=user_id, platform="facebook",
            access_token=page_token, page_id=page_id,
            token_expires_at=expires_at
        )
        if ig_account:
            save_social_account(
                user_id=user_id, platform="instagram",
                access_token=page_token, page_id=ig_account["id"]
            )

        return {
            "message"  : "Facebook connected ✅",
            "page_id"  : page_id,
            "instagram": ig_account["id"] if ig_account else "Not found"
        }


# ── LinkedIn ──

@app.get("/auth/linkedin/connect")
def linkedin_connect(current_user: dict = Depends(get_current_user)):
    user_id  = current_user["user_id"]
    existing = get_social_account(user_id, "linkedin")
    if existing:
        return {"already_connected": True, "message": "LinkedIn already connected ✅", "page_id": existing["page_id"]}
    url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={LINKEDIN_REDIRECT_URI}"
        f"&scope=openid profile email w_member_social"
        f"&state={current_user['user_id']}"
    )
    return {"already_connected": False, "oauth_url": url}


@app.get("/auth/linkedin/callback")
async def linkedin_callback(code: str = Query(...), state: str = Query(...)):
    user_id = int(state)
    async with httpx.AsyncClient() as client:
        token_data = (await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code", "code": code,
                "client_id": LINKEDIN_CLIENT_ID, "client_secret": LINKEDIN_CLIENT_SECRET,
                "redirect_uri": LINKEDIN_REDIRECT_URI
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )).json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail=f"LinkedIn token error: {token_data}")

        profile  = (await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )).json()
        user_urn = f"urn:li:person:{profile.get('sub')}"

        save_social_account(
            user_id=user_id, platform="linkedin",
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            page_id=user_urn
        )
    return {"message": "LinkedIn connected ✅", "user_urn": user_urn}


# ── Platform status (simple connected/not) ──

@app.get("/platforms/status")
def platform_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    status  = {}
    for platform in ["facebook", "instagram", "linkedin"]:
        account           = get_social_account(user_id, platform)
        status[platform]  = "connected" if account else "not connected"
    return status


# ── Platform accounts (real profile names) ──

@app.get("/platforms/accounts")
async def platform_accounts(current_user: dict = Depends(get_current_user)):
    user_id  = current_user["user_id"]
    accounts = {}

    # ── Facebook ──
    fb_account = get_social_account(user_id, "facebook")
    if fb_account:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/v18.0/{fb_account['page_id']}",
                    params={"fields": "id,name,fan_count", "access_token": fb_account["access_token"]}
                )
                data = resp.json()
                accounts["facebook"] = {
                    "connected"  : True,
                    "page_id"    : fb_account["page_id"],
                    "name"       : data.get("name", "Facebook Page"),
                    "followers"  : data.get("fan_count", 0)
                }
        except Exception:
            accounts["facebook"] = {"connected": True, "page_id": fb_account["page_id"], "name": "Facebook Page", "followers": 0}
    else:
        accounts["facebook"] = {"connected": False}

    # ── Instagram ──
    ig_account = get_social_account(user_id, "instagram")
    if ig_account:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/v18.0/{ig_account['page_id']}",
                    params={"fields": "id,name,username,followers_count", "access_token": ig_account["access_token"]}
                )
                data = resp.json()
                accounts["instagram"] = {
                    "connected"  : True,
                    "page_id"    : ig_account["page_id"],
                    "name"       : data.get("name", "Instagram Account"),
                    "username"   : data.get("username", ""),
                    "followers"  : data.get("followers_count", 0)
                }
        except Exception:
            accounts["instagram"] = {"connected": True, "page_id": ig_account["page_id"], "name": "Instagram Account", "followers": 0}
    else:
        accounts["instagram"] = {"connected": False}

    # ── LinkedIn ──
    li_account = get_social_account(user_id, "linkedin")
    if li_account:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {li_account['access_token']}"}
                )
                data = resp.json()
                accounts["linkedin"] = {
                    "connected" : True,
                    "page_id"   : li_account["page_id"],
                    "name"      : data.get("name", "LinkedIn User"),
                    "email"     : data.get("email", "")
                }
        except Exception:
            accounts["linkedin"] = {"connected": True, "page_id": li_account["page_id"], "name": "LinkedIn User"}
    else:
        accounts["linkedin"] = {"connected": False}

    return accounts


# ── SECTION 6 — MEDIA UPLOAD ────────────────────────────

@app.post("/media/upload")
async def upload_media(
    file         : UploadFile = File(...),
    current_user : dict       = Depends(get_current_user)
):

    allowed = {"image/jpeg", "image/jpg", "image/png"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are supported")

    contents = await file.read()
    if len(contents) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max size is 8MB")

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder          = "socialdesk",
            resource_type   = "image",
            allowed_formats = ["jpg", "jpeg", "png"],
            transformation  = [
                {"width": 1080, "height": 1080, "crop": "limit"},  
                {"quality": "auto"},
                {"fetch_format": "jpg"}  
            ]
        )
        return {
            "success"    : True,
            "url"        : result["secure_url"],
            "public_id"  : result["public_id"],
            "width"      : result.get("width"),
            "height"     : result.get("height"),
            "format"     : result.get("format"),
            "size_bytes" : result.get("bytes")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ── SECTION 5 — POST ROUTES ─────────────────────────────

class CreatePostRequest(BaseModel):
    content_text    : str
    media_url       : Optional[str] = None
    platforms       : List[str]
    recurrence_type : Optional[str] = "ONE_TIME"
    interval_days   : Optional[int] = 1
    start_date      : str
    end_date        : Optional[str] = None
    max_occurrences : Optional[int] = None
    timezone        : Optional[str] = "UTC"


class UpdatePostRequest(BaseModel):
    content_text : Optional[str] = None
    media_url    : Optional[str] = None
    platforms    : Optional[List[str]] = None
    scheduled_at : Optional[str] = None


class UserProfileRequest(BaseModel):
    persona        : str           
    industry       : str           
    brand_name     : str           
    tone           : str           
    audience       : str           
    country_code   : str           
    language       : str = "english"
    posts_per_week : int = 3



@app.post("/user/profile")
def save_user_profile(req: UserProfileRequest, current_user: dict = Depends(get_current_user)):
    execute_query("""
        INSERT INTO user_profiles 
            (user_id, persona, industry, brand_name, tone, audience, country_code, language, posts_per_week)
        VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            persona        = EXCLUDED.persona,
            industry       = EXCLUDED.industry,
            brand_name     = EXCLUDED.brand_name,
            tone           = EXCLUDED.tone,
            audience       = EXCLUDED.audience,
            country_code   = EXCLUDED.country_code,
            language       = EXCLUDED.language,
            posts_per_week = EXCLUDED.posts_per_week,
            updated_at     = NOW()
    """, (
        current_user["user_id"], req.persona, req.industry,
        req.brand_name, req.tone, req.audience,
        req.country_code, req.language, req.posts_per_week
    ))
    return {"message": "Profile saved ✅"}


@app.get("/user/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (current_user["user_id"],),
        fetch="one"
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete questionnaire.")
    return profile


@app.post("/posts/")
def create_post(req: CreatePostRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    start   = datetime.fromisoformat(req.start_date.replace('Z', '+00:00'))
    end     = datetime.fromisoformat(req.end_date.replace('Z', '+00:00')) if req.end_date else None

    template = create_post_template(
        user_id         = user_id,
        content_text    = req.content_text,
        media_url       = req.media_url,
        platforms       = req.platforms,
        recurrence_type = req.recurrence_type,
        interval_days   = req.interval_days,
        start_date      = start,
        end_date        = end,
        max_occurrences = req.max_occurrences,
        timezone        = req.timezone
    )
    template_id = template["id"]

    dates = calc_dates(
        recurrence_type = req.recurrence_type,
        start_date      = start,
        interval_days   = req.interval_days,
        count           = 30,
        end_date        = end,
        max_occurrences = req.max_occurrences
    )

    created_posts = []
    for date in dates:
        post = create_scheduled_post(template_id, date)
        created_posts.append({"post_id": post["id"], "scheduled_at": date.isoformat()})

    return {
        "message"         : "Post scheduled successfully ✅",
        "template_id"     : template_id,
        "total_scheduled" : len(created_posts),
        "upcoming_posts"  : created_posts[:5]
    }


@app.get("/posts/")
def list_posts(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    if status:
        posts = get_posts_by_status(user_id, status)
    else:
        posts = []
        for s in ["scheduled", "awaiting_approval", "approved", "posted", "failed", "expired"]:
            posts.extend(get_posts_by_status(user_id, s) or [])
    return {"posts": posts, "total": len(posts)}


@app.get("/posts/{post_id}")
def get_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    return post


@app.put("/posts/{post_id}")
def edit_post(post_id: int, req: UpdatePostRequest, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] not in ("scheduled", "awaiting_approval"):
        raise HTTPException(status_code=400, detail=f"Cannot edit post with status: {post['status']}")

    from database import execute_query

    updates = []
    params  = []

    if req.content_text is not None:
        updates.append("content_text = %s")
        params.append(req.content_text)
        execute_query(
            "UPDATE post_templates SET content_text = %s WHERE id = %s",
            (req.content_text, post["template_id"])
        )

    if req.media_url is not None:
        updates.append("media_url = %s")
        params.append(req.media_url)
        execute_query(
            "UPDATE post_templates SET media_url = %s WHERE id = %s",
            (req.media_url, post["template_id"])
        )

    if req.platforms is not None:
        updates.append("platforms = %s")
        params.append(req.platforms)
        execute_query(
            "UPDATE post_templates SET platforms = %s WHERE id = %s",
            (req.platforms, post["template_id"])
        )

    if req.scheduled_at is not None:
        new_dt = datetime.fromisoformat(req.scheduled_at.replace('Z', '+00:00'))
        updates.append("scheduled_at = %s")
        params.append(new_dt)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("status = %s")
    params.append("scheduled")
    updates.append("confirmation_token = NULL")
    updates.append("confirmation_sent_at = NULL")
    updates.append("token_used = FALSE")

    params.append(post_id)
    execute_query(
        f"UPDATE scheduled_posts SET {', '.join(updates)} WHERE id = %s",
        tuple(params)
    )

    return {"message": f"Post {post_id} updated ✅", "post_id": post_id}


@app.delete("/posts/{post_id}")
def delete_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] == "posted":
        raise HTTPException(status_code=400, detail="Cannot delete an already published post")

    from database import execute_query
    execute_query("DELETE FROM post_targets WHERE scheduled_post_id = %s", (post_id,))
    execute_query("DELETE FROM scheduled_posts WHERE id = %s",     (post_id,))

    return {"message": f"Post {post_id} deleted ✅"}


@app.post("/posts/{post_id}/publish")
def publish_now(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] == "posted":
        raise HTTPException(status_code=400, detail="Post already published")
    if post["status"] == "posting":
        raise HTTPException(status_code=400, detail="Post is currently being published")

    approve_post(post_id)
    publish_post_task.delay(post_id)
    return {"message": f"Post {post_id} queued for immediate publishing ✅", "post_id": post_id}


@app.patch("/posts/{post_id}/skip")
def skip_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] != "scheduled":
        raise HTTPException(status_code=400, detail=f"Cannot skip post with status: {post['status']}")
    update_post_status(post_id, "skipped")
    return {"message": f"Post {post_id} skipped ✅"}


@app.patch("/posts/{post_id}/retry")
def retry_post(post_id: int, current_user: dict = Depends(get_current_user)):
    """Retry a failed post."""
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] not in ("failed", "expired"):
        raise HTTPException(status_code=400, detail=f"Can only retry failed/expired posts")
    approve_post(post_id)
    publish_post_task.delay(post_id)
    return {"message": f"Post {post_id} queued for retry ✅"}


@app.patch("/templates/{template_id}/pause")
def pause_automation(template_id: int, current_user: dict = Depends(get_current_user)):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your template")
    pause_template(template_id)
    return {"message": "Automation paused ⏸️"}


@app.patch("/templates/{template_id}/resume")
def resume_automation(template_id: int, current_user: dict = Depends(get_current_user)):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your template")
    resume_template(template_id)
    return {"message": "Automation resumed ▶️"}


# ── SECTION 7 — APPROVAL ROUTES ─────────────────────────

@app.get("/approvals/{post_id}/approve")
def approve(post_id: int, token: str = Query(...)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Post cannot be approved. Status: {post['status']}")
    if not verify_confirmation_token(token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    approve_post(post_id)
    publish_post_task.delay(post_id)
    return {"message": "Post approved! Publishing now... ✅", "post_id": post_id}


class RejectRequest(BaseModel):
    token  : str
    reason : Optional[str] = None


@app.post("/approvals/{post_id}/reject")
def reject(post_id: int, req: RejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Post cannot be rejected. Status: {post['status']}")
    if not verify_confirmation_token(req.token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    reject_post(post_id, req.reason)
    return {"message": "Post cancelled ❌", "post_id": post_id, "reason": req.reason}


@app.get("/approvals/pending")
def get_pending_approvals(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    posts   = get_posts_by_status(user_id, "awaiting_approval")
    return {"pending": posts, "count": len(posts) if posts else 0}


# ── SECTION 8 — ANALYTICS ───────────────────────────────

@app.get("/analytics")
def get_analytics(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    all_statuses = ["scheduled", "awaiting_approval", "approved", "posted", "failed", "expired", "cancelled", "skipped"]
    counts       = {}
    all_posts    = []

    for s in all_statuses:
        posts       = get_posts_by_status(user_id, s) or []
        counts[s]   = len(posts)
        all_posts.extend(posts)

    platform_stats = {"facebook": 0, "instagram": 0, "linkedin": 0}
    for post in all_posts:
        for plat in (post.get("platforms") or []):
            if plat in platform_stats:
                platform_stats[plat] += 1

    total = len(all_posts)

    return {
        "summary": {
            "total"            : total,
            "posted"           : counts.get("posted", 0),
            "scheduled"        : counts.get("scheduled", 0),
            "awaiting_approval": counts.get("awaiting_approval", 0),
            "failed"           : counts.get("failed", 0),
            "expired"          : counts.get("expired", 0),
            "cancelled"        : counts.get("cancelled", 0),
            "skipped"          : counts.get("skipped", 0),
        },
        "platforms": platform_stats,
        "success_rate": round(
            (counts.get("posted", 0) / max(counts.get("posted", 0) + counts.get("failed", 0), 1)) * 100, 1
        )
    }


# ── SECTION 9 — CALENDAR ROUTES ─────────────────────────

@app.get("/calendar")
def get_calendar(month: str = Query(..., description="Format: YYYY-MM"), current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    try:
        year, mon  = map(int, month.split("-"))
        start_date = datetime(year, mon, 1, tzinfo=timezone.utc)
        import calendar
        last_day   = calendar.monthrange(year, mon)[1]
        end_date   = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    posts = get_posts_for_calendar(user_id, start_date, end_date)
    calendar_data = {}
    for post in (posts or []):
        date_key = post["scheduled_at"].strftime("%Y-%m-%d")
        if date_key not in calendar_data:
            calendar_data[date_key] = []
        calendar_data[date_key].append({
            "post_id"      : post["id"],
            "scheduled_at" : post["scheduled_at"].isoformat(),
            "content"      : post["content_text"][:50] + "...",
            "platforms"    : post["platforms"],
            "status"       : post["status"]
        })

    return {"month": month, "calendar": calendar_data, "total": len(posts) if posts else 0}


from tasks import generate_ai_posts_task

@app.post("/ai/generate")
def trigger_ai_generation(current_user: dict = Depends(get_current_user)):
    """Manually trigger AI post generation for testing."""
    generate_ai_posts_task.delay(current_user["user_id"])
    return {"message": "AI post generation started ✅ Check your email shortly."}