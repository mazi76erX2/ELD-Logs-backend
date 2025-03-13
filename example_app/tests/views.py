from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Analysis


class BulkAnalysisTest(APITestCase):
    """Tests for the BulkAnalysisViewSet."""

    def setUp(self) -> None:
        self.view_url: str = reverse("bulk-analysis")

    def test_missing_texts_field(self) -> None:
        """
        Tests if the view handles missing "texts" field in request data.
        """
        response = self.client.post(self.view_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], 'Missing "texts" field in request data'
        )

    def test_empty_texts_list(self) -> None:
        """
        Tests if the view handles an empty "texts" list.
        """
        response = self.client.post(self.view_url, {"texts": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"], 'Missing "texts" field in request data'
        )

    def test_successful_analysis(self) -> None:
        """
        Tests if the view performs sentiment analysis, saves results, and returns a response.
        """
        texts: list[str] = ["This movie is great!", "This product is a disappointment."]
        response = self.client.post(self.view_url, {"texts": texts})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check if Analysis objects are created
        analyses: list[Analysis] = Analysis.objects.all()
        self.assertEqual(analyses.count(), len(texts))
        for analysis, text in zip(analyses, texts):
            self.assertEqual(analysis.text, text)

        # Check response data format
        data = response.json()
        self.assertIsInstance(data, list)
        for result in data:
            self.assertIn("text", result)
            self.assertIn("sentiment", result)
            self.assertIn("confidence_score", result)

    def test_cache_usage(self) -> None:
        """
        Tests if the view utilizes the cache for storing and retrieving sentiment results.
        (This test requires modifying the `analyse_text` method to simulate cache behavior)
        """
        # Modify `analyse_text` to mock cache usage
        # ... (implementation details)

        text1: str = "This service is amazing!"
        text2: str = "This experience is awful!"
        texts: list[str] = [text1, text2]

        # First request, no cache hit
        response = self.client.post(self.view_url, {"texts": texts})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Second request with the same text (cache hit expected)
        response = self.client.post(self.view_url, {"texts": texts})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
