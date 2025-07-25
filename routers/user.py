from io import BytesIO
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_db
from models import User
from schemas.user_schema import SuccessMessage, User as UserBase, UserCreate, UserResponse
from uuid import UUID
from typing import List
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

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
    s3_client = None 


def upload_file_to_spaces(file_data: bytes, filename: str, content_type: str):

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

user_router = APIRouter(prefix="/users", tags=["Users"])

def create_username(name: str, surname: str) -> str:
    return f"{name.lower()}.{surname.lower()}"

def get_image_urls(user: User) -> List[str]:
    urls = []
    for img in user.profile_images:
        urls.append(f"/users/image/{user.id}/{img.type}")
    return urls

@user_router.post("/", response_model=SuccessMessage)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.phone_number and db.query(User).filter(User.phone_number == user.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    username = create_username(user.name, user.surname)

    new_user = User(
        username=username,
        email=user.email,
        date_of_birth=user.date_of_birth,
        name=user.name,
        gender=user.gender,
        surname=user.surname,
        status="pending",
        phone_number=user.phone_number if user.phone_number else None,
        role="customer",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        email=new_user.email,
        date_of_birth=new_user.date_of_birth,
        name=new_user.name,
        gender=new_user.gender,
        surname=new_user.surname,
        phone_number=new_user.phone_number,
        personal_image_path=new_user.personal_image_path,
        user_id=new_user.id  # assuming `id` is UUID and maps to `user_id`
    )

@user_router.post("/image")
async def add_profile_image(
    user_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db) # This db dependency needs to be functional for your app
):
    
    # Query the database for the user
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Read the image file content
    contents = await file.read()
    
    # Generate a unique UUID for the image file
    image_uuid = uuid.uuid4()
    # Construct the filename for DigitalOcean Spaces, including a subdirectory
    # This ensures a consistent path for retrieval.
    spaces_filename = f"users/image/{image_uuid}" 

    # Upload the image to DigitalOcean Spaces
    image_url_from_spaces = upload_file_to_spaces(contents, spaces_filename, file.content_type)

    if image_url_from_spaces is None:
        raise HTTPException(status_code=500, detail="Failed to upload image to DigitalOcean Spaces.")

    user.personal_image_path = image_url_from_spaces
    
    try:
        db.add(user) # Add the modified user object to the session
        db.commit()  # Commit the transaction to save changes
        db.refresh(user) # Refresh the user object to reflect committed changes
    except Exception as e:
        db.rollback() # Rollback in case of an error
        raise HTTPException(status_code=500, detail=f"Failed to update user image path in database: {e}")

    # The returned URL is the direct link from DigitalOcean Spaces
    return {"msg": f"Profile image uploaded successfully", "image_url": image_url_from_spaces}

@user_router.get("/{username}", response_model=List[UserResponse])
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    users = db.query(User).filter(User.username == username).all()
    if not users:
        raise HTTPException(status_code=404, detail="User not found")

    # Attach image URLs to each user dict
    result = []
    for user in users:
        user_dict = user.__dict__.copy()
        user_dict["image_url"] = get_image_urls(user)
        result.append(user_dict)

    return result


@user_router.get("/{user_id}/details", response_model=UserResponse)
def get_user_by_id(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

@user_router.put("/{email}", response_model=UserBase)
def update_user(email: str, user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == email).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.phone_number and existing_user.phone_number != user.phone_number:
        if db.query(User).filter(User.phone_number == user.phone_number).first():
            raise HTTPException(status_code=400, detail="Phone number already registered")

    existing_user.email = user.email
    existing_user.name = user.name
    existing_user.surname = user.surname
    existing_user.date_of_birth = user.date_of_birth
    existing_user.phone_number = user.phone_number

    db.commit()
    db.refresh(existing_user)

    user_dict = existing_user.__dict__.copy()
    user_dict["image_urls"] = get_image_urls(existing_user)

    return user_dict


@user_router.delete("/{user_id}")
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"msg": "User deleted successfully"}


@user_router.get("/", response_model=List[UserBase])
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@user_router.get("/exists/{email}")
def user_exists(email: str, db: Session = Depends(get_db)):
    return db.query(User).filter(User.email == email).first() is not None
