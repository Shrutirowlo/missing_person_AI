from django.contrib import admin
from .models import SearchQueryLog

@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'verdict', 'consensus_score', 'arcface_score', 'cnn_score', 'mediapipe_score', 'top_matched_case', 'station', 'created_at')
    list_filter = ('verdict', 'station', 'created_at')
    search_fields = ('notes', 'top_matched_case__full_name', 'top_matched_case__case_id')
    readonly_fields = ('created_at', 'execution_time_ms', 'query_crop')
