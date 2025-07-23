from typing import List, Set
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status # Removed duplicate HTTPException, added status
from models import RequestPost, User, Product
from schemas.request_schema import RequestCreate, Request as RequestBase, RequestImageRead, RequestResponse, RequestUpdate # Assuming Request is renamed to RequestBase
from uuid import UUID

import uuid
import json
import boto3
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import os

from schemas.user_schema import SuccessMessage
from botocore.exceptions import NoCredentialsError

load_dotenv()

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
    

# Create a new router for requests
request_router = APIRouter(prefix="/requests", tags=["requests"]) # Added prefix for better organization

# CRUD operations for RequestPost

# Create a new request post

@request_router.post("/", response_model=SuccessMessage, status_code=status.HTTP_201_CREATED)
async def create_request(
    request_data: RequestCreate = Depends(),
    image: UploadFile = File(...),  # Single image upload
    db: Session = Depends(get_db)
):
    # Verify customer exists
    customer = db.query(User).filter(User.id == request_data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"File '{image.filename}' is not a valid image.")

    contents = await image.read()
    image_uuid = uuid.uuid4()
    spaces_filename = f"requests/images/{image_uuid}"

    image_url = upload_file_to_spaces(contents, spaces_filename, image.content_type)
    if image_url is None:
        raise HTTPException(status_code=500, detail=f"Failed to upload image '{image.filename}'.")

    # Create and save the request with image path
    db_request = RequestPost(
        title=request_data.title,
        category=request_data.category,
        description=request_data.description,
        quantity=request_data.quantity,
        offer_price=request_data.offer_price,
        customer_id=request_data.customer_id,
        image_path=image_url  # ✅ Save single image URL
    )

    try:
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
    except Exception as e:
        db.rollback()
        delete_file_from_spaces(spaces_filename)
        raise HTTPException(status_code=500, detail=f"Failed to create request: {e}")

    return SuccessMessage(message="Request created successfully")

# Get all request posts
@request_router.get("/", response_model=List[RequestBase]) # Corrected path from /get_all to /
async def get_all_requests(db: Session = Depends(get_db)):
    requests = db.query(RequestPost).all()
    return requests

# Get a request by id
@request_router.get("/{request_id}", response_model=RequestBase) # Corrected path from /get_single/{request_id}, and type to UUID
async def get_single_request(request_id: UUID, db: Session = Depends(get_db)): # Renamed function for clarity
    request = db.query(RequestPost).filter(RequestPost.id == request_id).first()
    if not request: # Added check for existence
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request

# Update a request
@request_router.put("/{request_id}", response_model=RequestBase) # Corrected path from /update/{request_id} and added request_id parameter
async def update_request(
    request_id: UUID, # Add request_id as path parameter
    request_update: RequestUpdate, # Renamed to avoid conflict with `Request` model
    db: Session = Depends(get_db)
):
    # Check if the request still exists
    existing_request = db.query(RequestPost).filter(RequestPost.id == request_id).first() # Use path parameter
    if not existing_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    
    # Update the fields
    # Use model_dump(exclude_unset=True) to only update fields that are provided in the payload
    for key, value in request_update.model_dump(exclude_unset=True).items(): # Use model_dump for Pydantic v2+
        setattr(existing_request, key, value)
    
    try:
        db.commit()
        db.refresh(existing_request)
        return existing_request
    except Exception as e: # Catch a more general Exception for database errors
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

# Delete a request
@request_router.delete("/{request_id}") # Corrected path from /delete/{request_id}
def delete_request(request_id: UUID, db: Session = Depends(get_db)):
    # Check if the request still exists
    existing_request = db.query(RequestPost).filter(RequestPost.id == request_id).first()
    if not existing_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    
    db.delete(existing_request)
    db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Request deleted successfully"})

@request_router.get("/matching_supplier_requests/{supplier_id}", response_model=List[RequestResponse])
def get_matching_supplier_requests(supplier_id: UUID, db: Session = Depends(get_db)):
    supplier = db.query(User).filter(User.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier_products = db.query(Product).filter(Product.supplier_id == supplier_id).all()
    if not supplier_products:
        raise HTTPException(status_code=400, detail="Supplier has no products.")

    product_categories = {product.category for product in supplier_products if product.category}
    print(f"Product categories for supplier {supplier_id}: {product_categories}")
    if not product_categories:
        raise HTTPException(status_code=400, detail="No product categories found.")

    matching_requests = db.query(RequestPost).filter(RequestPost.category.in_(product_categories)).all()


    return matching_requests  # SQLAlchemy models auto converted by FastAPI + Pydantic if `from_attributes` is set
