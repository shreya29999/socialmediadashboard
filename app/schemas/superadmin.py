from typing import Optional
from pydantic import BaseModel

class CreateAdminRequest(BaseModel):
    email        : str
    password     : str
    invite_code  : Optional[str] = None
    org_name     : str
    address      : Optional[str] = None
