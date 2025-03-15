from datetime import date, datetime
import polyline
import logging

from rest_framework.decorators import action
from rest_framework.response import Response
from adrf.viewsets import ViewSet
from asgiref.sync import sync_to_async
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from django.db.models.base import DatabaseError

from .models import ELDLog, ELDLogSheet, Location, RouteSegment, Trip
from .serializers import (
    RouteSegmentSerializer,
    TripInputSerializer,
    TripSerializer,
)
from .services.eld_calculator import ELDCalculator
from .services.eld_log_generator import ELDLogGenerator
from .services.map_service import MapService
from .services.image_storage import store_image_from_base64
from .services.routing import RoutingService

logger = logging.getLogger(__name__)


def json_serialize_date(obj) -> dict:
    """Convert date/datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class TripViewSet(ViewSet):
    """
    Async API endpoint for trips.
    """

    @swagger_auto_schema(
        operation_description="Plan a new trip with route, map and ELD sheet generation",
        request_body=TripInputSerializer,
        responses={201: TripSerializer(), 400: "Bad request"},
    )
    @action(detail=False, methods=["post"])
    async def plan(self, request):
        """Plan a new trip with route, map and ELD sheet generation."""
        input_serializer = TripInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = await self.process_trip_planning(input_serializer.validated_data)
        if "error" in result:
            return Response(
                {"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result, status=status.HTTP_201_CREATED)

    async def process_trip_planning(self, trip_data):
        """
        Process trip planning asynchronously.
        This process includes:
          - Geocoding the input locations.
          - Route calculation and segment creation.
          - Generating daily ELD logs and log sheet images.
          - Generating a map image showing the route with stops/rests.
        """
        try:
            # Geocode locations using RoutingService.
            current_location_data = await RoutingService.geocode_location(
                trip_data["current_location"]
            )
            pickup_location_data = await RoutingService.geocode_location(
                trip_data["pickup_location"]
            )
            dropoff_location_data = await RoutingService.geocode_location(
                trip_data["dropoff_location"]
            )

            if not all(
                [current_location_data, pickup_location_data, dropoff_location_data]
            ):
                return {"error": "Could not geocode one or more locations"}

            async def create_location(location_data, name):
                return await sync_to_async(Location.objects.get_or_create)(
                    latitude=location_data["latitude"],
                    longitude=location_data["longitude"],
                    defaults={"name": name, "address": location_data["display_name"]},
                )

            current_location, _ = await create_location(
                current_location_data, "Current Location"
            )
            pickup_location, _ = await create_location(
                pickup_location_data, "Pickup Location"
            )
            dropoff_location, _ = await create_location(
                dropoff_location_data, "Dropoff Location"
            )

            # Calculate routes between locations.
            current_to_pickup_route = await RoutingService.get_route(
                (current_location.latitude, current_location.longitude),
                (pickup_location.latitude, pickup_location.longitude),
            )
            pickup_to_dropoff_route = await RoutingService.get_route(
                (pickup_location.latitude, pickup_location.longitude),
                (dropoff_location.latitude, dropoff_location.longitude),
            )
            if not all([current_to_pickup_route, pickup_to_dropoff_route]):
                return {"error": "Could not calculate route between locations"}

            async def create_trip():
                return await sync_to_async(Trip.objects.create)(
                    current_location=current_location,
                    pickup_location=pickup_location,
                    dropoff_location=dropoff_location,
                    current_cycle_hours=trip_data["current_cycle_hours"],
                )

            trip = await create_trip()

            async def create_segments():
                segments = []
                # Segment: Current -> Pickup.
                seg1 = await sync_to_async(RouteSegment.objects.create)(
                    trip=trip,
                    start_location=current_location,
                    end_location=pickup_location,
                    distance_miles=current_to_pickup_route["distance_miles"],
                    estimated_duration_minutes=current_to_pickup_route[
                        "duration_minutes"
                    ],
                    geometry=current_to_pickup_route["geometry"],
                    segment_type="DRIVING",
                    order=1,
                )
                segments.append(seg1)
                # Pickup activity segment.
                seg2 = await sync_to_async(RouteSegment.objects.create)(
                    trip=trip,
                    start_location=pickup_location,
                    end_location=pickup_location,
                    distance_miles=0,
                    estimated_duration_minutes=60,  # Assumption: 1 hour for pickup.
                    geometry="",
                    segment_type="PICKUP",
                    order=2,
                )
                segments.append(seg2)

                # Route from Pickup -> Dropoff, optionally with a fuel-stop.
                if (
                    pickup_to_dropoff_route["distance_miles"]
                    > ELDCalculator.MAX_FUEL_RANGE
                ):
                    decoded = polyline.decode(pickup_to_dropoff_route["geometry"])
                    mid = len(decoded) // 2
                    fuel_stop_coords = decoded[mid]
                    fuel_location, _ = await sync_to_async(
                        Location.objects.get_or_create
                    )(
                        latitude=fuel_stop_coords[0],
                        longitude=fuel_stop_coords[1],
                        defaults={
                            "name": "Fuel Stop",
                            "address": f"Fuel Stop at {fuel_stop_coords[0]}, {fuel_stop_coords[1]}",
                        },
                    )
                    first_half_route = {
                        "distance_miles": pickup_to_dropoff_route["distance_miles"] / 2,
                        "duration_minutes": pickup_to_dropoff_route["duration_minutes"]
                        / 2,
                        "geometry": "",
                    }
                    seg3 = await sync_to_async(RouteSegment.objects.create)(
                        trip=trip,
                        start_location=pickup_location,
                        end_location=fuel_location,
                        distance_miles=first_half_route["distance_miles"],
                        estimated_duration_minutes=first_half_route["duration_minutes"],
                        geometry="",
                        segment_type="DRIVING",
                        order=3,
                    )
                    segments.append(seg3)
                    seg4 = await sync_to_async(RouteSegment.objects.create)(
                        trip=trip,
                        start_location=fuel_location,
                        end_location=dropoff_location,
                        distance_miles=pickup_to_dropoff_route["distance_miles"] / 2,
                        estimated_duration_minutes=pickup_to_dropoff_route[
                            "duration_minutes"
                        ]
                        / 2,
                        geometry="",
                        segment_type="DRIVING",
                        order=4,
                    )
                    segments.append(seg4)
                else:
                    seg3 = await sync_to_async(RouteSegment.objects.create)(
                        trip=trip,
                        start_location=pickup_location,
                        end_location=dropoff_location,
                        distance_miles=pickup_to_dropoff_route["distance_miles"],
                        estimated_duration_minutes=pickup_to_dropoff_route[
                            "duration_minutes"
                        ],
                        geometry=pickup_to_dropoff_route["geometry"],
                        segment_type="DRIVING",
                        order=3,
                    )
                    segments.append(seg3)
                return segments

            await create_segments()

            # Generate ELD logs using ELDCalculator.
            segments_data = ELDCalculator.calculate_trip_segments(trip)
            eld_logs_data = ELDCalculator.generate_eld_logs(trip, segments_data)

            for log_data in eld_logs_data:
                if isinstance(log_data.get("date"), (date, datetime)):
                    log_data["date"] = log_data["date"].isoformat()

            created_logs = []
            map_route_coords = []  # Collect coordinates for the route map.

            for log_data in eld_logs_data:
                # Convert the log date for our records.
                if isinstance(log_data["date"], (date, datetime)):
                    actual_date = (
                        log_data["date"]
                        if isinstance(log_data["date"], date)
                        else log_data["date"].date()
                    )
                else:
                    actual_date = datetime.now().date()

                # Make a copy of log data with the date in ISO format for JSON.
                log_data_copy = log_data.copy()
                log_data_copy["date"] = actual_date.isoformat()

                # Create the ELDLog record.
                log = await sync_to_async(ELDLog.objects.create)(
                    trip=trip, date=actual_date, log_data=log_data_copy
                )
                created_logs.append(log)

                # Generate the log sheet image using ELDLogGenerator.
                sheet_image_base64 = ELDLogGenerator.generate_log_image(log_data)
                # Save the generated image to disk.
                image_path = await store_image_from_base64(
                    sheet_image_base64,
                    folder="eld_logs",
                    filename=f"log_sheet_{log.id}.png",
                )

                # Create the corresponding ELDLogSheet record.
                await sync_to_async(ELDLogSheet.objects.create)(
                    eld_log=log,
                    log_sheet_data=ELDLogGenerator.generate_log_sheet(log_data),
                    log_image=image_path,  # Stored file path (or URL if preferred).
                )

                # Optionally, add coordinates for map markers. Here we use the pickup location.
                map_route_coords.append(
                    (pickup_location.latitude, pickup_location.longitude)
                )

            # Generate the overall route map image using the collected coordinates.
            map_image_base64 = await MapService.generate_map_image(
                route_coords=map_route_coords
            )
            map_image_path = await store_image_from_base64(
                map_image_base64, folder="trip_maps", filename=f"trip_{trip.id}_map.png"
            )

            # Optionally, if the Trip model supports a map_image field, save the path.
            trip.map_image = map_image_path
            await sync_to_async(trip.save)()

            # Attach the generated ELD logs to the trip and return the serialized trip data.
            await sync_to_async(trip.eld_logs.set)(created_logs)
            await sync_to_async(trip.save)()
            await sync_to_async(trip.refresh_from_db)()
            serializer = TripSerializer(trip)
            return await sync_to_async(lambda: serializer.data)()
        except ValueError as e:
            return {"error": f"Value error: {str(e)}"}
        except TypeError as e:
            return {"error": f"Type error: {str(e)}"}
        except KeyError as e:
            return {"error": f"Missing required data: {str(e)}"}
        except IOError as e:
            return {"error": f"File operation error: {str(e)}"}
        except DatabaseError as e:
            return {"error": f"Database error: {str(e)}"}


class RouteSegmentViewSet(ViewSet):
    """
    Async API endpoint for route segments.
    """

    queryset = RouteSegment.objects.all().order_by("order")
    serializer_class = RouteSegmentSerializer

    @swagger_auto_schema(
        operation_description="Get all segments for a specific trip",
        responses={200: RouteSegmentSerializer(many=True)},
    )
    @action(detail=False, methods=["get"])
    async def by_trip(self, request):
        """List all segments for a specific trip."""
        trip_id = request.query_params.get("trip_id")
        if not trip_id:
            return Response(
                {"error": "Trip ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            segments = await sync_to_async(list)(
                self.queryset.filter(trip_id=trip_id).order_by("order")
            )
            serializer = self.serializer_class(segments, many=True)
            return Response(serializer.data)
        except ValueError as e:
            return Response(
                {"error": f"Invalid trip ID format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            return Response(
                {"error": f"Database error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
