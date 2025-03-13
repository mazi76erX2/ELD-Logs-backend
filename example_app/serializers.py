from rest_framework import serializers

from .models import Analysis


class AnalysisSerializer(serializers.ModelSerializer):
    """
    Serializer class for the Analysis model.
    """

    class Meta:
        model = Analysis
        fields = "__all__"
