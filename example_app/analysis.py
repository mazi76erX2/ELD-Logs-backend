import logging

from transformers import TFAutoModelForSequenceClassification, AutoTokenizer
import tensorflow as tf

from django.conf import settings

SENTIMENT_LABELS = settings.SENTIMENT_LABELS
SAVE_MODELS_DIR = settings.SAVE_MODELS_DIR


async def analyse_sentiment_async(text: str) -> dict[str, float]:
    """
    Analyzes sentiment of a given text using the pre-trained RoBERTa model.

    Args:
        text: The text to analyze (str).

    Returns:
        A tuple containing the predicted sentiment label ("positive", "neutral", "negative")
        and the confidence score associated with the prediction (float).
    """
    try:
        tokenizer: AutoTokenizer = AutoTokenizer.from_pretrained(SAVE_MODELS_DIR)
        model: TFAutoModelForSequenceClassification = (
            TFAutoModelForSequenceClassification.from_pretrained(SAVE_MODELS_DIR)
        )

        async def _encode_text(text: str) -> tf.Tensor:
            return tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=512,
                return_tensors="tf",
            )

        encoded_input = await _encode_text(text)
        outputs: dict = model(encoded_input)
        logits: tf.Tensor = outputs.logits[0]
        predictions: tf.Tensor = tf.nn.softmax(logits)

        top_prediction, top_index = tf.nn.top_k(predictions, k=1)
        predicted_label_id: int = top_index.numpy()[0]
        predicted_label: str = SENTIMENT_LABELS[predicted_label_id]
        confidence_score: float = top_prediction.numpy()[0]

        logging.info(
            "Sentiment analysis for '%s': %s (%.2f)",
            text,
            predicted_label,
            confidence_score,
        )
        return {"sentiment": predicted_label, "confidence_score": confidence_score}

    except ValueError as e:
        # Handle potential errors during preprocessing or input conversion
        logging.error("An error occurred during text preprocessing '%s': %s", text, e)
        return {"error": "Preprocessing error"}

    except (tf.errors.OutOfRangeError, tf.errors.InvalidArgumentError) as e:
        # Handle potential TensorFlow errors (e.g., out-of-range tensor indices)
        logging.error("A TensorFlow error occurred '%s': %s", text, e)
        return {"error": "TensorFlow error"}

    except Exception as e:
        # Handle specific ValueError exception
        logging.error("An unexpected error occurred '%s': %s", text, e)
        return {"error": "Unexpected error"}
