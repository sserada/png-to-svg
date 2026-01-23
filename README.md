# PNG to SVG Converter

A modern web application that converts PNG images to true vector SVG format using VTracer. Built with Svelte for the frontend and FastAPI for the backend, this tool provides real-time conversion progress tracking and comprehensive error handling.

https://github.com/fightingsou/png-to-svg/assets/104222305/a33c68de-1575-42ab-b524-ecc5016f263c

## Features

### Core Functionality

- **True Vector Conversion**: Powered by [VTracer](https://github.com/visioncortex/vtracer), converts raster PNG images into scalable vector graphics (not just base64 embedding)
- **Drag & Drop Upload**: User-friendly interface with drag and drop support
- **Batch Processing**: Convert multiple PNG files simultaneously
- **ZIP Download**: Download all converted SVG files as a single ZIP archive

### User Experience

- **Real-time Progress**: Visual progress indicators for each file conversion
- **Status Tracking**: Per-file status display (Pending, Processing, Completed, Failed)
- **Error Handling**: Clear, actionable error messages when conversions fail
- **File Validation**: Client and server-side validation for file format and size

### Technical Details

- **File Format**: PNG only (validated on upload)
- **File Size Limit**: 10MB per file
- **Conversion Quality**: Configurable parameters for color precision, speckle filtering, and curve smoothing
- **Output**: True SVG vector paths (editable and infinitely scalable)

## Getting Started

### Prerequisites

- Docker (version 20.10 or later)
- Docker Compose (version 2.0 or later)

### Installation & Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/sserada/png-to-svg.git
   cd png-to-svg
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
   docker-compose up -d
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
docker-compose down
```

## Usage

1. **Upload PNG files**: Drag and drop PNG files or click to select
2. **Click Send**: Start the conversion process
3. **Monitor Progress**: Watch real-time status for each file
4. **Download**: Once complete, click Download to get a ZIP of all SVG files

## Troubleshooting

### Common Issues

**Container fails to start:**

```bash
# Check logs
docker logs pts-backend
docker logs pts-frontend

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**File conversion fails:**

- Ensure the file is a valid PNG (not corrupted)
- Check file size is under 10MB
- Verify the PNG is not too complex (millions of colors)

**Port already in use:**

- Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env`
- Restart the containers after making changes

## Technology Stack

### Frontend

- **Framework**: Svelte + SvelteKit
- **Styling**: Tailwind CSS + Skeleton UI
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

**Last Updated**: 2026-01-23
**Maintainer**: [sserada](https://srdev.com)
