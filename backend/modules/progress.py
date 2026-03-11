"""
Progress tracking for file conversions.

Provides an in-memory store for conversion progress, SSE streaming to clients,
and periodic cleanup of stale/old entries and static files.
"""
import os
import json
import time
import asyncio
import logging
from typing import Dict

from modules.config import (
    CLEANUP_INTERVAL_SECONDS,
    FILE_MAX_AGE_SECONDS,
    SSE_TIMEOUT_SECONDS,
    PROGRESS_CLEANUP_DELAY_SECONDS,
    PROGRESS_MAX_AGE_SECONDS,
)

logger = logging.getLogger(__name__)

# In-memory progress store: request_id -> {stage, progress, _updated_at}
progress_store: Dict[str, dict] = {}


def _update_progress(request_id: str, stage: str, progress: int) -> None:
    """Update progress for a request.

    For terminal stages ('completed', 'failed'), schedules automatic
    cleanup after PROGRESS_CLEANUP_DELAY_SECONDS.
    """
    progress_store[request_id] = {
        'stage': stage,
        'progress': progress,
        '_updated_at': time.monotonic(),
    }
    if stage in ('completed', 'failed'):
        # Schedule delayed removal so the client has time to read the final state
        asyncio.get_running_loop().call_later(
            PROGRESS_CLEANUP_DELAY_SECONDS,
            progress_store.pop, request_id, None
        )


async def event_generator(request_id: str):
    """SSE event generator that yields progress updates for a request.

    Polls progress_store at 200ms intervals. Terminates when the stage
    reaches 'completed'/'failed' or the SSE_TIMEOUT_SECONDS is exceeded.
    Internal fields (prefixed with '_') are filtered from client output.
    """
    last_stage = None
    start_time = time.monotonic()
    while time.monotonic() - start_time < SSE_TIMEOUT_SECONDS:
        entry = progress_store.get(request_id)
        if entry and entry['stage'] != last_stage:
            last_stage = entry['stage']
            # Filter out internal fields (e.g., _updated_at) before sending
            client_entry = {k: v for k, v in entry.items() if not k.startswith('_')}
            yield f"data: {json.dumps(client_entry)}\n\n"
            if entry['stage'] in ('completed', 'failed'):
                return
        await asyncio.sleep(0.2)
    yield f"data: {json.dumps({'stage': 'timeout', 'progress': 0})}\n\n"


async def cleanup_old_files() -> None:
    """Background task to periodically delete old static files and stale progress entries.

    Runs every CLEANUP_INTERVAL_SECONDS. Deletes request directories whose
    modification time exceeds FILE_MAX_AGE_SECONDS, and removes progress
    entries older than PROGRESS_MAX_AGE_SECONDS.
    """
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

        # Clean up old static files
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
