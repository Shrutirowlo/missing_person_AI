"""
test_api_endpoints.py
Automated end-to-end integration test for the Missing Person AI Backend.
Tests:
1. Authentication & JWT Tokens
2. Police Station / NGO Registry API
3. Case creation & photo upload
4. 3-Model Comparative AI Search (ArcFace + CNN + MediaPipe)
5. Analytics & Dashboard Summary
"""
import os
import sys
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import cv2
import numpy as np
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from stations.models import Station
from accounts.models import User
from cases.models import MissingPerson, PersonPhoto
from ai_engine.comparative_matcher import ComparativeMatcher
from ai_engine.feature_store import FeatureStore

def create_dummy_face_image(name="test_face.jpg", size=(200, 200)):
    """Creates a valid RGB face-like image for testing."""
    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    # Background
    img[:] = (220, 220, 220)
    # Head ellipse
    cv2.ellipse(img, (size[0]//2, size[1]//2), (60, 80), 0, 0, 360, (180, 150, 130), -1)
    # Eyes
    cv2.circle(img, (size[0]//2 - 25, size[1]//2 - 20), 8, (50, 50, 50), -1)
    cv2.circle(img, (size[0]//2 + 25, size[1]//2 - 20), 8, (50, 50, 50), -1)
    # Nose
    cv2.ellipse(img, (size[0]//2, size[1]//2 + 5), (6, 12), 0, 0, 360, (140, 110, 90), -1)
    # Mouth
    cv2.ellipse(img, (size[0]//2, size[1]//2 + 35), (20, 8), 0, 0, 360, (100, 50, 50), -1)
    
    _, buffer = cv2.imencode('.jpg', img)
    return SimpleUploadedFile(name, buffer.tobytes(), content_type='image/jpeg')

def run_tests():
    print("=" * 70)
    print("RUNNING MISSING PERSON AI BACKEND INTEGRATION TESTS")
    print("=" * 70)

    client = APIClient()

    # 1. Test Station Endpoints
    print("\n[TEST 1] Testing Stations API...")
    res = client.get('/api/stations/')
    assert res.status_code == 200, f"Failed: {res.status_code}"
    print(f"  [OK] GET /api/stations/ returned {res.status_code} with {len(res.data.get('results', res.data))} stations")

    # 2. Test User Registration & Login
    print("\n[TEST 2] Testing Auth & JWT Tokens...")
    reg_data = {
        'username': 'tester_officer',
        'email': 'tester@police.gov.in',
        'password': 'SecureTestPassword123',
        'role': 'POLICE_OFFICER',
        'badge_number': 'TEST-9988'
    }
    User.objects.filter(username='tester_officer').delete()
    res = client.post('/api/auth/register/', reg_data, format='json')
    assert res.status_code == 201, f"Registration failed: {res.status_code} - {res.data}"
    print(f"  [OK] POST /api/auth/register/ -> User registered successfully (ID: {res.data['id']})")

    login_res = client.post('/api/auth/login/', {
        'username': 'tester_officer',
        'password': 'SecureTestPassword123'
    }, format='json')
    assert login_res.status_code == 200, f"Login failed: {login_res.status_code}"
    token = login_res.data['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    print(f"  [OK] POST /api/auth/login/ -> Obtained JWT Access Token successfully")

    profile_res = client.get('/api/auth/profile/')
    assert profile_res.status_code == 200
    print(f"  [OK] GET /api/auth/profile/ -> Verified profile: {profile_res.data['username']} ({profile_res.data['role']})")

    # 3. Test Case Creation with Image
    print("\n[TEST 3] Testing Missing Person Case Creation & Vector Extraction...")
    station = Station.objects.first()
    test_photo = create_dummy_face_image("target_case_face.jpg")
    case_data = {
        'full_name': 'Aarav Sharma',
        'alias_name': 'Sonu',
        'case_type': 'MISSING_PERSON',
        'status': 'ACTIVE',
        'age': 16,
        'gender': 'MALE',
        'last_seen_location': 'Connaught Place Metro Station',
        'last_seen_city': 'New Delhi',
        'last_seen_state': 'Delhi',
        'physical_description': 'Wearing blue denim jacket and black sneakers.',
        'reporting_station': station.id if station else None,
        'photo': test_photo,
    }
    case_res = client.post('/api/cases/', case_data, format='multipart')
    assert case_res.status_code == 201, f"Case creation failed: {case_res.status_code} - {case_res.data}"
    case_id = case_res.data['id']
    print(f"  [OK] POST /api/cases/ -> Case Created successfully: Case ID [{case_res.data['case_id']}] {case_res.data['full_name']}")

    # Check case detail
    detail_res = client.get(f'/api/cases/{case_id}/')
    assert detail_res.status_code == 200
    assert len(detail_res.data['photos']) >= 1, "Photo was not attached"
    print(f"  [OK] GET /api/cases/{case_id}/ -> Retrieved case detail with {len(detail_res.data['photos'])} attached photos")

    # 4. Test 3-Model Comparative AI Search
    print("\n[TEST 4] Testing Comparative AI Search Endpoint (/api/match/search/)...")
    query_photo = create_dummy_face_image("query_search_face.jpg")
    search_res = client.post('/api/match/search/', {'image': query_photo}, format='multipart')
    assert search_res.status_code == 200, f"Search failed: {search_res.status_code} - {search_res.data}"
    
    data = search_res.data
    print(f"  [OK] POST /api/match/search/ Execution Succeeded!")
    print(f"    - Verdict: {data.get('verdict')}")
    print(f"    - Consensus Confidence: {data.get('consensus_confidence')}%")
    print(f"    - Inference Time: {data.get('execution_time_ms')} ms")
    
    breakdown = data.get('comparative_breakdown', {})
    print("    - Side-by-Side Model Breakdown:")
    for key, model_info in breakdown.items():
        print(f"      * {model_info.get('model_name')}: {model_info.get('score_percentage')}% ({model_info.get('status')})")

    print(f"    - Ranked Candidates Found: {len(data.get('candidate_matches', []))}")

    # 5. Test Analytics API
    print("\n[TEST 5] Testing Analytics & Dashboard Endpoint...")
    analytics_res = client.get('/api/analytics/summary/')
    assert analytics_res.status_code == 200
    overview = analytics_res.data.get('overview', {})
    print(f"  [OK] GET /api/analytics/summary/ -> Total Cases: {overview.get('total_cases')}, Active: {overview.get('active_cases')}, Branches: {analytics_res.data.get('network_branches', {}).get('total_branches')}")

    print("\n" + "=" * 70)
    print("ALL INTEGRATION TESTS COMPLETED SUCCESSFULLY! [100% PASS]")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
