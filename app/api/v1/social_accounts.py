import httpx
from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.db.database import get_social_account

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
