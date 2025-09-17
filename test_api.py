import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


@pytest.fixture(scope="session")
def auth_headers() -> Dict[str, str]:
    """Register a new user and return Authorization headers for requests."""
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"

    # Register user
    resp = client.post(
        "/auth/register",
        json={"username": username, "password": password, "is_admin": True},
    )
    assert resp.status_code in (200, 201, 400)  # 400 if username exists from a previous run

    # Login to obtain bearer token
    token_resp = client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def non_admin_headers() -> Dict[str, str]:
    """Register a non-admin user and return Authorization headers."""
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"
    client.post("/auth/register", json={"username": username, "password": password, "is_admin": False})
    resp = client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ------------------------ Auth ------------------------
def test_auth_login_invalid():
    resp = client.post(
        "/auth/login",
        data={"username": "unknown", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


def test_auth_refresh_success(auth_headers):
    # Obtain a refresh token by logging in via the same user created in fixture
    # We cannot directly call refresh without a token; reuse fixture flow
    # Extract refresh from a new login
    username = f"refresh_{uuid.uuid4().hex[:6]}"
    password = "Passw0rd!"
    client.post("/auth/register", json={"username": username, "password": password})
    login = client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json().get("access_token")


# ------------------------ Schools ------------------------
def test_schools_create_valid(auth_headers):
    resp = client.post(
        "/schools",
        json={"name": f"School {uuid.uuid4().hex[:6]}", "address": "123 Test St"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data and data["name"]


def test_schools_create_missing_fields(auth_headers):
    # Missing required name
    resp = client.post(
        "/schools",
        json={"address": "No Name Ave"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_schools_get_all(auth_headers):
    resp = client.get("/schools", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_schools_get_by_id_valid(auth_headers):
    created = client.post(
        "/schools",
        json={"name": f"Valid School {uuid.uuid4().hex[:6]}", "address": "Addr"},
        headers=auth_headers,
    ).json()
    resp = client.get(f"/schools/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"] and data["name"] == created["name"]


def test_schools_get_by_id_invalid(auth_headers):
    resp = client.get("/schools/999999", headers=auth_headers)
    assert resp.status_code == 404


# Update, Delete for Schools
def test_schools_update_and_delete(auth_headers):
    created = client.post(
        "/schools",
        json={"name": f"Upd School {uuid.uuid4().hex[:5]}", "address": "Addr"},
        headers=auth_headers,
    ).json()
    sid = created["id"]
    # Patch
    up = client.patch(f"/schools/{sid}", json={"address": "New"}, headers=auth_headers)
    assert up.status_code == 200 and up.json()["address"] == "New"
    # Delete
    d = client.delete(f"/schools/{sid}", headers=auth_headers)
    assert d.status_code == 204
    missing = client.get(f"/schools/{sid}", headers=auth_headers)
    assert missing.status_code == 404


# ------------------------ Teachers ------------------------
@pytest.fixture()
def school_id(auth_headers) -> int:
    resp = client.post(
        "/schools",
        json={"name": f"Teacher School {uuid.uuid4().hex[:6]}", "address": "TS"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_teachers_create_valid(auth_headers, school_id):
    resp = client.post(
        "/teachers",
        json={
            "name": f"Teacher {uuid.uuid4().hex[:5]}",
            "subject": "Math",
            "school_id": school_id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] and data["school_id"] == school_id and data["name"]


def test_teachers_create_missing_fields(auth_headers):
    # Missing required fields: name and school_id
    resp = client.post(
        "/teachers",
        json={"subject": "Science"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_teachers_get_all(auth_headers):
    resp = client.get("/teachers", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_teachers_get_by_id_valid(auth_headers, school_id):
    created = client.post(
        "/teachers",
        json={
            "name": f"Lookup T {uuid.uuid4().hex[:5]}",
            "subject": "English",
            "school_id": school_id,
        },
        headers=auth_headers,
    ).json()
    resp = client.get(f"/teachers/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"] and data["school_id"] == school_id


def test_teachers_get_by_id_invalid(auth_headers):
    resp = client.get("/teachers/999999", headers=auth_headers)
    assert resp.status_code == 404


def test_teachers_update_and_delete(auth_headers, school_id):
    created = client.post(
        "/teachers",
        json={
            "name": f"Upd T {uuid.uuid4().hex[:5]}",
            "subject": "Science",
            "school_id": school_id,
            "qualification": "M.Ed",
            "years_experience": 10,
        },
        headers=auth_headers,
    ).json()
    tid = created["id"]
    up = client.patch(f"/teachers/{tid}", json={"subject": "Math"}, headers=auth_headers)
    assert up.status_code == 200 and up.json()["subject"] == "Math"
    d = client.delete(f"/teachers/{tid}", headers=auth_headers)
    assert d.status_code == 204
    missing = client.get(f"/teachers/{tid}", headers=auth_headers)
    assert missing.status_code == 404


# Teachers search endpoint
def test_teachers_search_filters(auth_headers, school_id):
    t = client.post(
        "/teachers",
        json={
            "name": f"SearchT {uuid.uuid4().hex[:5]}",
            "subject": "Math",
            "school_id": school_id,
            "qualification": "PhD",
            "years_experience": 15,
        },
        headers=auth_headers,
    ).json()
    r = client.get(
        "/teachers/search",
        params={"qualification": "PhD", "subject": "Math", "years_experience": 15, "per_page": 20},
        headers=auth_headers,
    )
    assert r.status_code == 200
    ids = [tt["id"] for tt in r.json()]
    assert t["id"] in ids


# ------------------------ Students ------------------------
def test_students_create_valid(auth_headers):
    resp = client.post(
        "/students",
        json={"name": f"Student {uuid.uuid4().hex[:6]}", "grade": "A"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] and data["name"] and data.get("grade") in (None, "A", "B", "C", "D")


def test_students_create_missing_fields(auth_headers):
    # Missing required name
    resp = client.post(
        "/students",
        json={"grade": "B"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_students_get_all(auth_headers):
    resp = client.get("/students", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_students_get_by_id_valid(auth_headers):
    created = client.post(
        "/students",
        json={"name": f"Lookup S {uuid.uuid4().hex[:6]}", "grade": "C"},
        headers=auth_headers,
    ).json()
    resp = client.get(f"/students/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"] and data["name"] == created["name"]


def test_students_get_by_id_invalid(auth_headers):
    resp = client.get("/students/999999", headers=auth_headers)
    assert resp.status_code == 404


def test_students_update_and_delete(auth_headers):
    s = client.post(
        "/students",
        json={"name": f"Upd S {uuid.uuid4().hex[:6]}", "grade": "B"},
        headers=auth_headers,
    ).json()
    sid = s["id"]
    up = client.patch(f"/students/{sid}", json={"grade": "A"}, headers=auth_headers)
    assert up.status_code == 200 and up.json()["grade"] == "A"
    d = client.delete(f"/students/{sid}", headers=auth_headers)
    assert d.status_code == 204
    missing = client.get(f"/students/{sid}", headers=auth_headers)
    assert missing.status_code == 404


# Students search endpoint
def test_students_search_grade_name_teacher_and_pagination(auth_headers, school_id):
    # Create teacher and two students, relate both
    teacher = client.post(
        "/teachers",
        json={"name": f"RelT {uuid.uuid4().hex[:5]}", "subject": "English", "school_id": school_id},
        headers=auth_headers,
    ).json()
    s1 = client.post(
        "/students",
        json={"name": "Annabelle", "grade": "A"},
        headers=auth_headers,
    ).json()
    s2 = client.post(
        "/students",
        json={"name": "Anny", "grade": "A"},
        headers=auth_headers,
    ).json()
    # Assign
    a1 = client.post(f"/students/{s1['id']}/teachers/{teacher['id']}", headers=auth_headers)
    a2 = client.post(f"/students/{s2['id']}/teachers/{teacher['id']}", headers=auth_headers)
    assert a1.status_code == 204 and a2.status_code == 204

    # Page 1
    r1 = client.get(
        "/students/search",
        params={"grade": "A", "name": "ann", "teacher_id": teacher["id"], "page": 1, "per_page": 1},
        headers=auth_headers,
    )
    assert r1.status_code == 200 and len(r1.json()) == 1
    # Page 2
    r2 = client.get(
        "/students/search",
        params={"grade": "A", "name": "ann", "teacher_id": teacher["id"], "page": 2, "per_page": 1},
        headers=auth_headers,
    )
    assert r2.status_code == 200 and len(r2.json()) == 1


def test_students_search_invalid_grade(auth_headers):
    r = client.get(
        "/students/search",
        params={"grade": "Z"},
        headers=auth_headers,
    )
    assert r.status_code == 400


# Relationships and admin-only
def test_relationship_endpoints_and_admin_salary(auth_headers, non_admin_headers, school_id):
    # Create teacher with salary and a student
    t = client.post(
        "/teachers",
        json={
            "name": f"SalaryT {uuid.uuid4().hex[:5]}",
            "subject": "History",
            "school_id": school_id,
            "salary": 12345.0,
        },
        headers=auth_headers,
    ).json()
    s = client.post(
        "/students",
        json={"name": f"RelS {uuid.uuid4().hex[:6]}", "grade": "D"},
        headers=auth_headers,
    ).json()
    # Assign and fetch relationships
    a = client.post(f"/students/{s['id']}/teachers/{t['id']}", headers=auth_headers)
    assert a.status_code == 204
    ts = client.get(f"/students/{s['id']}/teachers", headers=auth_headers)
    assert ts.status_code == 200 and any(x["id"] == t["id"] for x in ts.json())
    ss = client.get(f"/teachers/{t['id']}/students", headers=auth_headers)
    assert ss.status_code == 200 and any(x["id"] == s["id"] for x in ss.json())
    # School teachers
    sc_t = client.get(f"/schools/{school_id}/teachers", headers=auth_headers)
    assert sc_t.status_code == 200 and any(x["id"] == t["id"] for x in sc_t.json())

    # Admin salary endpoint: 403 for non-admin, 200 for admin
    forbidden = client.get(f"/admin/teachers/{t['id']}/salary", headers=non_admin_headers)
    assert forbidden.status_code == 403
    ok = client.get(f"/admin/teachers/{t['id']}/salary", headers=auth_headers)
    assert ok.status_code == 200 and ok.json().get("salary") == 12345.0


