import json
import os
import glob
import base64
import binascii
import asyncio
import time
import uuid
import logging
import uvicorn
import vtracer
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
MAX_BASE64_LENGTH = MAX_FILE_SIZE * 4 // 3 + 100  # Base64 overhead + padding
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
CLEANUP_INTERVAL_SECONDS = 600   # Run cleanup every 10 minutes
FILE_MAX_AGE_SECONDS = 3600      # Delete files older than 1 hour
SSE_TIMEOUT_SECONDS = 60              # Max time for SSE progress stream
PROGRESS_CLEANUP_DELAY_SECONDS = 120   # Delay before cleaning up progress entries
PROGRESS_MAX_AGE_SECONDS = 300         # Max age for stale progress entries (5 minutes)
CONVERSION_TIMEOUT_SECONDS = 120       # Max time for a single conversion
MAX_SVG_SIZE = 50 * 1024 * 1024        # 50MB max SVG output size
DEFAULT_PRESET = 'balanced'
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

# Magic number signatures for supported image formats
IMAGE_SIGNATURES = {
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.bmp': [b'BM'],
    '.webp': [b'RIFF'],  # Full check: RIFF????WEBP
}

# Rate limiting
UPLOAD_RATE_LIMIT = "10/minute"
limiter = Limiter(key_func=get_remote_address)

# Progress tracking for SSE
progress_store: Dict[str, dict] = {}

# Load environment variables
load_dotenv()

# Validate required environment variables
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


async def cleanup_old_files() -> None:
    """Background task to periodically delete old files and stale progress entries."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            if not os.path.exists('static'):
                continue
            now = time.time()
            for entry in os.scandir('static'):
                if not entry.is_dir():
                    continue
                entry_path = entry.path
                if now - entry.stat().st_mtime > FILE_MAX_AGE_SECONDS:
                    for file in os.scandir(entry_path):
                        file_path = file.path
                        try:
                            os.remove(file_path)
                            logger.info(f"Deleted old file: {file_path}")
                        except OSError as e:
                            logger.error(f"Failed to delete file {file_path}: {e}")
                    try:
                        os.rmdir(entry_path)
                        logger.info(f"Deleted old directory: {entry_path}")
                    except OSError as e:
                        logger.error(f"Failed to delete directory {entry_path}: {e}")
        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")

        # Clean up stale progress entries
        try:
            now_mono = time.monotonic()
            stale_keys = [
                k for k, v in progress_store.items()
                if now_mono - v.get('_updated_at', 0) > PROGRESS_MAX_AGE_SECONDS
            ]
            for k in stale_keys:
                progress_store.pop(k, None)
            if stale_keys:
                logger.info(f"Cleaned up {len(stale_keys)} stale progress entries")
        except Exception as e:
            logger.error(f"Error during progress cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    if not os.path.exists('static'):
        os.mkdir('static')
    app.mount('/static', StaticFiles(directory='static'), name='static')
    cleanup_task = asyncio.create_task(cleanup_old_files())
    logger.info("Application started successfully")
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# Create FastAPI instance
app = FastAPI(docs_url='/api/docs', lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Origin for CORS
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if _allowed_origins_env:
    origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    origins = [
            f'http://localhost:{frontend_port}',
            f'http://{host}:{frontend_port}',
            ]

# Enable CORS
app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type'],
        )


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


def validate_file_header(filename: str, data: bytes) -> None:
    """
    Validate that file content matches its extension using magic numbers.

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

    # Additional check for WebP: RIFF????WEBP
    if file_ext == '.webp' and len(data) >= 12 and data[8:12] != b'WEBP':
        logger.warning(f"File is RIFF but not WebP: {filename}")
        raise HTTPException(
            status_code=400,
            detail={'error': ERROR_CODES['INVALID_FILE_HEADER'], 'code': 'INVALID_FILE_HEADER'}
        )


