from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'station', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'station')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone_number', 'badge_number', 'station', 'designation', 'profile_picture', 'is_verified')}),
    )
