from datetime import datetime, timezone, timedelta
import httpx
from fastapi import Query
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_current_user
from app.core.config import (
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    META_APP_ID,
    META_APP_SECRET,
    META_REDIRECT_URI,
    META_LOGIN_CONFIG_ID,
)
from app.core.helpers import normalize_email
from app.core.utils import create_access_token, hash_password, verify_password

from app.repositories.social_account_repository import (
    get_social_account,
    get_brand_social_accounts,
    save_social_account,
    save_brand_social_account,
)
from app.repositories.brand_repository import (
    get_brand_by_id,
    get_default_brand,
)
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_last_login,
    get_admins,
)
from app.integrations.admin_utils import resolve_admin_for_signup

from app.schemas.auth import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ═══════════════════════════════════════════════════════════
# STATE PARSING HELPER (used by all callbacks)
# ═══════════════════════════════════════════════════════════

def _parse_oauth_state(state: str) -> tuple[int, int | None]:
    """
    Parse OAuth state parameter.

    Supports:
      - "user_id"             → (user_id, None)      [user-scoped]
      - "user_id:brand_id"    → (user_id, brand_id)  [brand-scoped]

    Raises HTTPException on invalid format.
    """
    try:
        if ":" in state:
            user_id_str, brand_id_str = state.split(":", 1)
            user_id = int(user_id_str)
            brand_id = int(brand_id_str)
            return user_id, brand_id
        else:
            user_id = int(state)
            return user_id, None
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state parameter",
        )




@router.post("/register")
def register(req: RegisterRequest):
    email = normalize_email(req.email)

    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed = hash_password(req.password)

    admins = get_admins() or []

    resolved_admin = resolve_admin_for_signup(
        email=email,
        invite_code=req.invite_code,
        admin_email=req.admin_email,
        admins=admins,
        domain_mapping={
            "shilsha.com": "admin@shilsha.com"
        },
    )

    admin_id = resolved_admin["id"] if resolved_admin else None

    user = create_user(
        email,
        hashed,
        admin_id=admin_id,
        role=req.role,
    )

    token = create_access_token(
        user["id"],
        user["email"]
    )

    return {
        "message": "Registered successfully",
        "access_token": token,
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "admin_id": admin_id,
        "assigned_admin": bool(admin_id),
    }




@router.post("/login")
def login(req: LoginRequest):
    email = normalize_email(req.email)
    user = get_user_by_email(email)

    # 1. Verify credentials first.
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    # 2. ⭐ THEN check the role — outside the credentials block, at the same level.
    if user["role"] != req.role:
        raise HTTPException(
            status_code=403,
            detail=f"This account is not registered as {req.role}",
        )

    update_last_login(user["id"])

    token = create_access_token(user["id"], user["email"])

    default_brand = get_default_brand(user["id"])

    return {
        "message": "Login successful",
        "access_token": token,
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "admin_id": user.get("admin_id"),
        "default_brand": default_brand,
    }
# ═══════════════════════════════════════════════════════════
# ME
# ═══════════════════════════════════════════════════════════

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ═══════════════════════════════════════════════════════════
# FACEBOOK — CONNECT (2 endpoints for 2 scopes)
# ═══════════════════════════════════════════════════════════

