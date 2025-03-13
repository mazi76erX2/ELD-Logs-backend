import logging

from typing import Optional

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny

from adrf.viewsets import ViewSet

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


from .analysis import analyse_sentiment_async
from .models import Analysis
from .serializers import AnalysisSerializer


class BulkAnalysisViewSet(ViewSet):
    """
    Async ViewSet for performing bulk sentiment analysis on a list of texts.

    This ViewSet provides the following actions:
    - post:
        Analyzes a list of texts asynchronously, creates analysis objects,
        and returns the analysis results.

    The post action expects a POST request with the following data:
    - texts: A list of texts (in string format) to be analyzed. (Optional[list[str]])

    The post action returns a response with the following data:
    - A list of analysis objects containing the sentiment analysis results.

    Example usage:
    POST /bulk-analysis/
    {
        "texts": ["I love this product!", "This movie is terrible."]
    }
    """

    queryset = Analysis.objects.all()
    serializer_class = AnalysisSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["texts"],
            properties={
                "texts": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING),
                )
            },
        )
    )
    async def create(self, request: Request) -> Response:
        """
        Analyzes a list of texts asynchronously, creates analysis objects,
        """
        texts: Optional[list[str]] = request.data.get("texts", [])

        if not texts:
            logging.error('Missing "texts" field in request data')
            return Response(
                data={"error": 'Missing "texts" field in request data'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sentiment_results: list[dict[str, float]] = []
        for text in texts:
            cache_key: str = f"sentiment:{text}"

            cached_result: Optional[dict[str, float]] = cache.get(cache_key)
            if cached_result:
                logging.info("Sentiment analysis for '%s' retrieved from cache.", text)
                sentiment_results.append(cached_result)
            else:
                sentiment: dict[str, float] = await self.analyse_text(text)
                sentiment_results.append(sentiment)
                cache.set(cache_key, sentiment, timeout=None)

        analyses: list[Analysis] = [
            Analysis(
                text=text,
                sentiment=result["sentiment"],
                confidence_score=result["confidence_score"],
            )
            for result, text in zip(sentiment_results, texts)
        ]
        await Analysis.objects.abulk_create(analyses)
        logging.info("Successfully created {len(%s)} analysis objects.", analyses)

        serializer: AnalysisSerializer = AnalysisSerializer(analyses, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    async def analyse_text(self, text: str) -> dict[str, float]:
        sentiment: dict[str, float] = await analyse_sentiment_async(text)
        return sentiment
