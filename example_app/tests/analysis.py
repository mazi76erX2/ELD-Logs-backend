from unittest.mock import AsyncMock, patch

from django.test import TestCase

# from ..analysis import analyse_sentiment_async
# from ..views import BulkAnalysisViewSet


class SentimentAnalysisTest(TestCase):
    """Tests for the sentiment analysis functionality."""

    async def test_positive_sentiment(self):
        """
        Tests if the sentiment analysis function correctly identifies positive sentiment.
        Mock the tokenizer and model calls
        """
        mock_tokenizer = AsyncMock()
        mock_model = AsyncMock()

        with patch.object(analyse_sentiment_async, "tokenizer", mock_tokenizer):
            with patch.object(analyse_sentiment_async.model, "__call__", mock_model):
                text = "This movie is absolutely fantastic!"
                sentiment_result = await analyse_sentiment_async(text)

                mock_tokenizer.assert_awaited_once_with.return_value = {
                    "encoded_text": "encoded"
                }
                mock_model.assert_awaited_once_with.return_value = {
                    "logits": tf.Tensor([0.9, 0.1, 0.0])
                }
                expected_sentiment: str = "positive"
                expected_confidence: float = 0.9
                self.assertEqual(sentiment_result["sentiment"], expected_sentiment)
                self.assertAlmostEqual(
                    sentiment_result["confidence_score"], expected_confidence
                )

    async def test_negative_sentiment(self):
        """
        Tests if the sentiment analysis function correctly identifies negative sentiment.
        """

        mock_tokenizer = AsyncMock()
        mock_model = AsyncMock()

        with patch.object(analyse_sentiment_async, "tokenizer", mock_tokenizer):
            with patch.object(analyse_sentiment_async.model, "__call__", mock_model):
                text = "This product is a complete waste of money."
                sentiment_result = await analyse_sentiment_async(text)

                # Assert expected calls and return values
                mock_tokenizer.assert_awaited_once_with.return_value = {
                    "encoded_text": "encoded"
                }
                mock_model.assert_awaited_once_with.return_value = {
                    "logits": tf.Tensor([0.1, 0.8, 0.1])
                }
                expected_sentiment: str = "negative"
                expected_confidence: float = 0.8
                self.assertEqual(sentiment_result["sentiment"], expected_sentiment)
                self.assertAlmostEqual(
                    sentiment_result["confidence_score"], expected_confidence
                )

    async def test_neutral_sentiment(self):
        """
        Tests if the sentiment analysis function correctly identifies neutral sentiment.
        """

        mock_tokenizer = AsyncMock()
        mock_model = AsyncMock()

        with patch.object(analyse_sentiment_async, "tokenizer", mock_tokenizer):
            with patch.object(analyse_sentiment_async.model, "__call__", mock_model):
                text = "This movie is just okay, nothing special."
                sentiment_result = await analyse_sentiment_async(text)

                # Assert expected calls and return values
                mock_tokenizer.assert_awaited_once_with.return_value = {
                    "encoded_text": "encoded"
                }
                mock_model.assert_awaited_once_with.return_value = {
                    "logits": tf.Tensor([0.3, 0.3, 0.4])
                }
                expected_sentiment: str = (
                    "neutral"  # Adjust based on your model's logic
                )
                # Consider a threshold for confidence score to define neutral sentiment
                expected_confidence: float = (
                    None  # Or a specific value for neutral range
                )
                self.assertEqual(sentiment_result["sentiment"], expected_sentiment)
                if expected_confidence is not None:
                    self.assertAlmostEqual(
                        sentiment_result["confidence_score"], expected_confidence
                    )

    async def test_preprocessing_error(self):
        """
        Tests if the sentiment analysis function handles preprocessing errors gracefully.
        Mock the tokenizer to raise an error
        """
        mock_tokenizer = AsyncMock()
        mock_tokenizer.side_effect = ValueError("Invalid input text")

        with patch.object(analyse_sentiment_async, "tokenizer", mock_tokenizer):
            text = "This text has an error"
            sentiment_result = await analyse_sentiment_async(text)
            self.assertEqual(sentiment_result["error"], "Preprocessing error")
            self.assertIsInstance(sentiment_result, dict)

    async def test_tensorflow_error(self):
        """
        Tests if the sentiment analysis function handles TensorFlow errors gracefully.
        Mock the model call to raise an error
        """
        mock_model = AsyncMock()
        mock_model.side_effect = tf.errors.OutOfRangeError("Out of range error")

        with patch.object(analyse_sentiment_async.model, "__call__", mock_model):
            text = "Another error"
            sentiment_result = await analyse_sentiment_async(text)
            self.assertEqual(sentiment_result["error"], "TensorFlow error")
            self.assertIsInstance(sentiment_result, dict)

    async def test_unexpected_error(self):
        """
        Tests if the sentiment analysis function handles unexpected errors gracefully.
        """
        text = "Unexpected error"
        with self.assertRaises(Exception):
            await analyse_sentiment_async(text)
