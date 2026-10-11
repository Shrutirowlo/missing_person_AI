# RBAC Implementation Plan — Missing Person AI

**Scope:** Add full Role-Based Access Control (RBAC) with roles CITIZEN, POLICE, ADMIN, and NGO_WORKER to the existing FastAPI + React application. Every step leaves the codebase in a buildable, testable state.

**Key constraints discovered during exploration:**
- Role value `POLICE_OFFICER` in `schemas/auth.py` must be renamed to `POLICE` everywhere (no DB migration needed for existing test DBs — the test database uses mongomock).
- `auth_service.register()` accepts any role from the request payload — this is a security hole that must be closed first.
- No `approved` or `ngo_org` fields exist on user documents yet.
- `deps.py` has only `current_user_dep` — no role-enforcement helpers at all.
- `history.py` already has a partial ADMIN check (keep it, extend it).
- All AI adapter files are read-only; do not touch them.
- Test runner: `pytest` with `asyncio_mode = auto`, using `mongomock-motor` for in-memory DB.
- Test command (from backend/ directory): `python -m pytest tests/ -v`
- Frontend routing: React Router v6, `ProtectedRoute` wraps every authenticated page.

---

## Implementation Plan

- [ ] 1. **Standardize role values in the schema** — rename `POLICE_OFFICER` → `POLICE` in the `Role` literal and update `RegisterIn` default. Also remove the `role` field from `RegisterIn` (replace it with a private default of `"CITIZEN"` so users cannot self-assign any role at registration time).

  Files: `backend/app/schemas/auth.py`

  Changes:
  - Change `Role = Literal["ADMIN", "POLICE_OFFICER", "NGO_WORKER", "CITIZEN"]` to `Role = Literal["ADMIN", "POLICE", "NGO_WORKER", "CITIZEN"]`.
  - Remove the `role: Role = "CITIZEN"` field from `RegisterIn` entirely (callers must not send a role at registration).
  - Add `approved: bool = False` and `ngo_org: str | None = None` to `UserOut`.
  - Add a new `UserAdminOut` schema that extends `UserOut` with no extra fields (used for admin list responses; keeps the response model explicit).

  Verify: `python -m pytest tests/test_unit.py -v` — all existing unit tests pass.

---

- [ ] 2. **Fix auth_service.register() — clamp role to CITIZEN, set approved default** — Close the privilege-escalation hole where any caller can register as ADMIN or POLICE by sending `role` in the request body.

  Files: `backend/app/services/auth_service.py`

  Changes:
  - In `register()`, hard-code `"role": "CITIZEN"` in the document built from `payload` — ignore any `role` key that arrives in `payload`.
  - Add `"approved": False` and `"ngo_org": None` to the document.
  - Update `public_user()` to include `approved` and `ngo_org` in the returned dict (add them to the key list).

  Rationale: Registration must always produce a CITIZEN. Role assignment is an admin-only operation done after registration.

  Verify: `python -m pytest tests/test_unit.py -v` — all unit tests pass. The JWT roundtrip test still passes because it does not call `register()`.

---

- [ ] 3. **Add role-enforcement dependency factories to deps.py** — Create reusable FastAPI dependencies that raise `HTTP 403` for authenticated users who lack the required role. All new role checks throughout the API will import from this one file.

  Files: `backend/app/deps.py`

  Add these functions after `current_user_dep`:

  ```python
  from fastapi import Depends, HTTPException, status

  def require_role(*roles: str):
      """Returns a dependency that allows only the listed roles."""
      async def _dep(user: dict = Depends(current_user_dep)) -> dict:
          if user.get("role") not in roles:
              raise HTTPException(
                  status_code=status.HTTP_403_FORBIDDEN,
                  detail=f"Requires role: {', '.join(roles)}"
              )
          return user
      return _dep

  def require_admin():
      return require_role("ADMIN")

  def require_police_or_admin():
      return require_role("POLICE", "ADMIN")

  def require_ngo_or_above():
      """NGO_WORKER, POLICE, or ADMIN."""
      return require_role("NGO_WORKER", "POLICE", "ADMIN")

  def require_approved_police():
      """POLICE who have been approved by an admin, or ADMIN."""
      async def _dep(user: dict = Depends(current_user_dep)) -> dict:
          role = user.get("role")
          if role == "ADMIN":
              return user
          if role == "POLICE":
              if not user.get("approved", False):
                  raise HTTPException(
                      status_code=status.HTTP_403_FORBIDDEN,
                      detail="Police account pending admin approval."
                  )
              return user
          raise HTTPException(
              status_code=status.HTTP_403_FORBIDDEN,
              detail="Requires approved POLICE or ADMIN role."
          )
      return _dep
  ```

  Verify: `python -m pytest tests/test_unit.py -v` — no import errors, existing tests pass.

---

- [ ] 4. **Apply role guards to recognition.py** — Citizens and NGO workers must not call recognition endpoints. Both routes require an approved police officer or admin.

  Files: `backend/app/api/recognition.py`

  Changes:
  - Import `require_approved_police` from `..deps`.
  - Change `GET /recognition/availability`: replace `Depends(current_user_dep)` with `Depends(require_approved_police())`.
  - Change `POST /recognition/search`: replace `Depends(current_user_dep)` with `Depends(require_approved_police())`.

  Rationale: Recognition results expose registered-person identities. Only approved police and admins may see them.

  Verify: `python -m pytest tests/test_unit.py tests/test_pipeline.py -v` — all pass. (Recognition endpoint guards are tested in the RBAC test suite added in step 15.)

---

- [ ] 5. **Apply role guards to dataset.py** — Registered-person records, gallery photos, dataset info, and import endpoints are all police/admin-only.

  Files: `backend/app/api/dataset.py`

  Changes:
  - Import `require_approved_police`, `require_admin` from `..deps`.
  - `GET /dataset/info` → `Depends(require_approved_police())`.
  - `GET /dataset/photo` → `Depends(require_approved_police())`.
  - `POST /dataset/import` → `Depends(require_admin())` (admin-only, not police).
  - `GET /dataset/registered` → `Depends(require_approved_police())`.
  - `GET /dataset/registered/{identity}` → `Depends(require_approved_police())`.
  - `GET /dataset/gallery/{identity}/{filename}` → `Depends(require_approved_police())`.

  Verify: `python -m pytest tests/ -v` — existing tests pass (they use mock DB and do not call HTTP endpoints directly).

