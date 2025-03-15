import base64
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any
import os


class ELDLogGenerator:
    """
    Service for generating ELD log sheets.
    Combines grid data, table summaries and driver/trip info to generate a log sheet.
    """

    @staticmethod
    def generate_log_sheet(log_data: dict) -> dict:
        """
        Assemble log sheet data structure.
        This structure might be used by the frontend.
        """
        grid_data = ELDLogGenerator._create_grid_data(log_data.get("activities", []))
        hour_totals = ELDLogGenerator._calculate_hour_totals(
            log_data.get("activities", [])
        )
        recap = ELDLogGenerator._calculate_recap(log_data.get("activities", []))
        return {
            "date": log_data.get("date"),
            "grid_data": grid_data,
            "hour_totals": hour_totals,
            "recap": recap,
            "driver_info": {
                "name": "",  # To be filled as needed
                "id": "",
            },
            "vehicle_info": {},
        }

    @staticmethod
    def _create_grid_data(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Create an empty grid for 24 hours and 4 statuses
        grid = []
        for hour in range(24):
            grid.append(
                {
                    "hour": hour,
                    "cells": [
                        False,
                        False,
                        False,
                        False,
                    ],  # Order: OFF_DUTY, SLEEPER_BERTH, DRIVING, ON_DUTY
                }
            )
        # Fill grid cells based on activities
        for activity in activities:
            status = activity["status"]
            try:
                start_time = datetime.strptime(activity["start_time"], "%H:%M")
                end_time = datetime.strptime(activity["end_time"], "%H:%M")
            except ValueError as e:
                # Log the error and continue with the next activity
                print(f"Invalid time format: {e}")
                continue

            if end_time < start_time:
                end_time += timedelta(hours=24)
            status_index = {
                "OFF_DUTY": 0,
                "SLEEPER_BERTH": 1,
                "DRIVING": 2,
                "ON_DUTY": 3,
            }.get(status, 0)
            current = start_time
            while current < end_time:
                hour = current.hour % 24
                grid[hour]["cells"][status_index] = True
                current += timedelta(minutes=15)
        return grid

    @staticmethod
    def _calculate_hour_totals(activities: List[Dict[str, Any]]) -> Dict[str, float]:
        totals = {"OFF_DUTY": 0, "SLEEPER_BERTH": 0, "DRIVING": 0, "ON_DUTY": 0}
        for activity in activities:
            try:
                start = datetime.strptime(activity["start_time"], "%H:%M")
                end = datetime.strptime(activity["end_time"], "%H:%M")
            except ValueError as e:
                print(f"Invalid time format: {e}")
                continue

            if end < start:
                end += timedelta(hours=24)
            hours = (end - start).total_seconds() / 3600
            if activity["status"] in totals:
                totals[activity["status"]] += hours
        return totals

    @staticmethod
    def _calculate_recap(activities: List[Dict[str, Any]]) -> Dict[str, float]:
        # Simplified recap; in a real scenario you can compute 70-hour rules, etc.
        try:
            total_driving = sum(
                (
                    datetime.strptime(act["end_time"], "%H:%M")
                    - datetime.strptime(act["start_time"], "%H:%M")
                ).total_seconds()
                / 60
                for act in activities
                if act.get("status") == "DRIVING"
            )
            return {"total_driving": total_driving}
        except ValueError as e:
            print(f"Error calculating recap: {e}")
            return {"total_driving": 0}

    @staticmethod
    def _get_font(size):
        """
        Try to load a font with fallbacks to ensure we always get a font.
        """
        font_options = [
            # DejaVu is commonly available on Linux systems
            ("DejaVuSans.ttf", size),
            ("DejaVuSans-Bold.ttf", size),
            # Liberation fonts (commonly installed with fonts-liberation)
            ("LiberationSans-Regular.ttf", size),
            ("LiberationSans-Bold.ttf", size),
            # FreeSans is available on many Linux distros
            ("FreeSans.ttf", size),
            # Try system fonts with different paths
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size),
            # As a last resort, use default
            (None, size),
        ]

        for font_name, font_size in font_options:
            try:
                if font_name is None:
                    return ImageFont.load_default()
                return ImageFont.truetype(font_name, font_size)
            except (OSError, IOError) as e:
                continue

        # If all else fails, return default font
        return ImageFont.load_default()

    @staticmethod
    def generate_log_image(log_data: dict) -> str:
        """
        Generate an image of the ELD log sheet using the grid and summary information.
        Returns a base64 encoded PNG image.
        """
        print("Generating log image...")
        width, height = 1200, 800
        try:
            image = Image.new("RGB", (width, height), color="white")
            draw = ImageDraw.Draw(image)

            # Use the font loading method with fallbacks
            title_font = ELDLogGenerator._get_font(18)
            header_font = ELDLogGenerator._get_font(14)
            normal_font = ELDLogGenerator._get_font(12)
            small_font = ELDLogGenerator._get_font(10)

            # Title and date
            draw.text(
                (width // 2, 30),
                "DRIVER'S DAILY LOG",
                fill="black",
                font=title_font,
                anchor="mm",
            )
            date_obj = log_data.get("date")
            if isinstance(date_obj, datetime):
                date_str = date_obj.strftime("%m/%d/%Y")
            else:
                date_str = str(date_obj)
            draw.text(
                (width // 2, 60),
                f"Date: {date_str}",
                fill="black",
                font=header_font,
                anchor="mm",
            )

            # Draw a simplified grid for the daily log
            grid_top, grid_left = 100, 100
            grid_width, grid_height = width - 200, 300
            cell_width = grid_width / 24.0
            cell_height = grid_height / 4.0

            # Draw vertical (hour) grid lines and hour labels
            for i in range(25):
                x = grid_left + i * cell_width
                draw.line([(x, grid_top), (x, grid_top + grid_height)], fill="grey")
                if i < 24:
                    draw.text(
                        (x + cell_width / 2, grid_top - 15),
                        f"{i}",
                        fill="black",
                        font=small_font,
                        anchor="mm",
                    )
            # Draw horizontal lines for statuses
            for j in range(5):
                y = grid_top + j * cell_height
                draw.line([(grid_left, y), (grid_left + grid_width, y)], fill="grey")

            # Get grid data from generator
            grid_data = ELDLogGenerator._create_grid_data(
                log_data.get("activities", [])
            )
            for hour_info in grid_data:
                hr = hour_info["hour"]
                for idx, active in enumerate(hour_info["cells"]):
                    if active:
                        x1 = grid_left + hr * cell_width
                        y1 = grid_top + idx * cell_height
                        x2 = x1 + cell_width
                        y2 = y1 + cell_height
                        draw.rectangle([(x1, y1), (x2, y2)], fill="black")

            # Convert the PIL image to a base64 string.
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            print("Image generation successful")
            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            print(f"Failed to generate log image: {e}")
            raise RuntimeError(f"Failed to generate log image: {e}")
