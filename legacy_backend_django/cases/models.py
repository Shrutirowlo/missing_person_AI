import uuid
from django.db import models
from django.conf import settings

def generate_case_id():
    return f"MP-{uuid.uuid4().hex[:8].upper()}"

class MissingPerson(models.Model):
    CASE_TYPE_CHOICES = [
        ('MISSING_PERSON', 'Missing Person Report'),
        ('FOUND_PERSON', 'Found / Sheltered Person'),
        ('UNIDENTIFIED_BODY', 'Unidentified Person / Body'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active Investigation / Open'),
        ('FOUND', 'Found / Located'),
        ('RESOLVED', 'Case Resolved / Reunited'),
        ('CLOSED', 'Case Closed / Inactive'),
    ]

    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other / Non-binary'),
        ('UNKNOWN', 'Unknown'),
    ]

    case_id = models.CharField(max_length=64, unique=True, default=generate_case_id, help_text="Official Case ID or FIR Number")
    full_name = models.CharField(max_length=200, help_text="Full Name of the missing or found person")
    alias_name = models.CharField(max_length=150, blank=True, default='', help_text="Nickname, Alias, or AKA")
    case_type = models.CharField(max_length=30, choices=CASE_TYPE_CHOICES, default='MISSING_PERSON')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    age = models.PositiveIntegerField(null=True, blank=True, help_text="Age in years (or estimated age)")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='UNKNOWN')
    date_missing_or_found = models.DateField(null=True, blank=True, help_text="Date when person went missing or was found")
    
    last_seen_location = models.CharField(max_length=255, blank=True, default='')
    last_seen_city = models.CharField(max_length=100, blank=True, default='')
    last_seen_state = models.CharField(max_length=100, blank=True, default='')

    physical_description = models.TextField(blank=True, default='', help_text="Height, skin complexion, hair color, birthmarks, tattoos, clothing")
    medical_conditions = models.TextField(blank=True, default='', help_text="Mental health, speech impairment, medical alerts")
    
    contact_person = models.CharField(max_length=150, blank=True, default='', help_text="Family contact person / Guardian name")
    contact_phone = models.CharField(max_length=50, blank=True, default='', help_text="Helpline / Family phone number")
    contact_email = models.EmailField(blank=True, default='')

    reporting_station = models.ForeignKey(
        'stations.Station',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases',
        help_text="Originating Police Station or NGO Branch"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_cases'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Missing Person Case'
        verbose_name_plural = 'Missing Person Cases'

    def __str__(self):
        return f"[{self.case_id}] {self.full_name} ({self.get_case_type_display()}) - {self.status}"

    @property
    def primary_photo(self):
        return self.photos.filter(is_primary=True).first() or self.photos.first()


class PersonPhoto(models.Model):
    case = models.ForeignKey(
        MissingPerson,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    image = models.ImageField(upload_to='cases/original/')
    face_crop = models.ImageField(upload_to='cases/crops/', blank=True, null=True)
    is_primary = models.BooleanField(default=False)

    # Serialized JSON vectors for high-speed retrieval & caching
    arcface_vector = models.TextField(blank=True, default='', help_text="512-D ArcFace float array JSON")
    cnn_vector = models.TextField(blank=True, default='', help_text="128-D Deep CNN float array JSON")
    mediapipe_vector = models.TextField(blank=True, default='', help_text="478 3D MediaPipe landmark float array JSON")
    bounding_box = models.CharField(max_length=100, blank=True, default='', help_text="[x, y, w, h] face bounding box")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']
        verbose_name = 'Person Photo'
        verbose_name_plural = 'Person Photos'

    def __str__(self):
        return f"Photo #{self.id} for {self.case.full_name} ({self.case.case_id})"
