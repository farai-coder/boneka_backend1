from pydantic import BaseModel, EmailStr
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID


class AuthBase(BaseModel):
    user_id : UUID
    password : str
    
class AuthLogin(BaseModel):
    email: EmailStr
    password : str

class AddPassword(BaseModel):
    email: EmailStr
    password : str

class AuthResponse(BaseModel):
    user_id : UUID
    status : str
    role : str

class LoginResponse(BaseModel):
    user_id : UUID
    status : str
    role : str
    name: str
    profile_image: Optional[str] = None
    email: EmailStr
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    business_profile_image: Optional[str] = None    
    
class PasswordResetRequest(BaseModel):
    email: str
    
class PasswordChange(BaseModel):
    user_id : UUID
    email: EmailStr
    old_password : str
    new_password : str