@router.get("/facebook/connect")
def facebook_connect(
    force: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """User-scoped Facebook connect. Returns OAuth URL with state=user_id."""
    user_id = current_user["user_id"]

    existing = get_social_account(user_id, "facebook")

    if existing and not force:
        return {
            "already_connected": True,
            "message": "Facebook already connected ✅",
            "page_id": existing["page_id"],
        }

    url = (
        "https://www.facebook.com/v26.0/dialog/oauth"
        f"?client_id={META_APP_ID}"
        f"&redirect_uri={META_REDIRECT_URI}"
        f"&config_id={META_LOGIN_CONFIG_ID}"
        f"&state={user_id}"
        f"&response_type=code"
    )

    return {
        "already_connected": False,
        "oauth_url": url,
        "forced": force,
    }


@router.get("/facebook/brands/{brand_id}/connect")
def facebook_brand_connect(
    brand_id: int,
    force: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Brand-scoped Facebook connect. Returns OAuth URL with state=user_id:brand_id."""
    user_id = current_user["user_id"]

    # Validate brand ownership
    brand = get_brand_by_id(user_id=user_id, brand_id=brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    existing = get_brand_social_accounts(
        user_id=user_id,
        brand_id=brand_id,
        platform="facebook",
    )

    if existing and not force:
        return {
            "already_connected": True,
            "message": "Facebook already connected to this brand",
            "brand_id": brand_id,
            "accounts": existing,
        }

    # Brand-scoped state
    state = f"{user_id}:{brand_id}"

    url = (
        "https://www.facebook.com/v26.0/dialog/oauth"
        f"?client_id={META_APP_ID}"
        f"&redirect_uri={META_REDIRECT_URI}"
        f"&config_id={META_LOGIN_CONFIG_ID}"
        f"&state={state}"
        f"&response_type=code"
    )

    return {
        "already_connected": False,
        "brand_id": brand_id,
        "oauth_url": url,
        "forced": force,
    }


# ═══════════════════════════════════════════════════════════
# FACEBOOK — SINGLE CALLBACK (handles both scopes)
# ═══════════════════════════════════════════════════════════

@router.get("/facebook/callback")
async def facebook_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Unified Facebook callback.

    Handles:
      - user-scoped:  state = "user_id"
      - brand-scoped: state = "user_id:brand_id"

    Saves account to user OR brand accordingly.
    """
    # ⭐ Flexible state parsing
    user_id, brand_id = _parse_oauth_state(state)

    # Validate brand if present
    if brand_id is not None:
        brand = get_brand_by_id(user_id=user_id, brand_id=brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    async with httpx.AsyncClient() as client:
        # ── Exchange code for short-lived token ──
        token_response = await client.get(
            "https://graph.facebook.com/v26.0/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": META_REDIRECT_URI,
                "code": code,
            },
        )
        token_data = token_response.json()
        short_lived_token = token_data.get("access_token")
        if not short_lived_token:
            raise HTTPException(
                status_code=400,
                detail=f"Facebook token error: {token_data}",
            )

        # ── Exchange for long-lived token ──
        long_response = await client.get(
            "https://graph.facebook.com/v26.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": short_lived_token,
            },
        )
        long_data = long_response.json()
        long_lived_token = long_data.get("access_token", short_lived_token)
        expires_in = long_data.get("expires_in", 5184000)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # ── Fetch user's pages ──
        pages_response = await client.get(
            "https://graph.facebook.com/v26.0/me/accounts",
            params={
                "access_token": long_lived_token,
                "fields": "id,name,access_token,instagram_business_account",
                "limit": 100,
            },
        )
        pages = pages_response.json().get("data", [])

        ig_account = None
        ig_username = None
        page_name = None

        if pages:
            page = pages[0]
            page_id = page["id"]
            page_name = page.get("name")
            page_token = page.get("access_token", long_lived_token)

            ig_resp = await client.get(
                f"https://graph.facebook.com/v26.0/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token,
                },
            )
            ig_account = ig_resp.json().get("instagram_business_account")
            if ig_account:
                ig_detail_resp = await client.get(
                    f"https://graph.facebook.com/v26.0/{ig_account['id']}",
                    params={
                        "fields": "username",
                        "access_token": page_token,
                    },
                )
                ig_username = ig_detail_resp.json().get("username")
        else:
            me_data = (
                await client.get(
                    "https://graph.facebook.com/v26.0/me",
                    params={
                        "access_token": long_lived_token,
                        "fields": "id,name",
                    },
                )
            ).json()
            page_id = me_data.get("id")
            page_name = me_data.get("name")
            page_token = long_lived_token

        # ⭐ SAVE — Branch on scope
        if brand_id is not None:
            # ── Brand-scoped save ──
            save_brand_social_account(
                user_id=user_id,
                brand_id=brand_id,
                platform="facebook",
                access_token=page_token,
                page_id=page_id,
                token_expires_at=expires_at,
                account_name=page_name,
            )
            if ig_account:
                save_brand_social_account(
                    user_id=user_id,
                    brand_id=brand_id,
                    platform="instagram",
                    access_token=page_token,
                    page_id=ig_account["id"],
                    account_name=ig_username,
                )
        else:
            # ── User-scoped save ──
            save_social_account(
                user_id=user_id,
                platform="facebook",
                access_token=page_token,
                page_id=page_id,
                token_expires_at=expires_at,
                account_name=page_name,
            )
            if ig_account:
                save_social_account(
                    user_id=user_id,
                    platform="instagram",
                    access_token=page_token,
                    page_id=ig_account["id"],
                    account_name=ig_username,
                )

    return {
        "message": "Facebook connected ✅",
        "page_id": page_id,
        "instagram": ig_account["id"] if ig_account else "Not found",
        "brand_id": brand_id,       # None for user-scoped
    }



