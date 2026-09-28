from typing import Optional
from pydantic import BaseModel

class RegisterRequest(BaseModel):
    email       : str
    password    : str
    timezone    : Optional[str] = "UTC"
    invite_code : Optional[str] = None
    admin_email : Optional[str] = None
class LoginRequest(BaseModel):
    email    : str
    password : str
class RejectRequest(BaseModel):
    token  : str
    reason : Optional[str] = None
