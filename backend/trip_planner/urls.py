from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LocationViewSet, TripViewSet, ELDLogSheetViewSet


router = DefaultRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"trips", TripViewSet, basename="trip")
router.register(r"eld_log_sheets", ELDLogSheetViewSet, basename="eld_log_sheet")

urlpatterns = [
    path("", include(router.urls)),
]
