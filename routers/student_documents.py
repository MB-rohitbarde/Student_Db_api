from typing import List
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Student
import crud
import schemas
from s3_utils import upload_file_to_s3, get_presigned_download_url
from settings import aws_settings
from exceptions import (
    APIException, ValidationError, NotFoundError, ConflictError, 
    FileTooLargeError, S3Error, DatabaseError
)


router = APIRouter(prefix="/students", tags=["Student Documents"])


@router.post(
	"/{student_id}/documents",
	response_model=schemas.StudentDocumentResponse,
	status_code=status.HTTP_201_CREATED,
	summary="Upload student document",
	description="Upload a document for a student. Note: maximum file size is 5 MB per upload.",
)
def upload_student_document(
	student_id: int,
	file: UploadFile = File(..., description="Select file (max 5 MB)"),
	document_name: str = Form(...),
	document_type: str = Form(...),
	db: Session = Depends(get_db),
):
	try:
		logger = logging.getLogger("student_documents")
		logger.info(f"Upload request: student_id={student_id}, name={document_name}, type={document_type}")
		# Validate inputs
		if student_id <= 0:
			raise ValidationError("Student ID must be a positive integer", "student_id")
		
		if not document_name or not document_name.strip():
			raise ValidationError("Document name is required", "document_name")
		
		if not document_type or not document_type.strip():
			raise ValidationError("Document type is required", "document_type")
		
		# Validate file
		if not file.filename:
			raise ValidationError("File is required", "file")
		
		# Check S3 configuration
		if not aws_settings.s3_bucket:
			raise S3Error("S3 bucket not configured (AWS_S3_BUCKET)", "upload")

		# Check if student exists
		student = db.get(Student, student_id)
		if not student:
			raise NotFoundError("Student", student_id)

		# Read and validate file size (max 5 MB)
		content = file.file.read()
		max_bytes = 5 * 1024 * 1024
		if content is not None and len(content) > max_bytes:
			raise FileTooLargeError(max_bytes, len(content))

		# Upload to S3 under a namespaced key
		key = f"students/{student_id}/{document_name.strip()}"
		try:
			url = upload_file_to_s3(content, aws_settings.s3_bucket, key, content_type=file.content_type)
		except Exception as e:
			logger.exception("S3 upload failed")
			raise S3Error(f"Failed to upload file to S3: {str(e)}", "upload")

		# Persist metadata
		try:
			created = crud.create_student_document(
				db,
				schemas.StudentDocumentCreate(
					student_id=student_id,
					document_name=document_name.strip(),
					document_type=document_type.strip(),
					s3_url=url,
				),
			)
			return created
		except Exception as e:
			logger.exception("DB save failed for student document")
			db.rollback()
			raise DatabaseError(f"Failed to save document metadata: {str(e)}", "create_document")
	
	except (ValidationError, NotFoundError, FileTooLargeError, S3Error, DatabaseError):
		raise
	except Exception as e:
		logging.getLogger("student_documents").exception("Unhandled upload error")
		raise APIException(f"Document upload failed: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/{student_id}/documents", response_model=List[schemas.StudentDocumentResponse])
def list_student_documents(student_id: int, db: Session = Depends(get_db)):
	try:
		logger = logging.getLogger("student_documents")
		logger.info(f"List documents request: student_id={student_id}")
		# Validate input
		if student_id <= 0:
			raise ValidationError("Student ID must be a positive integer", "student_id")
		
		# Check if student exists
		student = db.get(Student, student_id)
		if not student:
			raise NotFoundError("Student", student_id)
		
		# Get documents
		try:
			docs = crud.get_student_documents_by_student(db, student_id)
		except Exception as e:
			raise DatabaseError(f"Failed to retrieve documents: {str(e)}", "list_documents")
		
		# Attach presigned download URLs
		results: List[schemas.StudentDocumentResponse] = []
		for d in docs:
			download = None
			if aws_settings.s3_bucket:
				try:
					# Recover the object key from stored URL robustly
					from s3_utils import extract_key_from_url
					key = extract_key_from_url(d.s3_url, aws_settings.s3_bucket)
					download = get_presigned_download_url(
						aws_settings.s3_bucket,
						key,
						filename=d.document_name,
						content_type=None,  # could be derived if stored; left None to use S3 object's content-type
					)
				except Exception as e:
					# Log the error but don't fail the entire request
					logger.warning(f"Failed to generate download URL for document {d.id}: {str(e)}")
			
			results.append(
				schemas.StudentDocumentResponse(
					id=d.id,
					student_id=d.student_id,
					document_name=d.document_name,
					document_type=d.document_type,
					s3_url=d.s3_url,
					uploaded_at=d.uploaded_at,
					download_url=download,
				)
			)
		return results
	
	except (ValidationError, NotFoundError, DatabaseError):
		raise
	except Exception as e:
		logging.getLogger("student_documents").exception("Unhandled list documents error")
		raise APIException(f"Failed to list documents: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


## Removed: get student document URL (redirect) endpoint


## Removed: download-proxy endpoint


## Removed: download document by id endpoint


@router.get(
	"/{student_id}/download-document",
	responses={
		200: {
			"content": {
				"application/pdf": {"schema": {"type": "string", "format": "binary"}},
				"application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
			},
			"description": "Download the latest document for a student by student_id",
		}
	},
)
def download_latest_document_for_student(student_id: int, db: Session = Depends(get_db)):
	"""Download the most recently uploaded document for a given student."""
	try:
		logger = logging.getLogger("student_documents")
		logger.info(f"Download latest request: student_id={student_id}")
		# Validate input
		if student_id <= 0:
			raise ValidationError("Student ID must be a positive integer", "student_id")
		
		# Check if student exists
		student = db.get(Student, student_id)
		if not student:
			raise NotFoundError("Student", student_id)
		
		# Check S3 configuration
		if not aws_settings.s3_bucket:
			raise S3Error("S3 bucket not configured", "download")
		
		# Get latest document by uploaded_at (desc)
		try:
			docs = crud.get_student_documents_by_student(db, student_id)
		except Exception as e:
			raise DatabaseError(f"Failed to retrieve documents: {str(e)}", "get_documents")
		
		if not docs:
			raise NotFoundError("Document", f"student_id={student_id}")
		
		doc = docs[0]
		
		# Extract key and stream from S3
		from s3_utils import extract_key_from_url, get_object_stream_and_content_type
		try:
			key = extract_key_from_url(doc.s3_url, aws_settings.s3_bucket)
			stream, content_type = get_object_stream_and_content_type(aws_settings.s3_bucket, key)
		except Exception as exc:
			msg = str(exc)
			if "NoSuchKey" in msg or "Not Found" in msg:
				raise NotFoundError("File", key)
			logger.exception("S3 get_object failed")
			raise S3Error(f"Failed to fetch object from S3: {str(exc)}", "download")
		
		headers = {"Content-Disposition": f"attachment; filename=\"{doc.document_name}\""}
		return StreamingResponse(stream, media_type=content_type or "application/octet-stream", headers=headers)
	
	except (ValidationError, NotFoundError, S3Error, DatabaseError):
		raise
	except Exception as e:
		logging.getLogger("student_documents").exception("Unhandled download error")
		raise APIException(f"Document download failed: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
