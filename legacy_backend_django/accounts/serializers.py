from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User
from stations.serializers import StationSerializer
from stations.models import Station

class UserProfileSerializer(serializers.ModelSerializer):
    station_details = StationSerializer(source='station', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'badge_number',
            'designation',
            'station',
            'station_details',
            'profile_picture',
            'is_verified',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    station_id = serializers.PrimaryKeyRelatedField(
        queryset=Station.objects.all(),
        source='station',
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'badge_number',
            'designation',
            'station_id',
        ]

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        # By default auto-verify local testing users
        user.is_verified = True
        user.save()
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        token['email'] = user.email
        token['full_name'] = user.get_full_name() or user.username
        token['station_id'] = user.station.id if user.station else None
        token['station_name'] = user.station.name if user.station else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserProfileSerializer(self.user).data
        return data
