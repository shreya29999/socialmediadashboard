from typing import Optional
from enum import Enum
from pydantic import BaseModel

class UserRole(str, Enum):
    USER = "user"

class RegisterRequest(BaseModel):
    email       : str
    password    : str
    timezone    : Optional[str] = "UTC"
    invite_code : Optional[str] = None
    admin_email : Optional[str] = None
    role        : Optional[UserRole] = UserRole.USER
class LoginRequest(BaseModel):
    email    : str
    password : str
class RejectRequest(BaseModel):
    token  : str
    reason : Optional[str] = None