def validate_file(filename: str, file_size: int) -> None:
    """
    Validate file format and size.

    Raises:
        HTTPException: If validation fails
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

PRESETS = {
    'high_quality': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 8,
        'layer_difference': 8,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 20,
        'splice_threshold': 45,
        'path_precision': 5,
    },
    'balanced': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 4,
        'color_precision': 6,
        'layer_difference': 16,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 10,
        'splice_threshold': 45,
        'path_precision': 3,
    },
    'fast': {
        'colormode': 'color',
        'mode': 'spline',
        'filter_speckle': 8,
        'color_precision': 4,
        'layer_difference': 32,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 5,
        'splice_threshold': 45,
        'path_precision': 2,
    },
}


# Allowed custom parameter ranges for validation
CUSTOM_PARAM_RANGES = {
    'colormode': {'type': 'enum', 'values': ['color', 'binary']},
    'mode': {'type': 'enum', 'values': ['spline', 'polygon', 'none']},
    'filter_speckle': {'type': 'int', 'min': 1, 'max': 128},
    'color_precision': {'type': 'int', 'min': 1, 'max': 8},
    'layer_difference': {'type': 'int', 'min': 1, 'max': 256},
    'corner_threshold': {'type': 'int', 'min': 0, 'max': 180},
    'length_threshold': {'type': 'float', 'min': 0.0, 'max': 100.0},
    'max_iterations': {'type': 'int', 'min': 1, 'max': 50},
    'splice_threshold': {'type': 'int', 'min': 0, 'max': 180},
    'path_precision': {'type': 'int', 'min': 1, 'max': 10},
}


def validate_custom_params(params: dict) -> dict:
    """Validate and sanitize custom conversion parameters.

    Returns validated params merged with balanced preset defaults.

    Raises:
        HTTPException: If any parameter is invalid
    """
    base = dict(PRESETS[DEFAULT_PRESET])
    for key, value in params.items():
        if key not in CUSTOM_PARAM_RANGES:
            continue  # Ignore unknown keys
        spec = CUSTOM_PARAM_RANGES[key]
        if spec['type'] == 'enum':
            if value not in spec['values']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: {value}. "
                            f"Allowed: {spec['values']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = value
        elif spec['type'] == 'int':
            try:
                val = int(value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: must be integer",
                            'code': 'INVALID_PARAM'}
                )
            if val < spec['min'] or val > spec['max']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Value for {key} must be between "
                            f"{spec['min']} and {spec['max']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = val
        elif spec['type'] == 'float':
            try:
                val = float(value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Invalid value for {key}: must be number",
                            'code': 'INVALID_PARAM'}
                )
            if val < spec['min'] or val > spec['max']:
                raise HTTPException(
                    status_code=400,
                    detail={'error': f"Value for {key} must be between "
                            f"{spec['min']} and {spec['max']}", 'code': 'INVALID_PARAM'}
                )
            base[key] = val
    return base


def image_to_svg(path: str, params: dict | None = None, preset: str = DEFAULT_PRESET) -> str:
    """
    Convert image to SVG using vtracer for true vectorization.

    Args:
        path: Path to the image file to convert
        params: Custom conversion parameters (overrides preset)
        preset: Conversion preset ('high_quality', 'balanced', 'fast')

    Returns:
        Path to the converted SVG file

    Raises:
        HTTPException: If conversion fails
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
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as remove_err:
                logger.error(f"Failed to clean up {output_path}: {remove_err}")
        raise HTTPException(
            status_code=500,
            detail={'error': ERROR_CODES['CONVERSION_FAILED'], 'code': 'CONVERSION_FAILED'}
        )


@app.get('/backend/health')
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({'status': 'healthy'})


@app.get('/backend/presets')
async def get_presets() -> JSONResponse:
    """Return available conversion presets and custom parameter definitions."""
    return JSONResponse({
        'presets': list(PRESETS.keys()),
        'default': DEFAULT_PRESET,
        'preset_values': PRESETS,
        'custom_params': CUSTOM_PARAM_RANGES,
    })


def _update_progress(request_id: str, stage: str, progress: int) -> None:
    """Update progress for a request."""
    progress_store[request_id] = {
        'stage': stage,
        'progress': progress,
        '_updated_at': time.monotonic(),
    }
    if stage in ('completed', 'failed'):
        asyncio.get_running_loop().call_later(
            PROGRESS_CLEANUP_DELAY_SECONDS,
            progress_store.pop, request_id, None
        )


@app.get('/backend/progress/{request_id}')
async def stream_progress(request_id: str):
    """SSE endpoint to stream conversion progress for a request."""
    if not _validate_uuid(request_id):
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid request_id: must be a valid UUID format', 'code': 'INVALID_UUID'}
        )

    async def event_generator():
        last_stage = None
        start_time = time.monotonic()
        while time.monotonic() - start_time < SSE_TIMEOUT_SECONDS:
            entry = progress_store.get(request_id)
            if entry and entry['stage'] != last_stage:
                last_stage = entry['stage']
                client_entry = {k: v for k, v in entry.items() if not k.startswith('_')}
                yield f"data: {json.dumps(client_entry)}\n\n"
                if entry['stage'] in ('completed', 'failed'):
                    return
            await asyncio.sleep(0.2)
        yield f"data: {json.dumps({'stage': 'timeout', 'progress': 0})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@app.post('/backend/upload/{request_id}')
