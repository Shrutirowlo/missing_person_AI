from django.db import models
from django.conf import settings

class SearchQueryLog(models.Model):
    VERDICT_CHOICES = [
        ('MATCH_FOUND', 'Match Found'),
        ('POSSIBLE_MATCH', 'Possible Match'),
        ('NO_MATCH', 'No Match'),
        ('NO_FACE', 'No Face Detected'),
    ]

    query_image = models.ImageField(upload_to='queries/images/')
    query_crop = models.ImageField(upload_to='queries/crops/', blank=True, null=True)
    searched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='searches'
    )
    station = models.ForeignKey(
        'stations.Station',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='station_searches'
    )
    
    top_matched_case = models.ForeignKey(
        'cases.MissingPerson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_hits'
    )

    arcface_score = models.FloatField(default=0.0, help_text="ArcFace Confidence Score %")
    cnn_score = models.FloatField(default=0.0, help_text="CNN Confidence Score %")
    mediapipe_score = models.FloatField(default=0.0, help_text="MediaPipe Confidence Score %")
    consensus_score = models.FloatField(default=0.0, help_text="Aggregated Consensus Score %")
    
    verdict = models.CharField(max_length=50, choices=VERDICT_CHOICES, default='NO_MATCH')
    notes = models.TextField(blank=True, default='')
    results_payload = models.JSONField(default=dict, blank=True, help_text="Full comparative breakdown & candidates JSON")
    execution_time_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Search Query Log'
        verbose_name_plural = 'Search Query Logs'

    def __str__(self):
        return f"Search #{self.id} - {self.verdict} ({self.consensus_score}%) at {self.created_at.strftime('%Y-%m-%d %H:%M')}"
