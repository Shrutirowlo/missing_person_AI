from rest_framework import serializers
from .models import Station

class StationSerializer(serializers.ModelSerializer):
    total_cases_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Station
        fields = [
            'id',
            'name',
            'branch_type',
            'branch_code',
            'address',
            'city',
            'state',
            'pincode',
            'contact_phone',
            'contact_email',
            'officer_in_charge',
            'is_active',
            'total_cases_count',
            'created_at',
            'updated_at',
        ]

    def get_total_cases_count(self, obj):
        return getattr(obj, 'cases_count', obj.cases.count() if hasattr(obj, 'cases') else 0)
