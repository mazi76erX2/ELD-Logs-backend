import math
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..models import Trip


class ELDCalculator:
    """Service for calculating HOS compliance and generating ELD logs."""

    # Constants for HOS regulations
    MAX_DRIVING_HOURS = 11.0  # Maximum driving hours per day
    MAX_ON_DUTY_HOURS = 14.0  # Maximum on-duty hours per day
    MIN_OFF_DUTY_HOURS = 10.0  # Minimum off-duty hours between shifts
    MAX_CYCLE_HOURS = 70.0  # Maximum hours in 8-day cycle

    # Average speeds and times
    AVG_SPEED_MPH = 55  # Average driving speed in mph
    LOADING_UNLOADING_HOURS = 1  # Time for pickup/dropoff
    FUELING_HOURS = 0.5  # Time for fueling
    MAX_FUEL_RANGE = 1000  # Maximum miles between fueling stops

    @staticmethod
    def calculate_trip_segments(trip: Trip) -> List[Dict[str, Any]]:
        """Calculate all segments of a trip including rest periods."""
        # Get locations
        current = trip.current_location
        pickup = trip.pickup_location
        dropoff = trip.dropoff_location

        # Initialize trip segments
        segments: List[Dict[str, Any]] = []

        # Add segment from current location to pickup
        current_to_pickup = {
            "start": current,
            "end": pickup,
            "type": "DRIVING",
            "distance": 0,
            "duration": 0,
        }

        # Add pickup activity
        pickup_activity = {
            "start": pickup,
            "end": pickup,
            "type": "PICKUP",
            "distance": 0,
            "duration": ELDCalculator.LOADING_UNLOADING_HOURS * 60,
        }

        # Add segment from pickup to dropoff
        pickup_to_dropoff = {
            "start": pickup,
            "end": dropoff,
            "type": "DRIVING",
            "distance": 0,
            "duration": 0,
        }

        # Add dropoff activity
        dropoff_activity = {
            "start": dropoff,
            "end": dropoff,
            "type": "DROPOFF",
            "distance": 0,
            "duration": ELDCalculator.LOADING_UNLOADING_HOURS * 60,
        }

        planned_segments = [
            current_to_pickup,
            pickup_activity,
            pickup_to_dropoff,
            dropoff_activity,
        ]
        return planned_segments

    @staticmethod
    def generate_eld_logs(
        trip: Trip, segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate ELD logs based on trip segments.
        This simulates creating daily logs with driving, on-duty, and off-duty activities.
        """
        logs = []
        start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        current_time = start_time
        current_date = current_time.date()
        current_log = {"date": current_date, "activities": []}

        remaining_drive_hours = ELDCalculator.MAX_DRIVING_HOURS
        remaining_duty_hours = ELDCalculator.MAX_ON_DUTY_HOURS
        cycle_hours_used = trip.current_cycle_hours

        for segment in segments:
            segment_type = segment["type"]
            duration_hours = segment["duration"] / 60

            # Handle different segment types
            if segment_type == "DRIVING":
                # Check if we need a break for HOS compliance
                if (
                    remaining_drive_hours < duration_hours
                    or remaining_duty_hours < duration_hours
                ):
                    # Add rest period
                    rest_duration = ELDCalculator.MIN_OFF_DUTY_HOURS
                    rest_end_time = current_time + timedelta(hours=rest_duration)

                    # Check if rest spans to next day
                    if rest_end_time.date() > current_date:
                        # Close current day's log
                        logs.append(current_log)

                        # Create new day log
                        current_date = rest_end_time.date()
                        current_log = {"date": current_date, "activities": []}

                    # Add rest activity
                    current_log["activities"].append(
                        {
                            "status": "OFF_DUTY",
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": rest_end_time.strftime("%H:%M"),
                            "location": segment["start"].name,
                            "remarks": "Required rest period",
                        }
                    )

                    current_time = rest_end_time
                    remaining_drive_hours = ELDCalculator.MAX_DRIVING_HOURS
                    remaining_duty_hours = ELDCalculator.MAX_ON_DUTY_HOURS

                # Handle driving segment
                drive_end_time = current_time + timedelta(hours=duration_hours)

                # Check if driving spans to next day
                if drive_end_time.date() > current_date:
                    # Split the driving period
                    day_end = current_time.replace(hour=23, minute=59, second=59)
                    first_part_hours = (day_end - current_time).total_seconds() / 3600

                    # Add driving activity for current day
                    current_log["activities"].append(
                        {
                            "status": "DRIVING",
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": day_end.strftime("%H:%M"),
                            "location": f"En route from {segment['start'].name} to {segment['end'].name}",
                            "remarks": "Driving",
                        }
                    )

                    # Update hours used
                    remaining_drive_hours -= first_part_hours
                    remaining_duty_hours -= first_part_hours
                    cycle_hours_used += first_part_hours

                    # Close current day's log
                    logs.append(current_log)

                    # Create new day log
                    current_date = drive_end_time.date()
                    current_time = datetime(
                        current_date.year, current_date.month, current_date.day, 0, 0, 0
                    )
                    current_log = {"date": current_date, "activities": []}

                    # Add remaining driving for new day
                    second_part_hours = duration_hours - first_part_hours
                    current_log["activities"].append(
                        {
                            "status": "DRIVING",
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": drive_end_time.strftime("%H:%M"),
                            "location": f"En route from {segment['start'].name} to {segment['end'].name}",
                            "remarks": "Driving continued",
                        }
                    )

                    remaining_drive_hours -= second_part_hours
                    remaining_duty_hours -= second_part_hours
                    cycle_hours_used += second_part_hours
                else:
                    # Normal same-day driving activity
                    current_log["activities"].append(
                        {
                            "status": "DRIVING",
                            "start_time": current_time.strftime("%H:%M"),
                            "end_time": drive_end_time.strftime("%H:%M"),
                            "location": f"En route from {segment['start'].name} to {segment['end'].name}",
                            "remarks": "Driving",
                        }
                    )

                    remaining_drive_hours -= duration_hours
                    remaining_duty_hours -= duration_hours
                    cycle_hours_used += duration_hours
            elif segment_type in ["PICKUP", "DROPOFF"]:
                # Handle pickup/dropoff activities
                activity_end_time = current_time + timedelta(hours=duration_hours)

                current_log["activities"].append(
                    {
                        "status": "ON_DUTY",
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": activity_end_time.strftime("%H:%M"),
                        "location": segment["start"].name,
                        "remarks": "Pickup" if segment_type == "PICKUP" else "Dropoff",
                    }
                )

            elif segment_type == "FUEL":
                # Handle fueling stops
                fuel_end_time = current_time + timedelta(
                    hours=ELDCalculator.FUELING_HOURS
                )

                current_log["activities"].append(
                    {
                        "status": "ON_DUTY",
                        "start_time": current_time.strftime("%H:%M"),
                        "end_time": fuel_end_time.strftime("%H:%M"),
                        "location": segment["start"].name,
                        "remarks": "Fueling",
                    }
                )

                remaining_duty_hours -= ELDCalculator.FUELING_HOURS
                cycle_hours_used += ELDCalculator.FUELING_HOURS
                current_time = fuel_end_time

        # Add the final day's log
        logs.append(current_log)

        return logs

    @staticmethod
    def draw_eld_grid(log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate ELD grid visualization data for a daily log."""
        # This would return data needed to draw the log grid
        # In a real implementation, this might return SVG or canvas drawing instructions

        activities = log_data["activities"]
        grid_data = {
            "date": log_data["date"],
            "hours": [f"{h:02d}:00" for h in range(24)],
            "statuses": ["OFF_DUTY", "SLEEPER", "DRIVING", "ON_DUTY"],
            "cells": [],
        }

        # For each activity, determine which cells to fill in
        for activity in activities:
            status = activity["status"]
            start_time = datetime.strptime(activity["start_time"], "%H:%M")
            end_time = datetime.strptime(activity["end_time"], "%H:%M")

            # If end time is earlier than start time, it's crossing midnight
            if end_time < start_time:
                end_time = end_time.replace(day=start_time.day + 1)

            # Calculate duration in 15-minute increments
            duration_minutes = (end_time - start_time).total_seconds() / 60
            blocks = int(duration_minutes / 15)

            # Add cells for each 15-minute block
            for i in range(blocks):
                cell_time = start_time + timedelta(minutes=i * 15)
                grid_data["cells"].append(
                    {
                        "hour": cell_time.hour,
                        "quarter": cell_time.minute // 15,
                        "status": status,
                    }
                )

        return grid_data
