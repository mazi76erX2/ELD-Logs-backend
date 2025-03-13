from django.db import models
from typing import Any, Optional
import uuid


class Location(models.Model):
    """Model representing a geographical location."""
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
        }


class Trip(models.Model):
    """Model representing a trip with start, pickup, and delivery points."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    current_location = models.ForeignKey(
        Location, related_name='trips_as_current', on_delete=models.CASCADE
    )
    pickup_location = models.ForeignKey(
        Location, related_name='trips_as_pickup', on_delete=models.CASCADE
    )
    dropoff_location = models.ForeignKey(
        Location, related_name='trips_as_dropoff', on_delete=models.CASCADE
    )
    current_cycle_hours = models.FloatField(help_text="Current hours used in the 70-hour/8-day cycle")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Trip {self.id}: {self.current_location.name} to {self.dropoff_location.name}"


class RouteSegment(models.Model):
    """Model representing a segment of the route between two points."""
    class SegmentTypeChoices(models.TextChoices):
        DRIVING = 'Driving'
        REST = 'Mandatory Rest'
        FUEL = 'Fueling Stop'
        PICKUP = 'Pickup'
        DROPOFF = 'Dropoff'
    
    trip = models.ForeignKey(Trip, related_name='segments', on_delete=models.CASCADE)
    start_location = models.ForeignKey(
        Location, related_name='segments_as_start', on_delete=models.CASCADE
    )
    end_location = models.ForeignKey(
        Location, related_name='segments_as_end', on_delete=models.CASCADE
    )
    distance_miles = models.FloatField()
    estimated_duration_minutes = models.IntegerField()
    geometry = models.TextField(help_text="Encoded polyline or GeoJSON for the route segment")
    segment_type = models.CharField(max_length=20, choices=SegmentTypeChoices)
    order = models.IntegerField(help_text="Order of this segment in the complete route")

    def __str__(self) -> str:
        return f"{self.segment_type} from {self.start_location.name} to {self.end_location.name}"


class ELDLog(models.Model):
    """Model representing a daily ELD log."""
    trip = models.ForeignKey(Trip, related_name='eld_logs', on_delete=models.CASCADE)
    date = models.DateField()
    log_data = models.JSONField(help_text="JSON representation of the log activities")
    
    class Meta:
        unique_together = ['trip', 'date']
        
    def __str__(self) -> str:
        return f"ELD Log for {self.trip.id} on {self.date}"
