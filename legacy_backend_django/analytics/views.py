from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Count, Avg
from cases.models import MissingPerson, PersonPhoto
from stations.models import Station
from matching.models import SearchQueryLog
from matching.serializers import SearchQueryLogSerializer

class DashboardAnalyticsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total_cases = MissingPerson.objects.count()
        active_cases = MissingPerson.objects.filter(status='ACTIVE').count()
        found_cases = MissingPerson.objects.filter(status='FOUND').count()
        resolved_cases = MissingPerson.objects.filter(status='RESOLVED').count()
        closed_cases = MissingPerson.objects.filter(status='CLOSED').count()

        missing_type_count = MissingPerson.objects.filter(case_type='MISSING_PERSON').count()
        found_type_count = MissingPerson.objects.filter(case_type='FOUND_PERSON').count()
        unidentified_count = MissingPerson.objects.filter(case_type='UNIDENTIFIED_BODY').count()

        total_stations = Station.objects.filter(is_active=True).count()
        police_stations_count = Station.objects.filter(branch_type='POLICE_STATION', is_active=True).count()
        ngo_count = Station.objects.filter(branch_type='NGO_BRANCH', is_active=True).count()
        shelters_count = Station.objects.filter(branch_type='SHELTER_HOME', is_active=True).count()

        total_searches = SearchQueryLog.objects.count()
        matches_found = SearchQueryLog.objects.filter(verdict='MATCH_FOUND').count()
        possible_matches = SearchQueryLog.objects.filter(verdict='POSSIBLE_MATCH').count()
        no_matches = SearchQueryLog.objects.filter(verdict='NO_MATCH').count()

        # Average model scores across past queries
        avg_scores = SearchQueryLog.objects.aggregate(
            avg_arcface=Avg('arcface_score'),
            avg_cnn=Avg('cnn_score'),
            avg_mediapipe=Avg('mediapipe_score'),
            avg_consensus=Avg('consensus_score'),
            avg_latency=Avg('execution_time_ms')
        )

        recent_searches = SearchQueryLog.objects.select_related('top_matched_case', 'station').order_by('-created_at')[:6]
        recent_searches_data = SearchQueryLogSerializer(recent_searches, many=True, context={'request': request}).data

        # Top stations with highest active cases
        top_stations = Station.objects.annotate(
            cases_count=Count('cases')
        ).order_by('-cases_count')[:5].values('id', 'name', 'branch_code', 'city', 'state', 'cases_count')

        return Response({
            'overview': {
                'total_cases': total_cases,
                'active_cases': active_cases,
                'found_cases': found_cases,
                'resolved_cases': resolved_cases,
                'closed_cases': closed_cases,
                'resolution_rate_percentage': round((resolved_cases + found_cases) / max(1, total_cases) * 100, 1),
            },
            'cases_by_type': {
                'missing_person': missing_type_count,
                'found_person': found_type_count,
                'unidentified': unidentified_count,
            },
            'network_branches': {
                'total_branches': total_stations,
                'police_stations': police_stations_count,
                'ngo_foundations': ngo_count,
                'shelter_homes': shelters_count,
                'top_contributing_stations': list(top_stations),
            },
            'search_intelligence': {
                'total_searches_executed': total_searches,
                'verified_matches': matches_found,
                'possible_matches': possible_matches,
                'no_matches': no_matches,
                'match_rate_percentage': round((matches_found + possible_matches) / max(1, total_searches) * 100, 1),
                'model_benchmarks': {
                    'arcface_avg_score': round(avg_scores.get('avg_arcface') or 0.0, 2),
                    'cnn_avg_score': round(avg_scores.get('avg_cnn') or 0.0, 2),
                    'mediapipe_avg_score': round(avg_scores.get('avg_mediapipe') or 0.0, 2),
                    'consensus_avg_score': round(avg_scores.get('avg_consensus') or 0.0, 2),
                    'average_inference_time_ms': round(avg_scores.get('avg_latency') or 0.0, 1),
                }
            },
            'recent_alerts': recent_searches_data,
        }, status=status.HTTP_200_OK)
