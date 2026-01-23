import os
import glob
import base64
import uvicorn
import vtracer
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
ALLOWED_EXTENSIONS = {'.png'}
ERROR_CODES = {
    'INVALID_FORMAT': 'File format is not supported. Only PNG files are allowed.',
    'FILE_TOO_LARGE': f'File size exceeds the maximum limit of {MAX_FILE_SIZE / (1024 * 1024):.0f}MB.',
    'CONVERSION_FAILED': 'Failed to convert PNG to SVG. The image may be corrupted or too complex.',
    'MISSING_DATA': 'Invalid request data. Please provide both file name and data.',
}

# Load environment variables
load_dotenv()

# Create FastAPI instance
app = FastAPI(docs_url='/api/docs')

# Validate environment variables
host = os.getenv("HOST")
port = os.getenv("PORT")
frontend_port = os.getenv("FRONTEND_PORT")

# Origin for CORS
origins = [
        f'http://localhost:{frontend_port}',
        f'http://{host}:{frontend_port}',
        ]

# Enable CORS
app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
        )

@app.on_event('startup')
async def startup_event():
    if not os.path.exists('static'):
        os.mkdir('static')
    app.mount('/static', StaticFiles(directory='static'), name='static')
    logger.info("Application started successfully")

def validate_file(filename: str, file_size: int) -> None:
    """
    Validate file format and size.

    Args:
        filename: Name of the file
        file_size: Size of the file in bytes

    Raises:
        HTTPException: If validation fails
    """
    # Check file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file format: {filename} (extension: {file_ext})")
        raise HTTPException(
            status_code=400,
            detail={'error': ERROR_CODES['INVALID_FORMAT'], 'code': 'INVALID_FORMAT'}
        )

    # Check file size
    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {filename} ({file_size} bytes)")
        raise HTTPException(
            status_code=413,
            detail={'error': ERROR_CODES['FILE_TOO_LARGE'], 'code': 'FILE_TOO_LARGE'}
        )

def png_to_svg(path: str) -> str:
    """
    Convert PNG to SVG using vtracer for true vectorization.

    Args:
        path: Path to the PNG file to convert

    Returns:
        Path to the converted SVG file

    Raises:
        HTTPException: If conversion fails
    """
    output_path = path.replace('.png', '.svg').replace('.PNG', '.svg')

    try:
        logger.info(f"Starting conversion: {path}")
        vtracer.convert_image_to_svg_py(
            path,
            output_path,
            colormode='color',
            mode='spline',
            filter_speckle=4,
            color_precision=6,
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3
        )
        logger.info(f"Successfully converted: {path} -> {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Conversion failed for {path}: {str(e)}", exc_info=True)
        # Clean up partial files if they exist
        if os.path.exists(output_path):
            os.remove(output_path)
        raise HTTPException(
            status_code=500,
            detail={'error': ERROR_CODES['CONVERSION_FAILED'], 'code': 'CONVERSION_FAILED', 'details': str(e)}
        )

@app.post('/backend/upload/{request_id}')
async def image_processing(request_id: str, data: Dict):
    """
    Process uploaded PNG file and convert to SVG.

    Args:
        request_id: Unique request identifier
        data: Dictionary containing 'name' and 'data' (base64 encoded image)

    Returns:
        JSONResponse with the URL of the converted SVG file

    Raises:
        HTTPException: If validation or conversion fails
    """
    try:
        # Validate request data
        if 'name' not in data or 'data' not in data:
            logger.error(f"Missing data in request {request_id}")
            raise HTTPException(
                status_code=400,
                detail={'error': ERROR_CODES['MISSING_DATA'], 'code': 'MISSING_DATA'}
            )

        name = data['name']
        img_data = data['data'].split(',')[1]
        decoded_img = base64.b64decode(img_data)

        # Validate file
        validate_file(name, len(decoded_img))

        # Create directory if it doesn't exist
        request_dir = f'static/{request_id}'
        if not os.path.exists(request_dir):
            os.makedirs(request_dir, exist_ok=True)

        # Save the uploaded file
        file_path = f'{request_dir}/{name}'
        with open(file_path, 'wb') as f:
            f.write(decoded_img)
        logger.info(f"Saved uploaded file: {file_path}")

        # Convert to SVG
        output_path = png_to_svg(file_path)

        # Generate response URL
        svg_filename = Path(output_path).name
        response_url = f'http://{host}:{port}/static/{request_id}/{svg_filename}'

        logger.info(f"Request {request_id} completed successfully")
        return JSONResponse({
            'success': True,
            'url': response_url,
            'filename': svg_filename
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in request {request_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={'error': 'An unexpected error occurred', 'code': 'INTERNAL_ERROR', 'details': str(e)}
        )

@app.get('/backend/download/{request_id}', response_class=FileResponse)
async def get_image(request_id: str):
    if not os.path.exists(f'static/{request_id}'):
        return JSONResponse({'message': 'Not found'}, status_code=404)
    svg_path = glob.glob(f'static/{request_id}/*.svg')
    if len(svg_path) == 0:
        return JSONResponse({'message': 'Not found'}, status_code=404)
    return FileResponse(svg_path[0])

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(port))

