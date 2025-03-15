from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .extra_views import (
    LocationViewSet,
    TripViewSet,
    ELDLogSheetViewSet,
    RouteSegmentViewSet,
)


router = DefaultRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"trips", TripViewSet, basename="trip")
router.register(r"eld_log_sheets", ELDLogSheetViewSet, basename="eld_log_sheet")
router.register(r"route_segments", RouteSegmentViewSet, basename="route_segment")

urlpatterns = [
    path("", include(router.urls)),
]
