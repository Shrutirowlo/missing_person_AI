from rest_framework import serializers
from .models import MissingPerson, PersonPhoto
from stations.serializers import StationSerializer

class PersonPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonPhoto
        fields = [
            'id',
            'case',
            'image',
            'face_crop',
            'is_primary',
            'bounding_box',
            'created_at',
        ]
        read_only_fields = ['id', 'face_crop', 'bounding_box', 'created_at']

class MissingPersonListSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='reporting_station.name', read_only=True)
    reporting_station_name = serializers.CharField(source='reporting_station.name', read_only=True)
    station_city = serializers.CharField(source='reporting_station.city', read_only=True)
    station_phone = serializers.CharField(source='reporting_station.contact_phone', read_only=True)
    primary_photo_url = serializers.SerializerMethodField(read_only=True)
    primary_crop_url = serializers.SerializerMethodField(read_only=True)
    photos_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MissingPerson
        fields = [
            'id',
            'case_id',
            'full_name',
            'alias_name',
            'case_type',
            'status',
            'age',
            'gender',
            'date_missing_or_found',
            'last_seen_location',
            'last_seen_city',
            'last_seen_state',
            'reporting_station',
            'station_name',
            'reporting_station_name',
            'station_city',
            'station_phone',
            'primary_photo_url',
            'primary_crop_url',
            'photos_count',
            'created_at',
            'updated_at',
        ]


    def get_primary_photo_url(self, obj):
        photo = obj.primary_photo
        if photo and photo.image:
            request = self.context.get('request')
            return request.build_absolute_uri(photo.image.url) if request else photo.image.url
        return None

    def get_primary_crop_url(self, obj):
        photo = obj.primary_photo
        if photo and photo.face_crop:
            request = self.context.get('request')
            return request.build_absolute_uri(photo.face_crop.url) if request else photo.face_crop.url
        return None

    def get_photos_count(self, obj):
        return obj.photos.count()

class MissingPersonDetailSerializer(serializers.ModelSerializer):
    photos = PersonPhotoSerializer(many=True, read_only=True)
    station_details = StationSerializer(source='reporting_station', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = MissingPerson
        fields = [
            'id',
            'case_id',
            'full_name',
            'alias_name',
            'case_type',
            'status',
            'age',
            'gender',
            'date_missing_or_found',
            'last_seen_location',
            'last_seen_city',
            'last_seen_state',
            'physical_description',
            'medical_conditions',
            'contact_person',
            'contact_phone',
            'contact_email',
            'reporting_station',
            'station_details',
            'created_by',
            'created_by_name',
            'photos',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_id', 'created_at', 'updated_at']

class MissingPersonCreateSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = MissingPerson
        fields = [
            'id',
            'case_id',
            'full_name',
            'alias_name',
            'case_type',
            'status',
            'age',
            'gender',
            'date_missing_or_found',
            'last_seen_location',
            'last_seen_city',
            'last_seen_state',
            'physical_description',
            'medical_conditions',
            'contact_person',
            'contact_phone',
            'contact_email',
            'reporting_station',
            'photo',
        ]
        read_only_fields = ['id', 'case_id']

    def create(self, validated_data):
        photo_file = validated_data.pop('photo', None)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            if not validated_data.get('reporting_station') and request.user.station:
                validated_data['reporting_station'] = request.user.station

        case = MissingPerson.objects.create(**validated_data)

        if photo_file:
            PersonPhoto.objects.create(
                case=case,
                image=photo_file,
                is_primary=True
            )

        return case
