import os
from dataclasses import dataclass
from pathlib import Path

try:
	from dotenv import load_dotenv  # type: ignore
	# Load from project root .env if present
	load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except Exception:
	# dotenv is optional at runtime
	pass


@dataclass
class AWSSettings:
	aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
	aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
	aws_region_name: str | None = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
	s3_endpoint_url: str | None = os.getenv("AWS_S3_ENDPOINT_URL")  # for MinIO/custom endpoints
	s3_bucket: str | None = os.getenv("AWS_S3_BUCKET")


aws_settings = AWSSettings()
