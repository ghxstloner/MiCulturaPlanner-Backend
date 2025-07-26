"""
Esquemas para autenticación
"""
from typing import Optional
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    login: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_info: dict
    message: str

class TokenData(BaseModel):
    login: Optional[str] = None
    user_id: Optional[str] = None

class UserResponse(BaseModel):
    login: str
    name: str
    email: str
    is_admin: bool
    active: bool
    id_aerolinea: Optional[int] = None