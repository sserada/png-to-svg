"""
Application configuration: constants, environment variables, and logging setup.
"""
import os
import logging

from dotenv import load_dotenv

# --- Logging ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Size & format limits ---

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
# Base64 encoding expands data by ~4/3; add padding tolerance
MAX_BASE64_LENGTH = MAX_FILE_SIZE * 4 // 3 + 100
MAX_SVG_SIZE = 50 * 1024 * 1024  # 50MB max SVG output size
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}


# --- Timing constants ---

CLEANUP_INTERVAL_SECONDS = 600          # Run cleanup every 10 minutes
FILE_MAX_AGE_SECONDS = 3600             # Delete files older than 1 hour
SSE_TIMEOUT_SECONDS = 60               # Max time for SSE progress stream
PROGRESS_CLEANUP_DELAY_SECONDS = 120    # Delay before cleaning up finished progress entries
PROGRESS_MAX_AGE_SECONDS = 300          # Max age for stale progress entries (5 minutes)
CONVERSION_TIMEOUT_SECONDS = 120        # Max time for a single conversion


# --- Rate limiting ---

UPLOAD_RATE_LIMIT = "10/minute"


# --- Default preset ---

DEFAULT_PRESET = 'balanced'


# --- Structured error messages ---

ERROR_CODES = {
    'INVALID_FORMAT': 'File format is not supported. Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF.',
    'FILE_TOO_LARGE': f'File size exceeds the maximum limit of {MAX_FILE_SIZE / (1024 * 1024):.0f}MB.',
    'CONVERSION_FAILED': 'Failed to convert image to SVG. The image may be corrupted or too complex.',
    'CONVERSION_TIMEOUT': 'Conversion timed out. The image may be too complex for this preset.',
    'MISSING_DATA': 'Invalid request data. Please provide both file name and data.',
    'PAYLOAD_TOO_LARGE': 'Base64 payload exceeds the maximum allowed size.',
    'SVG_TOO_LARGE': 'Generated SVG is too large. Try a simpler image or the "fast" preset.',
    'INVALID_FILE_HEADER': 'File content does not match its extension. The file may be corrupted or renamed.',
}


# --- Environment variables ---

load_dotenv()

host = os.getenv("HOST")
port = os.getenv("PORT")
frontend_port = os.getenv("FRONTEND_PORT")

_REQUIRED_ENV_VARS = {"HOST": host, "PORT": port, "FRONTEND_PORT": frontend_port}
_missing = [k for k, v in _REQUIRED_ENV_VARS.items() if not v]
if _missing:
    logger.warning(f"Missing environment variables: {', '.join(_missing)}. "
                   "Using defaults (HOST=localhost, PORT=8000, FRONTEND_PORT=3000).")
    host = host or "localhost"
    port = port or "8000"
    frontend_port = frontend_port or "3000"
