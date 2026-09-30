from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_current_user
from app.repositories.user_repository import (
    get_user_profile as get_user_profile_repo,
    save_user_profile,
    
)
from app.schemas.users import UserProfileRequest
router = APIRouter(prefix="/user", tags=["Users"])


@router.post("/profile")
def save_user_profile(
    req: UserProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    industry = (
        req.industry
        if isinstance(req.industry, str)
        else ", ".join(req.industry)
    )

    tone = (
        req.tone
        if isinstance(req.tone, str)
        else ", ".join(req.tone)
    )

    audience = (
        req.audience
        if isinstance(req.audience, str)
        else ", ".join(req.audience)
    )

    save_user_profile(
        user_id=current_user["user_id"],
        persona=req.persona,
        industry=industry,
        brand_name=req.brand_name,
        tone=tone,
        audience=audience,
        country_code=req.country_code,
        language=req.language,
        posts_per_week=req.posts_per_week,
    )

    return {"message": "Profile saved ✅"}


@router.get("/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    profile = get_user_profile_repo(current_user["user_id"])

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Please complete questionnaire.",
        )

    return profile
