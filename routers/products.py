from io import BytesIO
from typing import Optional, List
import uuid
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form, status, Request # Import Request
from models import Product, User
from schemas.products_schema import Product as ProductBase, ProductCreate, ProductResponse # Assuming Product is renamed to ProductBase in schemas
from uuid import UUID, uuid4

from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
from pydantic import BaseModel, ConfigDict # Import BaseModel and ConfigDict for Pydantic models
from typing import Optional, List
from io import BytesIO
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse # Import RedirectResponse

from schemas.supplier_schema import SupplierResponse
from schemas.user_schema import SuccessMessage
import os
# Load environment variables from .env file

# Configuration from environment variables
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# --- Validate Configuration (Optional but Recommended) ---
required_vars = ["SPACES_REGION", "SPACES_ENDPOINT", "ACCESS_KEY", "SECRET_KEY", "BUCKET_NAME"]
for var in required_vars:
    if os.getenv(var) is None:
        raise ValueError(f"Environment variable {var} not set. Please check your .env file.")

# Initialize S3 client globally. This should ideally be handled with FastAPI's dependency injection
# or application startup events for more robust error handling and resource management.
try:
    session = boto3.session.Session()
    s3_client = session.client(
        's3',
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )
except Exception as e:
    print(f"Error initializing S3 client: {e}")
    s3_client = None # Set to None if initialization fails, and handle this in functions


def upload_file_to_spaces(file_data: bytes, filename: str, content_type: str):
    """
    Uploads a file to DigitalOcean Spaces.

    Args:
        file_data (bytes): The content of the file to upload.
        filename (str): The desired filename in Spaces.
        content_type (str): The MIME type of the file (e.g., "image/jpeg").

    Returns:
        str: The public URL of the uploaded file, or None if an error occurs.
    """
    if s3_client is None:
        print("S3 client not initialized. Cannot upload file.")
        return None
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=file_data,
            ACL='public-read',  # Makes the file publicly accessible
            ContentType=content_type
        )
        # Construct the public URL for the uploaded file
        return f"{SPACES_ENDPOINT}/{BUCKET_NAME}/{filename}"
    except NoCredentialsError:
        print("Credentials not available. Check ACCESS_KEY and SECRET_KEY in .env.")
        return None
    except Exception as e:
        print(f"Error uploading file to Spaces: {e}")
        return None

def delete_file_from_spaces(filename: str):
    """
    Deletes a file from DigitalOcean Spaces.

    Args:
        filename (str): The filename (Key) of the file to delete in Spaces.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    if s3_client is None:
        print("S3 client not initialized. Cannot delete file.")
        return False
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=filename)
        return True
    except Exception as e:
        print(f"Error deleting file from Spaces: {e}")
        return False

# Create a new router for products
product_router = APIRouter(prefix="/products", tags=["products"])

# Helper to construct image URL dynamically
def _get_image_url(request: Request, image_id: UUID) -> str:
    # Use request.url_for to generate the absolute URL for the image endpoint
    # The 'get_product_image_route' should match the name of your route function for fetching images
    return str(request.url_for("get_product_image_route", image_id=image_id))

@product_router.post("/", response_model=SuccessMessage, status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str = Form(...),
    category: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    supplier_id: str = Form(...),
    image: UploadFile = File(...),   # Required image upload
    db: Session = Depends(get_db),
):
    # Optionally validate supplier exists (uncomment if needed)
    # supplier = db.query(User).filter(User.id == supplier_id).first()
    # if not supplier:
    #     raise HTTPException(status_code=404, detail="Supplier not found")

    # Validate image is an actual image (content_type check)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"File {image.filename} is not an image.")

    # Read and upload image to storage
    contents = await image.read()
    image_uuid = uuid4()
    spaces_filename = f"products/images/{image_uuid}"

    image_url = upload_file_to_spaces(contents, spaces_filename, image.content_type)
    if image_url is None:
        raise HTTPException(status_code=500, detail="Failed to upload image to DigitalOcean Spaces.")

    # Create Product DB object
    db_product = Product(
        name=name,
        category=category,
        description=description,
        price=price,
        supplier_id=supplier_id,
        image_path=image_url,
    )

    try:
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
    except Exception as e:
        db.rollback()
        delete_file_from_spaces(spaces_filename)
        raise HTTPException(status_code=500, detail=f"Failed to create product: {e}")

    return SuccessMessage(message="Product created successfully")

@product_router.get("/{product_id}", response_model=ProductBase)
def get_product(
    request: Request, # Added Request dependency
    product_id: UUID, 
    db: Session = Depends(get_db)
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    product_response = ProductBase.model_validate(db_product)
    if db_product.main_image_id:
        product_response.main_image_url = _get_image_url(request, db_product.main_image_id)
    return product_response

@product_router.get("/", response_model=List[ProductResponse])
def get_all_products(
    request: Request,
    db: Session = Depends(get_db)
):
    products = db.query(Product).all()
    product_list = []

    for product in products:
        product_data = ProductResponse.from_orm(product)
        product_list.append(product_data)

    return product_list

@product_router.put("/{product_id}", response_model=ProductBase)
def update_product(
    request: Request, # Added Request dependency
    product_id: UUID, 
    product_update: ProductCreate, 
    db: Session = Depends(get_db)
):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    for key, value in product_update.model_dump(exclude_unset=True).items():
        if key in ['file', 'main_image_id']:
            continue
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)

    product_response = ProductBase.model_validate(db_product)
    if db_product.main_image_id:
        product_response.main_image_url = _get_image_url(request, db_product.main_image_id)
    return product_response

@product_router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    db.delete(db_product)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Product and associated main image deleted successfully"})

@product_router.get("/supplier/{supplier_id}", response_model=List[ProductBase])
def get_products_by_supplier(
    request: Request, # Added Request dependency
    supplier_id: UUID, 
    db: Session = Depends(get_db)
):
    db_supplier = db.query(User).filter(User.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    
    products = db.query(Product).filter(Product.supplier_id == supplier_id).all()
    
    products_with_images = []
    for product in products:
        product_response = ProductBase.model_validate(product)
        if product.main_image_id:
            product_response.main_image_url = _get_image_url(request, product.main_image_id)
        products_with_images.append(product_response)
    return products_with_images

@product_router.get("/category/{category}", response_model=List[ProductBase])
def get_products_by_category(
    request: Request, # Added Request dependency
    category: str, 
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(Product.category == category).all()
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No products found in this category")
    
    products_with_images = []
    for product in products:
        product_response = ProductBase.model_validate(product)
        if product.main_image_id:
            product_response.main_image_url = _get_image_url(request, product.main_image_id)
        products_with_images.append(product_response)
    return products_with_images

@product_router.get("/search/{query}", response_model=List[ProductBase])
def search_products(
    request: Request, # Added Request dependency
    query: str, 
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(Product.name.ilike(f"%{query}%")).all()
    if not products:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No products found matching the query")
    
    products_with_images = []
    for product in products:
        product_response = ProductBase.model_validate(product)
        if product.main_image_id:
            product_response.main_image_url = _get_image_url(request, product.main_image_id)
        products_with_images.append(product_response)
    return products_with_images

@product_router.get("/supplier/{supplier_id}/count")
def count_products_by_supplier(supplier_id: UUID, db: Session = Depends(get_db)):
    supplier = db.query(User).filter(User.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    
    count = db.query(Product).filter(Product.supplier_id == supplier_id).count()
    return {"count": count}

@product_router.get("/count")
def count_all_products(db: Session = Depends(get_db)):
    count = db.query(Product).count()
    return {"count": count}