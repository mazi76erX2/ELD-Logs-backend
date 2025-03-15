import aiohttp
import base64
import io
import logging
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class MapService:
    """
    Service to generate a map image using matplotlib for plotting route coordinates.
    This avoids dependency on external map services that may be unreliable.
    """

    @staticmethod
    async def generate_map_image(
        route_coords: list[tuple[float, float]],
        width: int = 800,
        height: int = 600,
    ) -> str:
        """
        Given a list of (lat, lon) tuples representing the route,
        generate a map image with markers for stops and a line for the route.
        Returns a base64 encoded PNG image.
        """
        # This is a CPU-bound operation, not I/O-bound
        # So we don't need to use await here
        return MapService._create_map_image(route_coords, width, height)

    @staticmethod
    def _create_map_image(
        route_coords: list[tuple[float, float]],
        width: int = 800,
        height: int = 600,
    ) -> str:
        """
        Synchronous helper method to create the map image.
        """
        print("map image")
        if not route_coords or len(route_coords) < 1:
            # Create a blank image if no coordinates
            blank_img = Image.new("RGB", (width, height), color="white")
            draw = ImageDraw.Draw(blank_img)
            draw.text(
                (width // 2 - 100, height // 2), "No route data available", fill="black"
            )

            buffer = io.BytesIO()
            blank_img.save(buffer, format="PNG")
            buffer.seek(0)
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"

        try:
            # Extract latitudes and longitudes
            latitudes = [coord[0] for coord in route_coords]
            longitudes = [coord[1] for coord in route_coords]

            # Create figure with specific size
            dpi = 100  # dots per inch
            fig_width = width / dpi
            fig_height = height / dpi

            fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

            # Plot route line
            ax.plot(longitudes, latitudes, "b-", linewidth=2)

            # Plot markers for each point
            ax.plot(longitudes, latitudes, "ro", markersize=8)

            # Add labels for first and last points
            if len(route_coords) > 1:
                ax.annotate(
                    "Start",
                    xy=(longitudes[0], latitudes[0]),
                    xytext=(10, 10),
                    textcoords="offset points",
                )
                ax.annotate(
                    "End",
                    xy=(longitudes[-1], latitudes[-1]),
                    xytext=(10, 10),
                    textcoords="offset points",
                )

            # Add some margin around the points
            margin = 0.05  # 5% margin
            lat_range = max(latitudes) - min(latitudes)
            lon_range = max(longitudes) - min(longitudes)

            # Ensure minimum ranges to avoid issues with single points
            min_range = 0.01  # Minimum range to display
            lat_range = max(lat_range, min_range)
            lon_range = max(lon_range, min_range)

            ax.set_xlim(
                min(longitudes) - margin * lon_range,
                max(longitudes) + margin * lon_range,
            )
            ax.set_ylim(
                min(latitudes) - margin * lat_range, max(latitudes) + margin * lat_range
            )

            # Set labels and title
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_title("Trip Route Map")

            # Add grid
            ax.grid(True)

            # Ensure figure is tight
            plt.tight_layout()

            # Save to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format="png")
            plt.close(fig)

            # Convert to base64
            buffer.seek(0)
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"

        except ValueError as e:
            logger.error(f"Value error while generating map: {e}")
            return MapService._generate_error_image(
                width, height, f"Invalid coordinate values: {str(e)}"
            )
        except TypeError as e:
            logger.error(f"Type error while generating map: {e}")
            return MapService._generate_error_image(
                width, height, f"Invalid data type: {str(e)}"
            )
        except IOError as e:
            logger.error(f"I/O error while generating map: {e}")
            return MapService._generate_error_image(
                width, height, f"Image processing error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error while generating map: {e}", exc_info=True)
            return MapService._generate_error_image(
                width, height, f"Map generation failed: {str(e)}"
            )

    @staticmethod
    def _generate_error_image(width: int, height: int, error_message: str) -> str:
        """
        Generate a simple error image with the provided message.
        """
        try:
            error_img = Image.new("RGB", (width, height), color="white")
            draw = ImageDraw.Draw(error_img)

            # Draw error message in the center
            draw.text((width // 2 - 150, height // 2), error_message, fill="red")
            draw.text(
                (width // 2 - 150, height // 2 + 20),
                "Please check server logs for details",
                fill="red",
            )

            buffer = io.BytesIO()
            error_img.save(buffer, format="PNG")
            buffer.seek(0)
            base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{base64_str}"
        except Exception as e:
            # Last resort fallback
            logger.critical(
                f"Failed to generate even the error image: {e}", exc_info=True
            )
            return ""
