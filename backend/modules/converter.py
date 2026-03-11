"""
Image-to-SVG conversion using vtracer.

Wraps vtracer.convert_image_to_svg_py with error handling and cleanup.
Called from a thread pool (asyncio.to_thread) to avoid blocking the event loop.
"""
import os
import logging
from pathlib import Path

import vtracer
from fastapi import HTTPException

from modules.config import DEFAULT_PRESET, ERROR_CODES
from modules.presets import PRESETS

logger = logging.getLogger(__name__)


def image_to_svg(path: str, params: dict | None = None, preset: str = DEFAULT_PRESET) -> str:
    """
    Convert an image file to SVG using vtracer.

    Args:
        path: Path to the source image file
        params: Custom vtracer parameters (overrides preset if provided)
        preset: Named preset to use when params is None

    Returns:
        Path to the generated SVG file

    Raises:
        HTTPException: If conversion fails (cleans up partial output)
    """
    output_path = str(Path(path).with_suffix('.svg'))
    if params is None:
        params = PRESETS.get(preset, PRESETS[DEFAULT_PRESET])

    try:
        logger.info(f"Starting conversion: {path} (preset: {preset})")
        vtracer.convert_image_to_svg_py(
            path,
            output_path,
            **params
        )
        logger.info(f"Successfully converted: {path} -> {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Conversion failed for {path}: {str(e)}", exc_info=True)
        # Clean up any partial SVG output
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as remove_err:
                logger.error(f"Failed to clean up {output_path}: {remove_err}")
        raise HTTPException(
            status_code=500,
            detail={'error': ERROR_CODES['CONVERSION_FAILED'], 'code': 'CONVERSION_FAILED'}
        )
