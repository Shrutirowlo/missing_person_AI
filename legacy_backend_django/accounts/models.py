from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('POLICE_OFFICER', 'Police Officer'),
        ('NGO_WORKER', 'NGO Worker / Social Worker'),
        ('CITIZEN', 'Citizen / Victim Relative'),
        ('ADMIN', 'System Administrator'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='POLICE_OFFICER')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    badge_number = models.CharField(max_length=50, blank=True, default='', help_text="Police Badge Number or NGO Employee ID")
    station = models.ForeignKey(
        'stations.Station',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officers',
        help_text="Assigned Police Station or NGO Branch"
    )
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    designation = models.CharField(max_length=100, blank=True, default='')
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
