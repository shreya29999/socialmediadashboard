from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.media import router as media_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.posts import router as posts_router
from app.api.v1.social_accounts import router as social_accounts_router
from app.api.v1.superadmin import router as superadmin_router
from app.api.v1.users import router as users_router
from app.core.config import ALLOWED_ORIGINS, configure_cloudinary
from app.core.logging import logger
from app.db.database import init_db


configure_cloudinary()

app = FastAPI(
    title="Social Media Dashboard",
    description="Automate your social media posts",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("App started, DB ready")


@app.on_event("shutdown")
async def shutdown():
    logger.info("App shutting down")


@app.get("/api")
def root():
    return {"message": "Social Media Dashboard API v2 ✅"}


app.include_router(auth_router)
app.include_router(social_accounts_router)
app.include_router(media_router)
app.include_router(users_router)
app.include_router(posts_router)
app.include_router(approvals_router)
app.include_router(analytics_router)
app.include_router(calendar_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(superadmin_router)
app.include_router(notifications_router)

# Serve the dashboard from FastAPI so its API requests stay on the same origin.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
