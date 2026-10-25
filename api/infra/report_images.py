"""Read registered report images from the mounted artifact filesystem."""

import base64
from pathlib import Path


def get_base64_image(image_path: str) -> str:
    """Return a base64-encoded image payload."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_plot(image_path: str) -> str | bool:
    """Read a plot from the path registered on the authorized sample.

    Args:
        image_path: Sample artifact path, or an empty string when not registered.

    Returns:
        Base64 image content, or False when the path is absent or not a file.

    Raises:
        OSError: The registered file exists but cannot be read.
    """
    if image_path and Path(image_path).is_file():
        return get_base64_image(image_path)
    return False
