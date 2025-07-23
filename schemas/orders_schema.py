from decimal import Decimal
from pydantic import BaseModel
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime # Corrected: Imported 'datetime' class directly

class OrderAction(BaseModel):
    user_id : UUID
    order_id : UUID
    action : Literal["delivered","cancelled"]
    
class RequestInfo(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    category: Optional[str]

    class Config:
        from_attributes = True # Corrected: Renamed from 'orm_mode'
    
class OrderOut(BaseModel):
    id: UUID
    status: str
    total_price: Decimal
    quantity: int
    created_at: datetime # This now correctly refers to the 'datetime' class
    request: RequestInfo

    class Config:
        from_attributes = True # Corrected: Renamed from 'orm_mode'