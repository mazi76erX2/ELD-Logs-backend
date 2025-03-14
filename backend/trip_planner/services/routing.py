import logging
from typing import Any, Dict, Optional, Tuple

import aiohttp
import redis
from django.conf import settings

from ..models import Location, RouteSegment, Trip

# Initialize Redis connection
redis_client = redis.Redis.from_url(settings.REDIS_LOCATION)
CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours

logger = logging.getLogger(__name__)


class RoutingService:
    """Service for calculating routes using OpenStreetMap and OSRM."""

    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving/"

    @staticmethod
    async def geocode_location(address: str) -> Optional[Dict[str, float]]:
        """Geocode an address to get coordinates."""
        cache_key = f"geocode:{address}"
        cached_result = redis_client.get(cache_key)

        # if cached_result:
        #     return dict(eval((await cached_result).decode("utf-8")))

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": "1"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers={"User-Agent": "ELDTripPlanner/1.0"}
            ) as response:
                print("Response", response)
                if response.status != 200:
                    logger.error(f"Geocoding error: {await response.text()}")
                    return None

                data = await response.json()

                if not data:
                    return None

                result = {
                    "latitude": float(data[0]["lat"]),
                    "longitude": float(data[0]["lon"]),
                    "display_name": data[0]["display_name"],
                }

                # Cache the result
                redis_client.set(cache_key, str(result), ex=CACHE_TIMEOUT)

                return result

    @staticmethod
    async def get_route(
        start_coords: Tuple[float, float], end_coords: Tuple[float, float]
    ) -> Optional[Dict[str, Any]]:
        """Get route information between two points."""
        start_str = f"{start_coords[1]},{start_coords[0]}"
        end_str = f"{end_coords[1]},{end_coords[0]}"

        cache_key = f"route:{start_str}:{end_str}"
        cached_result = redis_client.get(cache_key)

        # if cached_result:
        #     return dict(eval((await cached_result).decode("utf-8")))

        url = f"{RoutingService.OSRM_BASE_URL}{start_str};{end_str}"
        params = {"overview": "full", "geometries": "polyline", "steps": "true"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Routing error: {await response.text()}")
                    return None

                data = await response.json()

                if data["code"] != "Ok" or not data["routes"]:
                    return None

                route = data["routes"][0]

                # Convert distance from meters to miles
                distance_miles = route["distance"] * 0.000621371

                # Convert duration from seconds to minutes
                duration_minutes = route["duration"] / 60

                result = {
                    "distance_miles": distance_miles,
                    "duration_minutes": duration_minutes,
                    "geometry": route["geometry"],
                    "steps": route["legs"][0]["steps"],
                }
                print(5555)

                # Cache the result
                redis_client.set(cache_key, str(result), ex=CACHE_TIMEOUT)

                return result
