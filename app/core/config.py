import os

import cloudinary
from dotenv import load_dotenv

load_dotenv()

# APPLICATION CONFIGURATION

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000",
    ).split(",")
    if origin.strip()
]
# META CONFIGURATION

META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI")

# LINKEDIN CONFIGURATION

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")

# CLOUDINARY CONFIGURATION


CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# APPLICATION URL

BASE_URL = os.getenv("BASE_URL")

# REDIS CONFIGURATION


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

REDIS_CONNECT_TIMEOUT = float(
    os.getenv("REDIS_CONNECT_TIMEOUT", "5")
)

REDIS_SOCKET_TIMEOUT = float(
    os.getenv("REDIS_SOCKET_TIMEOUT", "5")
)

# STATUS LIST

STATUS_LIST = [
    "scheduled",
    "awaiting_hr_approval",
    "awaiting_admin_approval",
    "approved",
    "posting",
    "posted",
    "failed",
    "expired",
    "cancelled",
    "skipped",
]

# CLOUDINARY SETUP


def configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )