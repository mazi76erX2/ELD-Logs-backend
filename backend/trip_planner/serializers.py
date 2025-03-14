from rest_framework.exceptions import ValidationError
from adrf.serializers import Serializer
from rest_framework import serializers

from .models import ELDLog, ELDLogSheet, Location, RouteSegment, Trip


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "address", "latitude", "longitude"]


class RouteSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteSegment
        fields = [
            "id",
            "start_location",
            "end_location",
            "distance_miles",
            "estimated_duration_minutes",
            "geometry",
            "segment_type",
            "order",
        ]
        read_only_fields = ["id"]


class ELDLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ELDLog
        fields = ["id", "trip", "date", "log_data"]
        read_only_fields = ["id"]


class TripSerializer(serializers.ModelSerializer):
    segments = RouteSegmentSerializer(many=True, read_only=True)
    eld_logs = ELDLogSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_hours",
            "segments",
            "eld_logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TripInputSerializer(Serializer):
    current_location = serializers.CharField(required=True)
    pickup_location = serializers.CharField(required=True)
    dropoff_location = serializers.CharField(required=True)
    current_cycle_hours = serializers.FloatField(
        required=True, min_value=0, max_value=70
    )

    def validate_current_cycle_hours(self, value: float) -> float:
        if value < 0 or value > 70:
            raise ValidationError("Current cycle hours must be between 0 and 70")
        return value


class ELDLogSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ELDLogSheet
        fields = ["id", "eld_log", "log_sheet_data", "log_image", "created_at"]
