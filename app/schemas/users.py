from typing import Union, List
from pydantic import BaseModel

class UserProfileRequest(BaseModel):
    persona        : str
    industry       : Union[str, List[str]]
    brand_name     : str
    tone           : Union[str, List[str]]
    audience       : Union[str, List[str]]
    country_code   : str
    language       : str = "english"
    posts_per_week : int = 3
