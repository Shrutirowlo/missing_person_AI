from django.db import models


class MissingPerson(models.Model):

    STATUS_CHOICES = [
        ("missing", "Missing"),
        ("found", "Found"),
        ("safe", "Safe"),
    ]

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=150)

    age = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    last_seen_location = models.CharField(
        max_length=255,
        blank=True
    )

    last_seen_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="missing"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name

class PersonImage(models.Model):

    person = models.ForeignKey(
        MissingPerson,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(
        upload_to="missing_persons/"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.person.name} - {self.image.name}"