---

- [ ] 6. **Apply role guards to history.py** — Tighten the existing partial check. Citizens may only view their own searches, and recognized-person identity fields must be stripped from citizen responses.

  Files: `backend/app/api/history.py`

  Changes:
  - Import `require_role` from `..deps`.
  - `GET /search-history`:
    - Keep `user: dict = Depends(current_user_dep)`.
    - The existing `scope = user["id"] if (mine or user.get("role") != "ADMIN") else None` remains; no data leaks here since `SearchHistoryItem` only has model/status/predicted_label — but `predicted_label` is a registered-person identity label. Strip it from the response when the user is CITIZEN or NGO_WORKER:
      ```python
      role = user.get("role")
      restricted = role in ("CITIZEN", "NGO_WORKER")
      for item in items:
          if restricted:
              item["predicted_label"] = None
              item["person_id"] = None
      ```
  - `GET /search-history/{search_id}`:
    - Keep existing ownership check.
    - If `user.get("role") in ("CITIZEN", "NGO_WORKER")`, strip sensitive fields from every result in `results`: remove `predicted_label`, `registered_match`, `registered_person_id`, `source_photo_url`, `source_photo_path`, `detail` (replace with `{}`), and replace `explanation` with `"Your report has been submitted. Authorized personnel can review it."`.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 7. **Apply role guards and ownership to persons.py** — Citizens can only view/edit their own reports. NGO workers can only view cases shared with their NGO. Police and admins can see all. Strip AI labels from responses for citizens and NGO workers.

  Files: `backend/app/api/persons.py`

  Changes:

  a. Update `_person_out()` — add a `role` parameter (default `"ADMIN"`) that controls whether `ai_labels` is included in each image dict:
  ```python
  def _person_out(doc: dict, base_url: str = "", role: str = "ADMIN") -> dict:
      restricted = role in ("CITIZEN", "NGO_WORKER")
      images = [
          {"id": img["id"],
           "url": f"{base_url}/storage/{img['path']}" if base_url else f"/storage/{img['path']}",
           "is_primary": img.get("is_primary", False),
           "ai_labels": {} if restricted else img.get("ai_labels", {}),
           "created_at": img.get("created_at")}
          for img in doc.get("images", [])
      ]
      return {**{k: v for k, v in doc.items() if k != "images"},
              "date_last_seen": str(doc.get("date_last_seen")) if doc.get("date_last_seen") else None,
              "images": images}
  ```

  b. `POST /persons` (create) — remains accessible to all authenticated users (any role can report a missing person); no change except passing `role=user["role"]` to `_person_out`.

  c. `GET /persons` (list) — citizens see only their own reports (`created_by == user["id"]`); NGO workers see cases where `shared_with_ngo` contains their `ngo_org`; police and admins see all:
  ```python
  role = user.get("role")
  if role == "CITIZEN":
      docs = await PersonRepository(db).list_persons_by_creator(user["id"], status=status, q=q, limit=limit, skip=skip)
  elif role == "NGO_WORKER":
      ngo_org = user.get("ngo_org") or ""
      docs = await PersonRepository(db).list_persons_for_ngo(ngo_org, status=status, q=q, limit=limit, skip=skip)
  else:
      docs = await PersonRepository(db).list_persons(status=status, q=q, limit=limit, skip=skip)
  return [_person_out(d, role=role) for d in docs]
  ```

  d. `GET /persons/{person_id}` — citizens can only retrieve their own reports (check `doc["created_by"] == user["id"]`; raise 403 otherwise); NGO workers can only retrieve cases shared with them; police/admin unrestricted:
  ```python
  role = user.get("role")
  if role == "CITIZEN" and doc.get("created_by") != user["id"]:
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
  elif role == "NGO_WORKER":
      ngo_org = user.get("ngo_org") or ""
      if ngo_org not in (doc.get("shared_with_ngo") or []):
          raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case not shared with your NGO")
  return _person_out(doc, role=role)
  ```

  e. `PUT /persons/{person_id}` — citizens can only edit their own reports; NGO workers cannot edit person records (raise 403); police/admin unrestricted. Prevent citizens from changing `status` to police-only values:
  ```python
  role = user.get("role")
  if role == "NGO_WORKER":
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="NGO workers cannot edit person records directly")
  if role == "CITIZEN" and doc.get("created_by") != user["id"]:
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
  ```

  f. `DELETE /persons/{person_id}` — citizens can only archive their own reports; NGO workers cannot archive; police/admin unrestricted.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 8. **Apply role guards to images.py** — Uploading reference photos to a missing-person record is open to all authenticated users (citizens need to attach photos to their own reports). Add an ownership check.

  Files: `backend/app/api/images.py`

  Changes:
  - Add an ownership check: if `user.get("role") == "CITIZEN"`, verify `person["created_by"] == user["id"]`. If not, raise HTTP 403.
  - If `user.get("role") == "NGO_WORKER"`, verify the case is in `shared_with_ngo` for the worker's org. If not, raise HTTP 403.
  - Strip `ai_labels` from the response if `user.get("role") in ("CITIZEN", "NGO_WORKER")`: return `"ai_labels": {}` in each saved dict.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 9. **Add new repository methods to PersonRepository** — The `list_persons` and `get_by_id` methods need variants that filter by `created_by` and `shared_with_ngo`. Also add the `shared_with_ngo` field to the create document shape.

  Files: `backend/app/repositories/persons.py`

  Add these methods to `PersonRepository`:
  ```python
  async def list_persons_by_creator(self, creator_id: str, *, status: str | None = None,
                                     q: str | None = None, limit: int = 50, skip: int = 0) -> list[dict]:
      query: dict = {"archived": False, "created_by": creator_id}
      if status:
          query["status"] = status
      if q:
          query["full_name"] = {"$regex": q, "$options": "i"}
      cursor = self.persons.find(query).sort("created_at", -1).skip(skip).limit(limit)
      out = []
      async for doc in cursor:
          item = _out(doc)
          item["images"] = await self.list_images(item["id"])
          out.append(item)
      return out

  async def list_persons_for_ngo(self, ngo_org: str, *, status: str | None = None,
                                   q: str | None = None, limit: int = 50, skip: int = 0) -> list[dict]:
      query: dict = {"archived": False, "shared_with_ngo": ngo_org}
      if status:
          query["status"] = status
      if q:
          query["full_name"] = {"$regex": q, "$options": "i"}
      cursor = self.persons.find(query).sort("created_at", -1).skip(skip).limit(limit)
      out = []
      async for doc in cursor:
          item = _out(doc)
          item["images"] = await self.list_images(item["id"])
          out.append(item)
      return out
  ```

  Also update `create()` to initialize `shared_with_ngo: []` and `ngo_notes: ""` on every new document.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 10. **Apply role guards to users.py** — The `GET /users` list endpoint already checks ADMIN, but `GET /users/me` is fine for any role. Confirm and add an `approved` field to the `/me` response by including it via `_pub()`.

  Files: `backend/app/api/users.py`

  Changes:
  - Update `_pub()` to include `"approved"` and `"ngo_org"` in the returned keys.
  - `GET /users` — the existing `if user.get("role") != "ADMIN": raise 403` check is correct; keep it. Change it to use `require_admin()` dep for consistency (replace `Depends(current_user_dep)` with `Depends(require_admin())`).
  - Import `require_admin` from `..deps`.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 11. **Create the Admin router** — New file with user management endpoints. Admins can list users, approve/revoke police accounts, change roles (cannot promote to a higher role than POLICE), and view all users.

  Files: `backend/app/api/admin.py` (new file)

  Create with these endpoints:

  ```python
  from fastapi import APIRouter, Depends, HTTPException, status
  from motor.motor_asyncio import AsyncIOMotorDatabase
  from ..deps import db_dep, require_admin
  from ..repositories.users import UserRepository
  from ..schemas.auth import UserOut
  from pydantic import BaseModel

  router = APIRouter(prefix="/admin", tags=["admin"])

  class RoleChangeIn(BaseModel):
      role: str  # validated against allowed values in the handler

  class ApprovalIn(BaseModel):
      approved: bool

  ASSIGNABLE_ROLES = {"CITIZEN", "POLICE", "NGO_WORKER"}  # ADMIN cannot be self-assigned

  @router.get("/users", response_model=list[UserOut])
  async def list_all_users(
      user: dict = Depends(require_admin()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      docs = await UserRepository(db).list_all(limit=500)
      return [_pub(d) for d in docs]

  @router.patch("/users/{user_id}/role")
  async def change_user_role(
      user_id: str,
      payload: RoleChangeIn,
      user: dict = Depends(require_admin()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      if payload.role not in ASSIGNABLE_ROLES:
          raise HTTPException(status_code=400, detail=f"Cannot assign role '{payload.role}'. Allowed: {ASSIGNABLE_ROLES}")
      repo = UserRepository(db)
      target = await repo.get_by_id(user_id)
      if target is None:
          raise HTTPException(status_code=404, detail="User not found")
      updated = await repo.update(user_id, {"role": payload.role, "approved": False})
      return _pub(updated)

  @router.patch("/users/{user_id}/approval")
  async def set_approval(
      user_id: str,
      payload: ApprovalIn,
      user: dict = Depends(require_admin()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      repo = UserRepository(db)
      target = await repo.get_by_id(user_id)
      if target is None:
          raise HTTPException(status_code=404, detail="User not found")
      if target.get("role") != "POLICE":
          raise HTTPException(status_code=400, detail="Only POLICE accounts require approval")
      updated = await repo.update(user_id, {"approved": payload.approved})
      return _pub(updated)

  @router.post("/users/{user_id}/promote-admin")
  async def promote_to_admin(
      user_id: str,
      user: dict = Depends(require_admin()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      """Only existing admins can promote another user to ADMIN."""
      repo = UserRepository(db)
      target = await repo.get_by_id(user_id)
      if target is None:
          raise HTTPException(status_code=404, detail="User not found")
      updated = await repo.update(user_id, {"role": "ADMIN", "approved": True})
      return _pub(updated)

  def _pub(doc: dict) -> dict:
      return {k: doc.get(k) for k in
              ("id", "username", "email", "first_name", "last_name", "role", "approved", "ngo_org", "created_at")}
  ```

  Verify: `python -m pytest tests/ -v` — all existing tests pass (no existing test calls these endpoints).

