from django.contrib import admin
from .models import MissingPerson, PersonPhoto

class PersonPhotoInline(admin.TabularInline):
    model = PersonPhoto
    extra = 1
    readonly_fields = ('face_crop', 'bounding_box', 'created_at')
    fields = ('image', 'face_crop', 'is_primary', 'bounding_box', 'created_at')

@admin.register(MissingPerson)
class MissingPersonAdmin(admin.ModelAdmin):
    list_display = ('case_id', 'full_name', 'case_type', 'status', 'age', 'gender', 'reporting_station', 'created_at')
    list_filter = ('case_type', 'status', 'gender', 'reporting_station')
    search_fields = ('case_id', 'full_name', 'alias_name', 'last_seen_location', 'last_seen_city')
    inlines = [PersonPhotoInline]

@admin.register(PersonPhoto)
class PersonPhotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'case', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
