from datetime import date, datetime

import polyline
from rest_framework.decorators import action
from rest_framework.response import Response
from adrf.viewsets import ViewSet
from asgiref.sync import sync_to_async
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import ELDLog, ELDLogSheet, Location, RouteSegment, Trip
from .serializers import (
    ELDLogSerializer,
    ELDLogSheetSerializer,
    LocationSerializer,
    RouteSegmentSerializer,
    TripInputSerializer,
    TripSerializer,
)
from .services.eld_calculator import ELDCalculator
from .services.eld_log_generator import ELDLogGenerator
from .services.routing import RoutingService


def json_serialize_date(obj) -> dict:
    """Convert date/datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class LocationViewSet(ViewSet):
    """Async API endpoint for locations."""

    queryset = Location.objects.all().order_by("-created_at")
    serializer_class = LocationSerializer

    @swagger_auto_schema(
        operation_description="Get all locations",
        responses={200: LocationSerializer(many=True)},
    )
    async def list(self, request):
        """List all locations."""
        locations = await sync_to_async(list)(self.queryset)
        serializer = self.serializer_class(locations, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get a specific location",
        responses={200: LocationSerializer(), 404: "Location not found"},
    )
    async def retrieve(self, request, pk=None):
        """Retrieve a specific location."""
        try:
            location = await sync_to_async(Location.objects.get)(pk=pk)
        except Location.DoesNotExist:
            return Response(
                {"error": "Location not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(location)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new location",
        request_body=LocationSerializer,
        responses={201: LocationSerializer()},
    )
    async def create(self, request):
        """Create a new location."""
        serializer = self.serializer_class(data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        location = await sync_to_async(serializer.save)()
        return Response(
            self.serializer_class(location).data, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        operation_description="Update a location",
        request_body=LocationSerializer,
        responses={200: LocationSerializer(), 404: "Location not found"},
    )
    async def update(self, request, pk=None):
        """Update a location."""
        try:
            location = await sync_to_async(Location.objects.get)(pk=pk)
        except Location.DoesNotExist:
            return Response(
                {"error": "Location not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(location, data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_location = await sync_to_async(serializer.save)()
        return Response(self.serializer_class(updated_location).data)


class TripViewSet(ViewSet):
    """Async API endpoint for trips."""

    queryset = Trip.objects.all().order_by("-created_at")
    serializer_class = TripSerializer

    @swagger_auto_schema(
        operation_description="Get all trips",
        responses={200: TripSerializer(many=True)},
    )
    async def list(self, request):
        """List all trips."""
        trips = await sync_to_async(list)(self.queryset)
        serializer = self.serializer_class(trips, many=True)
        return await sync_to_async(lambda: Response(serializer.data))()

    @swagger_auto_schema(
        operation_description="Get a specific trip",
        responses={200: TripSerializer(), 404: "Trip not found"},
    )
    async def retrieve(self, request, pk=None):
        """Retrieve a specific trip."""
        try:
            trip = await sync_to_async(Trip.objects.get)(pk=pk)
        except Trip.DoesNotExist:
            return Response(
                {"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(trip)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Plan a new trip with route and ELD calculations",
        request_body=TripInputSerializer,
        responses={201: TripSerializer(), 400: "Bad request"},
    )
    @action(detail=False, methods=["post"])
    async def plan(self, request):
        """Plan a new trip with route and ELD calculations."""
        input_serializer = TripInputSerializer(data=request.data)
        print("1")
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        print(2)

        result = await self.process_trip_planning(input_serializer.validated_data)
        print("exit")
        if "error" in result:
            return Response(
                {"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(result, status=status.HTTP_201_CREATED)

    async def process_trip_planning(self, trip_data):
        """Process trip planning asynchronously."""
        # Geocode locations using the RoutingService
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
        print(3)

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

        # Calculate routes
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
            # Current -> Pickup segment
            seg1 = await sync_to_async(RouteSegment.objects.create)(
                trip=trip,
                start_location=current_location,
                end_location=pickup_location,
                distance_miles=current_to_pickup_route["distance_miles"],
                estimated_duration_minutes=current_to_pickup_route["duration_minutes"],
                geometry=current_to_pickup_route["geometry"],
                segment_type="DRIVING",
                order=1,
            )
            segments.append(seg1)
            # Pickup activity segment
            seg2 = await sync_to_async(RouteSegment.objects.create)(
                trip=trip,
                start_location=pickup_location,
                end_location=pickup_location,
                distance_miles=0,
                estimated_duration_minutes=60,  # 1 hour for pickup
                geometry="",
                segment_type="PICKUP",
                order=2,
            )
            segments.append(seg2)
            # Create fuel stop if needed
            if pickup_to_dropoff_route["distance_miles"] > ELDCalculator.MAX_FUEL_RANGE:
                decoded = polyline.decode(pickup_to_dropoff_route["geometry"])
                mid = len(decoded) // 2
                fuel_stop_coords = decoded[mid]
                fuel_location, _ = await sync_to_async(Location.objects.get_or_create)(
                    latitude=fuel_stop_coords[0],
                    longitude=fuel_stop_coords[1],
                    defaults={
                        "name": "Fuel Stop",
                        "address": f"Fuel Stop at {fuel_stop_coords[0]}, {fuel_stop_coords[1]}",
                    },
                )
                first_half_route = {
                    "distance_miles": pickup_to_dropoff_route["distance_miles"] / 2,
                    "duration_minutes": pickup_to_dropoff_route["duration_minutes"] / 2,
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

        segments = await create_segments()

        # Generate ELD logs using ELDCalculator (using your constants and HOS logic)
        segments_data = ELDCalculator.calculate_trip_segments(trip)
        eld_logs = ELDCalculator.generate_eld_logs(trip, segments_data)
        created_logs = []
        for log_data in eld_logs:
            # Convert the date object to a string if it's a date object
            if isinstance(log_data['date'], (date, datetime)):
                log_data_copy = log_data.copy()  # Create a copy to avoid modifying the original
                log_data_copy['date'] = json_serialize_date(log_data['date'])
            else:
                log_data_copy = log_data
                
            log = await sync_to_async(ELDLog.objects.create)(
                trip=trip,
                date=log_data['date'],  # Original date object for the date field
                log_data=log_data_copy  # Copy with serialized date for the JSON field
            )
            created_logs.append(log)

        await sync_to_async(trip.eld_logs.set)(created_logs)
        await sync_to_async(trip.save)()
        await sync_to_async(trip.refresh_from_db)()
        serializer = TripSerializer(trip)
        return await sync_to_async(lambda: serializer.data)()


class ELDLogViewSet(ViewSet):
    """Async API endpoint for ELD Logs."""

    queryset = ELDLog.objects.all().order_by("-date")
    serializer_class = ELDLogSerializer

    @swagger_auto_schema(
        operation_description="Get all ELD logs",
        responses={200: ELDLogSerializer(many=True)},
    )
    async def list(self, request):
        """List all ELD logs."""
        logs = await sync_to_async(list)(self.queryset)
        serializer = self.serializer_class(logs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get a specific ELD log",
        responses={200: ELDLogSerializer(), 404: "ELD log not found"},
    )
    async def retrieve(self, request, pk=None):
        """Retrieve a specific ELD log."""
        try:
            log = await sync_to_async(ELDLog.objects.get)(pk=pk)
        except ELDLog.DoesNotExist:
            return Response(
                {"error": "ELD log not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(log)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new ELD log",
        request_body=ELDLogSerializer,
        responses={201: ELDLogSerializer()},
    )
    async def create(self, request):
        """Create a new ELD log."""
        serializer = self.serializer_class(data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        log = await sync_to_async(serializer.save)()
        return Response(self.serializer_class(log).data, status=status.HTTP_201_CREATED)


class ELDLogSheetViewSet(ViewSet):
    """Async API endpoint for ELD Log Sheets."""

    queryset = ELDLogSheet.objects.all().order_by("-created_at")
    serializer_class = ELDLogSheetSerializer

    @swagger_auto_schema(
        operation_description="Get all ELD log sheets",
        responses={200: ELDLogSheetSerializer(many=True)},
    )
    async def list(self, request):
        """List all ELD log sheets."""
        log_sheets = await sync_to_async(list)(self.queryset)
        serializer = self.serializer_class(log_sheets, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get a specific ELD log sheet",
        responses={200: ELDLogSheetSerializer(), 404: "ELD log sheet not found"},
    )
    async def retrieve(self, request, pk=None):
        """Retrieve a specific ELD log sheet."""
        try:
            log_sheet = await sync_to_async(ELDLogSheet.objects.get)(pk=pk)
        except ELDLogSheet.DoesNotExist:
            return Response(
                {"error": "ELD log sheet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(log_sheet)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Generate an ELD log sheet for a given ELD log",
        responses={200: ELDLogSheetSerializer(), 404: "ELD Log not found"},
        manual_parameters=[
            openapi.Parameter(
                name="pk",
                in_=openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                description="ELD Log ID",
                required=True,
            )
        ],
    )
    @action(detail=True, methods=["get"])
    async def generate_log(self, request, pk=None):
        """
        Generate an ELD log sheet (including a base64 image) for a given ELDLog.
        """
        try:
            eld_log = await sync_to_async(ELDLog.objects.get)(pk=pk)
        except ELDLog.DoesNotExist:
            return Response(
                {"error": "ELD Log not found."}, status=status.HTTP_404_NOT_FOUND
            )

        log_data = eld_log.log_data
        if "date" in log_data and not isinstance(log_data["date"], datetime):
            try:
                log_data["date"] = datetime.fromisoformat(log_data["date"])
            except Exception:
                log_data["date"] = datetime.now()
        else:
            log_data["date"] = datetime.now()

        log_sheet_data = ELDLogGenerator.generate_log_sheet(log_data)
        log_image = ELDLogGenerator.generate_log_image(log_data)

        log_sheet, _ = await sync_to_async(ELDLogSheet.objects.update_or_create)(
            eld_log=eld_log,
            defaults={"log_sheet_data": log_sheet_data, "log_image": log_image},
        )
        serializer = ELDLogSheetSerializer(log_sheet)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Create a new ELD log sheet",
        request_body=ELDLogSheetSerializer,
        responses={201: ELDLogSheetSerializer()},
    )
    async def create(self, request):
        """Create a new ELD log sheet."""
        serializer = self.serializer_class(data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        log_sheet = await sync_to_async(serializer.save)()
        return Response(
            self.serializer_class(log_sheet).data, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        operation_description="Update an ELD log sheet",
        request_body=ELDLogSheetSerializer,
        responses={200: ELDLogSheetSerializer(), 404: "ELD log sheet not found"},
    )
    async def update(self, request, pk=None):
        """Update an ELD log sheet."""
        try:
            log_sheet = await sync_to_async(ELDLogSheet.objects.get)(pk=pk)
        except ELDLogSheet.DoesNotExist:
            return Response(
                {"error": "ELD log sheet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(log_sheet, data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_log_sheet = await sync_to_async(serializer.save)()
        return Response(self.serializer_class(updated_log_sheet).data)

    @swagger_auto_schema(
        operation_description="Delete an ELD log sheet",
        responses={204: "No content", 404: "ELD log sheet not found"},
    )
    async def destroy(self, request, pk=None):
        """Delete an ELD log sheet."""
        try:
            log_sheet = await sync_to_async(ELDLogSheet.objects.get)(pk=pk)
        except ELDLogSheet.DoesNotExist:
            return Response(
                {"error": "ELD log sheet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        await sync_to_async(log_sheet.delete)()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteSegmentViewSet(ViewSet):
    """Async API endpoint for Route Segments."""

    queryset = RouteSegment.objects.all().order_by("trip", "order")
    serializer_class = RouteSegmentSerializer

    @swagger_auto_schema(
        operation_description="Get all route segments",
        responses={200: RouteSegmentSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter(
                "trip_id",
                openapi.IN_QUERY,
                description="Filter by trip ID",
                type=openapi.TYPE_STRING,
                required=False,
            )
        ],
    )
    async def list(self, request):
        """List all route segments with optional trip filter."""
        trip_id = request.query_params.get("trip_id")
        if trip_id:
            queryset = RouteSegment.objects.filter(trip_id=trip_id).order_by("order")
        else:
            queryset = self.queryset

        segments = await sync_to_async(list)(queryset)
        serializer = self.serializer_class(segments, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Get a specific route segment",
        responses={200: RouteSegmentSerializer(), 404: "Route segment not found"},
    )
    async def retrieve(self, request, pk=None):
        """Retrieve a specific route segment."""
        try:
            segment = await sync_to_async(RouteSegment.objects.get)(pk=pk)
        except RouteSegment.DoesNotExist:
            return Response(
                {"error": "Route segment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(segment)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new route segment",
        request_body=RouteSegmentSerializer,
        responses={201: RouteSegmentSerializer()},
    )
    async def create(self, request):
        """Create a new route segment."""
        serializer = self.serializer_class(data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        segment = await sync_to_async(serializer.save)()
        return Response(
            self.serializer_class(segment).data, status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        operation_description="Update a route segment",
        request_body=RouteSegmentSerializer,
        responses={200: RouteSegmentSerializer(), 404: "Route segment not found"},
    )
    async def update(self, request, pk=None):
        """Update a route segment."""
        try:
            segment = await sync_to_async(RouteSegment.objects.get)(pk=pk)
        except RouteSegment.DoesNotExist:
            return Response(
                {"error": "Route segment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(segment, data=request.data)
        if not await sync_to_async(serializer.is_valid)():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_segment = await sync_to_async(serializer.save)()
        return Response(self.serializer_class(updated_segment).data)

    @swagger_auto_schema(
        operation_description="Delete a route segment",
        responses={204: "No content", 404: "Route segment not found"},
    )
    async def destroy(self, request, pk=None):
        """Delete a route segment."""
        try:
            segment = await sync_to_async(RouteSegment.objects.get)(pk=pk)
        except RouteSegment.DoesNotExist:
            return Response(
                {"error": "Route segment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        await sync_to_async(segment.delete)()
        return Response(status=status.HTTP_204_NO_CONTENT)
