from rest_framework import serializers
from .models import EmailEvent


class EmailEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailEvent
        fields = '__all__'