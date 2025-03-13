from django.db import models


class Analysis(models.Model):
    """
    Stores the results of text sentiment analysis.

    Fields:
        text (str): The analyzed text content.
        sentiment (SentimentChoices): The overall sentiment of the text.
        confidence_score (float, optional): The confidence score associated
            with the sentiment prediction (between 0.0 and 1.0).
        created_at (datetime.datetime): The timestamp when the analysis was
            created (automatically set on creation).
    """

    class SentimentChoices(models.TextChoices):
        POSITIVE = "positive"
        NEGATIVE = "negative"
        NEUTRAL = "neutral"

    text = models.TextField(blank=False, null=False)
    sentiment = models.CharField(
        choices=SentimentChoices, max_length=8, blank=True, null=True
    )
    confidence_score = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.text[:20]}..." if self.text is not None else ""
