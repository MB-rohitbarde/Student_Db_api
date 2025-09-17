from __future__ import annotations

from typing import BinaryIO, Optional

import boto3  # type: ignore
from botocore.client import Config  # type: ignore

from settings import aws_settings
import re
from urllib.parse import urlparse


def _s3_client():
	"""Create and return a configured boto3 S3 client."""
	# Use virtual addressing for AWS; path-style for custom endpoints (e.g., MinIO)
	use_path_style = bool(aws_settings.s3_endpoint_url)
	config = Config(s3={"addressing_style": "path" if use_path_style else "virtual"})

	# Sanitize region: default if placeholder/invalid
	region = aws_settings.aws_region_name or "us-east-1"
	if region.upper() == "YOUR_REGION" or not re.match(r"^[a-z]{2}-[a-z]+-\d$", region):
		region = "us-east-1"

	kwargs = {
		"region_name": region,
		"aws_access_key_id": aws_settings.aws_access_key_id,
		"aws_secret_access_key": aws_settings.aws_secret_access_key,
		"config": config,
	}
	if aws_settings.s3_endpoint_url:
		kwargs["endpoint_url"] = aws_settings.s3_endpoint_url
	return boto3.client("s3", **{k: v for k, v in kwargs.items() if v is not None})


def upload_file_to_s3(file: BinaryIO | bytes | str, bucket_name: str, key: str, content_type: Optional[str] = None) -> str:
	"""Upload a file-like/bytes/local-path to S3 at bucket/key and return the s3 object URL.

	If a custom endpoint is configured, returns that base URL. Otherwise, uses AWS standard format.
	"""
	s3 = _s3_client()
	extra_args = {"ContentType": content_type} if content_type else None
	if isinstance(file, (bytes, bytearray)):
		s3.put_object(Bucket=bucket_name, Key=key, Body=file, **({"ContentType": content_type} if content_type else {}))
	else:
		# boto3 supports file-like objects and local file paths via upload_fileobj/upload_file
		try:
			# Try treating as file-like
			s3.upload_fileobj(file, bucket_name, key, ExtraArgs=(extra_args or {}))  # type: ignore[arg-type]
		except Exception:
			# Fallback: assume it's a local file path
			s3.upload_file(str(file), bucket_name, key, ExtraArgs=(extra_args or {}))  # type: ignore[arg-type]

	return get_file_url(bucket_name, key)


def get_file_url(bucket_name: str, key: str) -> str:
	"""Return a public-style object URL (does not sign). Use presigned URLs if bucket is private."""
	if aws_settings.s3_endpoint_url:
		# Custom endpoint (e.g., MinIO): {endpoint}/{bucket}/{key}
		base = aws_settings.s3_endpoint_url.rstrip("/")
		return f"{base}/{bucket_name}/{key}"
	region = aws_settings.aws_region_name or "us-east-1"
	return f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"


def get_presigned_download_url(
	bucket_name: str,
	key: str,
	expires_in_seconds: int = 900,
	filename: Optional[str] = None,
	content_type: Optional[str] = None,
) -> str:
	"""Generate a time-limited presigned URL for downloading an object.

	Optionally sets Content-Disposition filename and Content-Type hints.
	"""
	s3 = _s3_client()
	params = {"Bucket": bucket_name, "Key": key}
	if filename:
		params["ResponseContentDisposition"] = f"inline; filename=\"{filename}\""
	if content_type:
		params["ResponseContentType"] = content_type
	return s3.generate_presigned_url(
		"get_object",
		Params=params,
		ExpiresIn=expires_in_seconds,
	)


def get_object_stream_and_content_type(bucket_name: str, key: str):
	"""Return a tuple (iterator, content_type) for the S3 object suitable for StreamingResponse."""
	s3 = _s3_client()
	obj = s3.get_object(Bucket=bucket_name, Key=key)
	body = obj["Body"]  # botocore.response.StreamingBody
	content_type = obj.get("ContentType") or "application/octet-stream"

	def _iter_chunks(chunk_size: int = 8192):
		while True:
			data = body.read(chunk_size)
			if not data:
				break
			yield data

	return _iter_chunks(), content_type


def extract_key_from_url(object_url: str, bucket_name: str | None) -> str:
	"""Extract the S3 object key from a given object URL.

	Handles both virtual-hosted-style (bucket.s3.region.amazonaws.com/key)
	and path-style/custom endpoints (endpoint/bucket/key).
	"""
	parsed = urlparse(object_url)
	path = parsed.path.lstrip("/")  # e.g., 'key' or 'bucket/key'
	if bucket_name and path.startswith(f"{bucket_name}/"):
		return path[len(bucket_name) + 1 :]
	return path
