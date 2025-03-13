from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.core.cache import cache

from ..views import BulkAnalysisViewSet


class CacheTest(TestCase):
    """Tests for the caching functionality in BulkAnalysisViewSet."""

    @patch.object(cache, "get")
    def test_cache_hit(self, mock_cache_get: AsyncMock) -> None:
        """
        Tests if the viewset retrieves sentiment results from the cache when a hit occurs.

        Mocks the cache to return a pre-existing sentiment result and asserts that the
        cached value is returned and the cache lookup is performed with the correct key.
        """

        mock_cache_get.return_value = {"sentiment": "positive", "confidence_score": 0.8}
        text: str = "This movie is fantastic!"

        view = BulkAnalysisViewSet()
        sentiment_results: list[dict[str, float]] = (
            view._get_sentiment_results_from_cache([text])
        )

        mock_cache_get.assert_called_once_with(f"sentiment:{text}")
        self.assertEqual(
            sentiment_results, [{"sentiment": "positive", "confidence_score": 0.8}]
        )

    @patch.object(cache, "get")
    def test_cache_miss(self, mock_cache_get: AsyncMock) -> None:
        """
        Tests if the viewset performs sentiment analysis when a cache miss occurs.

        Mocks the cache to return None and asserts that the cache is looked up with the
        correct key and an empty list is returned.
        """

        mock_cache_get.return_value = None
        text: str = "This product is a disappointment."

        view = BulkAnalysisViewSet()
        sentiment_results: list[dict[str, float]] = (
            view._get_sentiment_results_from_cache([text])
        )

        mock_cache_get.assert_called_once_with(f"sentiment:{text}")
        self.assertEqual(sentiment_results, [])

    @patch.object(cache, "set")
    def test_cache_update(self, mock_cache_set: AsyncMock) -> None:
        """
        Tests if the viewset updates the cache with analyzed sentiment results.

        Mocks the sentiment analysis to return a result and simulates the internal logic
        of the view when a cache miss occurs. Asserts that the cache is updated with the
        analyzed sentiment result using the correct key and no timeout is set.

        Simulate calling the private method with mocked sentiment analysis
        """

        sentiment_result: dict[str, float] = {
            "sentiment": "negative",
            "confidence_score": 0.7,
        }

        def mock_analyse_sentiment(text: str) -> dict[str, float]:
            return sentiment_result

        text: str = "This service is terrible."
        view = BulkAnalysisViewSet()
        view._get_sentiment_results_from_cache([text], mock_analyse_sentiment)

        mock_cache_set.assert_called_once_with(
            f"sentiment:{text}", sentiment_result, timeout=None
        )
