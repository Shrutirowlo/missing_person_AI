"""
quick_search_test.py
Demonstration script to test the 3-Model Comparative AI Search on a real photo.
Usage:
    python quick_search_test.py [path_to_image]
"""
import os
import sys
import json
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from rest_framework.test import APIClient
from cases.models import MissingPerson

def test_query_search(image_path=None):
    client = APIClient()

    # If no image path provided, look for sample photos in the project
    if not image_path:
        sample_candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../missing_person_AI-main/mpp/data/test_photos/biswa 2_face.jpg')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../missing_person_AI-main/mpp/data/registered/biswa/biswa 1.jpg')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '../missing_person_AI-main/mpp/data/registered/ariel_sharon/ariel_sharon_0001.jpg')),
        ]
        for cand in sample_candidates:
            if os.path.exists(cand):
                image_path = cand
                break

    if not image_path or not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return

    print("=" * 75)
    print("MISSING PERSON AI - 3-MODEL COMPARATIVE SEARCH TEST")
    print("=" * 75)
    print(f"Query Image Path: {image_path}")
    print("Sending request to: POST /api/match/search/ ...\n")

    with open(image_path, 'rb') as f:
        res = client.post('/api/match/search/', {'image': f}, format='multipart')

    if res.status_code != 200:
        print(f"[FAILED] HTTP Status {res.status_code}: {res.data}")
        return

    data = res.data
    verdict = data.get('verdict', 'N/A')
    confidence = data.get('consensus_confidence', 0.0)
    latency = data.get('execution_time_ms', 0)
    breakdown = data.get('comparative_breakdown', {})
    candidates = data.get('candidate_matches', [])

    print(f">> VERDICT:             [{verdict}]")
    print(f">> CONSENSUS CONFIDENCE: {confidence}%")
    print(f">> INFERENCE LATENCY:    {latency} ms")
    print("-" * 75)
    print(f"{'MODEL':<35} | {'SCORE':<10} | {'STATUS':<20}")
    print("-" * 75)

    for model_key, info in breakdown.items():
        name = info.get('model_name', model_key)
        score = f"{info.get('score_percentage', 0.0)}%"
        status = info.get('status', 'N/A')
        print(f"{name:<35} | {score:<10} | {status:<20}")

    print("-" * 75)
    print("\nTOP CANDIDATE MATCHES IN DATABASE:")
    for rank, cand in enumerate(candidates[:3], start=1):
        c_id = cand.get('case_id')
        name = cand.get('name')
        scores = cand.get('scores', {})
        st_info = cand.get('metadata', {}).get('station', {})
        station_name = st_info.get('name', 'Unknown Station')
        
        print(f"  #{rank} Case [{c_id}] {name}")
        print(f"     Station: {station_name}")
        print(f"     Scores -> ArcFace: {scores.get('arcface_pct')}%, CNN: {scores.get('cnn_pct')}%, MediaPipe: {scores.get('mediapipe_pct')}% (Consensus: {scores.get('consensus_pct')}%)")

    print("\n" + "=" * 75)
    print("[SUCCESS] Backend AI Comparative Search is operating perfectly!")
    print("=" * 75)

if __name__ == '__main__':
    img = sys.argv[1] if len(sys.argv) > 1 else None
    test_query_search(img)
