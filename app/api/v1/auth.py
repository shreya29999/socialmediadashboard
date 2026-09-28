from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user
from app.core.config import (
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    META_APP_ID,
    META_APP_SECRET,
    META_REDIRECT_URI,
)
from app.core.helpers import normalize_email
from app.core.utils import create_access_token, hash_password, verify_password
from app.db.database import (
    create_user,
    get_admins,
    get_social_account,
    get_user_by_email,
    get_user_by_id,
    save_social_account,
    update_last_login,
)
from app.integrations.admin_utils import resolve_admin_for_signup
from app.schemas.auth import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(req: RegisterRequest):
    email = normalize_email(req.email)
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(req.password)
    admins = get_admins() or []
    resolved_admin = resolve_admin_for_signup(
        email=email,
        invite_code=req.invite_code,
        admin_email=req.admin_email,
        admins=admins,
        domain_mapping={"shilsha.com":"admin@shilsha.com"},
    )
    admin_id = resolved_admin["id"] if resolved_admin else None
    user = create_user(email, hashed, admin_id=admin_id)
    token = create_access_token(user["id"], user["email"])
    return {
        "message"      : "Registered successfully",
        "access_token" : token,
        "user_id"      : user["id"],
        "email"        : user["email"],
        "admin_id"     : admin_id,
        "assigned_admin": bool(admin_id)
    }


@router.post("/login")
def login(req: LoginRequest):
    email = normalize_email(req.email)
    user = get_user_by_email(email)
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


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/facebook/connect")
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


@router.get("/facebook/callback")
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
        ig_username = None
        page_name  = None
        if pages:
            page       = pages[0]
            page_id    = page["id"]
            page_name  = page.get("name")
            page_token = page.get("access_token", long_lived_token)
            ig_resp    = await client.get(
                f"https://graph.facebook.com/v18.0/{page_id}",
                params={"fields": "instagram_business_account", "access_token": page_token}
            )
            ig_account = ig_resp.json().get("instagram_business_account")
            if ig_account:
                ig_detail_resp = await client.get(
                    f"https://graph.facebook.com/v18.0/{ig_account['id']}",
                    params={"fields": "username", "access_token": page_token}
                )
                ig_username = ig_detail_resp.json().get("username")
        else:
            me_data    = (await client.get(
                "https://graph.facebook.com/v18.0/me",
                params={"access_token": long_lived_token, "fields": "id,name"}
            )).json()
            page_id    = me_data.get("id")
            page_name  = me_data.get("name")
            page_token = long_lived_token
        save_social_account(
            user_id=user_id, platform="facebook",
            access_token=page_token, page_id=page_id,
            token_expires_at=expires_at,
            account_name=page_name
        )
        if ig_account:
            save_social_account(
                user_id=user_id, platform="instagram",
                access_token=page_token, page_id=ig_account["id"],
                account_name=ig_username
            )
        return {
            "message"  : "Facebook connected ✅",
            "page_id"  : page_id,
            "instagram": ig_account["id"] if ig_account else "Not found"
        }


@router.get("/linkedin/connect")
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


@router.get("/linkedin/callback")
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
            page_id=user_urn,
            account_name=profile.get("name"),
            account_email=profile.get("email")
        )
    return {"message": "LinkedIn connected ✅","user_urn": user_urn}
