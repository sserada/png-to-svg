import base64
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from main import (
    app,
    validate_file,
    _validate_uuid,
    sanitize_filename,
    PRESETS,
    progress_store,
    _update_progress,
)


# --- Unit tests for utility functions ---


class TestValidateUuid:
    def test_valid_uuid(self):
        assert _validate_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uuid_v4(self):
        assert _validate_uuid("f47ac10b-58cc-4372-a567-0e02b2c3d479") is True

    def test_invalid_uuid(self):
        assert _validate_uuid("not-a-uuid") is False

    def test_empty_string(self):
        assert _validate_uuid("") is False

    def test_partial_uuid(self):
        assert _validate_uuid("550e8400-e29b") is False


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("image.png") == "image.png"

    def test_path_traversal(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_path_traversal_with_slashes(self):
        assert sanitize_filename("/etc/shadow") == "shadow"

    def test_hidden_file(self):
        assert sanitize_filename(".hidden.png") == "hidden.png"

    def test_only_dots(self):
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("...")
        assert exc_info.value.status_code == 400

    def test_empty_filename(self):
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("")
        assert exc_info.value.status_code == 400

    def test_directory_only(self):
        # Path("foo/bar/").name returns "bar"
        assert sanitize_filename("foo/bar/baz.png") == "baz.png"


class TestValidateFile:
    def test_valid_png(self):
        # Should not raise
        validate_file("image.png", 1024)

    def test_valid_png_uppercase(self):
        validate_file("IMAGE.PNG", 1024)

    def test_valid_jpg(self):
        # JPG is now supported
        validate_file("image.jpg", 1024)

    def test_valid_jpeg(self):
        # JPEG is now supported
        validate_file("image.jpeg", 1024)

    def test_valid_webp(self):
        validate_file("image.webp", 1024)

    def test_valid_bmp(self):
        validate_file("image.bmp", 1024)

    def test_valid_gif(self):
        validate_file("image.gif", 1024)

    def test_valid_webp_uppercase(self):
        validate_file("IMAGE.WEBP", 1024)

    def test_valid_bmp_uppercase(self):
        validate_file("IMAGE.BMP", 1024)

    def test_valid_gif_uppercase(self):
        validate_file("IMAGE.GIF", 1024)

    def test_invalid_extension_txt(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_file("image.txt", 1024)
        assert exc_info.value.status_code == 400

    def test_invalid_extension_svg(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_file("image.svg", 1024)
        assert exc_info.value.status_code == 400

    def test_no_extension(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_file("image", 1024)
        assert exc_info.value.status_code == 400

    def test_file_too_large(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_file("image.png", 11 * 1024 * 1024)
        assert exc_info.value.status_code == 413

    def test_file_exactly_at_limit(self):
        # Should not raise
        validate_file("image.png", 10 * 1024 * 1024)


# --- Integration tests for endpoints ---


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/backend/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.anyio
async def test_upload_invalid_uuid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/backend/upload/not-a-uuid",
            json={"name": "test.png", "data": "data:image/png;base64,abc"},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_UUID"


@pytest.mark.anyio
async def test_upload_missing_data():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "test.png"},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "MISSING_DATA"


@pytest.mark.anyio
async def test_upload_invalid_format():
    # Create a small valid base64 payload with invalid file extension
    img_bytes = b"\x00" * 100
    b64 = base64.b64encode(img_bytes).decode()
    data_url = f"data:text/plain;base64,{b64}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "test.txt", "data": data_url},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_FORMAT"


@pytest.mark.anyio
@patch("main.image_to_svg")
async def test_upload_path_traversal(mock_image_to_svg):
    # Mock vtracer to avoid actual conversion
    mock_image_to_svg.return_value = "static/550e8400-e29b-41d4-a716-446655440000/passwd.svg"

    img_bytes = b"\x00" * 100
    b64 = base64.b64encode(img_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "../../etc/passwd.png", "data": data_url},
            )
    # Should succeed with sanitized filename, not write to ../../etc/
    # The filename gets sanitized to "passwd.png"
    assert response.status_code == 200


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
    b64 = base64.b64encode(png_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "test.png", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "test.svg"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_jpg_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    # JFIF header for JPG
    jpg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 50
    b64 = base64.b64encode(jpg_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "photo.jpg", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "photo.svg"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_jpeg_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    jpg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 50
    b64 = base64.b64encode(jpg_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "photo.jpeg", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "photo.svg"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_jpg_uppercase_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    jpg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 50
    b64 = base64.b64encode(jpg_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "PHOTO.JPG", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "PHOTO.svg"


@pytest.mark.anyio
@patch("main.image_to_svg")
async def test_upload_mixed_formats_sequentially(mock_image_to_svg):
    """Test uploading PNG, JPG, and JPEG files in sequence."""
    files = [
        ("test.png", "image/png", b'\x89PNG\r\n\x1a\n' + b'\x00' * 50),
        ("test.jpg", "image/jpeg", b'\xff\xd8\xff\xe0' + b'\x00' * 50),
        ("test.jpeg", "image/jpeg", b'\xff\xd8\xff\xe0' + b'\x00' * 50),
    ]

    for filename, mime, raw_bytes in files:
        svg_name = filename.rsplit(".", 1)[0] + ".svg"
        mock_image_to_svg.return_value = f"static/550e8400-e29b-41d4-a716-446655440000/{svg_name}"

        b64 = base64.b64encode(raw_bytes).decode()
        data_url = f"data:{mime};base64,{b64}"

        with patch("builtins.open", MagicMock()):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                    json={"name": filename, "data": data_url},
                )

        assert response.status_code == 200, f"Failed for {filename}"
        result = response.json()
        assert result["success"] is True
        assert result["filename"] == svg_name


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_jpg_conversion_failure(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock(
        side_effect=Exception("Corrupted image")
    )

    jpg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 50
    b64 = base64.b64encode(jpg_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        with patch("main.os.path.exists", side_effect=lambda p: False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                    json={"name": "corrupted.jpg", "data": data_url},
                )

    assert response.status_code == 500
    result = response.json()
    assert result["detail"]["code"] == "CONVERSION_FAILED"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_webp_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    webp_bytes = b'RIFF' + b'\x00' * 4 + b'WEBP' + b'\x00' * 40
    b64 = base64.b64encode(webp_bytes).decode()
    data_url = f"data:image/webp;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "photo.webp", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "photo.svg"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_bmp_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    bmp_bytes = b'BM' + b'\x00' * 50
    b64 = base64.b64encode(bmp_bytes).decode()
    data_url = f"data:image/bmp;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "photo.bmp", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "photo.svg"


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_gif_success(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    gif_bytes = b'GIF89a' + b'\x00' * 50
    b64 = base64.b64encode(gif_bytes).decode()
    data_url = f"data:image/gif;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "animation.gif", "data": data_url},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["filename"] == "animation.svg"


class TestPresets:
    def test_presets_exist(self):
        assert 'high_quality' in PRESETS
        assert 'balanced' in PRESETS
        assert 'fast' in PRESETS

    def test_preset_keys(self):
        for preset_name, params in PRESETS.items():
            assert 'colormode' in params
            assert 'filter_speckle' in params
            assert 'color_precision' in params

    def test_high_quality_more_precise(self):
        assert PRESETS['high_quality']['color_precision'] > PRESETS['balanced']['color_precision']
        assert PRESETS['high_quality']['max_iterations'] > PRESETS['balanced']['max_iterations']

    def test_fast_less_precise(self):
        assert PRESETS['fast']['color_precision'] < PRESETS['balanced']['color_precision']
        assert PRESETS['fast']['max_iterations'] < PRESETS['balanced']['max_iterations']


@pytest.mark.anyio
async def test_get_presets():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/backend/presets")
    assert response.status_code == 200
    result = response.json()
    assert 'presets' in result
    assert 'balanced' in result['presets']
    assert result['default'] == 'balanced'


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_with_preset(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
    b64 = base64.b64encode(png_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "test.png", "data": data_url, "preset": "high_quality"},
            )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    # Verify vtracer was called with high_quality params
    call_kwargs = mock_vtracer.convert_image_to_svg_py.call_args
    assert call_kwargs[1]['color_precision'] == 8


@pytest.mark.anyio
@patch("main.vtracer")
@patch("main.os.makedirs")
@patch("main.os.path.exists", return_value=False)
async def test_upload_with_invalid_preset_falls_back(mock_exists, mock_makedirs, mock_vtracer):
    mock_vtracer.convert_image_to_svg_py = MagicMock()

    png_bytes = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
    b64 = base64.b64encode(png_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    with patch("builtins.open", MagicMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/backend/upload/550e8400-e29b-41d4-a716-446655440000",
                json={"name": "test.png", "data": data_url, "preset": "nonexistent"},
            )

    assert response.status_code == 200
    # Should fall back to balanced
    call_kwargs = mock_vtracer.convert_image_to_svg_py.call_args
    assert call_kwargs[1]['color_precision'] == 6


@pytest.mark.anyio
async def test_download_invalid_uuid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/backend/download/not-a-uuid")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_download_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/backend/download/550e8400-e29b-41d4-a716-446655440001"
        )
    assert response.status_code == 404


# --- SSE Progress endpoint tests ---


@pytest.mark.anyio
async def test_progress_invalid_uuid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/backend/progress/not-a-uuid")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_progress_completed_stream():
    """Test that SSE stream returns progress and terminates on completion."""
    request_id = "550e8400-e29b-41d4-a716-446655440099"
    # Pre-populate progress as completed
    progress_store[request_id] = {'stage': 'completed', 'progress': 100}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/backend/progress/{request_id}")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Should contain the completed event
    assert '"completed"' in response.text
    assert '"progress": 100' in response.text

    # Cleanup
    progress_store.pop(request_id, None)


@pytest.mark.anyio
async def test_progress_failed_stream():
    """Test that SSE stream terminates on failure."""
    request_id = "550e8400-e29b-41d4-a716-446655440098"
    progress_store[request_id] = {'stage': 'failed', 'progress': 0}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/backend/progress/{request_id}")

    assert response.status_code == 200
    assert '"failed"' in response.text

    progress_store.pop(request_id, None)


class TestUpdateProgress:
    def test_update_progress_stores_entry(self):
        request_id = "test-progress-store-1"
        _update_progress(request_id, 'converting', 50)
        assert progress_store[request_id] == {'stage': 'converting', 'progress': 50}
        progress_store.pop(request_id, None)

    def test_update_progress_overwrites(self):
        request_id = "test-progress-store-2"
        _update_progress(request_id, 'decoding', 10)
        _update_progress(request_id, 'saving', 25)
        assert progress_store[request_id] == {'stage': 'saving', 'progress': 25}
        progress_store.pop(request_id, None)
