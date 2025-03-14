# backend/eld_planner/services/eld_log_generator.py
import base64
import json
import math
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class ELDLogGenerator:
    """Service for generating ELD log sheets in the standard format."""

    # Constants for the log grid
    HOURS_IN_DAY = 24
    STATUS_TYPES = ["OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY"]

    @staticmethod
    def generate_log_sheet(log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete ELD log sheet for one day."""
        date = log_data.get("date")
        activities = log_data.get("activities", [])

        # Create the log sheet data structure
        log_sheet = {
            "date": date,
            "driver_info": {
                "name": "",  # To be filled by frontend
                "id": "",  # To be filled by frontend
                "co_driver": "",
                "cycle": "70 Hour / 8 Day",
            },
            "vehicle_info": {
                "truck_number": "",
                "trailer_numbers": "",
                "shipping_docs": "",
            },
            "carrier_info": {"name": "", "main_office": "", "home_terminal": ""},
            "trip_info": {"from": "", "to": "", "total_miles": 0, "remarks": ""},
            "grid_data": ELDLogGenerator._create_grid_data(activities),
            "hour_totals": ELDLogGenerator._calculate_hour_totals(activities),
            "recap": ELDLogGenerator._calculate_recap(activities),
        }

        return log_sheet

    @staticmethod
    def _create_grid_data(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create the grid data for the log visualization."""
        # Initialize empty grid (24 hours x 4 status types)
        grid = []
        for hour in range(24):
            grid.append(
                {
                    "hour": hour,
                    "cells": [False, False, False, False],  # One cell per status type
                }
            )

        # Fill in the grid based on activities
        for activity in activities:
            status_type = activity["status"]
            start_time_str = activity["start_time"]
            end_time_str = activity["end_time"]

            # Parse times
            start_time = datetime.strptime(start_time_str, "%H:%M")
            end_time = datetime.strptime(end_time_str, "%H:%M")

            # Handle overnight activities
            if end_time < start_time:
                end_time = end_time.replace(day=start_time.day + 1)

            # Convert status to index
            status_index = ELDLogGenerator.STATUS_TYPES.index(status_type)

            # Calculate duration and fill grid
            duration_minutes = (end_time - start_time).total_seconds() / 60
            current_time = start_time

            while current_time < end_time:
                hour = current_time.hour
                grid[hour]["cells"][status_index] = True

                # Move to next 15-minute block
                current_time += timedelta(minutes=15)

        return grid

    @staticmethod
    def _calculate_hour_totals(activities: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate total hours per status type."""
        totals = {"OFF_DUTY": 0, "SLEEPER_BERTH": 0, "DRIVING": 0, "ON_DUTY": 0}

        for activity in activities:
            status = activity["status"]
            start_time = datetime.strptime(activity["start_time"], "%H:%M")
            end_time = datetime.strptime(activity["end_time"], "%H:%M")

            # Handle overnight activities
            if end_time < start_time:
                end_time = end_time.replace(day=start_time.day + 1)

            # Calculate hours
            hours = (end_time - start_time).total_seconds() / 3600
            totals[status] += hours

        return totals

    @staticmethod
    def _calculate_recap(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate the recap section (simplified for now)."""
        # This would be more complex in a real implementation
        # It would include calculations for the 70-hour/8-day rule
        return {
            "today": {
                "total_on_duty": 0,  # Calculated from activities
                "total_driving": 0,  # Calculated from activities
            },
            "available_hours": {
                "driving": 11,  # Maximum daily driving
                "on_duty": 14,  # Maximum daily on-duty
                "cycle": 70,  # Maximum 8-day cycle
            },
        }

    @staticmethod
    def generate_log_image(log_data: Dict[str, Any]) -> str:
        """Generate an image of the ELD log and return as base64."""
        # Create a new image
        width, height = 1200, 800
        image = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(image)

        # Try to load fonts (fallback to default if not available)
        try:
            title_font = ImageFont.truetype("Arial", 18)
            header_font = ImageFont.truetype("Arial", 14)
            normal_font = ImageFont.truetype("Arial", 12)
            small_font = ImageFont.truetype("Arial", 10)
        except IOError:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            normal_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw title
        draw.text(
            (width / 2, 30),
            "DRIVER'S DAILY LOG",
            fill="black",
            font=title_font,
            anchor="mm",
        )

        # Draw date
        date_str = (
            log_data["date"].strftime("%m/%d/%Y")
            if isinstance(log_data["date"], datetime)
            else log_data["date"]
        )
        draw.text(
            (width / 2, 60),
            f"Date: {date_str}",
            fill="black",
            font=header_font,
            anchor="mm",
        )

        # Draw driver info section
        draw.rectangle([(50, 100), (width - 50, 180)], outline="black")
        draw.line([(width / 2, 100), (width / 2, 180)], fill="black")
        draw.text((60, 110), "Driver Name:", fill="black", font=normal_font)
        draw.text((60, 140), "Co-Driver:", fill="black", font=normal_font)
        draw.text((width / 2 + 10, 110), "Carrier:", fill="black", font=normal_font)
        draw.text((width / 2 + 10, 140), "Main Office:", fill="black", font=normal_font)

        # Draw vehicle info section
        draw.rectangle([(50, 200), (width - 50, 280)], outline="black")
        draw.line([(width / 2, 200), (width / 2, 280)], fill="black")
        draw.text((60, 210), "Truck Number:", fill="black", font=normal_font)
        draw.text((60, 240), "Trailer Number(s):", fill="black", font=normal_font)
        draw.text((width / 2 + 10, 210), "From:", fill="black", font=normal_font)
        draw.text((width / 2 + 10, 240), "To:", fill="black", font=normal_font)

        # Draw grid headers
        grid_top = 300
        grid_left = 100
        grid_width = width - 200
        grid_height = 200
        cell_width = grid_width / 24  # 24 hours

        # Draw hour labels
        for i in range(25):  # 0-24 hours (25 lines including start and end)
            x = grid_left + i * cell_width
            draw.line([(x, grid_top), (x, grid_top + grid_height)], fill="black")
            if i < 24:  # Don't draw label for the 24th line
                draw.text(
                    (x + cell_width / 2, grid_top - 10),
                    f"{i}",
                    fill="black",
                    font=small_font,
                    anchor="mm",
                )

        # Draw status labels and horizontal lines
        status_labels = ["OFF", "SB", "D", "ON"]
        for i in range(5):  # 4 status types (5 lines including start and end)
            y = grid_top + i * (grid_height / 4)
            draw.line([(grid_left, y), (grid_left + grid_width, y)], fill="black")
            if i < 4:  # Don't draw label for the bottom line
                draw.text(
                    (grid_left - 30, y + (grid_height / 8)),
                    status_labels[i],
                    fill="black",
                    font=normal_font,
                    anchor="mm",
                )

        # Draw grid data
        grid_data = log_data.get("grid_data", [])
        cell_height = grid_height / 4

        for hour_data in grid_data:
            hour = hour_data["hour"]
            cells = hour_data["cells"]

            for status_idx, is_active in enumerate(cells):
                if is_active:
                    # Fill this cell
                    x1 = grid_left + hour * cell_width
                    y1 = grid_top + status_idx * cell_height
                    x2 = x1 + cell_width
                    y2 = y1 + cell_height

                    # Draw a filled rectangle
                    draw.rectangle([(x1, y1), (x2, y2)], fill="black")

        # Draw totals section
        totals_top = grid_top + grid_height + 50
        draw.text(
            (width / 4, totals_top),
            "Hours Summary",
            fill="black",
            font=header_font,
            anchor="mm",
        )

        # Draw hours table
        table_top = totals_top + 30
        table_headers = ["", "Today", "Period"]
        table_rows = [
            "Off Duty",
            "Sleeper Berth",
            "Driving",
            "On Duty (Not Driving)",
            "Total",
        ]

        # Draw table headers
        for i, header in enumerate(table_headers):
            x = width / 4 + i * 100
            draw.text(
                (x, table_top), header, fill="black", font=normal_font, anchor="mm"
            )

        # Draw row labels and data
        hour_totals = log_data.get("hour_totals", {})
        for i, row in enumerate(table_rows):
            y = table_top + 30 + i * 25
            draw.text(
                (width / 4 - 100, y), row, fill="black", font=normal_font, anchor="mm"
            )

            # Today's hours (simplified)
            if row == "Off Duty":
                value = hour_totals.get("OFF_DUTY", 0)
            elif row == "Sleeper Berth":
                value = hour_totals.get("SLEEPER_BERTH", 0)
            elif row == "Driving":
                value = hour_totals.get("DRIVING", 0)
            elif row == "On Duty (Not Driving)":
                value = hour_totals.get("ON_DUTY", 0)
            elif row == "Total":
                value = sum(hour_totals.values())
            else:
                value = 0

            draw.text(
                (width / 4, y),
                f"{value:.1f}",
                fill="black",
                font=normal_font,
                anchor="mm",
            )

        # Convert to base64
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"
