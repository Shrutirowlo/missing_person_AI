from rest_framework import serializers
from .models import SearchQueryLog
from cases.serializers import MissingPersonListSerializer

class SearchQueryLogSerializer(serializers.ModelSerializer):
    top_case_details = MissingPersonListSerializer(source='top_matched_case', read_only=True)
    searched_by_name = serializers.CharField(source='searched_by.get_full_name', read_only=True)
    station_name = serializers.CharField(source='station.name', read_only=True)

    class Meta:
        model = SearchQueryLog
        fields = [
            'id',
            'query_image',
            'query_crop',
            'searched_by',
            'searched_by_name',
            'station',
            'station_name',
            'top_matched_case',
            'top_case_details',
            'arcface_score',
            'cnn_score',
            'mediapipe_score',
            'consensus_score',
            'verdict',
            'notes',
            'results_payload',
            'execution_time_ms',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
