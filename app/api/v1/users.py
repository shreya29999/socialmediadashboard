from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.db.database import execute_query
from app.schemas.users import UserProfileRequest

router = APIRouter(prefix="/user", tags=["Users"])


@router.post("/profile")
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


@router.get("/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    profile = execute_query(
        "SELECT * FROM user_profiles WHERE user_id = %s",
        (current_user["user_id"],),
        fetch="one"
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete questionnaire.")
    return profile
