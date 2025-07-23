import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas.supplier_schema import SupplierResponse, SupplierUpdate  # Use the Pydantic schema for input validation
from uuid import UUID
from fastapi.responses import JSONResponse
from io import BytesIO
from fastapi.responses import StreamingResponse

from schemas.user_schema import SuccessMessage
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

# Load environment variables from .env file
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

supplier_router = APIRouter(prefix="/supplier", tags=["Suppliers"])

# Helper to get image url for business pic
def get_business_image_url(user_id: UUID):
    return f"/supplier/image/{user_id}/business"

@supplier_router.put("/business/{user_id}", response_model=SuccessMessage)
def add_or_edit_business_profile(user_id: UUID, business_data: SupplierResponse, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if email or phone used by others
    email_used = db.query(User).filter(User.business_email == business_data.business_email, User.id != user_id).first()
    if email_used:
        raise HTTPException(status_code=400, detail="Email already in use by another account")

    if business_data.business_phone_number:
        phone_used = db.query(User).filter(User.business_phone_number == business_data.business_phone_number, User.id != user_id).first()
        if phone_used:
            raise HTTPException(status_code=400, detail="Phone number already in use by another account")

    # Update business info
    user.business_name = business_data.business_name
    user.business_category = business_data.business_category
    user.business_description = business_data.business_description
    user.business_type = business_data.business_type
    user.business_email = business_data.business_email
    user.business_phone_number = business_data.business_phone_number
    user.latitude = business_data.latitude
    user.longitude = business_data.longitude

    # Ensure role is supplier
    user.role = "supplier"

    db.commit()
    db.refresh(user)
    return {"message": "Business profile editted successfully"}

@supplier_router.delete("/business/{user_id}")
def delete_business_profile(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Clear business fields
    user.business_name = None
    user.business_category = None
    user.business_description = None
    user.business_type = None

    # Optionally reset role back to customer or another role
    user.role = "customer"

    db.commit()
    return {"message": "Business profile deleted successfully"}

@supplier_router.get("/image/{user_id}/business")
def get_business_profile_image(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    business_img = next((img for img in user.profile_images if img.type == "business"), None)
    if not business_img:
        raise HTTPException(status_code=404, detail="Business profile image not found")

    return StreamingResponse(BytesIO(business_img.image_data), media_type="image/png")

@supplier_router.post("/image/{user_id}/business")
async def add_or_update_business_image(
    user_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Read the image file content
    contents = await file.read()

    # Generate a unique UUID for the image file
    image_uuid = uuid.uuid4()
    # Construct the filename for DigitalOcean Spaces, including a subdirectory
    spaces_filename = f"users/image/{image_uuid}" 

    # Upload the image to DigitalOcean Spaces
    image_url_from_spaces = upload_file_to_spaces(contents, spaces_filename, file.content_type)

    if image_url_from_spaces is None:
        raise HTTPException(status_code=500, detail="Failed to upload image to DigitalOcean Spaces.")

    # Update the business_image_path field in the User model
    user.business_image_path = image_url_from_spaces
    
    try:
        db.add(user) # Add the modified user object to the session
        db.commit()  # Commit the transaction to save changes
        db.refresh(user) # Refresh the user object to reflect committed changes
    except Exception as e:
        db.rollback() # Rollback in case of an error
        raise HTTPException(status_code=500, detail=f"Failed to update business image path in database: {e}")

    # The returned URL is the direct link from DigitalOcean Spaces
    return {"msg": "Business profile image uploaded successfully", "image_url": image_url_from_spaces}

@supplier_router.get("/business/{user_id}", response_model=SupplierUpdate)
def get_business_profile(user_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves business profile information for a user, including the business image URL.

    Args:
        user_id (UUID): The ID of the user (supplier).
        db (Session): Database session dependency.

    Raises:
        HTTPException: If the user is not found.

    Returns:
        SupplierUpdate: The business profile data, including the image URL from DigitalOcean Spaces.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Directly use the business_image_path from the User model
    # This path already contains the full DigitalOcean Spaces URL
    business_image_url = user.business_image_path

    business_data = SupplierUpdate(
        business_name=user.business_name,
        business_category=user.business_category,
        business_description=user.business_description,
        business_type=user.business_type,
        business_email=user.business_email,
        phone_number=user.business_phone_number,
        latitude=user.latitude,
        longitude=user.longitude,
        image_url=business_image_url # Use the stored full URL directly
    )
    return business_data
