from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    login: str
    name: str
    email: str
    active: str
    priv_admin: Optional[str] = None
    id_aerolinea: Optional[int] = None
    picture: Optional[str] = None

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    login: str
    password: str