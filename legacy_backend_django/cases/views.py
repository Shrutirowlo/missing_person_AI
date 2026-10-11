from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from .models import MissingPerson, PersonPhoto
from .serializers import (
    MissingPersonListSerializer,
    MissingPersonDetailSerializer,
    MissingPersonCreateSerializer,
    PersonPhotoSerializer,
)
from ai_engine.feature_store import FeatureStore

class MissingPersonListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['full_name', 'alias_name', 'case_id', 'last_seen_location', 'last_seen_city', 'last_seen_state', 'physical_description']
    ordering_fields = ['created_at', 'age', 'full_name', 'date_missing_or_found']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MissingPersonCreateSerializer
        return MissingPersonListSerializer

    def get_queryset(self):
        queryset = MissingPerson.objects.select_related('reporting_station').prefetch_related('photos').all()

        # Query parameter filters
        case_type = self.request.query_params.get('case_type')
        status_param = self.request.query_params.get('status')
        gender = self.request.query_params.get('gender')
        station_id = self.request.query_params.get('station_id')
        city = self.request.query_params.get('city')
        state = self.request.query_params.get('state')

        if case_type:
            queryset = queryset.filter(case_type=case_type)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if gender:
            queryset = queryset.filter(gender=gender)
        if station_id:
            queryset = queryset.filter(reporting_station_id=station_id)
        if city:
            queryset = queryset.filter(Q(last_seen_city__icontains=city) | Q(reporting_station__city__icontains=city))
        if state:
            queryset = queryset.filter(Q(last_seen_state__icontains=state) | Q(reporting_station__state__icontains=state))

        return queryset

class MissingPersonDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MissingPerson.objects.select_related('reporting_station', 'created_by').prefetch_related('photos').all()
    serializer_class = MissingPersonDetailSerializer
    permission_classes = [permissions.AllowAny]

class CasePhotoUploadView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            case = MissingPerson.objects.get(pk=pk)
        except MissingPerson.DoesNotExist:
            return Response({'error': 'Missing person case not found'}, status=status.HTTP_404_NOT_FOUND)

        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        is_primary = request.data.get('is_primary', 'false').lower() == 'true'

        if is_primary:
            case.photos.update(is_primary=False)

        photo = PersonPhoto.objects.create(
            case=case,
            image=image_file,
            is_primary=is_primary
        )

        serializer = PersonPhotoSerializer(photo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ReindexEmbeddingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        feature_store = FeatureStore()
        feature_store.sync_from_database()
        return Response({
            'status': 'SUCCESS',
            'indexed_records_count': len(feature_store.get_all_records()),
            'message': 'All missing person facial embeddings re-synchronized into active cache.'
        })
