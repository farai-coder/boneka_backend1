from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env file — assumes it is in the same directory as this file
env_path = Path(__file__).parent / "routers" / ".env"
if not env_path.exists():
    raise FileNotFoundError(f".env file not found at {env_path}")

load_dotenv(dotenv_path=env_path)

# Load variables with fallback defaults for safety
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")  # Default to "prefer" if not set

# Debug prints (remove or comment out in production)
print(f"DB_USERNAME={DB_USERNAME}")
print(f"DB_PASSWORD={'*' * len(DB_PASSWORD) if DB_PASSWORD else None}")
print(f"DB_HOST={DB_HOST}")
print(f"DB_PORT={DB_PORT}")
print(f"DB_NAME={DB_NAME}")
print(f"DB_SSLMODE={DB_SSLMODE}")

# Validate critical environment variables
missing_vars = [var for var in ["DB_USERNAME", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"] if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {missing_vars}")

# Compose the SQL Alchemy database URL
SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode={DB_SSLMODE}"
)

# Create engine and session local
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
