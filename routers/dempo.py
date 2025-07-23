import os
import uuid
import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import FastAPI, APIRouter, UploadFile, HTTPException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# --- Validate Configuration (Optional but Recommended) ---
# It's good practice to ensure all necessary environment variables are loaded.
required_vars = ["SPACES_REGION", "SPACES_ENDPOINT", "ACCESS_KEY", "SECRET_KEY", "BUCKET_NAME"]
for var in required_vars:
    if os.getenv(var) is None:
        raise ValueError(f"Environment variable {var} not set. Please check your .env file.")

# Create S3 client session
# This should ideally be done once and reused, or within a dependency injection system for FastAPI.
# For simplicity, we'll initialize it globally here.
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
    # Depending on your deployment, you might want to raise an exception or log more severely
    s3_client = None # Set to None if initialization fails


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

# Initialize FastAPI router
router = APIRouter()

@router.post("/upload-image/")
async def upload_image(file: UploadFile):
    """
    API endpoint to upload an image file to DigitalOcean Spaces.

    Args:
        file (UploadFile): The uploaded image file.

    Raises:
        HTTPException: If the uploaded file is not an image or upload fails.

    Returns:
        dict: A dictionary containing the public URL of the uploaded image.
    """
    # Validate file content type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    
    # Read file contents asynchronously
    contents = await file.read()
    
    # Generate a unique filename to prevent collisions
    unique_filename = f"users/image/{uuid.uuid4()}" # Using a subdirectory for user images
    
    # Upload the file to DigitalOcean Spaces
    url = upload_file_to_spaces(contents, unique_filename, file.content_type)
    
    if url is None:
        raise HTTPException(status_code=500, detail="Failed to upload image to Spaces.")
    
    return {"url": url}

@router.get("/get-image/{file_id}")
def get_image(file_id: str):
    """
    API endpoint to retrieve the public URL of an image from DigitalOcean Spaces.

    Args:
        file_id (str): The unique ID of the image (e.g., a UUID).

    Returns:
        dict: A dictionary containing the public URL of the image.
    """
    # Construct the full filename including the subdirectory
    full_filename = f"users/image/{file_id}"
    return {"url": f"{SPACES_ENDPOINT}/{BUCKET_NAME}/{full_filename}"}

# Initialize FastAPI application
app = FastAPI(
    title="DigitalOcean Spaces File Uploader",
    description="A simple FastAPI application to upload and retrieve files from DigitalOcean Spaces.",
    version="1.0.0"
)

# Include the router with a prefix for all file-related endpoints
app.include_router(router, prefix="/files")

if __name__ == "__main__":
    import uvicorn
    # Run the FastAPI application
    # host="0.0.0.0" makes the server accessible from any IP, useful in Docker/containerized environments
    # port=8000 is the default port for FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
