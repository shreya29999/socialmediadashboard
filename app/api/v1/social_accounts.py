import httpx
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from app.repositories.social_account_repository import (
    get_brand_social_accounts,
)
from app.repositories.brand_repository import get_brand_by_id
from app.api.dependencies import get_current_user
from app.repositories.social_account_repository import get_social_account

router = APIRouter(prefix="/platforms", tags=["Social Accounts"])


@router.get("/status")
def platform_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    status  = {}
    for platform in ["facebook", "instagram", "linkedin"]:
        account           = get_social_account(user_id, platform)
        status[platform]  = "connected" if account else "not connected"
    return status


@router.get("/accounts")
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




@router.get("/brands/{brand_id}/accounts")
async def brand_platform_accounts(
    brand_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    brand = get_brand_by_id(
        user_id=user_id,
        brand_id=brand_id,
    )

    if not brand:
        raise HTTPException(
            status_code=404,
            detail="Brand not found",
        )

    social_accounts = get_brand_social_accounts(
        user_id=user_id,
        brand_id=brand_id,
    )

    accounts = {}

    for account in social_accounts:
        platform = account["platform"]

        if platform == "facebook":
            accounts.setdefault("facebook", []).append({
                "id": account["id"],
                "connected": True,
                "page_id": account["page_id"],
                "name": account["account_name"] or "Facebook Page",
                "followers": 0,
            })

        elif platform == "instagram":
            accounts.setdefault("instagram", []).append({
                "id": account["id"],
                "connected": True,
                "page_id": account["page_id"],
                "name": account["account_name"] or "Instagram Account",
                "username": "",
                "followers": 0,
            })

        elif platform == "linkedin":
            accounts.setdefault("linkedin", []).append({
                "id": account["id"],
                "connected": True,
                "page_id": account["page_id"],
                "name": account["account_name"] or "LinkedIn User",
                "email": account["account_email"] or "",
            })

    return {
        "brand_id": brand_id,
        "accounts": accounts,
    }