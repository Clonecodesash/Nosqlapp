"""Centralised configuration: environment variables and shared constants."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1").strip()
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "").strip()
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "").strip()
AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS = int(os.getenv("AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS", "3600"))

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
