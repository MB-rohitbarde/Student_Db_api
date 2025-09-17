from sqlalchemy import Column, Integer, String, ForeignKey, Table, UniqueConstraint, DateTime, Boolean, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


# Association table for the many-to-many relationship between Student and Teacher
student_teacher_association = Table(
    "student_teacher",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", Integer, ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("student_id", "teacher_id", name="uq_student_teacher"),
)


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    address = Column(String(255), nullable=True)

    # One-to-many: School -> Teachers
    teachers = relationship("Teacher", back_populates="school", cascade="all, delete", passive_deletes=True)


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    salary = Column(Float, nullable=True)
    # Additional useful fields
    email = Column(String(255), nullable=True, unique=True, index=True)  # contact email
    phone = Column(String(50), nullable=True)  # contact phone number
    hire_date = Column(Date, nullable=True)  # date the teacher was hired
    years_experience = Column(Integer, nullable=True)  # total years of experience
    qualification = Column(String(255), nullable=True)  # highest degree/certification

    # Many-to-one to School
    school = relationship("School", back_populates="teachers")

    # Many-to-many with Students
    students = relationship(
        "Student",
        secondary=student_teacher_association,
        back_populates="teachers",
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    grade = Column(String(50), nullable=True)
    # Additional useful fields
    email = Column(String(255), nullable=True, unique=True, index=True)  # contact email
    phone = Column(String(50), nullable=True)  # contact phone number
    date_of_birth = Column(Date, nullable=True)  # birth date
    enrollment_date = Column(Date, nullable=True)  # date the student enrolled
    address = Column(String(255), nullable=True)  # home address

    # Many-to-many with Teachers
    teachers = relationship(
        "Teacher",
        secondary=student_teacher_association,
        back_populates="students",
    )

    # One-to-many: Student -> StudentDocument
    documents = relationship(
        "StudentDocument",
        back_populates="student",
        cascade="all, delete",
        passive_deletes=True,
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_admin = Column(Boolean, nullable=False, server_default="0")



class StudentDocument(Base):
    __tablename__ = "student_documents"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    document_name = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False)
    s3_url = Column(String(1024), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationship back to Student
    student = relationship("Student", back_populates="documents")

