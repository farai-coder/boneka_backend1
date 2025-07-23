from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    supplier_id: UUID    
    category: str  # e.g. electronics, furniture, etc.

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    supplier_id: UUID    
    category: str  # e.g. electronics, furniture, etc.
    image_path: Optional[str] = None  # URL or path to the product image

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(ProductBase):
    name: str
    description: Optional[str] = None
    price: float
    supplier_id: UUID    
    category: str  # e.g. electronics, furniture, etc.
    
class Product(ProductBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class SuccessMessage(BaseModel):
    message: str
