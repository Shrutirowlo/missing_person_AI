from rest_framework import serializers

from .models import MissingPerson, PersonImage


class PersonImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonImage
        fields = [
            "id",
            "image",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_at",
        ]


class MissingPersonSerializer(serializers.ModelSerializer):
    images = PersonImageSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = MissingPerson
        fields = [
            "id",
            "name",
            "age",
            "gender",
            "description",
            "last_seen_location",
            "last_seen_date",
            "status",
            "created_at",
            "updated_at",
            "images",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "images",
        ]