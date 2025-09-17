"""FastAPI application exposing a simple school management API.

This module defines authentication (JWT access/refresh), user registration,
and CRUD endpoints for `School`, `Teacher`, and `Student` models, including
relationship queries. Security helpers and dependencies are provided to
protect routes requiring authenticated or admin users.
"""

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from enum import Enum
import os
import secrets
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

from database import engine, get_db
from models import Base, Student, Teacher, School, User
from passlib.context import CryptContext
from routers.student_documents import router as docs_router
from logging_config import init_logging
import schemas as schemas
from exceptions import (
    create_exception_handlers, APIException, ValidationError, NotFoundError, 
    ConflictError, UnauthorizedError, ForbiddenError, DatabaseError
)


# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME_SUPER_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


class GradeEnum(str, Enum):
    """Enum for valid student grades."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"

# Dropdown choice lists for Teacher search filters
QUALIFICATION_CHOICES = [
    "Diploma",
    "B.Ed",
    "M.Ed",
    "B.Sc",
    "M.Sc",
    "M.A",
    "PhD",
]

SUBJECT_CHOICES = [
    "Math",
    "Science",
    "English",
    "History",
    "Geography",
    "Computer",
    "Physics",
    "Chemistry",
    "Biology",
    "Economics",
]

YEARS_EXPERIENCE_CHOICES = [0, 1, 2, 3, 5, 7, 10, 12, 15, 20, 25, 30]

# Security dependencies and password hashing context
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short‑lived JWT access token for API authentication.

    Encodes the provided `data` payload with an expiration suitable for
    bearer authorization on protected endpoints.
    """
    to_encode = data.copy()  # avoid mutating caller-provided data
    expire = datetime.now(tz=timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})  # standard expiration claim
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a longer‑lived JWT refresh token for issuing new access tokens.

    Marks the token with type "refresh" and uses a longer expiration to allow
    clients to obtain new access tokens without re‑authenticating.
    """
    to_encode = data.copy()  # avoid mutating caller-provided data
    expire = datetime.now(tz=timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})  # mark JWT as refresh token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored password hash."""
    return pwd_context.verify(plain_password, password_hash)  # bcrypt verification


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for secure storage in the database."""
    return pwd_context.hash(plain_password)


def authenticate_user_db(db: Session, username: str, password: str) -> bool:  
    """Check user credentials against the database.

    Returns True when the user exists and the supplied password is valid.
    """
    user = db.query(User).filter(User.username == username).first()  # locate user by username
    if not user:
        return False
    return verify_password(password, user.password_hash)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decode the bearer token and return a minimal user context.

    Raises 401 if the token is invalid or missing required claims.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # verify signature and exp
        username: str | None = payload.get("sub")  # subject identifies the user
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return {"username": username, "is_admin": payload.get("is_admin", False)}  # minimal principal


async def get_current_admin_user(current=Depends(get_current_user)):
    """Ensure the current user has admin privileges.

    Raises 403 when the authenticated user is not an admin.
    """
    if not current.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current


# Create FastAPI app instance
app = FastAPI(title="School-Teacher-Student API")

# Initialize logging early
init_logging()

# Register exception handlers
create_exception_handlers(app)


# Request/response logging middleware
import logging

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("request")
    logger.info(f"Incoming {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            logger.error(f"Completed {request.method} {request.url.path} -> {response.status_code}")
        else:
            logger.info(f"Completed {request.method} {request.url.path} -> {response.status_code}")
        return response
    except Exception as exc:
        logger.exception(f"Error during {request.method} {request.url.path}: {exc}")
        raise


# Public token endpoint (login)
@app.post("/auth/login", response_model=schemas.TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate credentials and issue access and refresh tokens."""
    try:
        if not form_data.username or not form_data.password:
            raise ValidationError("Username and password are required")
        
        if not authenticate_user_db(db, form_data.username, form_data.password):
            raise UnauthorizedError("Incorrect username or password")
        
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user:
            raise UnauthorizedError("User not found")
        
        access_token = create_access_token({"sub": form_data.username, "type": "access", "is_admin": bool(user.is_admin)})
        refresh_token = create_refresh_token({"sub": form_data.username, "is_admin": bool(user.is_admin)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "is_admin": bool(user.is_admin),
        }
    except (ValidationError, UnauthorizedError):
        raise
    except Exception as e:
        raise APIException(f"Login failed: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.post("/auth/refresh", response_model=schemas.TokenResponse)
async def refresh_access_token(payload: schemas.RefreshRequest):
    """Validate a refresh token and return a new access/refresh token pair."""
    try:
        if not payload.refresh_token:
            raise ValidationError("Refresh token is required")
        
        data = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("type") != "refresh":
            raise ValidationError("Invalid token type")
        username = data.get("sub")
        if not username:
            raise ValidationError("Invalid token payload")
        
        is_admin = bool(data.get("is_admin", False))
        access_token = create_access_token({"sub": username, "type": "access", "is_admin": is_admin})
        # Optional rotation: issue a new refresh token each time
        refresh_token = create_refresh_token({"sub": username, "is_admin": is_admin})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "is_admin": is_admin,
        }
    except JWTError:
        raise UnauthorizedError("Invalid or expired refresh token")
    except (ValidationError, UnauthorizedError):
        raise
    except Exception as e:
        raise APIException(f"Token refresh failed: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


# Protected router: all routes below require a valid bearer token
router = APIRouter(dependencies=[Depends(get_current_user)])


# Create tables (no-op if already created)
Base.metadata.create_all(bind=engine)


# CRUD for Schools
@router.post("/schools", response_model=schemas.SchoolOut, status_code=status.HTTP_201_CREATED)
def create_school(payload: schemas.SchoolCreate, db: Session = Depends(get_db)):
    """Create a new `School` ensuring name uniqueness."""
    try:
        if not payload.name or not payload.name.strip():
            raise ValidationError("School name is required", "name")
        
        existing = db.query(School).filter(School.name == payload.name).first()
        if existing:
            raise ConflictError("School with this name already exists", "school")
        
        school = School(name=payload.name.strip(), address=payload.address)
        db.add(school)
        db.commit()
        db.refresh(school)
        return school
    except (ValidationError, ConflictError):
        raise
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to create school: {str(e)}", "create_school")


@router.get("/schools", response_model=List[schemas.SchoolOut])
def list_schools(db: Session = Depends(get_db)):
    """Return all schools."""
    try:
        schools = db.query(School).all()
        return schools
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve schools: {str(e)}", "list_schools")


@router.get("/schools/{school_id}", response_model=schemas.SchoolOut)
def get_school(school_id: int, db: Session = Depends(get_db)):
    """Fetch a single `School` by id or 404 if missing."""
    try:
        if school_id <= 0:
            raise ValidationError("School ID must be a positive integer", "school_id")
        
        school = db.get(School, school_id)
        if not school:
            raise NotFoundError("School", school_id)
        return school
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve school: {str(e)}", "get_school")


@router.patch("/schools/{school_id}", response_model=schemas.SchoolOut)
def update_school(school_id: int, payload: schemas.SchoolUpdate, db: Session = Depends(get_db)):
    """Partially update a `School`'s fields by id."""
    try:
        if school_id <= 0:
            raise ValidationError("School ID must be a positive integer", "school_id")
        
        school = db.get(School, school_id)
        if not school:
            raise NotFoundError("School", school_id)
        
        # Check for name conflicts if name is being updated
        if payload.name is not None and payload.name != school.name:
            if not payload.name.strip():
                raise ValidationError("School name cannot be empty", "name")
            existing = db.query(School).filter(School.name == payload.name).first()
            if existing:
                raise ConflictError("School with this name already exists", "school")
        
        if payload.name is not None:
            school.name = payload.name.strip()
        if payload.address is not None:
            school.address = payload.address
        
        db.commit()
        db.refresh(school)
        return school
    except (ValidationError, NotFoundError, ConflictError):
        raise
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to update school: {str(e)}", "update_school")


@router.delete("/schools/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_school(school_id: int, db: Session = Depends(get_db)):
    """Delete a `School` by id."""
    try:
        if school_id <= 0:
            raise ValidationError("School ID must be a positive integer", "school_id")
        
        school = db.get(School, school_id)
        if not school:
            raise NotFoundError("School", school_id)
        
        db.delete(school)
        db.commit()
        return None
    except (ValidationError, NotFoundError):
        raise
    except Exception as e:
        db.rollback()
        raise DatabaseError(f"Failed to delete school: {str(e)}", "delete_school")


# CRUD for Teachers
@router.post("/teachers", response_model=schemas.TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: schemas.TeacherCreate, db: Session = Depends(get_db)):
    """Create a new `Teacher` linked to an existing `School`."""
    school = db.get(School, payload.school_id)  # ensure school exists
    if not school:
        raise HTTPException(status_code=400, detail="Associated school not found")
    teacher = Teacher(
        name=payload.name,
        subject=payload.subject,
        school_id=payload.school_id,
        salary=payload.salary,
        email=payload.email,
        phone=payload.phone,
        hire_date=payload.hire_date,
        years_experience=payload.years_experience,
        qualification=payload.qualification,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.get("/teachers", response_model=List[schemas.TeacherOut])
def list_teachers(page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    """Return teachers with simple pagination (default 20 per page).

    Query params:
    - page: 1-based page number
    - per_page: items per page (defaults to 20)
    """
    # Normalize invalid inputs
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    # Calculate offset and apply to query
    offset = (page - 1) * per_page
    teachers = db.query(Teacher).offset(offset).limit(per_page).all()
    return teachers


@router.get("/teachers/search", response_model=List[schemas.TeacherOut])
def search_teachers(
    qualification: str | None = Query(None, description="Filter by qualification", enum=QUALIFICATION_CHOICES),
    years_experience: int | None = Query(None, description="Filter by years of experience", enum=YEARS_EXPERIENCE_CHOICES),
    subject: str | None = Query(None, description="Filter by subject", enum=SUBJECT_CHOICES),
    page: int = Query(1, description="1-based page number"),
    per_page: int = Query(20, description="Items per page (default 20)"),
    db: Session = Depends(get_db),
):
    """Search teachers using optional dropdown filters.

    Filters:
    - qualification: exact match from predefined list.
    - years_experience: exact match from predefined set of values.
    - subject: exact match from predefined list.
    - page/per_page: pagination controls (defaults 1 and 20).
    """
    query = db.query(Teacher)

    if qualification is not None:
        query = query.filter(Teacher.qualification == qualification)
    if years_experience is not None:
        query = query.filter(Teacher.years_experience == years_experience)
    if subject is not None:
        query = query.filter(Teacher.subject == subject)

    # Normalize pagination
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page).all()


@router.get("/teachers/{teacher_id}", response_model=schemas.TeacherOut)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """Fetch a single `Teacher` by id or 404 if missing."""
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher


# Admin-only endpoint to read salaries
@router.get("/admin/teachers/{teacher_id}/salary")
def get_teacher_salary(teacher_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin_user)):
    """Admin-only endpoint to return a teacher's salary."""
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return {"teacher_id": teacher.id, "salary": teacher.salary}


@router.patch("/teachers/{teacher_id}", response_model=schemas.TeacherOut)
def update_teacher(teacher_id: int, payload: schemas.TeacherUpdate, db: Session = Depends(get_db)):
    """Partially update a `Teacher` including school reassignment validation."""
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    if payload.name is not None:
        teacher.name = payload.name
    if payload.subject is not None:
        teacher.subject = payload.subject
    if payload.school_id is not None:
        school = db.get(School, payload.school_id)  # validate reassigned school
        if not school:
            raise HTTPException(status_code=400, detail="Associated school not found")
        teacher.school_id = payload.school_id
    db.commit()
    db.refresh(teacher)
    return teacher


@router.delete("/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """Delete a `Teacher` by id."""
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    db.delete(teacher)
    db.commit()
    return None


# CRUD for Students
@router.post("/students", response_model=schemas.StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: schemas.StudentCreate, db: Session = Depends(get_db)):
    """Create a new `Student`."""
    student = Student(name=payload.name, grade=payload.grade)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/students", response_model=List[schemas.StudentOut])
def list_students(page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    """Return students with simple pagination (default 20 per page).

    Query params:
    - page: 1-based page number
    - per_page: items per page (defaults to 20)
    """
    # Guard against invalid inputs
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    # Calculate offset for the requested page
    offset = (page - 1) * per_page

    # Apply offset/limit to the query for pagination
    students = db.query(Student).offset(offset).limit(per_page).all()
    return students


@router.get("/students/search", response_model=List[schemas.StudentOut])
def search_students(
    grade: str | None = Query(None, description="Select grade from dropdown", enum=["A", "B", "C", "D"]),
    name: str | None = Query(None, description="Enter name for partial matching"),
    teacher_id: int | None = Query(None, description="Filter students taught by this teacher id"),
    page: int = Query(1, description="1-based page number"),
    per_page: int = Query(20, description="Items per page (default 20)"),
    db: Session = Depends(get_db),
):
    """Search students by optional filters.

    Filters:
    - grade: exact match filter; select from dropdown (A, B, C, D).
    - name: partial match (case-insensitive, substring search).
    - teacher_id: filter students associated with the given teacher.
    - page: pagination page number (1-based)
    - per_page: items per page (defaults to 20)

    Returns a list of students matching all provided filters.
    """
    query = db.query(Student)

    # Apply grade filter if provided (validate against allowed values)
    if grade is not None:
        allowed_grades = ["A", "B", "C", "D"]
        if grade not in allowed_grades:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid grade. Use one of A, B, C, D.")
        query = query.filter(Student.grade == grade)

    # Apply case-insensitive name substring filter if provided
    if name is not None and name.strip() != "":
        query = query.filter(Student.name.ilike(f"%{name}%"))

    # Filter by teacher relationship if provided
    if teacher_id is not None:
        query = query.join(Student.teachers).filter(Teacher.id == teacher_id).distinct()

    # Normalize pagination params
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    # Apply pagination
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page).all()


@router.get("/students/{student_id}", response_model=schemas.StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Fetch a single `Student` by id or 404 if missing."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.patch("/students/{student_id}", response_model=schemas.StudentOut)
def update_student(student_id: int, payload: schemas.StudentUpdate, db: Session = Depends(get_db)):
    """Partially update a `Student`'s fields by id."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if payload.name is not None:
        student.name = payload.name
    if payload.grade is not None:
        student.grade = payload.grade
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Delete a `Student` by id."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    db.commit()
    return None


# Relationship endpoints
@router.post("/students/{student_id}/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_teacher_to_student(student_id: int, teacher_id: int, db: Session = Depends(get_db)):
    """Associate a `Teacher` with a `Student` if not already related."""
    student = db.get(Student, student_id)  # ensure student exists
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    teacher = db.get(Teacher, teacher_id)  # ensure teacher exists
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    if teacher not in student.teachers:
        student.teachers.append(teacher)  # create association
        db.commit()
    return None


@router.get("/students/{student_id}/teachers", response_model=List[schemas.TeacherOut])
def get_teachers_for_student(student_id: int, db: Session = Depends(get_db)):
    """List all teachers assigned to a specific student."""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student.teachers


@router.get("/teachers/{teacher_id}/students", response_model=List[schemas.StudentOut])
def get_students_for_teacher(teacher_id: int, db: Session = Depends(get_db)):
    """List all students taught by a specific teacher."""
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher.students


@router.get("/schools/{school_id}/teachers", response_model=List[schemas.TeacherOut])
def get_teachers_for_school(school_id: int, db: Session = Depends(get_db)):
    """List all teachers employed by a specific school."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school.teachers
app.include_router(router)
app.include_router(docs_router)


# Public user registration
@app.post("/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user with hashed password and optional admin flag."""
    existing = db.query(User).filter(User.username == payload.username).first()  # enforce unique username
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    # Set created_at explicitly to satisfy NOT NULL on older SQLite schemas
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        created_at=datetime.now(tz=timezone.utc),  # server-side timestamp
        is_admin=bool(payload.is_admin or False),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

