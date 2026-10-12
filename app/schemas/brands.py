from pydantic import BaseModel , Field

class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    logo_url: str | None = None

class BrandResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    is_active: bool
    is_default: bool    