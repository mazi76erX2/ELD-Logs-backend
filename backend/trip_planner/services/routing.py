import logging
from typing import Any, Dict, Optional, Tuple
import json

import aiohttp
import redis
from django.conf import settings


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

        if cached_result:
            try:
                # Directly decode bytes without await - bytes objects are not awaitable
                return json.loads(cached_result.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as e:
                logger.warning(f"Failed to decode cached geocode data: {e}")
                # Continue to fetch new data if cache parsing fails

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": "1"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers={"User-Agent": "ELDTripPlanner/1.0"}
                ) as response:
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

                    # Cache the result as JSON string instead of Python string representation
                    redis_client.set(cache_key, json.dumps(result), ex=CACHE_TIMEOUT)

                    return result
        except Exception as e:
            logger.error(f"Error during geocoding: {e}")
            return None

    @staticmethod
    async def get_route(
        start_coords: Tuple[float, float], end_coords: Tuple[float, float]
    ) -> Optional[Dict[str, Any]]:
        """Get route information between two points."""
        start_str = f"{start_coords[1]},{start_coords[0]}"
        end_str = f"{end_coords[1]},{end_coords[0]}"

        cache_key = f"route:{start_str}:{end_str}"
        cached_result = redis_client.get(cache_key)

        if cached_result:
            try:
                # Directly decode bytes without await - bytes objects are not awaitable
                return json.loads(cached_result.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as e:
                logger.warning(f"Failed to decode cached route data: {e}")
                # Continue to fetch new data if cache parsing fails

        url = f"{RoutingService.OSRM_BASE_URL}{start_str};{end_str}"
        params = {"overview": "full", "geometries": "polyline", "steps": "true"}

        try:
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

                    # Cache the result as JSON string instead of Python string representation
                    redis_client.set(cache_key, json.dumps(result), ex=CACHE_TIMEOUT)

                    return result
        except Exception as e:
            logger.error(f"Error during routing: {e}")
            return None
