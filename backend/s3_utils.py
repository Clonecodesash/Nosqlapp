"""Amazon S3 helpers for storing and serving ER-schema images."""

from mimetypes import guess_extension
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status

import os

from config import (
    AWS_REGION,
    AWS_S3_BUCKET,
    AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS,
    AWS_S3_PUBLIC_BASE_URL,
    SUPPORTED_IMAGE_TYPES,
)
from models import ERSchema


def require_s3_config():
    if not AWS_S3_BUCKET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS_S3_BUCKET is not configured")
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AWS credentials are not configured")


def build_s3_public_url(object_key: str):
    if AWS_S3_PUBLIC_BASE_URL:
        return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{object_key}"
    return f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{object_key}"


def build_s3_uri(object_key: str):
    return f"s3://{AWS_S3_BUCKET}/{object_key}"


def create_s3_client():
    return boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4"))


def get_display_image_url(er_schema: ERSchema):
    if not er_schema.image_s3_key:
        return er_schema.image_url
    return create_presigned_image_url(er_schema.image_s3_key)


def create_presigned_image_url(object_key: str):
    require_s3_config()
    try:
        return create_s3_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": AWS_S3_BUCKET, "Key": object_key},
            ExpiresIn=AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "ClientError")
        message = error.get("Message", "Failed to create image URL")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create S3 image URL: {code} - {message}",
        )
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create S3 image URL: {type(exc).__name__}",
        )


async def read_uploaded_image(image: UploadFile):
    content_type = image.content_type or ""
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image must be JPG, PNG, WebP, or GIF. HEIC is not supported by most browsers.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file is required")
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be 5MB or smaller")

    return image_bytes, content_type


def upload_image_to_s3(image_bytes: bytes, content_type: str):
    require_s3_config()
    extension = guess_extension(content_type) or ".bin"
    object_key = f"schemas/{uuid4().hex}{extension}"
    s3_client = create_s3_client()

    try:
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "ClientError")
        message = error.get("Message", "Failed to upload image to S3")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload image to S3: {code} - {message}",
        )
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload image to S3: {type(exc).__name__}",
        )

    return object_key, build_s3_uri(object_key)
