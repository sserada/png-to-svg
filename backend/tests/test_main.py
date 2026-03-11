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
