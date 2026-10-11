# Missing Person AI — FastAPI Backend

Production-style API around the three ORIGINAL, read-only AI approaches
(CNN, ArcFace, MediaPipe + KNN). Nothing here retrains, modifies, or
regenerates the AI artifacts.

## AI integration (read-only)

Adapters in `app/ai/adapters/` load the ORIGINAL artifacts **read-only**
from `MPP_ORIGINAL_ROOT` (default `C:/Users/shrut_hi39oyy/Downloads/mpp/mpp`):

| Model | Artifacts used | Status |
|---|---|---|
| CNN (authoritative embedding pipeline) | `models/cnn_face_embedding_model.keras`, `models/cnn_embedding_knn.joblib`, `models/cnn_embedding_labels.npy` (22-class), `data/cnn_features/cnn_train_{embeddings,labels}.npy` | runs |
| ArcFace | `data/arcface_features/{X,y}.npy` + InsightFace `buffalo_l/w600k_r50.onnx` cache | runs |
| MediaPipe + KNN | requires `models/face_landmarker.task` | **BLOCKED — asset absent; adapter reports `model_unavailable`, never substitutes** |

Legacy files (`cnn_face_model.keras`, `cnn_labels.npy`, `arcface_knn.joblib`)
are intentionally NOT used. Check `GET /api/recognition/availability`
for live per-model status.

## How a query links to a registered person

Each AI model predicts its own label from its own ORIGINAL gallery.
A query links to a person when the **same original model** predicts the
**same label** for the query and for one of that person's reference
photos (photos are tagged by the original models at upload time and the
tags are stored verbatim on the photo record). Fallback: exact
name match. Nothing is ever forced — no linked record means
`match_found: false` with the raw model prediction still shown.

Adapters are process-wide singletons (`app/ai/registry.py`), so heavy
models load once; inference is serialized per adapter. First request
after startup is slow (model load), later ones are fast.

## The searched dataset (mpp/data)

Searches run against the ORIGINAL dataset under `MPP_ORIGINAL_ROOT/data`
(1,139 CNN photos / 22 people; 1,878 ArcFace photos / 21 people —
see `GET /api/dataset/info`). Each result carries the model's own
per-photo ranking exactly as the original scripts print it:
- CNN `detail.top_images`: rank + label + cosine similarity per training
  photo (the original CNN index stores no source file per row, so none
  is attached — nothing guessed).
- ArcFace `detail.top_matches`: rank + label + similarity + `photo_id`,
  resolved from the ORIGINAL `paths.npy` (1:1 with feature rows).
- `GET /api/dataset/photo?model=arcface&index=N` serves that original
  dataset photo read-only (index only, containment-enforced, auth
  required). The frontend shows these thumbnails under each result.

## Run

Requirements: Python 3.12+, MongoDB running on `MONGODB_URL`.

```bat
cd backend
..\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
REM edit .env: set JWT_SECRET_KEY and MONGODB_URL
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/healthz` (reports MongoDB reachability)

## Importing data/registered/ into MongoDB (required once)

The recognition gallery on disk (`MPP_ORIGINAL_ROOT/data/registered/`,
20 identities / 1872 photos) must be mirrored into MongoDB
(`registered_persons` + `registered_images`) before matches can link.
Idempotent and additive-only — re-runs create nothing new and never touch
users, missing persons, or history. Original files stay on disk untouched.

```bat
cd backend
..\.venv\Scripts\python.exe -m app.import_command
```

or with the server running (any logged-in user):

    POST /api/dataset/import

Verify: `GET /api/dataset/registered` (20 records), each result then
carries `registered_match` + `registered_person_id` + one backend-written
`explanation` that the UI displays verbatim — prediction, gallery match,
and record link can never contradict each other.

## API groups

| Group | Examples |
|---|---|
| `/api/auth/` | `POST register`, `POST login`, `GET/PATCH profile`, `POST logout` |
| `/api/users/` | `GET me`, `GET` (admin) |
| `/api/persons/` | `POST/GET`, `GET/PUT/DELETE /{id}` (delete = archive) |
| `/api/images/` | `POST /persons/{id}` multiple reference photos |
| `/api/recognition/` | `GET /availability`, `POST /search` (`model=cnn\|arcface\|mediapipe_knn\|all`) |
| `/api/search-history/` | `GET`, `GET /{id}` |

## Tests

```bat
..\.venv\Scripts\python.exe -m pytest tests/ -q
```

Unit tests need no MongoDB. The legacy Django prototype is preserved
untouched at `../legacy_backend_django/` for reference.
