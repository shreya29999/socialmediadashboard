# Section 1: JWT Utilities
# Section 2: Confirmation Token
# Section 3: Password Hashing
# Section 4: Recurrence / Next Date Calculator
# Section 5: OAuth Token Refresh

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from croniter import croniter
import secrets
import hashlib
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# ================================================================
# SECTION 1 — JWT UTILITIES
# ================================================================

JWT_SECRET     = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MINUTES", 1440))


def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub"   : str(user_id),
        "email" : email,
        "exp"   : datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MIN)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "user_id" : int(payload.get("sub")),
            "email"   : payload.get("email")
        }
    except JWTError:
        return None


# ================================================================
# SECTION 2 — CONFIRMATION TOKEN
# ================================================================

def generate_confirmation_token() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_confirmation_token(raw_token: str, hashed_token: str) -> bool:
    return hash_token(raw_token) == hashed_token


# ================================================================
# SECTION 3 — PASSWORD HASHING
# ================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ================================================================
# SECTION 4 — RECURRENCE / NEXT DATE CALCULATOR
# ================================================================

def calculate_next_dates(
    recurrence_type : str,
    start_date      : datetime,
    interval_days   : int = 1,
    count           : int = 30,
    end_date        : Optional[datetime] = None,
    max_occurrences : Optional[int] = None
) -> list:

    dates = []

    if recurrence_type == "ONE_TIME":
        if _is_valid_date(start_date, end_date, max_occurrences, 0):
            dates.append(start_date)
        return dates

    if recurrence_type == "EVERY_X_DAYS":
        current = start_date
        occurrence = 0
        while len(dates) < count:
            if not _is_valid_date(current, end_date, max_occurrences, occurrence):
                break
            dates.append(current)
            current = current + timedelta(days=interval_days)
            occurrence += 1
        return dates

    if recurrence_type == "WEEKLY":
        current = start_date
        occurrence = 0
        while len(dates) < count:
            if not _is_valid_date(current, end_date, max_occurrences, occurrence):
                break
            dates.append(current)
            current = current + timedelta(weeks=1)
            occurrence += 1
        return dates

    if recurrence_type == "MONTHLY":
        current = start_date
        occurrence = 0
        while len(dates) < count:
            if not _is_valid_date(current, end_date, max_occurrences, occurrence):
                break
            dates.append(current)
            current = _add_one_month(current)
            occurrence += 1
        return dates
    if recurrence_type == "CRON":
        cron = croniter(str(interval_days), start_date)
        occurrence = 0
        while len(dates) < count:
            next_date = cron.get_next(datetime)
            if not _is_valid_date(next_date, end_date, max_occurrences, occurrence):
                break
            dates.append(next_date)
            occurrence += 1
        return dates

    return dates


def calculate_single_next_date(
    recurrence_type : str,
    last_date       : datetime,
    interval_days   : int = 1,
    end_date        : Optional[datetime] = None,
    max_occurrences : Optional[int] = None,
    occurrence_count: int = 0
) -> Optional[datetime]:
    if recurrence_type == "ONE_TIME":
        return None

    if recurrence_type == "EVERY_X_DAYS":
        next_date = last_date + timedelta(days=interval_days)

    elif recurrence_type == "WEEKLY":
        next_date = last_date + timedelta(weeks=1)

    elif recurrence_type == "MONTHLY":
        next_date = _add_one_month(last_date)

    elif recurrence_type == "CRON":
        cron = croniter(str(interval_days), last_date)
        next_date = cron.get_next(datetime)

    else:
        return None
    if not _is_valid_date(next_date, end_date, max_occurrences, occurrence_count):
        return None

    return next_date


def _is_valid_date(
    date            : datetime,
    end_date        : Optional[datetime],
    max_occurrences : Optional[int],
    occurrence_count: int
) -> bool:
    if end_date and date > end_date:
        return False
    if max_occurrences and occurrence_count >= max_occurrences:
        return False
    return True


def _add_one_month(dt: datetime) -> datetime:
    month = dt.month + 1
    year  = dt.year

    if month > 12:
        month = 1
        year += 1

    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day     = min(dt.day, max_day)

    return dt.replace(year=year, month=month, day=day)


# ================================================================
# SECTION 5 — OAUTH TOKEN REFRESH
# ================================================================

async def refresh_facebook_token(current_token: str) -> Optional[dict]:
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.facebook.com/oauth/access_token",
                params={
                    "grant_type"        : "fb_exchange_token",
                    "client_id"         : os.getenv("META_APP_ID"),
                    "client_secret"     : os.getenv("META_APP_SECRET"),
                    "fb_exchange_token" : current_token
                }
            )
            data = response.json()

            if "access_token" in data:
                expires_in  = data.get("expires_in", 5184000) 
                expires_at  = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                return {
                    "access_token" : data["access_token"],
                    "expires_at"   : expires_at
                }
            return None

    except Exception as e:
        print(f"❌ Facebook token refresh failed: {e}")
        return None


async def refresh_linkedin_token(refresh_token: str) -> Optional[dict]:
    if not refresh_token:
        print("❌ No LinkedIn refresh token available")
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type"    : "refresh_token",
                    "refresh_token" : refresh_token,
                    "client_id"     : os.getenv("LINKEDIN_CLIENT_ID"),
                    "client_secret" : os.getenv("LINKEDIN_CLIENT_SECRET")
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            print(f"🔍 LinkedIn refresh response: {response.status_code} {response.text}")
            data = response.json()

            if "access_token" in data:
                expires_in = data.get("expires_in", 5184000)
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                return {
                    "access_token"  : data["access_token"],
                    "refresh_token" : data.get("refresh_token", refresh_token),
                    "expires_at"    : expires_at
                }
            return None

    except Exception as e:
        print(f"❌ LinkedIn token refresh failed: {e}")
        return None
    

async def check_and_refresh_token(user_id: int, platform: str) -> Optional[str]:
    from database import get_social_account, update_access_token

    account = get_social_account(user_id, platform)
    if not account:
        print(f"❌ No {platform} account found for user {user_id}")
        return None

    now        = datetime.now(timezone.utc)
    expires_at = account["token_expires_at"]

    if not expires_at:
        print(f"✅ {platform} token has no expiry, using as is")
        return account["access_token"]

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at > now + timedelta(hours=1):
        print(f"✅ {platform} token still valid")
        return account["access_token"]

    print(f"🔄 Refreshing {platform} token for user {user_id}")

    if platform in ("facebook", "instagram"):
        result = await refresh_facebook_token(account["access_token"])
    elif platform == "linkedin":
        result = await refresh_linkedin_token(account.get("refresh_token"))
    else:
        return None

    if result:
        update_access_token(account["id"], result["access_token"], result["expires_at"])
        print(f"✅ {platform} token refreshed successfully")
        return result["access_token"]

    print(f"⚠️ {platform} refresh failed, trying existing token")
    return account["access_token"]