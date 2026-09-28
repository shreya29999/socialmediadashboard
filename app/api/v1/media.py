import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_current_user
from app.core.config import configure_cloudinary

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
