# from sqlalchemy import select

# from app.db.models import SocialAccount
# from app.db.session import SessionLocal


# # def save_social_account(
# #     user_id: int,
# #     platform: str,
# #     access_token: str,
# #     refresh_token: str | None = None,
# #     token_expires_at=None,
# #     page_id: str | None = None,
# #     account_name: str | None = None,
# #     account_email: str | None = None,
# # ):
# #     with SessionLocal() as db:
# #         account = db.execute(
# #             select(SocialAccount).where(
# #                 SocialAccount.user_id == user_id,
# #                 SocialAccount.platform == platform,
# #             )
# #         ).scalar_one_or_none()

# #         if account is None:
# #             account = SocialAccount(
# #                 user_id=user_id,
# #                 platform=platform,
# #                 access_token=access_token,
# #                 refresh_token=refresh_token,
# #                 token_expires_at=token_expires_at,
# #                 page_id=page_id,
# #                 account_name=account_name,
# #                 account_email=account_email,
# #             )
# #             db.add(account)
# #             db.commit()
# #             db.refresh(account)
# #             return {"id": account.id}

# #         account.access_token = access_token
# #         account.refresh_token = refresh_token
# #         account.token_expires_at = token_expires_at
# #         account.page_id = page_id
# #         account.account_name = account_name
# #         account.account_email = account_email
# #         db.commit()
# #         return {"id": account.id}

# def save_social_account(
#     user_id: int,
#     platform: str,
#     access_token: str,
#     refresh_token: str | None = None,
#     token_expires_at=None,
#     page_id: str | None = None,
#     account_name: str | None = None,
#     account_email: str | None = None,
# ):
#     with SessionLocal() as db:
#         account = db.execute(
#             select(SocialAccount).where(
#                 SocialAccount.user_id == user_id,
#                 SocialAccount.platform == platform,
#                 SocialAccount.page_id == page_id,
#             )
#         ).scalar_one_or_none()

#         if account is None:
#             account = SocialAccount(
#                 user_id=user_id,
#                 platform=platform,
#                 access_token=access_token,
#                 refresh_token=refresh_token,
#                 token_expires_at=token_expires_at,
#                 page_id=page_id,
#                 account_name=account_name,
#                 account_email=account_email,
#             )

#             db.add(account)
#             db.commit()
#             db.refresh(account)

#             return {"id": account.id}

#         account.access_token = access_token
#         account.refresh_token = refresh_token
#         account.token_expires_at = token_expires_at
#         account.account_name = account_name
#         account.account_email = account_email

#         db.commit()

#         return {"id": account.id}

# # def get_social_account(user_id: int, platform: str):
# #     with SessionLocal() as db:
# #         account = db.execute(
# #             select(SocialAccount).where(
# #                 SocialAccount.user_id == user_id,
# #                 SocialAccount.platform == platform,
# #             )
# #         ).scalar_one_or_none()

# #         if account is None:
# #             return None

# #         return {
# #             "id": account.id,
# #             "user_id": account.user_id,
# #             "platform": account.platform,
# #             "access_token": account.access_token,
# #             "refresh_token": account.refresh_token,
# #             "token_expires_at": account.token_expires_at,
# #             "page_id": account.page_id,
# #             "account_name": account.account_name,
# #             "account_email": account.account_email,
# #             "created_at": account.created_at,
# #         }

# def get_social_accounts(
#     user_id: int,
#     platform: str | None = None,
# ):
#     with SessionLocal() as db:
#         query = select(SocialAccount).where(
#             SocialAccount.user_id == user_id
#         )

#         if platform:
#             query = query.where(
#                 SocialAccount.platform == platform
#             )

#         accounts = db.execute(
#             query.order_by(
#                 SocialAccount.platform,
#                 SocialAccount.created_at,
#             )
#         ).scalars().all()

#         return [
#             {
#                 "id": account.id,
#                 "user_id": account.user_id,
#                 "platform": account.platform,
#                 "access_token": account.access_token,
#                 "refresh_token": account.refresh_token,
#                 "token_expires_at": account.token_expires_at,
#                 "page_id": account.page_id,
#                 "account_name": account.account_name,
#                 "account_email": account.account_email,
#                 "created_at": account.created_at,
#             }
#             for account in accounts
#         ]

# def update_access_token(account_id: int, new_token: str, new_expiry):
#     with SessionLocal() as db:
#         account = db.get(SocialAccount, account_id)
#         if account is None:
#             return None

#         account.access_token = new_token
#         account.token_expires_at = new_expiry
#         db.commit()
#         return {"id": account.id}



from sqlalchemy import select

from app.db.models import SocialAccount
from app.db.session import SessionLocal


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
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.page_id == page_id,
            )
        ).scalar_one_or_none()

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

        return [
            {
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
            for account in accounts
        ]


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


def get_social_account(user_id: int, platform: str):
    with SessionLocal() as db:
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
            )
        ).scalar_one_or_none()

        if account is None:
            return None

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
