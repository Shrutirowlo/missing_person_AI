from django.db import models

class Station(models.Model):
    BRANCH_TYPE_CHOICES = [
        ('POLICE_STATION', 'Police Station'),
        ('NGO_BRANCH', 'NGO Branch / Foundation'),
        ('SHELTER_HOME', 'Government / Children Shelter Home'),
        ('HOSPITAL_DESK', 'Hospital Helpdesk'),
        ('OTHER', 'Other Organization'),
    ]

    name = models.CharField(max_length=255, help_text="Official name of the station or organization")
    branch_type = models.CharField(max_length=50, choices=BRANCH_TYPE_CHOICES, default='POLICE_STATION')
    branch_code = models.CharField(max_length=50, unique=True, help_text="Unique station / branch identifier")
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20, blank=True, default='')
    contact_phone = models.CharField(max_length=50)
    contact_email = models.EmailField(blank=True, default='')
    officer_in_charge = models.CharField(max_length=150, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Station / NGO Branch'
        verbose_name_plural = 'Stations & NGO Branches'

    def __str__(self):
        return f"{self.name} ({self.branch_code}) - {self.city}, {self.state}"
