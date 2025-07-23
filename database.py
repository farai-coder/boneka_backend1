from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# Define possible locations where Render might mount your secret .env file
possible_paths = [
    Path(__file__).parent / '.env',      # app root folder (likely)
    Path('/etc/secrets/.env'),           # Render's secret files folder (possible alternative)
]

env_path = None
for path in possible_paths:
    if path.exists():
        env_path = path
        break

if env_path:
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded .env from: {env_path}")
else:
    print("No .env file found in expected secret file locations.")

DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")  # FIXED here
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")  # default "prefer"


# Debug prints (remove in production)
print(f"DB_USERNAME={DB_USERNAME}")
print(f"DB_PASSWORD={'*' * len(DB_PASSWORD) if DB_PASSWORD else None}")
print(f"DB_HOST={DB_HOST}")
print(f"DB_PORT={DB_PORT}")
print(f"DB_NAME={DB_NAME}")
print(f"DB_SSLMODE={DB_SSLMODE}")


# Validate all required env variables
missing_vars = [var for var, val in {
    "DB_USERNAME": DB_USERNAME,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
}.items() if not val]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {missing_vars}")


SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode={DB_SSLMODE}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
