"""
Input validation: file format/size checks, UUID validation, filename sanitization,
and magic-number header verification.
"""
import uuid
import logging
from pathlib import Path

from fastapi import HTTPException

from modules.config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    ERROR_CODES,
)

logger = logging.getLogger(__name__)

# Magic number signatures for supported image formats.
# Each extension maps to a list of valid byte prefixes.
IMAGE_SIGNATURES = {
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.bmp': [b'BM'],
    '.webp': [b'RIFF'],  # Full check below: RIFF????WEBP
}


def _validate_uuid(value: str) -> bool:
    """Validate that a string is a valid UUID format."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a user-provided filename to prevent path traversal attacks.

    Strips directory components and leading dots, then validates
    the result is non-empty.

    Raises:
        HTTPException: If the filename is empty or invalid after sanitization
    """
    # Strip directory components (e.g., ../../etc/passwd -> passwd)
    sanitized = Path(filename).name
    # Strip leading dots to prevent hidden files
    sanitized = sanitized.lstrip('.')
    if not sanitized:
        logger.warning(f"Invalid filename after sanitization: {filename!r}")
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid filename.', 'code': 'INVALID_FILENAME'}
        )
    return sanitized


def validate_file(filename: str, file_size: int) -> None:
    """
    Validate file extension and size.

    Raises:
        HTTPException: If extension is unsupported or file exceeds size limit
    """
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file format: {filename} (extension: {file_ext})")
        raise HTTPException(
            status_code=400,
            detail={'error': ERROR_CODES['INVALID_FORMAT'], 'code': 'INVALID_FORMAT'}
        )
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {filename} ({file_size} bytes)")
        raise HTTPException(
            status_code=413,
            detail={'error': ERROR_CODES['FILE_TOO_LARGE'], 'code': 'FILE_TOO_LARGE'}
        )


def validate_file_header(filename: str, data: bytes) -> None:
    """
    Validate that file content matches its extension using magic number signatures.

    Prevents renamed files (e.g., a .exe renamed to .png) from being processed.

    Raises:
        HTTPException: If file header doesn't match the extension
    """
    file_ext = Path(filename).suffix.lower()
    signatures = IMAGE_SIGNATURES.get(file_ext)
    if signatures is None:
        return  # Extension not in signature map, skip header check

    if not any(data.startswith(sig) for sig in signatures):
        logger.warning(f"File header mismatch for {filename}: extension {file_ext} "
                       f"but header bytes {data[:8].hex()}")
        raise HTTPException(
            status_code=400,
            detail={'error': ERROR_CODES['INVALID_FILE_HEADER'], 'code': 'INVALID_FILE_HEADER'}
        )

    # WebP files are RIFF containers; verify the WEBP subtype at byte offset 8
    if file_ext == '.webp' and len(data) >= 12 and data[8:12] != b'WEBP':
        logger.warning(f"File is RIFF but not WebP: {filename}")
        raise HTTPException(
            status_code=400,
            detail={'error': ERROR_CODES['INVALID_FILE_HEADER'], 'code': 'INVALID_FILE_HEADER'}
        )
