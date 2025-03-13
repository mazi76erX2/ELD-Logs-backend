from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BulkAnalysisViewSet


router = DefaultRouter()
router.register(r"analyses", BulkAnalysisViewSet, basename="analyses")

urlpatterns = [
    path("", include(router.urls)),
]
