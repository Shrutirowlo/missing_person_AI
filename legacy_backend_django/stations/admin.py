from django.contrib import admin
from .models import Station

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch_code', 'branch_type', 'city', 'state', 'contact_phone', 'is_active')
    list_filter = ('branch_type', 'state', 'is_active')
    search_fields = ('name', 'branch_code', 'city', 'state', 'officer_in_charge')