---

- [ ] 12. **Create the NGO router** — New file with NGO-specific endpoints: list shared cases, submit sightings, view activity.

  Files: `backend/app/api/ngo.py` (new file), `backend/app/schemas/persons.py`

  a. Add schemas to `schemas/persons.py`:
  ```python
  class SightingIn(BaseModel):
      person_id: str
      location: str = ""
      description: str = ""
      photo_urls: list[str] = []

  class SightingOut(BaseModel):
      id: str
      person_id: str
      submitted_by: str
      ngo_org: str | None = None
      location: str = ""
      description: str = ""
      photo_urls: list[str] = []
      created_at: datetime | None = None

  class NgoShareIn(BaseModel):
      ngo_org: str
      ngo_notes: str = ""
  ```

  b. Create `backend/app/api/ngo.py`:
  ```python
  from datetime import datetime, timezone
  from fastapi import APIRouter, Depends, HTTPException, status
  from motor.motor_asyncio import AsyncIOMotorDatabase
  from bson import ObjectId
  from ..deps import db_dep, require_ngo_or_above, current_user_dep
  from ..repositories.persons import PersonRepository
  from ..schemas.persons import SightingIn, SightingOut

  router = APIRouter(prefix="/ngo", tags=["ngo"])

  @router.get("/cases")
  async def ngo_cases(
      user: dict = Depends(require_ngo_or_above()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      """NGO workers see cases shared with their NGO; police/admin see all."""
      repo = PersonRepository(db)
      role = user.get("role")
      if role == "NGO_WORKER":
          ngo_org = user.get("ngo_org") or ""
          docs = await repo.list_persons_for_ngo(ngo_org)
      else:
          docs = await repo.list_persons()
      return [_ngo_case_out(d) for d in docs]

  @router.post("/sightings", response_model=SightingOut, status_code=201)
  async def submit_sighting(
      payload: SightingIn,
      user: dict = Depends(require_ngo_or_above()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      repo = PersonRepository(db)
      person = await repo.get_by_id(payload.person_id)
      if person is None:
          raise HTTPException(status_code=404, detail="Person not found")
      role = user.get("role")
      if role == "NGO_WORKER":
          ngo_org = user.get("ngo_org") or ""
          if ngo_org not in (person.get("shared_with_ngo") or []):
              raise HTTPException(status_code=403, detail="Case not shared with your NGO")
      doc = {
          "person_id": payload.person_id,
          "submitted_by": user["id"],
          "ngo_org": user.get("ngo_org"),
          "location": payload.location,
          "description": payload.description,
          "photo_urls": payload.photo_urls,
          "created_at": datetime.now(timezone.utc),
      }
      res = await db["ngo_sightings"].insert_one(doc)
      doc["id"] = str(res.inserted_id)
      doc.pop("_id", None)
      return doc

  @router.get("/activity")
  async def my_activity(
      user: dict = Depends(require_ngo_or_above()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      """Returns sightings submitted by this user."""
      cursor = db["ngo_sightings"].find({"submitted_by": user["id"]}).sort("created_at", -1).limit(100)
      out = []
      async for doc in cursor:
          doc["id"] = str(doc.pop("_id"))
          out.append(doc)
      return out

  def _ngo_case_out(doc: dict) -> dict:
      """Strip AI labels and sensitive recognition fields from NGO responses."""
      images = [
          {"id": img["id"], "url": f"/storage/{img['path']}",
           "is_primary": img.get("is_primary", False), "created_at": img.get("created_at")}
          for img in doc.get("images", [])
      ]
      return {
          "id": doc["id"],
          "full_name": doc["full_name"],
          "age": doc.get("age"),
          "gender": doc.get("gender"),
          "last_seen_location": doc.get("last_seen_location", ""),
          "last_seen_city": doc.get("last_seen_city", ""),
          "last_seen_state": doc.get("last_seen_state", ""),
          "date_last_seen": str(doc["date_last_seen"]) if doc.get("date_last_seen") else None,
          "description": doc.get("description", ""),
          "status": doc.get("status"),
          "images": images,
          "created_at": doc.get("created_at"),
          "ngo_notes": doc.get("ngo_notes", ""),
      }
  ```

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 13. **Add case-sharing endpoint for police/admin** — Police and admins can mark a missing-person case as shared with a specific NGO.

  Files: `backend/app/api/persons.py`

  Add to `persons.py`:
  ```python
  from ..schemas.persons import NgoShareIn

  @router.patch("/{person_id}/share-ngo", response_model=PersonOut)
  async def share_with_ngo(
      person_id: str,
      payload: NgoShareIn,
      user: dict = Depends(require_police_or_admin()),
      db: AsyncIOMotorDatabase = Depends(db_dep)
  ):
      repo = PersonRepository(db)
      doc = await repo.get_by_id(person_id)
      if doc is None:
          raise HTTPException(status_code=404, detail="Person not found")
      shared = doc.get("shared_with_ngo") or []
      if payload.ngo_org not in shared:
          shared.append(payload.ngo_org)
      patch = {"shared_with_ngo": shared}
      if payload.ngo_notes:
          patch["ngo_notes"] = payload.ngo_notes
      updated = await repo.update(person_id, patch)
      return _person_out(updated, role=user["role"])
  ```
  Also import `require_police_or_admin` from `..deps` at the top of `persons.py`.

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 14. **Update db.py ensure_indexes()** — Add indexes for the new fields and collections.

  Files: `backend/app/db.py`

  Add to `ensure_indexes()`:
  ```python
  await db["users"].create_index("role")
  await db["users"].create_index("approved")
  await db["missing_persons"].create_index("created_by")
  await db["missing_persons"].create_index("shared_with_ngo")
  await db["ngo_sightings"].create_index("person_id")
  await db["ngo_sightings"].create_index("submitted_by")
  await db["ngo_sightings"].create_index("created_at")
  ```

  Verify: `python -m pytest tests/ -v` — all existing tests pass.

