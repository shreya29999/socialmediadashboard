from typing import Union, List,Optional
from pydantic import BaseModel

class UserProfileRequest(BaseModel):
    persona        : str
    industry       : Union[str, List[str]]
    brand_name     : str
    logo_url       : str | None = None
    tone           : Union[str, List[str]]
    audience       : Union[str, List[str]]
    country_code   : str
    language       : str = "english"
    posts_per_week : int = 3
    logo_size        : Optional[int] = 60       
    logo_position_x  : Optional[int] = 4         
    logo_position_y  : Optional[int] = 4         
    footer_height    : Optional[int] = 60       
    footer_width     : Optional[int] = 100     
    footer_position_x: Optional[int] = 0        
    footer_position_y: Optional[int] = 0         
    overlay_color    : Optional[str] = "#ffffff" 

class UserOverlayRequest(BaseModel):
    text: str | None = None
    position: str = "bottom-center"
    text_size: int
    color: Optional[str] = "#ffffff"    