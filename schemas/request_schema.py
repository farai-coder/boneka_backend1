import datetime
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class RequestBase(BaseModel):
    title: str
    category: str
    quantity:Optional[int] = 1
    description : Optional[str] = None
    offer_price : float
    customer_id: UUID
    
class RequestCreate(RequestBase):
    pass

class RequestUpdate(RequestBase):
    id : UUID 
        
class Request(RequestBase):
    id: UUID
    created_at: datetime.datetime    
    
    class Config:
        orm_mode = True



class RequestImageRead(BaseModel):
    id: UUID
    request_id: UUID

    class Config:
        orm_mode = True

class SuccessMessage(BaseModel):
    message: str

class RequestResponse(BaseModel):
    id: UUID
    title: str
    category: str
    description: Optional[str]
    quantity: int
    offer_price: float
    customer_id: UUID
    image_path: Optional[str]  # or List[str] if you store multiple images
    

    class Config:
        from_attributes = True  # This is for Pydantic v2 (formerly `orm_mode = True` in v1)