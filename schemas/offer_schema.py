from decimal import Decimal
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID

class OfferCreate(BaseModel):
    supplier_id: UUID
    proposed: Decimal

class OfferRead(BaseModel):
    id: UUID
    request_id: UUID
    supplier_id: UUID
    proposed: Decimal
    status: str
    created_at: datetime

    class Config:
        orm_mode = True

class RequestRead(BaseModel):
    id: UUID
    title: str
    description: str
    category: str
    offer_price: Decimal
    status: str
    offers_count: int

    class Config:
        orm_mode = True

class OfferAction(BaseModel):
    action: Literal["accept","reject", "confirm"]
    
class OfferAccept(BaseModel):
    request_id : UUID
    supplier_id: UUID


class SuccessMessage(BaseModel):
    message: str
