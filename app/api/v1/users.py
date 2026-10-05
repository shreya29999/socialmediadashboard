import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.api.dependencies import get_current_user
from app.repositories.user_repository import (
    get_user_profile as get_user_profile_repo,
    save_user_profile as save_user_profile_repo,
    update_user_logo,
    update_user_footer,
    

)
import cloudinary
import cloudinary.uploader
from app.core.config import configure_cloudinary
from app.schemas.users import UserProfileRequest
logger = logging.getLogger(__name__)

configure_cloudinary()
router = APIRouter(prefix="/user", tags=["Users"])



@router.put("/profile/logo")
async def upload_profile_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    allowed_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, and WebP logo images are supported.",
        )

    contents = await file.read()

    max_size = 5 * 1024 * 1024  # 5 MB

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Logo file is too large. Maximum size is 5MB.",
        )

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Logo file is empty.",
        )

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="socialdesk/logos",
            resource_type="image",
        )

        logo_url = result.get("secure_url")

        if not logo_url:
            raise HTTPException(
                status_code=500,
                detail="Cloudinary did not return a logo URL.",
            )

        save_user_profile_repo(
            user_id=current_user["user_id"],
            persona=None,
            industry=None,
            brand_name=None,
            logo_url=logo_url,
            tone=None,
            audience=None,
            country_code=None,
            language=None,
            posts_per_week=3,
        )

        return {
            "success": True,
            "message": "Logo uploaded successfully.",
            "logo_url": logo_url,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Logo upload failed: {str(e)}",
        )

@router.put("/profile/footer")
async def upload_profile_footer(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    allowed_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, and WEBP footer images are allowed.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Footer file is empty.",
        )

    max_size = 5 * 1024 * 1024

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Footer image must be smaller than 5 MB.",
        )

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="socialdesk/footers",
            resource_type="image",
        )

        footer_url = result.get("secure_url")

        if not footer_url:
            raise HTTPException(
                status_code=500,
                detail="Cloudinary did not return a footer URL.",
            )

        updated_footer = update_user_footer(
            user_id=current_user["user_id"],
            footer_url=footer_url,
        )

        if not updated_footer:
            raise HTTPException(
                status_code=404,
                detail="User profile not found.",
            )

        return {
            "success": True,
            "message": "Footer uploaded successfully.",
            "footer_url": footer_url,
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to upload footer | user_id=%s",
            current_user["user_id"],
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to upload footer.",
        ) from exc



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

    save_user_profile_repo(
        user_id=current_user["user_id"],
        persona=req.persona,
        industry=industry,
        brand_name=req.brand_name,
        logo_url=req.logo_url,  
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
