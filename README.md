# Image to SVG Converter

A modern web application that converts raster images (PNG, JPG/JPEG, WebP, BMP, GIF) to true vector SVG format using VTracer. Built with Svelte for the frontend and FastAPI for the backend, this tool provides real-time conversion progress tracking and comprehensive error handling.

https://github.com/fightingsou/png-to-svg/assets/104222305/a33c68de-1575-42ab-b524-ecc5016f263c

## Features

### Core Functionality

- **True Vector Conversion**: Powered by [VTracer](https://github.com/visioncortex/vtracer), converts raster images (PNG, JPG/JPEG, WebP, BMP, GIF) into scalable vector graphics (not just base64 embedding)
- **Drag & Drop Upload**: User-friendly interface with drag and drop support
- **Batch Processing**: Convert multiple image files simultaneously
- **ZIP Download**: Download all converted SVG files as a single ZIP archive

### User Experience

- **Real-time Progress**: Visual progress indicators for each file conversion
- **Status Tracking**: Per-file status display (Pending, Processing, Completed, Failed)
- **Error Handling**: Clear, actionable error messages when conversions fail
- **File Validation**: Client and server-side validation for file format and size

### Technical Details

- **File Formats**: PNG, JPG/JPEG, WebP, BMP, GIF (validated on upload)
- **File Size Limit**: 10MB per file
- **Quality Presets**: Three conversion presets — High Quality, Balanced, and Fast
- **Conversion Quality**: Configurable parameters for color precision, speckle filtering, and curve smoothing
- **Output**: True SVG vector paths (editable and infinitely scalable)

## Getting Started

### Prerequisites

- Docker (version 20.10 or later)
- Docker Compose (version 2.0 or later)

### Installation & Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/sserada/image-to-svg.git
   cd image-to-svg
   ```

2. **Configure environment variables**

   Copy the sample environment file:

   ```bash
   mv sample.env .env
   ```

3. **Edit `.env` file**

   Configure the following variables:

   ```bash
   IP=0.0.0.0                # Server IP address (use 0.0.0.0 for all interfaces)
   FRONTEND_PORT=55030       # Frontend port (default: 55030)
   BACKEND_PORT=55031        # Backend API port (default: 55031)
   ```

   > **Note**: You can find your local IP address using `ip a` (Linux) or `ifconfig` (macOS).

4. **Start the application**

   ```bash
   docker compose up -d
   ```

   This will:

   - Build the frontend and backend containers
   - Install all dependencies (including VTracer)
   - Start both services with hot-reload enabled

5. **Access the application**

   Open your browser and navigate to:

   ```
   http://{IP}:{FRONTEND_PORT}
   ```

   For example, if using default settings on localhost:

   ```
   http://localhost:55030
   ```

### Stopping the Application

```bash
docker compose down
```

## Usage

1. **Upload image files**: Drag and drop image files (PNG, JPG/JPEG, WebP, BMP, GIF) or click to select
2. **Select a quality preset**:
   - **High Quality**: Best visual fidelity, slower conversion (high color precision, minimal speckle filtering)
   - **Balanced** (default): Good trade-off between quality and speed
   - **Fast**: Quickest conversion, reduced detail (lower color precision, aggressive filtering)
3. **Click Send**: Start the conversion process
4. **Monitor Progress**: Watch real-time status for each file
5. **Download**: Once complete, click Download to get a ZIP of all SVG files

## Troubleshooting

### Common Issues

**Container fails to start:**

```bash
# Check logs
docker compose logs its-backend
docker compose logs its-frontend

# Rebuild containers
docker compose down
docker compose build --no-cache
docker compose up -d
```

**File conversion fails:**

- Ensure the file is a valid image format (PNG, JPG/JPEG, WebP, BMP, GIF)
- Check file size is under 10MB
- Verify the image is not too complex (millions of colors)

**Port already in use:**

- Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env`
- Restart the containers after making changes

## API Reference

### Health Check

```
GET /backend/health
```

Returns `{"status": "healthy"}` when the backend is running.

### Upload and Convert

```
POST /backend/upload/{request_id}
```

- `request_id` (path): UUID v4 format string
- Body (JSON): `{"name": "image.png", "data": "data:image/png;base64,...", "preset": "balanced"}`
- `preset` (optional): One of `high_quality`, `balanced` (default), `fast`
- Response: `{"success": true, "url": "...", "filename": "image.svg"}`

### List Presets

```
GET /backend/presets
```

Returns available conversion presets and their parameters:

```json
{
  "high_quality": {"color_precision": 8, "filter_speckle": 2, ...},
  "balanced": {"color_precision": 6, "filter_speckle": 4, ...},
  "fast": {"color_precision": 4, "filter_speckle": 8, ...}
}
```

### Download SVG

```
GET /backend/download/{request_id}
```

Returns the converted SVG file for the given request ID.

### Interactive Docs

Visit `http://localhost:55031/api/docs` for the Swagger UI.

## Development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
uvicorn main:app --host 0.0.0.0 --port 55031 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 55030
```

### Running Tests

```bash
# Backend
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run test
```

## FAQ

**Q: What is the maximum file size?**
A: 10MB per image.

**Q: Can I convert multiple files at once?**
A: Yes, select multiple files in the upload dialog. They are processed sequentially.

**Q: How long are converted files stored?**
A: Files are automatically deleted after 1 hour.

**Q: What conversion parameters does VTracer use?**
A: Three presets are available — High Quality, Balanced, and Fast. Each adjusts color precision, speckle filtering, and iteration count. Use the preset selector in the UI or the `preset` parameter in the API. See `backend/main.py` for exact values.

## Technology Stack

### Frontend

- **Framework**: Svelte 5 + SvelteKit 2
- **Styling**: Tailwind CSS
- **Language**: TypeScript

### Backend

- **Framework**: FastAPI (Python)
- **Vector Conversion**: VTracer 0.6.11
- **Server**: Uvicorn

### Infrastructure

- **Containerization**: Docker + Docker Compose
- **Development**: Hot-reload enabled for both frontend and backend

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [VTracer](https://github.com/visioncortex/vtracer) - Raster to vector graphics converter
- [Svelte](https://svelte.dev/) - Frontend framework
- [FastAPI](https://fastapi.tiangolo.com/) - Backend API framework

---

**Last Updated**: 2026-03-11
**Maintainer**: [sserada](https://srdev.com)
