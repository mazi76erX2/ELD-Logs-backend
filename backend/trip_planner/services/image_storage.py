import os
import base64
from pathlib import Path
from django.conf import settings
import aiofiles


async def store_image_from_base64(base64_str: str, folder: str, filename: str) -> str:
    """
    Decode a base64 encoded image and store it in the specified folder under MEDIA_ROOT.
    Returns the relative file path.
    """
    # Ensure the folder exists inside MEDIA_ROOT.
    media_folder = Path(settings.MEDIA_ROOT) / folder
    media_folder.mkdir(parents=True, exist_ok=True)

    # Remove any header (e.g. "data:image/png;base64,") from the base64 string.
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    image_data = base64.b64decode(base64_str)
    file_path = media_folder / filename

    # Use aiofiles for non-blocking file operations
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(image_data)

    # Return a relative path (e.g., "eld_logs/log_sheet_1234.png") that can be served from MEDIA_URL.
    return os.path.join(folder, filename)