@router.get("/linkedin/brands/{brand_id}/connect")
def linkedin_brand_connect(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Brand-scoped LinkedIn connect."""
    user_id = current_user["user_id"]

    brand = get_brand_by_id(user_id=user_id, brand_id=brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    existing = get_brand_social_accounts(
        user_id=user_id,
        brand_id=brand_id,
        platform="linkedin",
    )

    if existing:
        return {
            "already_connected": True,
            "brand_id": brand_id,
            "accounts": existing,
        }

    state = f"{user_id}:{brand_id}"

    url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={LINKEDIN_REDIRECT_URI}"
        f"&scope=openid%20profile%20email%20w_member_social"
        f"&state={state}"
    )

    return {
        "already_connected": False,
        "brand_id": brand_id,
        "oauth_url": url,
    }


# ═══════════════════════════════════════════════════════════
# LINKEDIN — SINGLE CALLBACK (handles both scopes)
# ═══════════════════════════════════════════════════════════

@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Unified LinkedIn callback.

    Handles:
      - user-scoped:  state = "user_id"
      - brand-scoped: state = "user_id:brand_id"

    Saves account to user OR brand accordingly.
    """
    # ⭐ Flexible state parsing
    user_id, brand_id = _parse_oauth_state(state)

    # Validate brand if present
    if brand_id is not None:
        brand = get_brand_by_id(user_id=user_id, brand_id=brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    async with httpx.AsyncClient() as client:
        # ── Exchange code for access token ──
        token_data = (
            await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                    "redirect_uri": LINKEDIN_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        ).json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail=f"LinkedIn token error: {token_data}",
            )

        # ── Fetch profile ──
        profile = (
            await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        ).json()

        user_urn = f"urn:li:person:{profile.get('sub')}"

        # ⭐ SAVE — Branch on scope
        if brand_id is not None:
            # ── Brand-scoped save ──
            save_brand_social_account(
                user_id=user_id,
                brand_id=brand_id,
                platform="linkedin",
                access_token=access_token,
                refresh_token=token_data.get("refresh_token"),
                page_id=user_urn,
                account_name=profile.get("name"),
                account_email=profile.get("email"),
            )
        else:
            # ── User-scoped save ──
            save_social_account(
                user_id=user_id,
                platform="linkedin",
                access_token=access_token,
                refresh_token=token_data.get("refresh_token"),
                page_id=user_urn,
                account_name=profile.get("name"),
                account_email=profile.get("email"),
            )

    return {
        "message": "LinkedIn connected ✅",
        "user_urn": user_urn,
        "brand_id": brand_id,       # None for user-scoped
    }