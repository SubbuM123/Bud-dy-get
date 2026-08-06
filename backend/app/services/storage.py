"""S3/MinIO file storage for receipt images and PDFs.

All uploaded files go to the single `s3_bucket` configured in config.py
(defaults to "receipts"), organized by user and upload month so the MinIO
console (http://localhost:9001 in local dev) stays browsable as the number of
receipts grows: `{user_id}/{YYYY-MM}/{uuid}_{original_filename}`. This module
is the only place in the backend that talks to boto3 directly - both
api/v1/receipts.py (upload) and workers/receipt_processing.py (download for
OCR) go through these functions rather than constructing their own S3
client, so the bucket name, credentials, and key-naming scheme stay in one
place.
"""

from datetime import datetime
from uuid import uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings


# Build a boto3 S3 client pointed at MinIO (or real S3, in a future non-local environment)
# using the endpoint/credentials from the centralized Settings object. Not cached at
# module level (unlike get_settings) since boto3 clients are cheap to construct and this
# keeps the function trivially mockable in tests.
def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


# Create the configured bucket if it doesn't already exist. MinIO (unlike real S3 in a
# provisioned AWS account) has no bucket until something creates one, so this is called
# before every upload rather than assumed to have been done out-of-band during deploy.
def ensure_bucket_exists() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


# Build the storage key for a newly uploaded receipt file. A random prefix (rather than
# just the original filename) avoids collisions between two users' (or one user's two)
# same-named uploads landing in the same user/month "folder".
def build_receipt_key(user_id: str, original_filename: str) -> str:
    month_prefix = datetime.utcnow().strftime("%Y-%m")
    safe_name = original_filename.replace("/", "_")
    return f"{user_id}/{month_prefix}/{uuid4()}_{safe_name}"


# Upload a file's bytes to the configured bucket under `key` and return that key (not a
# public URL - MinIO/S3 objects here are private; use generate_presigned_url for viewing).
def upload_file_to_s3(file_bytes: bytes, key: str, content_type: str) -> str:
    ensure_bucket_exists()
    settings = get_settings()
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


# Download a previously uploaded file's raw bytes - used by the Celery task to fetch a
# receipt for OCR/text extraction without ever writing it to local disk on the worker.
def download_file_from_s3(key: str) -> bytes:
    settings = get_settings()
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()


# Generate a temporary, signed URL so the frontend can display/download a receipt image
# directly from MinIO without the object ever needing to be public.
def generate_presigned_url(key: str, expiration_seconds: int = 3600) -> str:
    settings = get_settings()
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expiration_seconds,
    )


# Delete a previously uploaded file - called when a Receipt row is deleted so orphaned
# objects don't accumulate in the bucket.
def delete_file_from_s3(key: str) -> None:
    settings = get_settings()
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)
