"""
Simple migration helper to add new nullable columns to existing SQLite tables.

Usage:
  python migrate.py

It inspects current columns and issues ALTER TABLE ... ADD COLUMN for any
missing fields introduced in the latest models (students, teachers), and creates
new tables if needed (e.g., student_documents).
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"


def get_existing_columns(con: sqlite3.Connection, table: str) -> set[str]:
	cur = con.execute(f"PRAGMA table_info({table});")
	return {row[1] for row in cur.fetchall()}  # row[1] is column name


def table_exists(con: sqlite3.Connection, table: str) -> bool:
	cur = con.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
		(table,),
	)
	return cur.fetchone() is not None


def add_column(con: sqlite3.Connection, table: str, ddl: str) -> None:
	# SQLite cannot add a UNIQUE constrained column via ALTER TABLE.
	# So we always add as a plain column, and create a unique index separately if needed.
	con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl};")


def create_unique_index(con: sqlite3.Connection, table: str, column: str) -> None:
	index_name = f"ux_{table}_{column}"
	con.execute(
		f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column});"
	)


def migrate() -> None:
	con = sqlite3.connect(DB_PATH.as_posix())
	try:
		con.execute("PRAGMA foreign_keys = ON;")

		# Students: add new nullable columns if missing
		student_cols = get_existing_columns(con, "students")
		student_adds: list[tuple[str, str]] = [
			("email", "email TEXT"),
			("phone", "phone TEXT"),
			("date_of_birth", "date_of_birth DATE"),
			("enrollment_date", "enrollment_date DATE"),
			("address", "address TEXT"),
		]
		for col, ddl in student_adds:
			if col not in student_cols:
				add_column(con, "students", ddl)
		# Add unique index on email if column exists
		student_cols = get_existing_columns(con, "students")
		if "email" in student_cols:
			create_unique_index(con, "students", "email")

		# Teachers: add new nullable columns if missing
		teacher_cols = get_existing_columns(con, "teachers")
		teacher_adds: list[tuple[str, str]] = [
			("email", "email TEXT"),
			("phone", "phone TEXT"),
			("hire_date", "hire_date DATE"),
			("years_experience", "years_experience INTEGER"),
			("qualification", "qualification TEXT"),
		]
		for col, ddl in teacher_adds:
			if col not in teacher_cols:
				add_column(con, "teachers", ddl)
		# Add unique index on email if column exists
		teacher_cols = get_existing_columns(con, "teachers")
		if "email" in teacher_cols:
			create_unique_index(con, "teachers", "email")

		# Create student_documents table if missing
		if not table_exists(con, "student_documents"):
			con.execute(
				"""
				CREATE TABLE IF NOT EXISTS student_documents (
					id INTEGER PRIMARY KEY,
					student_id INTEGER NOT NULL,
					document_name TEXT NOT NULL,
					document_type TEXT NOT NULL,
					s3_url TEXT NOT NULL,
					uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
					FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
				);
				"""
			)
			# Helpful index on student_id for lookups
			con.execute(
				"CREATE INDEX IF NOT EXISTS ix_student_documents_student_id ON student_documents(student_id);"
			)

		con.commit()
		print("Migration complete.")
	finally:
		con.close()


if __name__ == "__main__":
	migrate()


