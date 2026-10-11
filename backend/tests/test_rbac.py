"""RBAC tests covering all 20 required cases.

Uses mongomock-motor for an in-memory database and httpx.AsyncClient
against the FastAPI app. No real MongoDB or AI model files required.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db import get_db
from app.deps import db_dep
from app.main import app
from app.security import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username: str, role: str, approved: bool = False, ngo_org: str | None = None) -> dict:
    return {
        "_id": ObjectId(),
        "username": username,
        "password_hash": hash_password("password123"),
        "email": f"{username}@test.example",
        "first_name": username,
        "last_name": "Test",
        "role": role,
        "approved": approved,
        "ngo_org": ngo_org,
        "created_at": datetime.now(timezone.utc),
    }


def _token(user_doc: dict) -> str:
    return create_access_token(
        str(user_doc["_id"]),
        {
            "username": user_doc["username"],
            "role": user_doc["role"],
            "approved": user_doc.get("approved", False),
            "ngo_org": user_doc.get("ngo_org"),
        },
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def mock_db():
    db = AsyncMongoMockClient()["test_rbac"]
    # Minimal indexes (mongomock doesn't enforce uniqueness, but keep them for parity)
    await db["users"].create_index("username")
    await db["missing_persons"].create_index("created_by")
    await db["missing_persons"].create_index("shared_with_ngo")
    return db


@pytest_asyncio.fixture
async def client(mock_db):
    # Override both db_dep (used directly) and get_db (called inside db_dep)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[db_dep] = lambda: mock_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, mock_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(db_dep, None)


async def _insert_user(mock_db, **kwargs) -> dict:
    doc = _make_user(**kwargs)
    await mock_db["users"].insert_one(doc)
    doc["id"] = str(doc["_id"])
    return doc


async def _insert_person(mock_db, created_by: str, shared_with_ngo: list | None = None) -> dict:
    doc = {
        "_id": ObjectId(),
        "full_name": "Test Person",
        "age": 30,
        "gender": "UNKNOWN",
        "status": "ACTIVE",
        "archived": False,
        "created_by": created_by,
        "shared_with_ngo": shared_with_ngo or [],
        "ngo_notes": "",
        "last_seen_location": "",
        "last_seen_city": "",
        "last_seen_state": "",
        "description": "",
        "contact_name": "",
        "contact_phone": "",
        "contact_email": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await mock_db["missing_persons"].insert_one(doc)
    doc["id"] = str(doc["_id"])
    return doc


# ---------------------------------------------------------------------------
# Tests 1–4: Recognition is restricted to approved POLICE and ADMIN;
# citizens/NGO get 403 (backend-enforced). Record listings stay restricted.
# ---------------------------------------------------------------------------

async def test_citizen_cannot_list_registered_persons(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen1", role="CITIZEN")
    tok = _token(citizen)
    res = await ac.get("/api/dataset/registered", headers=_auth(tok))
    assert res.status_code == 403


async def test_citizen_cannot_get_registered_person(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen2", role="CITIZEN")
    tok = _token(citizen)
    res = await ac.get("/api/dataset/registered/biswa", headers=_auth(tok))
    assert res.status_code == 403


async def test_citizen_cannot_call_recognition_search(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen3", role="CITIZEN")
    tok = _token(citizen)
    jpeg = b"\xff\xd8\xff" + b"\x00" * 100
    res = await ac.post(
        "/api/recognition/search",
        headers=_auth(tok),
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"model": "all"},
    )
    assert res.status_code == 403


async def test_approved_police_can_call_recognition_search(client):
    ac, db = client
    police = await _insert_user(db, username="police_search", role="POLICE", approved=True)
    tok = _token(police)
    # Auth passes; the blob is not a decodable JPEG, so every runnable model
    # reports its REAL decode error on its own card (status invalid_image).
    jpeg = b"\xff\xd8\xff" + b"\x00" * 100
    res = await ac.post(
        "/api/recognition/search",
        headers=_auth(tok),
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"model": "all"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["results"]["cnn"]["status"] == "invalid_image"
    assert body["results"]["cnn"]["error"]
    assert body["summary"]["verdict"] in ("inconclusive", "conflicting")


async def test_citizen_cannot_call_recognition_availability(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen4", role="CITIZEN")
    tok = _token(citizen)
    res = await ac.get("/api/recognition/availability", headers=_auth(tok))
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Test 5: Citizen history strips predicted_label
# ---------------------------------------------------------------------------

async def test_citizen_history_strips_predicted_label(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen5", role="CITIZEN")
    tok = _token(citizen)
    # Insert a search record directly in the mock DB
    await db["recognition_searches"].insert_one({
        "_id": ObjectId(),
        "searched_by": citizen["id"],
        "model": "cnn",
        "query_image_url": "/storage/queries/test.jpg",
        "created_at": datetime.now(timezone.utc),
        "results": [{"model": "cnn", "payload": {"predicted_label": "biswa", "status": "match"}}],
    })
    res = await ac.get("/api/search-history", headers=_auth(tok))
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["predicted_label"] is None


# ---------------------------------------------------------------------------
# Test 6: Citizen cannot view another citizen's report
# ---------------------------------------------------------------------------

async def test_citizen_cannot_view_another_citizens_report(client):
    ac, db = client
    citizen_a = await _insert_user(db, username="citizenA", role="CITIZEN")
    citizen_b = await _insert_user(db, username="citizenB", role="CITIZEN")
    person = await _insert_person(db, created_by=citizen_a["id"])
    tok_b = _token(citizen_b)
    res = await ac.get(f"/api/persons/{person['id']}", headers=_auth(tok_b))
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Test 7: Citizen cannot change own role via profile update
# ---------------------------------------------------------------------------

async def test_citizen_cannot_change_own_role(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen7", role="CITIZEN")
    tok = _token(citizen)
    # ProfileUpdateIn only accepts first_name/last_name/email — role is ignored
    res = await ac.patch("/api/auth/profile", headers=_auth(tok), json={"role": "ADMIN"})
    # Should succeed (200 or ignored field) — role must remain CITIZEN
    assert res.status_code in (200, 422)
    # Confirm role in DB is still CITIZEN
    updated = await db["users"].find_one({"_id": ObjectId(citizen["id"])})
    assert updated["role"] == "CITIZEN"


# ---------------------------------------------------------------------------
# Test 8: Citizen cannot access NGO sightings endpoint
# ---------------------------------------------------------------------------

async def test_citizen_cannot_access_ngo_sightings_endpoint(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen8", role="CITIZEN")
    tok = _token(citizen)
    res = await ac.post(
        "/api/ngo/sightings",
        headers=_auth(tok),
        json={"person_id": str(ObjectId()), "location": "Test", "description": ""},
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Tests 9–11: Police access (approved POLICE and ADMIN only; unapproved
# POLICE accounts stay blocked until an admin approves them)
# ---------------------------------------------------------------------------

async def test_police_unapproved_cannot_access_recognition(client):
    ac, db = client
    police = await _insert_user(db, username="police_unapp", role="POLICE", approved=False)
    tok = _token(police)
    res = await ac.get("/api/recognition/availability", headers=_auth(tok))
    # Pending approval: blocked until an admin approves the account.
    assert res.status_code == 403


async def test_police_approved_can_access_recognition(client):
    ac, db = client
    police = await _insert_user(db, username="police_app", role="POLICE", approved=True)
    tok = _token(police)
    res = await ac.get("/api/recognition/availability", headers=_auth(tok))
    # 200 means the endpoint is reachable (may return empty model info without AI artifacts)
    assert res.status_code == 200


async def test_police_approved_can_list_registered_persons(client):
    ac, db = client
    police = await _insert_user(db, username="police_list", role="POLICE", approved=True)
    tok = _token(police)
    res = await ac.get("/api/dataset/registered", headers=_auth(tok))
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Tests 12–14: Admin actions
# ---------------------------------------------------------------------------

async def test_admin_can_approve_police(client):
    ac, db = client
    admin = await _insert_user(db, username="admin_appr", role="ADMIN", approved=True)
    police = await _insert_user(db, username="police_to_approve", role="POLICE", approved=False)
    tok = _token(admin)
    res = await ac.patch(
        f"/api/admin/users/{police['id']}/approval",
        headers=_auth(tok),
        json={"approved": True},
    )
    assert res.status_code == 200
    assert res.json()["approved"] is True


async def test_admin_can_change_user_role(client):
    ac, db = client
    admin = await _insert_user(db, username="admin_role", role="ADMIN", approved=True)
    target = await _insert_user(db, username="target_role", role="CITIZEN")
    tok = _token(admin)
    res = await ac.patch(
        f"/api/admin/users/{target['id']}/role",
        headers=_auth(tok),
        json={"role": "POLICE"},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "POLICE"


async def test_citizen_cannot_promote_self(client):
    ac, db = client
    citizen = await _insert_user(db, username="citizen_promo", role="CITIZEN")
    tok = _token(citizen)
    res = await ac.patch(
        f"/api/admin/users/{citizen['id']}/role",
        headers=_auth(tok),
        json={"role": "ADMIN"},
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Tests 15–19: NGO worker permissions
# ---------------------------------------------------------------------------

async def test_ngo_can_view_shared_case(client):
    ac, db = client
    ngo = await _insert_user(db, username="ngo_view", role="NGO_WORKER", ngo_org="test_ngo")
    admin = await _insert_user(db, username="admin_share", role="ADMIN", approved=True)
    person = await _insert_person(db, created_by=admin["id"], shared_with_ngo=["test_ngo"])
    tok = _token(ngo)
    res = await ac.get("/api/ngo/cases", headers=_auth(tok))
    assert res.status_code == 200
    ids = [c["id"] for c in res.json()]
    assert person["id"] in ids


async def test_ngo_cannot_view_unshared_case(client):
    ac, db = client
    ngo = await _insert_user(db, username="ngo_unshared", role="NGO_WORKER", ngo_org="test_ngo")
    admin = await _insert_user(db, username="admin_nosha", role="ADMIN", approved=True)
    await _insert_person(db, created_by=admin["id"], shared_with_ngo=[])  # NOT shared
    tok = _token(ngo)
    res = await ac.get("/api/ngo/cases", headers=_auth(tok))
    assert res.status_code == 200
    assert res.json() == []


async def test_ngo_cannot_call_recognition(client):
    ac, db = client
    ngo = await _insert_user(db, username="ngo_recog", role="NGO_WORKER", ngo_org="test_ngo")
    tok = _token(ngo)
    res = await ac.get("/api/recognition/availability", headers=_auth(tok))
    # Recognition is restricted to approved POLICE / ADMIN.
    assert res.status_code == 403


async def test_ngo_cannot_access_registered_gallery(client):
    ac, db = client
    ngo = await _insert_user(db, username="ngo_gallery", role="NGO_WORKER", ngo_org="test_ngo")
    tok = _token(ngo)
    res = await ac.get("/api/dataset/registered", headers=_auth(tok))
    assert res.status_code == 403


async def test_ngo_can_submit_sighting_for_shared_case(client):
    ac, db = client
    ngo = await _insert_user(db, username="ngo_sight", role="NGO_WORKER", ngo_org="test_ngo")
    admin = await _insert_user(db, username="admin_sight", role="ADMIN", approved=True)
    person = await _insert_person(db, created_by=admin["id"], shared_with_ngo=["test_ngo"])
    tok = _token(ngo)
    res = await ac.post(
        "/api/ngo/sightings",
        headers=_auth(tok),
        json={"person_id": person["id"], "location": "Park", "description": "Saw someone"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["person_id"] == person["id"]
    assert data["ngo_org"] == "test_ngo"


# ---------------------------------------------------------------------------
# Test 20: Existing auth and report submission still work
# ---------------------------------------------------------------------------

async def test_existing_auth_and_report_submission_still_work(client):
    ac, db = client
    # Register → should become CITIZEN
    res = await ac.post("/api/auth/register", json={
        "username": "newcitizen20",
        "password": "password123",
        "email": "newcitizen20@test.example",
        "first_name": "New",
        "last_name": "Citizen",
    })
    assert res.status_code == 201  # register returns 201 Created
    data = res.json()
    assert data["user"]["role"] == "CITIZEN"
    tok = data["access_token"]

    # Login
    login_res = await ac.post("/api/auth/login", json={
        "username": "newcitizen20", "password": "password123"
    })
    assert login_res.status_code == 200
    assert login_res.json()["user"]["role"] == "CITIZEN"

    # Submit a missing-person report
    report_res = await ac.post(
        "/api/persons",
        headers=_auth(tok),
        json={
            "full_name": "Missing Person Test",
            "age": 25,
            "gender": "UNKNOWN",
            "last_seen_location": "Test City",
        },
    )
    assert report_res.status_code == 201
    assert report_res.json()["full_name"] == "Missing Person Test"


# ---------------------------------------------------------------------------
# Role-request at signup: CITIZEN instant, POLICE locked until approval,
# ADMIN/anything-else never self-granted.
# ---------------------------------------------------------------------------

async def test_register_requesting_police_stays_unapproved(client):
    ac, db = client
    res = await ac.post("/api/auth/register", json={
        "username": "officer_applicant",
        "password": "password123",
        "email": "officer_applicant@test.example",
        "requested_role": "POLICE",
    })
    assert res.status_code == 201
    user = res.json()["user"]
    assert user["role"] == "POLICE"
    assert user["approved"] is False
    # Locked out of protected endpoints until an admin approves
    tok = res.json()["access_token"]
    rec = await ac.get("/api/recognition/availability", headers=_auth(tok))
    assert rec.status_code == 403


async def test_register_requesting_admin_is_rejected(client):
    ac, _db = client
    res = await ac.post("/api/auth/register", json={
        "username": "sneaky_admin",
        "password": "password123",
        "requested_role": "ADMIN",
    })
    assert res.status_code == 422


async def test_register_defaults_to_citizen(client):
    ac, _db = client
    res = await ac.post("/api/auth/register", json={
        "username": "plain_citizen",
        "password": "password123",
    })
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "CITIZEN"


# ---------------------------------------------------------------------------
# Field-report match: visible to staff on history detail, stripped for
# restricted roles (CITIZEN/NGO_WORKER).
# ---------------------------------------------------------------------------

async def test_report_match_visible_to_police_stripped_for_citizen(client):
    ac, db = client
    police = await _insert_user(db, username="police_rm", role="POLICE", approved=True)
    citizen = await _insert_user(db, username="citizen_rm", role="CITIZEN")
    match = {"person_id": "abc123", "person_name": "Field Case",
             "photo_url": "/storage/persons/abc123/x.jpg",
             "similarity": 0.99, "model": "arcface", "note": "verify visually"}
    sid = ObjectId()
    await db["recognition_searches"].insert_one({
        "_id": sid, "searched_by": citizen["id"], "model": "all",
        "query_image_url": "/storage/queries/q.jpg",
        "created_at": datetime.now(timezone.utc), "report_match": match,
    })
    await db["recognition_results"].insert_one({
        "_id": ObjectId(), "search_id": str(sid), "model": "cnn",
        "payload": {"model": "cnn", "available": True, "match_found": False,
                    "status": "no_reliable_match"},
        "created_at": datetime.now(timezone.utc),
    })
    # Owner citizen sees scrubbed results and NO report match
    res = await ac.get(f"/api/search-history/{sid}", headers=_auth(_token(citizen)))
    assert res.status_code == 200
    assert res.json()["report_match"] is None
    # Admin sees the stored report match
    admin = await _insert_user(db, username="admin_rm", role="ADMIN", approved=True)
    res = await ac.get(f"/api/search-history/{sid}", headers=_auth(_token(admin)))
    assert res.status_code == 200
    assert res.json()["report_match"] == match


# ---------------------------------------------------------------------------
# Tests 21+: Add-person-to-dataset section (dashboard dataset upload)
# ---------------------------------------------------------------------------
def _real_png() -> bytes:
    import cv2
    import numpy as np

    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:] = (40, 80, 160)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


async def test_police_or_admin_can_add_person_photos(client, monkeypatch, tmp_path):
    from app.ai import gallery as gallery_mod
    from app.ai import index_ext as index_ext_mod

    ac, db = client
    monkeypatch.setattr(gallery_mod, "gallery_dir", lambda: str(tmp_path))
    # Isolate the extension index store too: embedding tmp photos must never
    # pollute the REAL storage/indexes used by recognition.
    monkeypatch.setattr(index_ext_mod, "extension_root", lambda: str(tmp_path / "indexes"))

    police = await _insert_user(db, username="police_ds", role="POLICE", approved=True)
    tok = _token(police)
    png = _real_png()
    res = await ac.post(
        "/api/dataset/person",
        headers=_auth(tok),
        data={"name": "John Doe"},
        files=[("files", ("a.png", png, "image/png")),
               ("files", ("b.png", png, "image/png"))],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["identity"] == "john_doe"
    assert body["saved_count"] == 2
    assert body["folder_photo_count"] == 2
    assert body["rejected"] == []

    folder = tmp_path / "john_doe"
    assert folder.is_dir()
    assert len(list(folder.iterdir())) == 2

    person = await db["registered_persons"].find_one({"identity": "john_doe"})
    assert person is not None
    assert person["image_count"] == 2
    assert person["name"] == "John Doe"
    imgs = [d async for d in db["registered_images"].find({"identity": "john_doe"})]
    assert len(imgs) == 2


async def test_citizen_and_ngo_cannot_add_person_photos(client, monkeypatch, tmp_path):
    from app.ai import gallery as gallery_mod

    ac, db = client
    monkeypatch.setattr(gallery_mod, "gallery_dir", lambda: str(tmp_path))

    # Writing to the protected registered gallery is POLICE/ADMIN only.
    for username, kwargs in (("citizen_ds3", {"role": "CITIZEN"}),
                             ("ngo_ds3", {"role": "NGO_WORKER", "ngo_org": "test_ngo"})):
        user = await _insert_user(db, username=username, **kwargs)
        res = await ac.post(
            "/api/dataset/person",
            headers=_auth(_token(user)),
            data={"name": "Blocked Person"},
            files=[("files", ("a.png", _real_png(), "image/png"))],
        )
        assert res.status_code == 403, (username, res.status_code, res.text[:200])


async def test_add_person_rejects_missing_name_and_bad_files(client, monkeypatch, tmp_path):
    from app.ai import gallery as gallery_mod
    from app.ai import index_ext as index_ext_mod

    ac, db = client
    monkeypatch.setattr(gallery_mod, "gallery_dir", lambda: str(tmp_path))
    monkeypatch.setattr(index_ext_mod, "extension_root", lambda: str(tmp_path / "indexes"))

    citizen = await _insert_user(db, username="citizen_ds2", role="POLICE", approved=True)
    tok = _token(citizen)

    # Missing name -> 400
    res = await ac.post(
        "/api/dataset/person", headers=_auth(tok),
        data={"name": "   "},
        files=[("files", ("a.png", _real_png(), "image/png"))],
    )
    assert res.status_code == 400

    # One bad file + one good file -> good one is stored, bad one reported
    garbage = b"\xff\xd8\xff" + b"\x00" * 20  # JPEG magic, undecodable content
    res = await ac.post(
        "/api/dataset/person", headers=_auth(tok),
        data={"name": "Jane Roe"},
        files=[("files", ("bad.jpg", garbage, "image/jpeg")),
               ("files", ("good.png", _real_png(), "image/png"))],
    )
    assert res.status_code == 201
    body = res.json()
    assert body["saved_count"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["filename"] == "bad.jpg"

    # Anonymous users are still blocked
    res = await ac.post(
        "/api/dataset/person", data={"name": "No Auth"},
        files=[("files", ("a.png", _real_png(), "image/png"))],
    )
    assert res.status_code == 401