---

- [ ] 15. **Register new routers in main.py** — Include `admin` and `ngo` routers.

  Files: `backend/app/main.py`

  Changes:
  - Add `from .api import admin, ngo` to the existing `from .api import ...` import line.
  - Add `app.include_router(admin.router, prefix=prefix)` and `app.include_router(ngo.router, prefix=prefix)` after the existing router registrations.

  Verify: `python -m pytest tests/ -v` — all existing tests pass (app still starts).

---

- [ ] 16. **Update auth_service.py login() to include approved/ngo_org in JWT and public_user()** — The token payload and the login response must carry `approved` so the frontend can show pending-approval screens without an extra API call.

  Files: `backend/app/services/auth_service.py`

  Changes:
  - In `login()`, update the `create_access_token` call to include `"approved": user.get("approved", False)` and `"ngo_org": user.get("ngo_org")` in the `extra` dict.
  - In `register()`, update the `create_access_token` call similarly (new users always get `approved=False`).
  - `public_user()` already includes `approved` and `ngo_org` after step 2; confirm it returns them.

  Verify: `python -m pytest tests/test_unit.py -v` — JWT roundtrip test still passes.

---

- [ ] 17. **Write the RBAC test suite** — Create `backend/tests/test_rbac.py` covering all 20 required cases. Use `mongomock-motor` and `httpx.AsyncClient` with the FastAPI app.

  Files: `backend/tests/test_rbac.py` (new file)

  Test cases (use `AsyncMongoMockClient` as the DB; override `get_db` via `app.dependency_overrides`):

  **Fixtures:**
  - `mock_db`: `AsyncMongoMockClient()["test_rbac"]` with indexes.
  - `client(mock_db)`: `httpx.AsyncClient(app=app, base_url="http://test")` with `get_db` overridden.
  - `citizen_token`: register a user (role forced to CITIZEN), login, return token.
  - `police_token_unapproved`: admin sets role to POLICE (approved=False), login, return token.
  - `police_token_approved`: admin approves the police user, login, return token.
  - `admin_token`: directly insert an ADMIN user into mock_db (bypassing register endpoint which clamps to CITIZEN), login, return token.
  - `ngo_token`: directly insert an NGO_WORKER user with `ngo_org="test_ngo"`, login, return token.

  **Tests (numbered to match the task requirements):**

  1. `test_citizen_cannot_list_registered_persons` — GET `/api/dataset/registered` with citizen token → 403.
  2. `test_citizen_cannot_get_registered_person` — GET `/api/dataset/registered/biswa` with citizen token → 403.
  3. `test_citizen_cannot_call_recognition_search` — POST `/api/recognition/search` with citizen token → 403.
  4. `test_citizen_cannot_call_recognition_availability` — GET `/api/recognition/availability` with citizen token → 403.
  5. `test_citizen_history_strips_predicted_label` — create a search record for the citizen in mock_db, then GET `/api/search-history` → 200, `predicted_label` is `None` in every item.
  6. `test_citizen_cannot_view_another_citizens_report` — create person owned by citizen A; GET `/api/persons/{id}` with citizen B's token → 403.
  7. `test_citizen_cannot_change_own_role` — PATCH `/api/auth/profile` with `{"role": "ADMIN"}` → role field ignored (profile update only allows first_name/last_name/email; the field is absent from `ProfileUpdateIn` so it is silently ignored; confirm the user's role remains CITIZEN after the call).
  8. `test_citizen_cannot_access_ngo_sightings_endpoint` — POST `/api/ngo/sightings` with citizen token → 403.
  9. `test_police_unapproved_cannot_access_recognition` — GET `/api/recognition/availability` with unapproved police token → 403.
  10. `test_police_approved_can_access_recognition` — GET `/api/recognition/availability` with approved police token → 200.
  11. `test_police_approved_can_list_registered_persons` — GET `/api/dataset/registered` with approved police token → 200.
  12. `test_admin_can_approve_police` — PATCH `/api/admin/users/{police_id}/approval` with `{"approved": true}` and admin token → 200, returned user has `approved: true`.
  13. `test_admin_can_change_user_role` — PATCH `/api/admin/users/{user_id}/role` with `{"role": "POLICE"}` and admin token → 200, returned user has `role: "POLICE"`.
  14. `test_citizen_cannot_promote_self` — POST `/api/admin/users/{own_id}/role` with citizen token → 403.
  15. `test_ngo_can_view_shared_case` — create person with `shared_with_ngo: ["test_ngo"]`; GET `/api/ngo/cases` with ngo_token → 200, case in list.
  16. `test_ngo_cannot_view_unshared_case` — create person with `shared_with_ngo: []`; GET `/api/ngo/cases` with ngo_token → 200, case NOT in list.
  17. `test_ngo_cannot_call_recognition` — GET `/api/recognition/availability` with ngo_token → 403.
  18. `test_ngo_cannot_access_registered_gallery` — GET `/api/dataset/registered` with ngo_token → 403.
  19. `test_ngo_can_submit_sighting_for_shared_case` — submit sighting for shared case with ngo_token → 201.
  20. `test_existing_auth_and_report_submission_still_work` — register (→ CITIZEN), login, POST `/api/persons` → 201. Confirm CITIZEN role. Confirm existing test_unit tests still pass.

  The test file must import the FastAPI `app` object and use `app.dependency_overrides[get_db] = lambda: mock_db` to inject the mock DB. Import `get_db` from `app.db`.

  Verify: `python -m pytest tests/test_rbac.py -v` — all 20 tests pass.

---

- [ ] 18. **Update AuthContext.jsx — add role helpers and approved field** — The frontend needs role-aware helpers to conditionally render navigation and guard routes.

  Files: `frontend/src/context/AuthContext.jsx`

  Changes:
  - Add role helper functions exported from the context value:
    ```javascript
    const isAdmin = useCallback(() => user?.role === 'ADMIN', [user]);
    const isPolice = useCallback(() => user?.role === 'POLICE', [user]);
    const isCitizen = useCallback(() => user?.role === 'CITIZEN', [user]);
    const isNGO = useCallback(() => user?.role === 'NGO_WORKER', [user]);
    const isPoliceApproved = useCallback(() => user?.role === 'POLICE' && user?.approved === true, [user]);
    const isPoliceOrAdmin = useCallback(() => ['POLICE', 'ADMIN'].includes(user?.role), [user]);
    ```
  - Add them to the `AuthContext.Provider value` object.
  - In the `login` and `register` callbacks, the `user` object returned from the API now includes `approved` and `ngo_org` — store them as-is (no change needed since the whole `res.data.user` is stored).

  Verify: No build step needed yet; will be verified when frontend is built in step 23.

---

- [ ] 19. **Create RoleRoute component** — A new gating component that wraps `ProtectedRoute` and additionally checks the user's role. Redirects to `/unauthorized` when the role requirement is not met.

  Files: `frontend/src/components/RoleRoute.jsx` (new file)

  ```jsx
  import { Navigate, useLocation } from 'react-router-dom';
  import { useAuth } from '../context/AuthContext';

  /**
   * RoleRoute({ allowedRoles: string[], children })
   * Renders children only if user.role is in allowedRoles.
   * Redirects to /pending-approval if police and not approved.
   * Redirects to /unauthorized otherwise.
   */
  export default function RoleRoute({ allowedRoles, children }) {
    const { user, loading } = useAuth();
    const location = useLocation();
    if (loading) return <div className="center-page">Loading…</div>;
    if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
    if (user.role === 'POLICE' && !user.approved && allowedRoles.includes('POLICE')) {
      return <Navigate to="/pending-approval" replace />;
    }
    if (!allowedRoles.includes(user.role)) {
      return <Navigate to="/unauthorized" replace />;
    }
    return children;
  }
  ```

  Verify: Will be verified in step 23 with the full frontend build.

---

- [ ] 20. **Create placeholder pages: Unauthorized.jsx and PendingApproval.jsx**

  Files:
  - `frontend/src/pages/Unauthorized.jsx` (new file)
  - `frontend/src/pages/PendingApproval.jsx` (new file)

  `Unauthorized.jsx`:
  ```jsx
  import { Link } from 'react-router-dom';

  export default function Unauthorized() {
    return (
      <div className="center-page">
        <h2>Access Denied</h2>
        <p className="muted">You do not have permission to view this page.</p>
        <Link to="/dashboard">← Back to Dashboard</Link>
      </div>
    );
  }
  ```

  `PendingApproval.jsx`:
  ```jsx
  import { useAuth } from '../context/AuthContext';

  export default function PendingApproval() {
    const { logout } = useAuth();
    return (
      <div className="center-page">
        <h2>Account Pending Approval</h2>
        <p className="muted">
          Your police account is awaiting administrator approval.
          You will be able to access the system once an administrator approves your account.
        </p>
        <button className="btn btn-ghost" onClick={logout}>Logout</button>
      </div>
    );
  }
  ```

  Verify: Will be verified in step 23.

---

- [ ] 21. **Create role-specific dashboard pages: AdminDashboard.jsx, PoliceDashboard.jsx, NGODashboard.jsx, CitizenDashboard.jsx**

  Files:
  - `frontend/src/pages/AdminDashboard.jsx` (new file)
  - `frontend/src/pages/PoliceDashboard.jsx` (new file)
  - `frontend/src/pages/NGODashboard.jsx` (new file)
  - `frontend/src/pages/CitizenDashboard.jsx` (new file)

  Each dashboard shows role-appropriate stats and links. Do not call `/recognition/availability` or any police-only endpoint from citizen or NGO dashboards.

  `AdminDashboard.jsx` — links to User Management (`/admin/users`), Police Approvals (`/admin/approvals`), Registered Persons (`/dataset`), and System Stats. Calls `GET /api/admin/users` to show pending police approvals count.

  `PoliceDashboard.jsx` — shows recognition model availability (calls `GET /api/recognition/availability`), links to Missing-Person Reports, Registered Persons, AI Recognition Search, Investigation History.

  `NGODashboard.jsx` — shows assigned cases count (calls `GET /api/ngo/cases`), links to Assigned Cases, Submit Sighting, Relief Coordination (placeholder), My Activity.

  `CitizenDashboard.jsx` — shows own report count (calls `GET /api/persons` which returns only the citizen's own reports), links to Report Missing Person (`/persons/new`), My Reports (`/persons`), Profile. Does NOT call `/recognition/availability`.

  Verify: Will be verified in step 23.

---

- [ ] 22. **Update Dashboard.jsx to dispatch to the role-specific dashboard**

  Files: `frontend/src/pages/Dashboard.jsx`

  Replace the entire page body with a role dispatcher:
  ```jsx
  import { useAuth } from '../context/AuthContext';
  import AdminDashboard from './AdminDashboard';
  import PoliceDashboard from './PoliceDashboard';
  import NGODashboard from './NGODashboard';
  import CitizenDashboard from './CitizenDashboard';

  export default function Dashboard() {
    const { user } = useAuth();
    if (user?.role === 'ADMIN') return <AdminDashboard />;
    if (user?.role === 'POLICE') return <PoliceDashboard />;
    if (user?.role === 'NGO_WORKER') return <NGODashboard />;
    return <CitizenDashboard />;
  }
  ```

  This means citizens no longer call `/recognition/availability` on dashboard load (the call lives only in `PoliceDashboard.jsx`), which eliminates the 403 citizens would get after step 4.

  Verify: Will be verified in step 23.

---

- [ ] 23. **Update Layout.jsx — role-based navigation**

  Files: `frontend/src/components/Layout.jsx`

  Replace the single hardcoded nav with a role-conditional nav:

  ```jsx
  import { Link, NavLink, useNavigate } from 'react-router-dom';
  import { useAuth } from '../context/AuthContext';

  function CitizenNav() {
    return (
      <>
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/persons/new">Report Missing Person</NavLink>
        <NavLink to="/persons">My Reports</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </>
    );
  }

  function PoliceNav() {
    return (
      <>
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/persons">Missing-Person Reports</NavLink>
        <NavLink to="/dataset">Registered Persons</NavLink>
        <NavLink to="/search">AI Recognition Search</NavLink>
        <NavLink to="/history">Investigation History</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </>
    );
  }

  function AdminNav() {
    return (
      <>
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/admin/users">User Management</NavLink>
        <NavLink to="/admin/approvals">Police Approvals</NavLink>
        <NavLink to="/dataset">Registered Persons</NavLink>
        <NavLink to="/admin/dataset">Dataset Management</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </>
    );
  }

  function NGONav() {
    return (
      <>
        <NavLink to="/dashboard">Dashboard</NavLink>
        <NavLink to="/ngo/cases">Assigned Cases</NavLink>
        <NavLink to="/ngo/shared">Shared Missing-Person Cases</NavLink>
        <NavLink to="/ngo/sighting">Submit Sighting</NavLink>
        <NavLink to="/ngo/activity">My Activity</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </>
    );
  }

  export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const onLogout = async () => { await logout(); navigate('/login'); };
    const NavItems = !user ? null
      : user.role === 'ADMIN' ? AdminNav
      : user.role === 'POLICE' ? PoliceNav
      : user.role === 'NGO_WORKER' ? NGONav
      : CitizenNav;

    return (
      <div className="app">
        <header className="topbar">
          <Link to={user ? '/dashboard' : '/'} className="brand">
            <span className="brand-mark">◉</span> Missing Person AI
          </Link>
          <nav className="nav">
            {user ? (
              <>
                {NavItems && <NavItems />}
                <span className="nav-user">{user.username} · {user.role}</span>
                <button className="btn btn-ghost" onClick={onLogout}>Logout</button>
              </>
            ) : (
              <>
                <NavLink to="/login">Login</NavLink>
                <NavLink to="/register" className="btn btn-primary">Register</NavLink>
              </>
            )}
          </nav>
        </header>
        <main className="content">{children}</main>
        <footer className="footer">AI-Powered Missing Person Identification · CNN · ArcFace · MediaPipe + KNN</footer>
      </div>
    );
  }
  ```

  Verify: Will be verified in step 23.

---

- [ ] 24. **Update Search.jsx — gate behind police/admin role**

  Files: `frontend/src/pages/Search.jsx`

  Add at the top of `Search()`:
  ```jsx
  import { useAuth } from '../context/AuthContext';
  // ...
  const { user } = useAuth();
  if (!['POLICE', 'ADMIN'].includes(user?.role)) {
    return (
      <div className="card">
        <h2>Recognition Search</h2>
        <p className="muted">AI recognition search is available to authorized personnel only.</p>
      </div>
    );
  }
  ```

  Note: the route will also be wrapped in `RoleRoute` in `App.jsx` (step 26), making this a belt-and-suspenders check.

  Verify: Will be verified in step 26 via build.

---

- [ ] 25. **Update SearchHistory.jsx and SearchDetail.jsx — strip sensitive fields for citizens**

  Files:
  - `frontend/src/pages/SearchHistory.jsx`
  - `frontend/src/pages/SearchDetail.jsx`

  `SearchHistory.jsx`:
  - Import `useAuth`, get `user`.
  - If `user?.role` is `CITIZEN` or `NGO_WORKER`, the backend already strips `predicted_label` and `person_id` (step 6), so the table just renders them as `—`. No additional change needed beyond noting the backend handles this — but add a conditional message for citizens: "Only recognition history relevant to your reports is shown."

  `SearchDetail.jsx`:
  - Import `useAuth`, get `user`.
  - If `user?.role` is `CITIZEN` or `NGO_WORKER`, hide `registered_match`, `registered_person_id`, `source_photo_url`, and the ArcFace/CNN gallery sections. Show only: model name, status badge, and the safe explanation from the backend ("Your report has been submitted. Authorized personnel can review it.").
  - Add this as a conditional render around the sensitive JSX blocks: `{['POLICE', 'ADMIN'].includes(user?.role) && ( ... )}`.

  Verify: Will be verified in step 26 via build.

---

- [ ] 26. **Update PersonDetails.jsx — hide AI labels for citizens and NGO workers**

  Files: `frontend/src/pages/PersonDetails.jsx`

  Changes:
  - Import `useAuth`, get `user`.
  - In the image figcaption, wrap the AI label display in `{['POLICE', 'ADMIN'].includes(user?.role) && ( ... )}`.
  - Hide the Archive button for citizens who don't own the record: add `{(user?.role !== 'CITIZEN' || person.created_by === user?.id) && <button ...>Archive</button>}`. (The backend enforces this too; this is UI hygiene.)
  - Hide the Edit button similarly for NGO workers.

  Verify: Will be verified in step 26 via build.

---

- [ ] 27. **Update App.jsx — add new routes and RoleRoute wrappers**

  Files: `frontend/src/App.jsx`

  Changes:
  - Import `RoleRoute`, `Unauthorized`, `PendingApproval`, and all new page components.
  - Add new routes:
    ```jsx
    <Route path="/unauthorized" element={<Unauthorized />} />
    <Route path="/pending-approval" element={<PendingApproval />} />
    <Route path="/search" element={
      <RoleRoute allowedRoles={['POLICE', 'ADMIN']}>
        <Search />
      </RoleRoute>
    } />
    <Route path="/history" element={
      <RoleRoute allowedRoles={['POLICE', 'ADMIN', 'CITIZEN', 'NGO_WORKER']}>
        <SearchHistory />
      </RoleRoute>
    } />
    <Route path="/history/:id" element={
      <RoleRoute allowedRoles={['POLICE', 'ADMIN', 'CITIZEN', 'NGO_WORKER']}>
        <SearchDetail />
      </RoleRoute>
    } />
    <Route path="/dataset" element={
      <RoleRoute allowedRoles={['POLICE', 'ADMIN']}>
        <DatasetPage />
      </RoleRoute>
    } />
    <Route path="/admin/users" element={
      <RoleRoute allowedRoles={['ADMIN']}>
        <AdminUsers />
      </RoleRoute>
    } />
    <Route path="/admin/approvals" element={
      <RoleRoute allowedRoles={['ADMIN']}>
        <AdminApprovals />
      </RoleRoute>
    } />
    <Route path="/admin/dataset" element={
      <RoleRoute allowedRoles={['ADMIN']}>
        <AdminDataset />
      </RoleRoute>
    } />
    <Route path="/ngo/cases" element={
      <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
        <NGOCases />
      </RoleRoute>
    } />
    <Route path="/ngo/sighting" element={
      <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
        <SubmitSighting />
      </RoleRoute>
    } />
    <Route path="/ngo/activity" element={
      <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
        <NGOActivity />
      </RoleRoute>
    } />
    <Route path="/ngo/shared" element={
      <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
        <NGOCases />
      </RoleRoute>
    } />
    ```
  - Keep the existing `/search`, `/history`, `/history/:id` routes but replace `ProtectedRoute` with `RoleRoute` as shown above. Remove the old `ProtectedRoute`-wrapped versions of these routes.

  Verify: Will be verified in step 28 via build.

---

- [ ] 28. **Create admin and NGO frontend pages**

  Files (all new):
  - `frontend/src/pages/AdminUsers.jsx` — table of all users from `GET /api/admin/users`; inline buttons to change role and approve/revoke police accounts.
  - `frontend/src/pages/AdminApprovals.jsx` — filtered view of AdminUsers showing only POLICE accounts with `approved: false`; approve button calls `PATCH /api/admin/users/{id}/approval`.
  - `frontend/src/pages/AdminDataset.jsx` — trigger dataset import via `POST /api/dataset/import`; show import result.
  - `frontend/src/pages/NGOCases.jsx` — list cases from `GET /api/ngo/cases`; each row links to the person detail page; no AI labels shown.
  - `frontend/src/pages/SubmitSighting.jsx` — form to POST `/api/ngo/sightings`; fields: person_id (searchable), location, description.
  - `frontend/src/pages/NGOActivity.jsx` — list sightings from `GET /api/ngo/activity`.
  - `frontend/src/api/admin.js` — thin wrappers: `listUsers()`, `changeRole(userId, role)`, `setApproval(userId, approved)`, `promoteAdmin(userId)`.
  - `frontend/src/api/ngo.js` — thin wrappers: `listCases()`, `submitSighting(payload)`, `getActivity()`.

  Each page should follow the same pattern as existing pages (useState + useEffect + api.get/post + error display).

  Verify: `cd frontend && npm run build` — build succeeds with no errors.

---

- [ ] 29. **Update Register.jsx — remove role selection field**

  Files: `frontend/src/pages/Register.jsx`

  The registration form must not offer a `role` dropdown. Read the current file first; if there is a role selector, remove it. The backend now ignores any `role` in the request and always creates CITIZEN — the UI should match by not sending it either.

  Verify: `cd frontend && npm run build` — build succeeds.

---

- [ ] 30. **Run the full backend RBAC test suite and confirm all 20 tests pass**

  Command (run from `backend/` directory):
  ```
  python -m pytest tests/test_rbac.py -v
  ```

  All 20 tests must pass. If any fail, fix the underlying backend code before continuing.

  Then run the full test suite to confirm nothing was broken:
  ```
  python -m pytest tests/ -v
  ```

  All existing tests (test_unit.py + test_pipeline.py) must continue to pass. Note: test_pipeline.py depends on the original mpp dataset files being present on disk; if they are absent in the test environment, those tests will be skipped or fail for a separate reason — that is pre-existing behavior and not an RBAC regression.

  Verify: Exit code 0 from `python -m pytest tests/test_rbac.py -v`.

---

- [ ] 31. **Write RBAC_SETUP.md** — Operational documentation explaining how to bootstrap the first admin, approve a police account, and test each role.

  Files: `RBAC_SETUP.md` (project root)

  Must cover:

  **Creating the first admin:**
  1. Register a normal account via the UI or API (becomes CITIZEN by design).
  2. Use the MongoDB shell or a one-off script to set `role: "ADMIN"` and `approved: true` directly on that user document:
     ```javascript
     db.users.updateOne({ username: "yourname" }, { $set: { role: "ADMIN", approved: true } })
     ```
  3. Log out and log back in — the JWT will now carry `role: "ADMIN"`.

  **Approving a police account:**
  1. Have the user register normally (they become CITIZEN).
  2. An admin uses `PATCH /api/admin/users/{id}/role` with `{"role": "POLICE"}`.
  3. An admin uses `PATCH /api/admin/users/{id}/approval` with `{"approved": true}`.
  4. The user logs out and back in — their JWT now carries `role: "POLICE"` and `approved: true`.

  **Testing the citizen interface:**
  - Register a new account. Log in. Confirm: Dashboard shows CitizenDashboard; the nav shows only Dashboard, Report Missing Person, My Reports, Profile, Logout. Attempting to navigate to `/search` redirects to `/unauthorized`.

  **Testing the police interface:**
  - Register + admin promotes to POLICE + admin approves. Log in. Confirm: Dashboard shows PoliceDashboard with model availability; nav shows AI Recognition Search, Registered Persons, etc.

  **Testing the NGO interface:**
  - Register + admin promotes to NGO_WORKER + admin sets `ngo_org`. Log in. Confirm: NGO dashboard shown; cannot access `/search` or `/dataset`.

  **Running the test suite:**
  ```
  cd backend
  python -m pytest tests/test_rbac.py -v
  python -m pytest tests/ -v
  ```

  Verify: File exists and is readable at `RBAC_SETUP.md`.

---

## Dependency Order Summary

```
Step 1 (schema) → Step 2 (auth_service) → Step 3 (deps)
→ Step 4 (recognition guards) → Step 5 (dataset guards)
→ Step 6 (history guards) → Step 7 (persons guards)
→ Step 8 (images guards) → Step 9 (PersonRepository methods)  [steps 7+9 together]
→ Step 10 (users.py) → Step 11 (admin router) → Step 12 (ngo router)
→ Step 13 (share-ngo endpoint) → Step 14 (db indexes) → Step 15 (main.py)
→ Step 16 (auth_service login JWT update) → Step 17 (RBAC tests)
→ Step 18 (AuthContext) → Step 19 (RoleRoute) → Step 20 (Unauthorized/Pending pages)
→ Step 21 (role dashboards) → Step 22 (Dashboard dispatcher)
→ Step 23 (Layout nav) → Step 24 (Search gate) → Step 25 (History/Detail strip)
→ Step 26 (PersonDetails) → Step 27 (App.jsx routes) → Step 28 (admin+NGO pages)
→ Step 29 (Register.jsx)
→ Step 30 (run tests) → Step 31 (docs)
```

Steps 7 and 9 must be done together since persons.py calls repository methods added in step 9.
Steps 11, 12, 13 are independent of each other but all depend on step 3.
Frontend steps 18–29 are independent of each other but all depend on backend steps being complete.
