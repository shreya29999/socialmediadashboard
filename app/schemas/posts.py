from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

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
