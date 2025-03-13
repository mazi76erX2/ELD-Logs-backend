import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from transformers import TFAutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to download the pre-trained tokenizer and model for sentiment analysis.
    """

    help = "Downloads the tokenizer and model for sentiment analysis."

    def handle(self, *args, **options):
        model = settings.MODEL_NAME
        save_models_dir = settings.SAVE_MODELS_DIR

        Path(save_models_dir).mkdir(parents=True, exist_ok=True)

        try:
            tokenizer: AutoTokenizer = AutoTokenizer.from_pretrained(model)
            tokenizer.save_pretrained(save_models_dir)

            model: TFAutoModelForSequenceClassification = (
                TFAutoModelForSequenceClassification.from_pretrained(model)
            )
            model.save_pretrained(save_models_dir)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully downloaded tokenizer and model from '{model}' to '{save_models_dir}'"
                )
            )
            logger.info(
                f"Successfully downloaded tokenizer and model from '{model}' to '{save_models_dir}'"
            )
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            self.stderr.write(self.style.ERROR(f"Error downloading model: {e}"))