@limiter.limit(UPLOAD_RATE_LIMIT)
async def image_processing(request: Request, request_id: str, data: Dict):
    """
    Process uploaded PNG file and convert to SVG.
    """
    if not _validate_uuid(request_id):
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid request_id: must be a valid UUID format', 'code': 'INVALID_UUID'}
        )

    try:
        if 'name' not in data or 'data' not in data:
            logger.error(f"Missing data in request {request_id}")
            raise HTTPException(
                status_code=400,
                detail={'error': ERROR_CODES['MISSING_DATA'], 'code': 'MISSING_DATA'}
            )

        preset = data.get('preset', DEFAULT_PRESET)
        if not isinstance(preset, str):
            raise HTTPException(
                status_code=400,
                detail={'error': 'Invalid preset: must be a string', 'code': 'INVALID_PRESET'}
            )

        _update_progress(request_id, 'decoding', 10)

        name = sanitize_filename(data['name'])

        try:
            img_data = data['data'].split(',')[1]
        except IndexError:
            raise HTTPException(
                status_code=400,
                detail={'error': 'Malformed data URL: missing base64 content.', 'code': 'MALFORMED_DATA_URL'}
            )

        if len(img_data) > MAX_BASE64_LENGTH:
            logger.warning(f"Base64 payload too large: {len(img_data)} chars (max {MAX_BASE64_LENGTH})")
            raise HTTPException(
                status_code=413,
                detail={'error': ERROR_CODES['PAYLOAD_TOO_LARGE'], 'code': 'PAYLOAD_TOO_LARGE'}
            )

        try:
            decoded_img = base64.b64decode(img_data, validate=True)
        except binascii.Error:
            raise HTTPException(
                status_code=400,
                detail={'error': 'Invalid base64 data.', 'code': 'INVALID_BASE64'}
            )

        validate_file(name, len(decoded_img))
        validate_file_header(name, decoded_img)

        _update_progress(request_id, 'saving', 25)

        request_dir = f'static/{request_id}'
        os.makedirs(request_dir, exist_ok=True)

        file_path = f'{request_dir}/{name}'
        with open(file_path, 'wb') as f:
            f.write(decoded_img)
        logger.info(f"Saved uploaded file: {file_path}")

        _update_progress(request_id, 'converting', 50)

        original_size = len(decoded_img)

        # Convert to SVG (run in thread pool to avoid blocking event loop)
        custom_params = data.get('custom_params')
        if custom_params and isinstance(custom_params, dict):
            conversion_params = validate_custom_params(custom_params)
        else:
            if preset not in PRESETS:
                logger.warning(f"Invalid preset '{preset}' for request {request_id}, using default")
                preset = DEFAULT_PRESET
            conversion_params = None

        convert_start = time.monotonic()
        try:
            output_path = await asyncio.wait_for(
                asyncio.to_thread(image_to_svg, file_path, conversion_params, preset),
                timeout=CONVERSION_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Conversion timed out for request {request_id}")
            raise HTTPException(
                status_code=504,
                detail={'error': ERROR_CODES['CONVERSION_TIMEOUT'], 'code': 'CONVERSION_TIMEOUT'}
            )
        conversion_time_ms = round((time.monotonic() - convert_start) * 1000)

        svg_size = os.path.getsize(output_path)
        if svg_size > MAX_SVG_SIZE:
            logger.warning(f"SVG output too large: {svg_size} bytes for request {request_id}")
            try:
                os.remove(output_path)
            except OSError as remove_err:
                logger.error(f"Failed to remove oversized SVG {output_path}: {remove_err}")
            raise HTTPException(
                status_code=413,
                detail={'error': ERROR_CODES['SVG_TOO_LARGE'], 'code': 'SVG_TOO_LARGE'}
            )
        svg_filename = Path(output_path).name
        scheme = request.url.scheme
        response_url = f'{scheme}://{host}:{port}/static/{request_id}/{svg_filename}'

        _update_progress(request_id, 'completed', 100)

        logger.info(f"Request {request_id} completed successfully")
        return JSONResponse({
            'success': True,
            'url': response_url,
            'filename': svg_filename,
            'original_size': original_size,
            'svg_size': svg_size,
            'conversion_time_ms': conversion_time_ms,
        })

    except HTTPException:
        _update_progress(request_id, 'failed', 0)
        raise
    except Exception as e:
        _update_progress(request_id, 'failed', 0)
        logger.error(f"Unexpected error in request {request_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={'error': 'An unexpected error occurred', 'code': 'INTERNAL_ERROR'}
        )


@app.get('/backend/download/{request_id}')
async def get_image(request_id: str):
    if not _validate_uuid(request_id):
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid request_id: must be a valid UUID format', 'code': 'INVALID_UUID'}
        )
    request_dir = f'static/{request_id}'
    if not os.path.exists(request_dir):
        raise HTTPException(status_code=404, detail={'error': 'Not found', 'code': 'NOT_FOUND'})
    svg_path = glob.glob(f'{request_dir}/*.svg')
    if len(svg_path) == 0:
        raise HTTPException(status_code=404, detail={'error': 'Not found', 'code': 'NOT_FOUND'})
    resolved = Path(svg_path[0]).resolve()
    if not resolved.is_relative_to(Path(request_dir).resolve()):
        raise HTTPException(status_code=404, detail={'error': 'Not found', 'code': 'NOT_FOUND'})
    svg_filename = resolved.name
    return FileResponse(
        str(resolved),
        media_type='image/svg+xml',
        headers={'Content-Disposition': f'attachment; filename="{svg_filename}"'}
    )


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(port))
