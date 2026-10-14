from typing import Literal, Optional
from enum import Enum
from pydantic import BaseModel

class UserRole(str, Enum):
    USER = "user"

from typing import Literal, Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    email: str
    password: str
    timezone: Optional[str] = "UTC"
    invite_code: Optional[str] = None
    admin_email: Optional[str] = None
    role: Literal["user", "superadmin"] = "user"
class LoginRequest(BaseModel):
    email    : str
    password : str
class RejectRequest(BaseModel):
    token  : str
    reason : Optional[str] = None
