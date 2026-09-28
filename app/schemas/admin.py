from pydantic import BaseModel

class CreateManagedUserRequest(BaseModel):
    email    : str
    password : str
