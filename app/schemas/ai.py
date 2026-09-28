from pydantic import BaseModel, Field

class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=800)
