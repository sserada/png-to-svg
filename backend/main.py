"""
Image-to-SVG Converter API

FastAPI application that accepts image uploads (PNG, JPG, JPEG, WebP, BMP, GIF),
converts them to SVG using vtracer, and provides download + SSE progress endpoints.

Module structure:
    modules/config.py      - Constants, env vars, logging
    modules/validation.py  - File/UUID validation, filename sanitization
    modules/presets.py     - Conversion presets, custom param validation
    modules/converter.py   - vtracer wrapper
    modules/progress.py    - Progress tracking, SSE streaming, cleanup
"""
import os
import glob
import base64
import binascii
import asyncio
import time
import logging

import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Dict

# --- Module imports ---
from modules.config import (
    host, port, frontend_port,
    UPLOAD_RATE_LIMIT,
    MAX_BASE64_LENGTH,
    MAX_SVG_SIZE,
    CONVERSION_TIMEOUT_SECONDS,
    DEFAULT_PRESET,
    ERROR_CODES,
)
from modules.validation import (
    _validate_uuid,
    sanitize_filename,
    validate_file,
    validate_file_header,
)
from modules.presets import (
    PRESETS,
    CUSTOM_PARAM_RANGES,
    validate_custom_params,
)
from modules.converter import image_to_svg
from modules.progress import (
    _update_progress,
    event_generator,
    cleanup_old_files,
)

logger = logging.getLogger(__name__)


# ============================================================
# Application setup
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: mount static dir and start background cleanup."""
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


app = FastAPI(docs_url='/api/docs', lifespan=lifespan)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: use ALLOWED_ORIGINS env var if set, otherwise derive from host/port
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if _allowed_origins_env:
    origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    origins = [
            f'http://localhost:{frontend_port}',
            f'http://{host}:{frontend_port}',
            ]

app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST'],
        allow_headers=['Content-Type'],
        )


# ============================================================
# Routes
# ============================================================

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


@app.get('/backend/progress/{request_id}')
async def stream_progress(request_id: str):
    """SSE endpoint to stream conversion progress for a request."""
    if not _validate_uuid(request_id):
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid request_id: must be a valid UUID format', 'code': 'INVALID_UUID'}
        )

    return StreamingResponse(
        event_generator(request_id),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@app.post('/backend/upload/{request_id}')
@limiter.limit(UPLOAD_RATE_LIMIT)
async def image_processing(request: Request, request_id: str, data: Dict):
    """
    Process an uploaded image file and convert it to SVG.

    Flow: validate request -> decode base64 -> validate file -> save to disk
          -> convert via vtracer (in thread pool) -> return SVG URL
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

        # Validate preset type early, before any file processing
        preset = data.get('preset', DEFAULT_PRESET)
        if not isinstance(preset, str):
            raise HTTPException(
                status_code=400,
                detail={'error': 'Invalid preset: must be a string', 'code': 'INVALID_PRESET'}
            )

        _update_progress(request_id, 'decoding', 10)

        name = sanitize_filename(data['name'])

        # Extract base64 content from data URL (format: "data:<mime>;base64,<content>")
        try:
            img_data = data['data'].split(',')[1]
        except IndexError:
            raise HTTPException(
                status_code=400,
                detail={'error': 'Malformed data URL: missing base64 content.', 'code': 'MALFORMED_DATA_URL'}
            )

        # Check base64 payload size before decoding to prevent memory exhaustion
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

        # Determine conversion parameters: custom params take priority over preset
        custom_params = data.get('custom_params')
        if custom_params and isinstance(custom_params, dict):
            conversion_params = validate_custom_params(custom_params)
        else:
            if preset not in PRESETS:
                logger.warning(f"Invalid preset '{preset}' for request {request_id}, using default")
                preset = DEFAULT_PRESET
            conversion_params = None

        # Run conversion in a thread pool to avoid blocking the async event loop
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

        # Guard against extremely large SVG output
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

        # Build response URL using the request's protocol (supports HTTPS proxies)
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
    """Download a converted SVG file by request ID."""
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

    # Verify the resolved path stays within the expected directory (prevent path traversal)
    resolved = Path(svg_path[0]).resolve()
    if not resolved.is_relative_to(Path(request_dir).resolve()):
        raise HTTPException(status_code=404, detail={'error': 'Not found', 'code': 'NOT_FOUND'})

    svg_filename = resolved.name
    return FileResponse(
        str(resolved),
        media_type='image/svg+xml',
        headers={'Content-Disposition': f'attachment; filename="{svg_filename}"'}
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(port))
