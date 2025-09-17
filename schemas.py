"""Pydantic schemas for request/response validation.

Defines input (Create/Update) and output schemas for Schools, Teachers,
and Students, plus authentication and user-related models. Output models
enable ORM serialization via `from_attributes` for SQLAlchemy objects.
"""

from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime


# Shared base schemas
class SchoolBase(BaseModel):
    """Shared fields used by School create/update operations."""
    name: str
    address: Optional[str] = None


class SchoolCreate(SchoolBase):
    """Payload to create a new School."""
    pass


class SchoolUpdate(BaseModel):
    """Payload to partially update School fields."""
    name: Optional[str] = None
    address: Optional[str] = None


class TeacherBase(BaseModel):
    """Shared fields used by Teacher create/update operations."""
    name: str
    subject: Optional[str] = None
    school_id: int
    salary: Optional[float] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    years_experience: Optional[int] = None
    qualification: Optional[str] = None


class TeacherCreate(TeacherBase):
    """Payload to create a new Teacher tied to a School."""
    pass


class TeacherUpdate(BaseModel):
    """Payload to partially update Teacher fields."""
    name: Optional[str] = None
    subject: Optional[str] = None
    school_id: Optional[int] = None
    salary: Optional[float] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    years_experience: Optional[int] = None
    qualification: Optional[str] = None


class StudentBase(BaseModel):
    """Shared fields used by Student create/update operations."""
    name: str
    grade: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    enrollment_date: Optional[date] = None
    address: Optional[str] = None


class StudentCreate(StudentBase):
    """Payload to create a new Student."""
    pass


class StudentUpdate(BaseModel):
    """Payload to partially update Student fields."""
    name: Optional[str] = None
    grade: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    enrollment_date: Optional[date] = None
    address: Optional[str] = None


# Response schemas with relations
class TeacherOut(BaseModel):
    """Response model for Teacher records (without relations)."""
    id: int
    name: str
    subject: Optional[str] = None
    school_id: int
    salary: Optional[float] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    years_experience: Optional[int] = None
    qualification: Optional[str] = None

    class Config:
        from_attributes = True


class StudentOut(BaseModel):
    """Response model for Student records (without relations)."""
    id: int
    name: str
    grade: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    enrollment_date: Optional[date] = None
    address: Optional[str] = None

    class Config:
        from_attributes = True


class SchoolOut(BaseModel):
    """Response model for School records (without relations)."""
    id: int
    name: str
    address: Optional[str] = None

    class Config:
        from_attributes = True


class StudentWithTeachers(StudentOut):
    """Student response including related Teacher summaries."""
    teachers: List[TeacherOut] = []


class TeacherWithStudents(TeacherOut):
    """Teacher response including related Student summaries."""
    students: List[StudentOut] = []


class SchoolWithTeachers(SchoolOut):
    """School response including related Teacher summaries."""
    teachers: List[TeacherOut] = []


# Auth schemas
class TokenResponse(BaseModel):
    """Response payload returned when authentication succeeds."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    is_admin: Optional[bool] = None


class RefreshRequest(BaseModel):
    """Request payload to refresh tokens using a refresh token."""
    refresh_token: str


# Users
class UserCreate(BaseModel):
    """Payload to register a new application user."""
    username: str
    password: str
    is_admin: Optional[bool] = False


class UserOut(BaseModel):
    """Response model for user details after registration or lookup."""
    id: int
    username: str

    class Config:
        from_attributes = True


# StudentDocument schemas
class StudentDocumentBase(BaseModel):
    """Shared fields for StudentDocument create operations."""
    document_name: str
    document_type: str
    s3_url: str


class StudentDocumentCreate(StudentDocumentBase):
    """Payload to create a new StudentDocument linked to a Student."""
    student_id: int


class StudentDocumentResponse(BaseModel):
    """Response model for StudentDocument records."""
    id: int
    student_id: int
    document_name: str
    document_type: str
    s3_url: str
    uploaded_at: datetime | None = None
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


