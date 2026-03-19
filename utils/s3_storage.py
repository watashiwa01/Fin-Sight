from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import (
    S3_ADDRESSING_STYLE,
    S3_BUCKET,
    S3_ENDPOINT_URL,
    S3_PREFIX,
    S3_REGION,
    S3_UPLOAD_MAX_MB,
    has_s3_storage,
)


def _safe_filename(filename: str) -> str:
    name = os.path.basename(filename or "upload.bin")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    if not name:
        name = "upload.bin"
    return name[:120]


def build_object_key(filename: str) -> str:
    safe_name = _safe_filename(filename)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex

    prefix = (S3_PREFIX or "").strip().strip("/")
    key = f"{ts}-{uid}-{safe_name}"
    return f"{prefix}/{key}" if prefix else key


def validate_object_key(key: str) -> str:
    if not key:
        raise ValueError("Missing object key")

    normalized = key.replace("\\", "/").lstrip("/")
    if normalized != key:
        raise ValueError("Invalid object key")

    if ".." in normalized.split("/"):
        raise ValueError("Invalid object key")

    prefix = (S3_PREFIX or "").strip().strip("/")
    if prefix and not normalized.startswith(prefix + "/"):
        raise ValueError("Invalid object key prefix")

    return normalized


def _get_s3_client():
    if not has_s3_storage():
        raise RuntimeError("S3 storage is not configured")

    import boto3
    from botocore.config import Config

    addressing_style = None
    if S3_ADDRESSING_STYLE in {"virtual", "path"}:
        addressing_style = S3_ADDRESSING_STYLE

    config_kwargs = {"signature_version": "s3v4"}
    if addressing_style:
        config_kwargs["s3"] = {"addressing_style": addressing_style}

    return boto3.client(
        "s3",
        region_name=S3_REGION or None,
        endpoint_url=S3_ENDPOINT_URL or None,
        config=Config(**config_kwargs),
    )


@dataclass(frozen=True)
class PresignedPost:
    key: str
    url: str
    fields: dict
    expires_in: int
    max_bytes: int


def create_presigned_post(
    filename: str,
    content_type: str | None = None,
    expires_in: int = 10 * 60,
) -> PresignedPost:
    """
    Create a presigned POST so the browser can upload directly to S3/R2.

    Notes:
    - Enforces a size cap via `content-length-range` to reduce abuse.
    - Requires bucket CORS to allow browser uploads from your deployed origin.
    """
    s3 = _get_s3_client()
    key = build_object_key(filename)

    content_type = (content_type or "application/octet-stream").strip() or "application/octet-stream"
    max_bytes = int(max(1.0, S3_UPLOAD_MAX_MB) * 1024 * 1024)

    presigned = s3.generate_presigned_post(
        Bucket=S3_BUCKET,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=expires_in,
    )

    return PresignedPost(
        key=key,
        url=presigned["url"],
        fields=presigned["fields"],
        expires_in=expires_in,
        max_bytes=max_bytes,
    )


def download_object_to_path(key: str, dest_path: str | Path) -> Path:
    """Download an object from S3 into a local file path."""
    s3 = _get_s3_client()
    safe_key = validate_object_key(key)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    obj = s3.get_object(Bucket=S3_BUCKET, Key=safe_key)
    body = obj["Body"]
    with dest.open("wb") as f:
        for chunk in body.iter_chunks(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    return dest


def delete_object(key: str) -> None:
    """Delete an object from S3."""
    s3 = _get_s3_client()
    safe_key = validate_object_key(key)
    s3.delete_object(Bucket=S3_BUCKET, Key=safe_key)
