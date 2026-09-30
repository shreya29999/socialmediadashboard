from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class RecurrenceType(str, Enum):
    ONE_TIME      = "ONE_TIME"
    EVERY_X_DAYS  = "EVERY_X_DAYS"
    WEEKLY        = "WEEKLY"
    MONTHLY       = "MONTHLY"
    CRON          = "CRON"
class Platform(str, Enum):
    facebook  = "facebook"
    instagram = "instagram"
    linkedin  = "linkedin"
class CreatePostRequest(BaseModel):
    content_text    : str = Field(..., min_length=1, max_length=2000)
    media_url       : Optional[str] = None
    platforms       : List[Platform]
    recurrence_type : RecurrenceType = RecurrenceType.ONE_TIME
    interval_days   : Optional[int] = 1
    start_date      : str
    end_date        : Optional[str] = None
    max_occurrences : Optional[int] = None
    timezone        : Optional[str] = "UTC"
class UpdatePostRequest(BaseModel):
    content_text : Optional[str] = Field(None, min_length=1, max_length=2000)
    media_url    : Optional[str] = None
    platforms    : Optional[List[Platform]] = None
    scheduled_at : Optional[str] = None

class GeneratePostRequest(BaseModel):
    """
    Request Schemas for AI-Based social Media Post
    """
    title: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Topic or title for the AI-generated social media post.",
    )

    platform: Platform = Field(
        default=Platform.linkedin,
        description="Social media platform for the generated post.",
    )
    generate_image: bool = Field(
        default=True,
        description="Whether to generate an AI image for the post.",
    )
    # scheduled_at: Optional[str] = Field(
    #     default=None,
    #     description="Optional scheduled publication time.",
    # )  
    scheduled_at: Optional[datetime] = None


class GeneratedPostResponse(BaseModel):
    """
    Response Schemas for the AI-Generated social media content
    """
    post_id: int
    title: str
    platform: Platform
    caption: str
    image_prompt: str
    image_url: Optional[str] = None
    status: str = "generated"
    scheduled_at: Optional[str] = None
