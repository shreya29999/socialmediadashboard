import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.schemas.users import UserOverlayRequest
from app.api.dependencies import get_current_user
from app.core.config import configure_cloudinary
from app.repositories.user_repository import update_user_overlay

configure_cloudinary()

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/upload")
async def upload_media(
    file         : UploadFile = File(...),
    current_user : dict = Depends(get_current_user)
):
    allowed_images = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
    allowed_videos = {"video/mp4", "video/mov", "video/quicktime", "video/avi", "video/mkv"}
    allowed = allowed_images | allowed_videos
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, WebP images and MP4, MOV, AVI videos are supported")
    contents = await file.read()    
    is_video = file.content_type in allowed_videos
    max_size = 650 * 1024 * 1024 if is_video else 8 * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {'650MB for videos' if is_video else '8MB for images'}"
        )
    try:
        upload_options = {
            "folder"        : "socialdesk",
            "resource_type" : "auto",   
        }
        if not is_video:
            upload_options["transformation"] = [
                {"width": 1080, "height": 1080, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]

        result = cloudinary.uploader.upload(contents, **upload_options)
        return {
            "success"      : True,
            "url"          : result["secure_url"],
            "public_id"    : result["public_id"],
            "resource_type": result.get("resource_type"), 
            "format"       : result.get("format"),
            "width"        : result.get("width"),
            "height"       : result.get("height"),
            "duration"     : result.get("duration"),       
            "size_bytes"   : result.get("bytes")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.put("/user/profile/overlay")
async def update_overlay(
    req: UserOverlayRequest,
    current_user: dict = Depends(get_current_user),
):
    allowed_positions = {
        "top-left",
        "top-center",
        "top-right",
        "center-left",
        "center",
        "center-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    }

    if req.position not in allowed_positions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid overlay position. "
                f"Allowed positions: {sorted(allowed_positions)}"
            ),
        )

    overlay_text = req.text.strip() if req.text else None

    if overlay_text == "":
        overlay_text = None

    try:
        result = update_user_overlay(
            user_id=current_user["user_id"],
            overlay_text=overlay_text,
            overlay_position=req.position,
            overlay_text_size=req.text_size,
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="User profile not found",
            )

        return {
            "success": True,
            "message": "Overlay settings updated successfully",
            "overlay_text": result["overlay_text"],
            "overlay_position": result["overlay_position"],
            "overlay_text_size": result["overlay_text_size"],
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update overlay settings: {str(e)}",
        )    
