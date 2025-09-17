"""
seed.py
---------
Utility script to populate the application's SQLite database with realistic demo data.

This script is intended for local development and testing. It creates a set of
schools, teachers (with subjects and salaries), and students, and then links
them through a many-to-many relationship (teachers assigned to students).

Run from the project root:
    python seed.py

Note: This will clear existing Schools/Teachers/Students to avoid duplicates.
"""

import random
import argparse
from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, School, Teacher, Student


FIRST_NAMES = [
    "Alex", "Jamie", "Taylor", "Jordan", "Casey", "Riley", "Avery", "Parker", "Quinn", "Morgan",
    "Drew", "Reese", "Skyler", "Rowan", "Cameron", "Hayden", "Elliot", "Emerson", "Finley", "Sage",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson",
    "Martinez", "Anderson", "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson", "White",
]

SUBJECTS = [
    "Math", "Science", "History", "English", "Art", "Music", "PE", "Biology", "Chemistry", "Physics",
    "Geography", "Economics", "Computer Science", "Literature", "Civics",
]

STREET_NAMES = [
    "Oak", "Maple", "Pine", "Cedar", "Elm", "Birch", "Willow", "Sycamore", "Chestnut", "Spruce",
]


def random_name() -> str:
    """Generate a simple realistic-looking full name for demo data."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_address() -> str:
    """Generate a plausible street address for demo school entries."""
    num = random.randint(100, 9999)
    return f"{num} {random.choice(STREET_NAMES)} St"


def seed(db: Session, num_schools: int = 20, num_teachers: int = 60, num_students: int = 80) -> None:
    """
    Populate the SQLite database with realistic demo data for Schools, Teachers, and Students.

    What it does:
    - Ensures all tables exist (so first run does not fail).
    - Clears existing rows (Schools, Teachers, Students) to avoid duplicates between runs.
    - Creates `num_schools` schools with random addresses.
    - Creates `num_teachers` teachers, each linked to a random school, with a subject and
      a realistic salary in the 35,000–120,000 range (so salary analytics have meaningful values).
    - Creates `num_students` students with random names and optional grades.
    - Assigns each student 1–5 random teachers (many-to-many) to simulate real schedules.

    Parameters:
    - db: SQLAlchemy Session connected to the same database as the app.
    - num_schools: Number of School rows to generate (default 20).
    - num_teachers: Number of Teacher rows to generate (default 60).
    - num_students: Number of Student rows to generate (default 80).

    Returns: None. Commits all inserts to the database.

    Note:
    - This function is destructive for these tables (it deletes existing rows first) to keep seeding idempotent.
    - Run from the project root with an active environment: `python seed.py`.
    """
    # Ensure tables exist so that first-time seeding can create the schema
    Base.metadata.create_all(bind=engine)

    # Clear existing data to avoid duplicates across multiple runs
    db.query(Teacher).delete()
    db.query(Student).delete()
    db.query(School).delete()
    db.commit()  # Commit deletes to release row locks and persist state

    # Create schools
    schools: List[School] = []
    for i in range(num_schools):
        school = School(name=f"School {i + 1}", address=random_address())
        db.add(school)
        schools.append(school)
    db.commit()  # Commit to assign primary keys (ids) for later FKs
    for s in schools:
        db.refresh(s)  # Refresh to ensure ids are present on Python objects

    # Create teachers
    teachers: List[Teacher] = []
    for i in range(num_teachers):
        school = random.choice(schools)
        # Salary in a realistic range (in local currency units)
        salary = float(random.randint(35000, 120000))
        teacher = Teacher(
            name=random_name(),
            subject=random.choice(SUBJECTS),
            school_id=school.id,
            salary=salary,
            email=f"teacher{i+1}@school.example.com",
            phone=f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
            hire_date=date.today() - timedelta(days=random.randint(365, 365*20)),
            years_experience=random.randint(0, 25),
            qualification=random.choice(["B.Ed", "M.Ed", "PhD", "PGCE", None]),
        )
        db.add(teacher)
        teachers.append(teacher)
    db.commit()  # Commit to persist teachers and assign their ids
    for t in teachers:
        db.refresh(t)  # Ensure relationship operations see up-to-date state

    # Create students
    students: List[Student] = []
    for i in range(num_students):
        grade = random.choice(["A", "B", "C", "D", None])
        dob_year = random.randint(2003, 2012)  # roughly 12-21 years old
        dob = date(dob_year, random.randint(1, 12), random.randint(1, 28))
        enroll = date.today() - timedelta(days=random.randint(30, 365*5))
        student = Student(
            name=random_name(),
            grade=grade,
            email=f"student{i+1}@mail.example.com",
            phone=f"+1-444-{random.randint(100,999)}-{random.randint(1000,9999)}",
            date_of_birth=dob,
            enrollment_date=enroll,
            address=f"{random.randint(100,9999)} {random.choice(STREET_NAMES)} Ave",
        )
        db.add(student)
        students.append(student)
    db.commit()  # Commit to get student ids before linking to teachers
    for st in students:
        db.refresh(st)  # Ensure we link using current ORM instances

    # Assign teachers to students (each student 1-5 teachers, no duplicates)
    for st in students:
        k = random.randint(1, 5)
        assigned = random.sample(teachers, k=k)
        for t in assigned:
            if t not in st.teachers:
                st.teachers.append(t)
    db.commit()  # Final commit to persist many-to-many links


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with demo data.")
    parser.add_argument("--schools", type=int, default=20, help="Number of schools to create (default: 20)")
    parser.add_argument("--teachers", type=int, default=60, help="Number of teachers to create (default: 60)")
    parser.add_argument("--students", type=int, default=80, help="Number of students to create (default: 80)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    random.seed(args.seed)
    db = SessionLocal()
    try:
        seed(db, num_schools=args.schools, num_teachers=args.teachers, num_students=args.students)
        print(
            f"Seeding complete. Created: schools={args.schools}, teachers={args.teachers}, students={args.students}"
        )
    finally:
        db.close()




