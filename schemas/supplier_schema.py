from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

class SupplierBase(BaseModel):
    email: EmailStr
    name: str
    phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    business_name: Optional[str] = None
    business_category: Optional[str] = None
    business_description: Optional[str] = None
    business_type: Optional[str] = None
    business_email: Optional[EmailStr] 
    image_url: Optional[str] = None

class SupplierResponse(BaseModel):
    business_name: Optional[str] = None
    business_phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    business_name: Optional[str] = None
    business_category: Optional[str] = None
    business_description: Optional[str] = None
    business_type: Optional[str] = None
    business_email: Optional[EmailStr] = None
    
class Supplier(SupplierBase):
    id: UUID
    status: str
    role: str 
    created_at: datetime
    
    class Config:
        orm_mode = True


class SuccessMessage(BaseModel):
    message: str

