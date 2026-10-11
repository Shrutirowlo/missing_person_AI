import time
import os
import cv2
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.base import ContentFile
from .models import SearchQueryLog
from .serializers import SearchQueryLogSerializer
from cases.models import MissingPerson
from ai_engine.comparative_matcher import ComparativeMatcher
from ai_engine.feature_store import FeatureStore

class ComparativeMatchSearchView(APIView):
    """
    Primary Comparative AI Face Search Endpoint.
    Accepts query photo, runs ArcFace, CNN, and MediaPipe pipelines,
    and returns a side-by-side comparative score matrix and candidate matches.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.matcher = ComparativeMatcher()
        self.feature_store = FeatureStore()

    def post(self, request):
        start_time = time.time()

        image_file = request.FILES.get('image') or request.FILES.get('photo') or request.FILES.get('file')
        if not image_file:
            return Response(
                {'error': 'No image file provided. Please upload an image under the "image" field.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Image validation: never trust client filename; check size/type (orchestration only)
        max_bytes = 8 * 1024 * 1024
        if image_file.size and image_file.size > max_bytes:
            return Response(
                {'error': f'Image too large ({image_file.size} bytes). Maximum is {max_bytes} bytes.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
        content_type = getattr(image_file, 'content_type', '')
        if content_type and content_type.lower() not in allowed_types:
            return Response(
                {'error': f'Unsupported image type: {content_type}. Use JPEG, PNG, or WEBP.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Model selector: cnn | arcface | mediapipe | mediapipe_knn | all (default all)
        raw_model = (
            request.data.get('model')
            or request.data.get('models')
            or request.query_params.get('model')
            or 'all'
        )
        if isinstance(raw_model, str):
            raw_model = raw_model.strip().lower()
        alias = {'mediapipe_knn': 'mediapipe', 'mp': 'mediapipe', 'all_models': 'all'}
        if isinstance(raw_model, str) and raw_model in alias:
            raw_model = alias[raw_model]
        if raw_model == 'all':
            requested_models = ('arcface', 'cnn', 'mediapipe')
        elif isinstance(raw_model, str) and ',' in raw_model:
            parts = [alias.get(p.strip(), p.strip()) for p in raw_model.split(',')]
            valid = [p for p in parts if p in ('arcface', 'cnn', 'mediapipe')]
            if not valid:
                return Response(
                    {'error': f'Invalid model value: {raw_model}. Use cnn, arcface, mediapipe_knn, or all.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            requested_models = tuple(valid)
        elif raw_model in ('arcface', 'cnn', 'mediapipe'):
            requested_models = (raw_model,)
        else:
            return Response(
                {'error': f'Invalid model value: {raw_model}. Use cnn, arcface, mediapipe_knn, or all.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Process query image and extract feature vectors
        try:
            query_data = self.matcher.process_query_image(image_file)
        except Exception as e:
            return Response(
                {'error': f'Failed to process query image: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Sync / Retrieve target records
        if not self.feature_store.is_synced or len(self.feature_store.get_all_records()) == 0:
            self.feature_store.sync_from_database()

        target_records = self.feature_store.get_all_records()

        # 3. Execute 3-model comparative matching
        analysis = self.matcher.compare(query_data, target_records, models=requested_models)

        execution_time_ms = int((time.time() - start_time) * 1000)
        analysis['execution_time_ms'] = execution_time_ms

        # 4. Save Search Query Audit Log
        try:
            user = request.user if request.user.is_authenticated else None
            station = user.station if user and user.station else None

            # Station filter override if provided in query
            station_id = request.data.get('station_id')
            if station_id and not station:
                from stations.models import Station
                station = Station.objects.filter(pk=station_id).first()

            breakdown = analysis.get('comparative_breakdown', {})
            arc_score = breakdown.get('arcface', {}).get('score_percentage', 0.0)
            cnn_score = breakdown.get('cnn', {}).get('score_percentage', 0.0)
            mp_score = breakdown.get('mediapipe', {}).get('score_percentage', 0.0)
            consensus = analysis.get('consensus_confidence', 0.0)
            verdict = analysis.get('verdict', 'NO_MATCH')

            top_case = None
            if analysis.get('candidate_matches'):
                top_record_id = analysis['candidate_matches'][0].get('record_id')
                if top_record_id:
                    top_case = MissingPerson.objects.filter(pk=top_record_id).first()

            verdict_code = 'MATCH_FOUND' if 'MATCH FOUND' in verdict else ('POSSIBLE_MATCH' if 'POSSIBLE' in verdict else 'NO_MATCH')

            log = SearchQueryLog.objects.create(
                query_image=image_file,
                searched_by=user,
                station=station,
                top_matched_case=top_case,
                arcface_score=arc_score,
                cnn_score=cnn_score,
                mediapipe_score=mp_score,
                consensus_score=consensus,
                verdict=verdict_code,
                results_payload=analysis,
                execution_time_ms=execution_time_ms,
            )

            # Save query face crop
            face_crop = query_data.get('face_crop_bgr')
            if face_crop is not None:
                is_success, buffer = cv2.imencode(".jpg", face_crop)
                if is_success:
                    crop_name = f"query_crop_{log.id}.jpg"
                    log.query_crop.save(crop_name, ContentFile(buffer.tobytes()), save=True)

            analysis['search_log_id'] = log.id
            if log.query_crop:
                analysis['query_crop_url'] = log.query_crop.url
            if log.query_image:
                analysis['query_image_url'] = log.query_image.url

        except Exception as e:
            print(f"[MatchingView] Notice: Could not save SearchQueryLog: {e}")

        return Response(analysis, status=status.HTTP_200_OK)


class SearchHistoryListView(generics.ListAPIView):
    serializer_class = SearchQueryLogSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = SearchQueryLog.objects.select_related('searched_by', 'station', 'top_matched_case').all()
        station_id = self.request.query_params.get('station_id')
        verdict = self.request.query_params.get('verdict')

        if station_id:
            queryset = queryset.filter(station_id=station_id)
        if verdict:
            queryset = queryset.filter(verdict=verdict)

        return queryset


class SearchDetailView(generics.RetrieveAPIView):
    queryset = SearchQueryLog.objects.select_related('searched_by', 'station', 'top_matched_case').all()
    serializer_class = SearchQueryLogSerializer
    permission_classes = [permissions.AllowAny]


class TestUIPageView(APIView):
    """Serves the modern React frontend application or the standalone tester interface."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.http import HttpResponse
        from django.conf import settings
        from pathlib import Path

        frontend_index = Path(settings.BASE_DIR).parent / 'frontend' / 'dist' / 'index.html'
        if frontend_index.exists():
            try:
                with open(frontend_index, 'r', encoding='utf-8') as f:
                    content = f.read()
                return HttpResponse(content, content_type='text/html')
            except Exception as e:
                print(f"[TestUIPageView] Error reading frontend dist index: {e}")

        from .test_ui_html import TEST_UI_HTML
        return HttpResponse(TEST_UI_HTML, content_type='text/html')


