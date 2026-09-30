from sqlalchemy import func, select

from app.db.models import PostTemplate, ScheduledPost, SocialAccount, User, UserProfile
from app.db.session import SessionLocal


def get_admins():
    with SessionLocal() as db:
        rows = db.execute(
            select(User.id, User.email, User.role, User.admin_id, User.invite_code)
            .where(User.role == "admin")
            .order_by(User.created_at.desc())
        ).all()
        return [
            {
                "id": row[0],
                "email": row[1],
                "role": row[2],
                "admin_id": row[3],
                "invite_code": row[4],
            }
            for row in rows
        ]


def get_all_users():
    with SessionLocal() as db:
        rows = db.execute(
            select(
                User.id,
                User.email,
                User.role,
                User.admin_id,
                User.last_login_at,
                User.created_at,
                UserProfile.persona,
                UserProfile.industry,
                UserProfile.brand_name,
                (
                    select(func.count(PostTemplate.id))
                    .where(PostTemplate.user_id == User.id)
                    .scalar_subquery()
                ).label("total_templates"),
                (
                    select(func.count(ScheduledPost.id))
                    .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
                    .where(PostTemplate.user_id == User.id)
                    .scalar_subquery()
                ).label("total_posts"),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.role != "superadmin")
            .order_by(User.created_at.desc())
        ).all()

        result = []
        for row in rows:
            user_id = row[0]
            connected_platforms = db.execute(
                select(SocialAccount.platform)
                .where(SocialAccount.user_id == user_id)
            ).scalars().all()
            result.append({
                "id": row[0],
                "email": row[1],
                "role": row[2],
                "admin_id": row[3],
                "last_login_at": row[4],
                "created_at": row[5],
                "persona": row[6],
                "industry": row[7],
                "brand_name": row[8],
                "connected_platforms": connected_platforms,
                "total_templates": row[9] or 0,
                "total_posts": row[10] or 0,
            })
        return result


def get_users_for_admin(admin_id: int):
    with SessionLocal() as db:
        rows = db.execute(
            select(
                User.id,
                User.email,
                User.role,
                User.admin_id,
                User.last_login_at,
                User.created_at,
                UserProfile.persona,
                UserProfile.industry,
                UserProfile.brand_name,
                (
                    select(func.count(PostTemplate.id))
                    .where(PostTemplate.user_id == User.id)
                    .scalar_subquery()
                ).label("total_templates"),
                (
                    select(func.count(ScheduledPost.id))
                    .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
                    .where(PostTemplate.user_id == User.id)
                    .scalar_subquery()
                ).label("total_posts"),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.admin_id == admin_id, User.role != "superadmin")
            .order_by(User.created_at.desc())
        ).all()

        result = []
        for row in rows:
            user_id = row[0]
            connected_platforms = db.execute(
                select(SocialAccount.platform)
                .where(SocialAccount.user_id == user_id)
            ).scalars().all()
            result.append({
                "id": row[0],
                "email": row[1],
                "role": row[2],
                "admin_id": row[3],
                "last_login_at": row[4],
                "created_at": row[5],
                "persona": row[6],
                "industry": row[7],
                "brand_name": row[8],
                "connected_platforms": connected_platforms,
                "total_templates": row[9] or 0,
                "total_posts": row[10] or 0,
            })
        return result


def get_admins_overview():
    with SessionLocal() as db:
        rows = db.execute(
            select(
                User.id,
                User.email,
                User.org_name,
                User.address,
                User.created_at,
            )
            .where(User.role == "admin")
            .order_by(User.created_at.desc())
        ).all()

        result = []
        for row in rows:
            admin_id = row[0]
            user_count = db.execute(
                select(func.count(User.id)).where(User.admin_id == admin_id)
            ).scalar() or 0
            social_accounts = {}
            social_rows = db.execute(
                select(SocialAccount.platform, func.count(SocialAccount.id))
                .join(User, SocialAccount.user_id == User.id)
                .where(User.admin_id == admin_id)
                .group_by(SocialAccount.platform)
            ).all()
            for platform, cnt in social_rows:
                social_accounts[platform] = cnt
            total_posts = db.execute(
                select(func.count(ScheduledPost.id))
                .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
                .join(User, PostTemplate.user_id == User.id)
                .where(User.admin_id == admin_id)
            ).scalar() or 0
            result.append({
                "id": row[0],
                "email": row[1],
                "org_name": row[2] or row[1],
                "address": row[3],
                "created_at": row[4],
                "user_count": user_count,
                "total_posts": total_posts,
                "social_accounts": social_accounts,
            })
        return result


def get_admin_overview_detail(admin_id: int):
    with SessionLocal() as db:
        admin = db.execute(
            select(User.id, User.email, User.org_name, User.address, User.created_at)
            .where(User.id == admin_id, User.role == "admin")
        ).first()
        if not admin:
            return None

        user_count = db.execute(
            select(func.count(User.id)).where(User.admin_id == admin_id)
        ).scalar() or 0
        total_posts = db.execute(
            select(func.count(ScheduledPost.id))
            .join(PostTemplate, ScheduledPost.template_id == PostTemplate.id)
            .join(User, PostTemplate.user_id == User.id)
            .where(User.admin_id == admin_id)
        ).scalar() or 0

        social_accounts = {}
        social_detail = {}
        rows = db.execute(
            select(SocialAccount.platform, SocialAccount.account_name, SocialAccount.account_email, User.email)
            .join(User, SocialAccount.user_id == User.id)
            .where(User.admin_id == admin_id)
            .order_by(SocialAccount.platform)
        ).all()
        for platform, account_name, account_email, user_email in rows:
            social_accounts[platform] = social_accounts.get(platform, 0) + 1
            social_detail.setdefault(platform, []).append({
                "account_name": account_name,
                "account_email": account_email,
                "user_email": user_email,
            })

        return {
            "admin": {
                "id": admin[0],
                "email": admin[1],
                "org_name": admin[2] or admin[1],
                "address": admin[3],
                "created_at": admin[4],
            },
            "user_count": user_count,
            "total_posts": total_posts,
            "social_accounts": social_accounts,
            "social_accounts_detail": social_detail,
            "recent_activity": [],
        }
