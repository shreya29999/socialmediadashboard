from sqlalchemy import select

from app.db.models import SocialAccount
from app.db.session import SessionLocal


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _account_to_dict(account) -> dict:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "platform": account.platform,
        "access_token": account.access_token,
        "refresh_token": account.refresh_token,
        "token_expires_at": account.token_expires_at,
        "page_id": account.page_id,
        "account_name": account.account_name,
        "account_email": account.account_email,
        "created_at": account.created_at,
    }


# ---------------------------------------------------------------------------
# Save / upsert
# ---------------------------------------------------------------------------

def save_social_account(
    user_id: int,
    platform: str,
    access_token: str,
    refresh_token: str | None = None,
    token_expires_at=None,
    page_id: str | None = None,
    account_name: str | None = None,
    account_email: str | None = None,
):
    with SessionLocal() as db:
        # Use .first() instead of .scalar_one_or_none() so that
        # pre-existing duplicate rows don't crash the OAuth callback.
        # We update the most recently created matching row.
        account = db.execute(
            select(SocialAccount)
            .where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.page_id == page_id,
            )
            .order_by(SocialAccount.created_at.desc(), SocialAccount.id.desc())
            .limit(1)
        ).scalars().first()

        if account is None:
            account = SocialAccount(
                user_id=user_id,
                platform=platform,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                page_id=page_id,
                account_name=account_name,
                account_email=account_email,
            )

            db.add(account)
            db.commit()
            db.refresh(account)

            return {"id": account.id}

        account.access_token = access_token
        account.refresh_token = refresh_token
        account.token_expires_at = token_expires_at
        account.account_name = account_name
        account.account_email = account_email

        db.commit()

        return {"id": account.id}


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_social_accounts(
    user_id: int,
    platform: str | None = None,
):
    with SessionLocal() as db:
        query = select(SocialAccount).where(
            SocialAccount.user_id == user_id
        )

        if platform:
            query = query.where(
                SocialAccount.platform == platform
            )

        accounts = db.execute(
            query.order_by(
                SocialAccount.platform,
                SocialAccount.created_at,
            )
        ).scalars().all()

        return [_account_to_dict(account) for account in accounts]


def get_social_account_by_id(
    account_id: int,
    user_id: int,
):
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.user_id == user_id,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        return _account_to_dict(account)


def get_social_account(user_id: int, platform: str):
    """
    Return the best matching social account for (user_id, platform).

    Previously this used `.scalar_one_or_none()`, which raises
    `MultipleResultsFound` if the user has more than one row for the
    same platform. That is a real possibility in production (users
    re-connecting OAuth creates a new row if page_id changes), so we
    now deterministically pick one:

        1. Prefer rows whose token has not expired.
        2. Among those, prefer the most recently created row.

    If you would rather treat duplicates as a hard error, replace the
    query below with `.scalar_one_or_none()` and fix the data instead.
    """
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount)
            .where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
            )
            .order_by(
                # Non-expired tokens first (NULL expiry is treated as
                # non-expired, which is the historical behaviour).
                SocialAccount.token_expires_at.is_(None).desc(),
                SocialAccount.token_expires_at.desc(),
                SocialAccount.created_at.desc(),
                SocialAccount.id.desc(),
            )
            .limit(1)
        ).scalars().first()

        if account is None:
            return None

        return _account_to_dict(account)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def update_access_token(
    account_id: int,
    new_token: str,
    new_expiry,
):
    with SessionLocal() as db:
        account = db.get(SocialAccount, account_id)

        if account is None:
            return None

        account.access_token = new_token
        account.token_expires_at = new_expiry

        db.commit()

        return {"id": account.id}


# ---------------------------------------------------------------------------
# Brand-scoped accounts
# ---------------------------------------------------------------------------

def save_brand_social_account(
    user_id: int,
    brand_id: int,
    platform: str,
    access_token: str,
    refresh_token: str | None = None,
    token_expires_at=None,
    page_id: str | None = None,
    account_name: str | None = None,
    account_email: str | None = None,
):
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount)
            .where(
                SocialAccount.user_id == user_id,
                SocialAccount.brand_id == brand_id,
                SocialAccount.platform == platform,
                SocialAccount.page_id == page_id,
            )
            .order_by(SocialAccount.created_at.desc(), SocialAccount.id.desc())
            .limit(1)
        ).scalars().first()

        if account is None:
            account = SocialAccount(
                user_id=user_id,
                brand_id=brand_id,
                platform=platform,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                page_id=page_id,
                account_name=account_name,
                account_email=account_email,
            )

            db.add(account)
            db.commit()
            db.refresh(account)

            return {"id": account.id}

        account.access_token = access_token
        account.refresh_token = refresh_token
        account.token_expires_at = token_expires_at
        account.account_name = account_name
        account.account_email = account_email

        db.commit()

        return {"id": account.id}


def get_brand_social_accounts(
    user_id: int,
    brand_id: int,
    platform: str | None = None,
):
    with SessionLocal() as db:
        query = select(SocialAccount).where(
            SocialAccount.user_id == user_id,
            SocialAccount.brand_id == brand_id,
        )

        if platform:
            query = query.where(
                SocialAccount.platform == platform
            )

        accounts = db.execute(
            query.order_by(
                SocialAccount.platform,
                SocialAccount.created_at,
            )
        ).scalars().all()

        return [
            {
                "id": account.id,
                "user_id": account.user_id,
                "brand_id": account.brand_id,
                "platform": account.platform,
                "access_token": account.access_token,
                "refresh_token": account.refresh_token,
                "token_expires_at": account.token_expires_at,
                "page_id": account.page_id,
                "account_name": account.account_name,
                "account_email": account.account_email,
                "created_at": account.created_at,
            }
            for account in accounts
        ]


def get_brand_social_account_by_id(
    account_id: int,
    user_id: int,
    brand_id: int,
):
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.user_id == user_id,
                SocialAccount.brand_id == brand_id,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        return {
            "id": account.id,
            "user_id": account.user_id,
            "brand_id": account.brand_id,
            "platform": account.platform,
            "access_token": account.access_token,
            "refresh_token": account.refresh_token,
            "token_expires_at": account.token_expires_at,
            "page_id": account.page_id,
            "account_name": account.account_name,
            "account_email": account.account_email,
            "created_at": account.created_at,
        }


def update_brand_social_account_token(
    account_id: int,
    user_id: int,
    brand_id: int,
    new_token: str,
    new_expiry,
):
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.user_id == user_id,
                SocialAccount.brand_id == brand_id,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

        account.access_token = new_token
        account.token_expires_at = new_expiry

        db.commit()

        return {"id": account.id}