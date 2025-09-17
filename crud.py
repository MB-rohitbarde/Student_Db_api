from typing import List

from sqlalchemy.orm import Session

import models
import schemas


def create_student_document(db: Session, document_data: schemas.StudentDocumentCreate) -> models.StudentDocument:
	"""Create and persist a new StudentDocument row.

	Raises if the referenced student does not exist due to FK constraint.
	"""
	doc = models.StudentDocument(
		student_id=document_data.student_id,
		document_name=document_data.document_name,
		document_type=document_data.document_type,
		s3_url=document_data.s3_url,
	)
	db.add(doc)
	db.commit()
	db.refresh(doc)
	return doc


def get_student_documents_by_student(db: Session, student_id: int) -> List[models.StudentDocument]:
	"""Return all documents associated with a given student id."""
	return (
		db.query(models.StudentDocument)
		.filter(models.StudentDocument.student_id == student_id)
		.order_by(models.StudentDocument.uploaded_at.desc())
		.all()
	)


def get_student_document_by_id(db: Session, document_id: int) -> models.StudentDocument | None:
	"""Return a single StudentDocument by its id, or None if missing."""
	return db.query(models.StudentDocument).filter(models.StudentDocument.id == document_id).first()


