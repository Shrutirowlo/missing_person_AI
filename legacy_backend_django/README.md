# Missing Person AI Backend API Documentation

A high-performance Django REST Framework backend integrating a **3-model comparative face recognition system** (**ArcFace**, **CNN**, and **MediaPipe**) designed for Police Stations, NGOs, and Citizen portals.

---

## 🚀 Quick Start

### 1. Run Migrations & Seed Sample Data
```bash
cd backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py seed_demo_data
```

### 2. Start the Backend Server
```bash
..\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```
- **Admin Panel**: `http://127.0.0.1:8000/admin/`
  - Username: `admin` | Password: `admin123password`
- **Police Officer Demo**:
  - Username: `officer_rajesh` | Password: `policepassword123`
- **NGO Worker Demo**:
  - Username: `ngo_ananya` | Password: `ngopassword123`

### 3. Run Automated Integration Test Suite
```bash
..\.venv\Scripts\python.exe test_api_endpoints.py
```

---

## 📡 REST API Reference

### 1. Authentication (`/api/auth/`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Register new user (Police Officer / NGO Worker / Citizen) |
| `POST` | `/api/auth/login/` | Obtain JWT Access and Refresh Tokens |
| `POST` | `/api/auth/refresh/` | Refresh expired access token |
| `GET` | `/api/auth/profile/` | Fetch current logged-in user profile & station |

---

### 2. Multi-Branch Station Registry (`/api/stations/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stations/` | List all registered Police Stations and NGO shelters (supports `?state=`, `?city=`, `?branch_type=`) |
| `POST` | `/api/stations/` | Register a new station / branch |
| `GET` | `/api/stations/<id>/` | View station details and total cases |

---

### 3. Missing Person Cases (`/api/cases/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/cases/` | Search & filter missing cases (`?status=ACTIVE`, `?gender=MALE`, `?case_type=MISSING_PERSON`) |
| `POST` | `/api/cases/` | Create a missing person case (supports multipart photo upload, triggers auto-indexing) |
| `GET` | `/api/cases/<id>/` | View full case record, all attached photos, and face crops |
| `PATCH` | `/api/cases/<id>/` | Update case status (e.g. mark as `FOUND` or `RESOLVED`) |
| `POST` | `/api/cases/<id>/photos/` | Attach additional photos to existing case |
| `POST` | `/api/cases/reindex/` | Re-synchronize in-memory embedding cache across all cases |

---

### 4. 3-Model Comparative AI Search (`/api/match/`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/match/search/` | Upload query image; runs **ArcFace**, **CNN**, and **MediaPipe** concurrently; returns side-by-side comparative score matrix and ranked candidate matches |
| `GET` | `/api/match/history/` | View search audit history across branches |
| `GET` | `/api/match/history/<id>/` | View specific search query result and crop |

#### Example Search Response:
```json
{
  "status": "SUCCESS",
  "verdict": "MATCH FOUND",
  "confidence_tier": "HIGH",
  "consensus_confidence": 76.14,
  "execution_time_ms": 1580,
  "comparative_breakdown": {
    "arcface": {
      "model_name": "ArcFace Buffalo_L (Deep Angular Margin)",
      "score_percentage": 99.9,
      "raw_similarity": 0.884,
      "predicted_person": "Biswa",
      "status": "HIGH_CONFIDENCE"
    },
    "cnn": {
      "model_name": "Deep Face CNN (Convolutional Feature Extractor)",
      "score_percentage": 70.5,
      "raw_similarity": 0.582,
      "predicted_person": "Biswa",
      "status": "MODERATE_CONFIDENCE"
    },
    "mediapipe": {
      "model_name": "MediaPipe Facial Mesh (478-Point 3D Geometry)",
      "score_percentage": 99.0,
      "raw_similarity": 0.941,
      "predicted_person": "Biswa",
      "status": "HIGH_CONFIDENCE"
    }
  },
  "candidate_matches": [
    {
      "case_id": "FIR-2026-1002",
      "name": "Biswa",
      "scores": {
        "arcface_pct": 99.9,
        "cnn_pct": 70.5,
        "mediapipe_pct": 99.0,
        "consensus_pct": 76.14
      }
    }
  ]
}
```

---

### 5. Analytics & Dashboard (`/api/analytics/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analytics/summary/` | Aggregate system metrics (total cases, resolution rates, model accuracy averages, active branches) |
