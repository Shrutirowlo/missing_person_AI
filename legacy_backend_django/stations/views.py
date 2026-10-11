from rest_framework import generics, permissions, filters
from django.db.models import Count
from .models import Station
from .serializers import StationSerializer

class StationListCreateView(generics.ListCreateAPIView):
    serializer_class = StationSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'branch_code', 'city', 'state', 'officer_in_charge']
    ordering_fields = ['name', 'city', 'state', 'created_at']

    def get_queryset(self):
        queryset = Station.objects.annotate(cases_count=Count('cases'))
        branch_type = self.request.query_params.get('branch_type')
        state = self.request.query_params.get('state')
        city = self.request.query_params.get('city')

        if branch_type:
            queryset = queryset.filter(branch_type=branch_type)
        if state:
            queryset = queryset.filter(state__icontains=state)
        if city:
            queryset = queryset.filter(city__icontains=city)

        return queryset

class StationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Station.objects.all()
    serializer_class = StationSerializer
    permission_classes = [permissions.AllowAny]
