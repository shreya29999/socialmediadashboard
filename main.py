from enum import Enum
from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime, timezone
import httpx
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from logger import logger

load_dotenv()

from database import (
    init_db,
    create_user,
    get_user_by_email,
    execute_query,
    get_user_by_id,
    get_admins,
    get_users_for_admin,
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
    get_posts_by_status_for_admin,
    get_posts_for_calendar,
    get_posts_for_calendar_for_admin,
    update_post_status,
    get_post_by_token,
    approve_post,
    reject_post,
    create_post_targets,
    get_superadmin,
    get_all_users,
    get_all_posts_for_superadmin,
    get_posts_awaiting_superadmin,
    create_approval_stage,
    update_hr_approval,
    update_superadmin_approval,
    save_superadmin_token,
    superadmin_final_approve,
    superadmin_final_reject,
    get_approval_stage,
    update_last_login
)
from utils import (
    create_access_token,
    verify_access_token,
    hash_password,
    verify_password,
    verify_confirmation_token,
    calculate_next_dates as calc_dates,
    generate_post_preview
)
from tasks import publish_post_task
from tasks import _escalate_to_superadmin
from event_fetcher import answer_rag_query
from admin_utils import resolve_admin_for_signup

app = FastAPI(
    title="Social Media Dashboard",
    description="Automate your social media posts",
    version="2.0.0"
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

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

@app.on_event("startup")
async def startup():
    init_db()
    logger.info("App started, DB ready")


@app.on_event("shutdown")
async def shutdown():
    logger.info("App shutting down")


@app.get("/")
def root():
    return {"message": "Social Media Dashboard API v2 ✅"}

class RegisterRequest(BaseModel):
    email       : str
    password    : str
    timezone    : Optional[str] = "UTC"
    invite_code : Optional[str] = None
    admin_email : Optional[str] = None

class LoginRequest(BaseModel):
    email    : str
    password : str

class RejectRequest(BaseModel):
    token  : str
    reason : Optional[str] = None


class CreateManagedUserRequest(BaseModel):
    email    : str
    password : str


class CreateAdminRequest(BaseModel):
    email       : str
    password    : str
    invite_code : Optional[str] = None

class RecurrenceType(str, Enum):
    ONE_TIME      = "ONE_TIME"
    EVERY_X_DAYS  = "EVERY_X_DAYS"
    WEEKLY        = "WEEKLY"
    MONTHLY       = "MONTHLY"
    CRON          = "CRON"


class Platform(str, Enum):
    facebook  = "facebook"
    instagram = "instagram"
    linkedin  = "linkedin"


class CreatePostRequest(BaseModel):
    content_text    : str = Field(..., min_length=1, max_length=2000)
    media_url       : Optional[str] = None
    platforms       : List[Platform]
    recurrence_type : RecurrenceType = RecurrenceType.ONE_TIME
    interval_days   : Optional[int] = 1
    start_date      : str
    end_date        : Optional[str] = None
    max_occurrences : Optional[int] = None
    timezone        : Optional[str] = "UTC"


class UpdatePostRequest(BaseModel):
    content_text : Optional[str] = Field(None, min_length=1, max_length=2000)
    media_url    : Optional[str] = None
    platforms    : Optional[List[Platform]] = None
    scheduled_at : Optional[str] = None


class UserProfileRequest(BaseModel):
    persona        : str
    industry       : Union[str, List[str]]
    brand_name     : str
    tone           : Union[str, List[str]]
    audience       : Union[str, List[str]]
    country_code   : str
    language       : str = "english"
    posts_per_week : int = 3


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token   = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def get_current_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token   = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload["user_id"])
    if not user or user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin access required")
    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token   = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload["user_id"])
    if not user or user["role"] not in {"admin", "superadmin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def get_actor_user(current_user: dict):
    return get_user_by_id(current_user["user_id"])


def can_access_resource(resource_user_id: int, current_user: dict) -> bool:
    actor = get_actor_user(current_user)
    if not actor:
        return False
    if actor["role"] == "superadmin":
        return True
    if actor["role"] == "admin":
        owner = get_user_by_id(resource_user_id)
        return bool(owner and owner.get("admin_id") == actor["id"])
    return resource_user_id == current_user["user_id"]


@app.post("/auth/register")
def register(req: RegisterRequest):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    admins = get_admins() or []
    resolved_admin = resolve_admin_for_signup(
        email=req.email,
        invite_code=req.invite_code,
        admin_email=req.admin_email,
        admins=admins,
        domain_mapping={"shilsha.com": "admin@shilsha.com"},
    )
    admin_id = resolved_admin["id"] if resolved_admin else None
    user = create_user(req.email, hashed, admin_id=admin_id)
    token = create_access_token(user["id"], user["email"])
    return {
        "message"      : "Registered successfully",
        "access_token" : token,
        "user_id"      : user["id"],
        "email"        : user["email"],
        "admin_id"     : admin_id,
        "assigned_admin": bool(admin_id)
    }

@app.post("/auth/login")
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    update_last_login(user["id"])   
    token = create_access_token(user["id"], user["email"])
    return {
        "message"      : "Login successful",
        "access_token" : token,
        "user_id"      : user["id"],
        "email"        : user["email"],
        "role"         : user["role"],
        "admin_id"     : user.get("admin_id")
    }


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


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
                "code" : code
            }
        )
        token_data = token_response.json()
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

        profile = (await client.get(
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
    return {"message": "LinkedIn connected ✅","user_urn": user_urn}


@app.get("/platforms/status")
def platform_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    status  = {}
    for platform in ["facebook", "instagram", "linkedin"]:
        account           = get_social_account(user_id, platform)
        status[platform]  = "connected" if account else "not connected"
    return status


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


@app.post("/media/upload")
async def upload_media(
    file         : UploadFile = File(...),
    current_user : dict = Depends(get_current_user)
):
    allowed_images = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
    allowed_videos = {"video/mp4", "video/mov", "video/quicktime", "video/avi", "video/mkv"}
    allowed = allowed_images | allowed_videos

    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, WebP images and MP4, MOV, AVI videos are supported")

    contents = await file.read()    
    is_video = file.content_type in allowed_videos
    max_size = 650 * 1024 * 1024 if is_video else 8 * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {'650MB for videos' if is_video else '8MB for images'}"
        )

    try:
        upload_options = {
            "folder"        : "socialdesk",
            "resource_type" : "auto",   
        }

        if not is_video:
            upload_options["transformation"] = [
                {"width": 1080, "height": 1080, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]

        result = cloudinary.uploader.upload(contents, **upload_options)
        return {
            "success"      : True,
            "url"          : result["secure_url"],
            "public_id"    : result["public_id"],
            "resource_type": result.get("resource_type"), 
            "format"       : result.get("format"),
            "width"        : result.get("width"),
            "height"       : result.get("height"),
            "duration"     : result.get("duration"),       
            "size_bytes"   : result.get("bytes")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/user/profile")
def save_user_profile(req: UserProfileRequest, current_user: dict = Depends(get_current_user)):
    industry = req.industry if isinstance(req.industry, str) else ", ".join(req.industry)
    tone     = req.tone     if isinstance(req.tone,     str) else ", ".join(req.tone)
    audience = req.audience if isinstance(req.audience, str) else ", ".join(req.audience)
    execute_query("""
        INSERT INTO user_profiles 
            (user_id, persona, industry, brand_name, tone, audience, country_code, language, posts_per_week)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        current_user["user_id"], req.persona, industry,
        req.brand_name, tone, audience,
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
    actor = get_actor_user(current_user)
    if actor and actor.get("role") == "admin":
        if status:
            posts = get_posts_by_status_for_admin(actor["id"], status)
        else:
            posts = []
            for s in ["scheduled", "awaiting_approval", "approved", "posted", "failed", "expired"]:
                posts.extend(get_posts_by_status_for_admin(actor["id"], s) or [])
        return {"posts": posts, "total": len(posts)}
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
    if not can_access_resource(post["user_id"], current_user):
        raise HTTPException(status_code=403, detail="Not your post")
    return post


@app.put("/posts/{post_id}")
def edit_post(post_id: int, req: UpdatePostRequest, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not can_access_resource(post["user_id"], current_user):
        raise HTTPException(status_code=403, detail="Not your post")
    if post["status"] not in ("scheduled", "awaiting_approval"):
        raise HTTPException(status_code=400, detail=f"Cannot edit post with status: {post['status']}")

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
    if not can_access_resource(post["user_id"], current_user):
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
    if not can_access_resource(post["user_id"], current_user):
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
    if not can_access_resource(post["user_id"], current_user):
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
    if not can_access_resource(post["user_id"], current_user):
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
    if not can_access_resource(template["user_id"], current_user):
        raise HTTPException(status_code=403, detail="Not your template")
    pause_template(template_id)
    return {"message": "Automation paused ⏸️"}


@app.patch("/templates/{template_id}/resume")
def resume_automation(template_id: int, current_user: dict = Depends(get_current_user)):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not can_access_resource(template["user_id"], current_user):
        raise HTTPException(status_code=403, detail="Not your template")
    resume_template(template_id)
    return {"message": "Automation resumed ▶️"}


@app.get("/approvals/{post_id}/hr-approve")
def hr_approve(post_id: int, token: str = Query(...)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    execute_query("UPDATE scheduled_posts SET token_used = TRUE WHERE id = %s", (post_id,))
    update_hr_approval(post_id, "approved")
    _escalate_to_superadmin(post_id, hr_status="approved")
    return {"message": "HR approved ✅ Post sent to SuperAdmin for final review.", "post_id": post_id}


@app.post("/approvals/{post_id}/hr-reject")
def hr_reject(post_id: int, req: RejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_hr_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(req.token, post["confirmation_token"]):
        raise HTTPException(status_code=400, detail="Invalid token")
    if post["token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    execute_query("UPDATE scheduled_posts SET token_used = TRUE WHERE id = %s", (post_id,))
    update_hr_approval(post_id, "rejected", req.reason)
    _escalate_to_superadmin(post_id, hr_status="rejected", hr_reason=req.reason)
    return {"message": "HR rejected. Escalated to SuperAdmin for final decision.", "post_id": post_id}


@app.get("/approvals/{post_id}/superadmin-approve")
def superadmin_approve_email(post_id: int, token: str = Query(...)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_superadmin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(token, post["superadmin_token"]):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if post["superadmin_token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    superadmin_final_approve(post_id)
    publish_post_task.delay(post_id)
    return {"message": "SuperAdmin approved ✅ Post is being published!", "post_id": post_id}


@app.post("/approvals/{post_id}/superadmin-reject")
def superadmin_reject_email(post_id: int, req: RejectRequest):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_superadmin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    if not verify_confirmation_token(req.token, post["superadmin_token"]):
        raise HTTPException(status_code=400, detail="Invalid token")
    if post["superadmin_token_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    superadmin_final_reject(post_id, req.reason)
    return {"message": "SuperAdmin rejected ❌ Post cancelled.", "post_id": post_id}

@app.get("/analytics")
def get_analytics(current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    all_statuses = ["scheduled", "awaiting_approval", "approved", "posted", "failed", "expired", "cancelled", "skipped"]
    counts       = {}
    all_posts    = []

    if actor and actor.get("role") == "admin":
        for s in all_statuses:
            posts       = get_posts_by_status_for_admin(actor["id"], s) or []
            counts[s]   = len(posts)
            all_posts.extend(posts)
    else:
        user_id = current_user["user_id"]
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

@app.get("/posts/upcoming")
def get_upcoming_posts(current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    if actor and actor.get("role") == "admin":
        posts = get_posts_by_status_for_admin(actor["id"], "scheduled")
    else:
        posts = get_posts_by_status(current_user["user_id"], "scheduled")
    upcoming = []
    for post in (posts or []):
        scheduled_at = post.get("scheduled_at")
        if hasattr(scheduled_at, "isoformat"):
            scheduled_at = scheduled_at.isoformat()
        content = (post.get("content_text") or "")
        if len(content) > 50:
            content = content[:50].rstrip() + "..."
        upcoming.append({
            "post_id": post.get("id"),
            "scheduled_at": scheduled_at,
            "content": content
        })
    return {"upcoming": upcoming, "total": len(posts) if posts else 0}


@app.get("/calendar")
def get_calendar(month: str = Query(..., description="Format: YYYY-MM"), current_user: dict = Depends(get_current_user)):
    actor = get_actor_user(current_user)
    try:
        year, mon  = map(int, month.split("-"))
        start_date = datetime(year, mon, 1, tzinfo=timezone.utc)
        import calendar
        last_day   = calendar.monthrange(year, mon)[1]
        end_date   = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

    if actor and actor.get("role") == "admin":
        posts = get_posts_for_calendar_for_admin(actor["id"], start_date, end_date)
    else:
        posts = get_posts_for_calendar(current_user["user_id"], start_date, end_date)
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
class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=800)


@app.post("/ai/generate")
def trigger_ai_generation(current_user: dict = Depends(get_current_user)):
    generate_ai_posts_task.delay(current_user["user_id"])
    return {"message": "AI post generation started ✅ Check your email shortly."}


@app.post("/ai/rag")
def rag_query(req: RagQueryRequest, current_user: dict = Depends(get_current_user)):
    result = answer_rag_query(current_user["user_id"], req.query)
    if not result:
        raise HTTPException(status_code=500, detail="RAG query failed")
    return {
        "query": req.query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", [])
    }

@app.delete("/ai/rag/history")
def clear_rag_history(current_user: dict = Depends(get_current_user)):
    execute_query(
        "DELETE FROM rag_chat_history WHERE user_id = %s",
        (current_user["user_id"],)
    )
    return {"message": "Chat history cleared ✅"}


@app.get("/posts/{post_id}/preview")
def preview_post(post_id: int, current_user: dict = Depends(get_current_user)):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if not can_access_resource(post["user_id"], current_user):
        raise HTTPException(status_code=403, detail="Not your post")
    preview = generate_post_preview(post)
    return {"post_id": post_id, "preview": preview}



@app.post("/admin/users")
def admin_create_user(req: CreateManagedUserRequest, current_user: dict = Depends(get_current_admin)):
    actor = get_actor_user(current_user)
    if not actor or actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    user = create_user(req.email, hashed, role="user", admin_id=actor["id"])
    return {
        "message": "User created successfully ✅",
        "user_id": user["id"],
        "email": user["email"],
        "password": req.password,
        "admin_id": actor["id"]
    }


@app.post("/superadmin/admins")
def create_admin_account(req: CreateAdminRequest, current_user: dict = Depends(get_current_superadmin)):
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    user = create_user(req.email, hashed, role="admin", invite_code=req.invite_code)
    return {"message": "Admin created successfully ✅", "user_id": user["id"], "email": user["email"], "invite_code": req.invite_code}


@app.post("/superadmin/create")
def create_superadmin_account(req: RegisterRequest):
    existing = get_superadmin()
    if existing:
        raise HTTPException(status_code=400, detail="SuperAdmin already exists")
    hashed = hash_password(req.password)
    user   = create_user(req.email, hashed, role="superadmin")
    token  = create_access_token(user["id"], user["email"])
    return {"message": "SuperAdmin created ✅", "access_token": token, "role": "superadmin"}


@app.get("/admin/users")
def admin_get_users(current_user: dict = Depends(get_current_admin)):
    user = get_user_by_id(current_user["user_id"])
    if user and user["role"] == "superadmin":
        users = get_all_users()
    else:
        users = get_users_for_admin(user["id"])
    return {"users": users, "total": len(users) if users else 0}


@app.get("/superadmin/users")
def superadmin_get_users(current_user: dict = Depends(get_current_superadmin)):
    users = get_all_users()
    return {"users": users, "total": len(users) if users else 0}


@app.get("/superadmin/posts")
def superadmin_get_all_posts(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_superadmin)
):
    posts = get_all_posts_for_superadmin(status_filter=status)
    return {"posts": posts, "total": len(posts) if posts else 0}


@app.get("/superadmin/pending")
def superadmin_get_pending(current_user: dict = Depends(get_current_superadmin)):
    posts = get_posts_awaiting_superadmin()
    return {"pending": posts, "count": len(posts) if posts else 0}


@app.post("/superadmin/posts/{post_id}/approve")
def superadmin_approve_dashboard(
    post_id: int,
    current_user: dict = Depends(get_current_superadmin)
):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_superadmin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    superadmin_final_approve(post_id)
    publish_post_task.delay(post_id)
    return {"message": f"Post {post_id} approved and queued for publishing ✅"}


@app.post("/superadmin/posts/{post_id}/reject")
def superadmin_reject_dashboard(
    post_id: int,
    req: RejectRequest,
    current_user: dict = Depends(get_current_superadmin)
):
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] != "awaiting_superadmin_approval":
        raise HTTPException(status_code=400, detail=f"Post status is: {post['status']}")
    superadmin_final_reject(post_id, req.reason)
    return {"message": f"Post {post_id} rejected ❌", "reason": req.reason}


@app.post("/posts/{post_id}/repost")
def repost(post_id: int, req: CreatePostRequest, current_user: dict = Depends(get_current_user)):
    original = get_post_by_id(post_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original post not found")
    if original["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your post")
    if original["status"] != "posted":
        raise HTTPException(status_code=400, detail="Can only repost published posts")

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
    post = create_scheduled_post(
        template["id"], start, reposted_from_id=post_id
    )
    create_approval_stage(post["id"])
    return {
        "message"         : "Repost scheduled ✅ Will go through HR → SuperAdmin approval",
        "new_post_id"     : post["id"],
        "reposted_from"   : post_id,
        "scheduled_at"    : start.isoformat()
    }