"""Регистрация/вход (энейблер), US-01 (каталог), US-11 (фильтр по специальности)."""
from tests.conftest import case_id


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={"email": "A@Test.kz", "password": "password123", "first_name": "A"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "student"

    assert client.post("/api/v1/auth/register", json={"email": "a@test.kz", "password": "password123",
                                                       "first_name": "A"}).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": "a@test.kz", "password": "wrong-pass"}).status_code == 401

    token = client.post("/api/v1/auth/login", json={"email": "a@test.kz", "password": "password123"}).json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert me.json()["email"] == "a@test.kz"


def test_short_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={"email": "b@test.kz", "password": "123", "first_name": "B"})
    assert r.status_code == 422


def test_requires_auth(client):
    assert client.get("/api/v1/cases").status_code == 401


def test_us01_catalog_shows_only_published(client, student):
    """6 кейсов в БД: 5 published + 1 draft → видим ровно 5 карточек, черновик скрыт."""
    data = client.get("/api/v1/cases", headers=student).json()
    assert data["count"] == 5
    codes = {c["code"] for c in data["items"]}
    assert "CASE-SURG-02" not in codes
    for c in data["items"]:
        assert c["specialty"] and c["difficulty"] and c["chief_complaint"]
        assert "diagnosis" not in c  # карточка не выдаёт диагноз


def test_us11_filter_by_specialty(client, student):
    specs = {s["specialty"]: s["count"] for s in client.get("/api/v1/cases/specialties", headers=student).json()}
    assert specs == {"Internal Medicine": 3, "Neurology": 1, "Surgery": 1}

    data = client.get("/api/v1/cases", params={"specialty": "Internal Medicine"}, headers=student).json()
    assert data["count"] == 3 == len(data["items"])
    assert all(c["specialty"] == "Internal Medicine" for c in data["items"])


def test_draft_case_not_available(client, student, admin):
    draft = next(c for c in client.get("/api/v1/admin/cases", headers=admin).json() if c["status"] == "draft")
    r = client.get(f"/api/v1/cases/{draft['id']}", headers=student)
    assert r.status_code == 404 and r.json()["detail"] == "Case not available"


def test_staff_endpoints_forbidden_for_students(client, student):
    assert client.get("/api/v1/admin/cases", headers=student).status_code == 403


def test_publish_flow(client, student, admin):
    draft = next(c for c in client.get("/api/v1/admin/cases", headers=admin).json() if c["status"] == "draft")
    assert client.post(f"/api/v1/admin/cases/{draft['id']}/publish", headers=admin).json()["status"] == "published"
    assert client.get("/api/v1/cases", headers=student).json()["count"] == 6
    assert case_id(client, student, "CASE-SURG-02") == draft["id"]


def test_icd_search(client, student):
    r = client.get("/api/v1/icd10", params={"q": "I20"}, headers=student).json()
    assert r[0]["code"].startswith("I20")
    r = client.get("/api/v1/icd10", params={"q": "unstable"}, headers=student).json()
    assert {"code": "I20.0", "name": "Unstable angina"} in r
