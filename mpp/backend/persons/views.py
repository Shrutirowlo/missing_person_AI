

from .models import MissingPerson
from .serializers import MissingPersonSerializer

from rest_framework import generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from .models import MissingPerson, PersonImage
from .serializers import MissingPersonSerializer, PersonImageSerializer


class PersonImageUploadView(generics.CreateAPIView):
    serializer_class = PersonImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        person_id = self.kwargs["pk"]

        person = MissingPerson.objects.get(
            id=person_id
        )

        serializer.save(
            person=person
        )


class MissingPersonListCreateView(
    generics.ListCreateAPIView
):
    queryset = MissingPerson.objects.all()
    serializer_class = MissingPersonSerializer
    permission_classes = [IsAuthenticated]


class MissingPersonDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    queryset = MissingPerson.objects.all()
    serializer_class = MissingPersonSerializer
    permission_classes = [IsAuthenticated]