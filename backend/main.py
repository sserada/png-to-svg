import os
import glob
import base64
import uvicorn
import vtracer

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

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

def png_to_svg(path: str):
    """
    Convert PNG to SVG using vtracer for true vectorization.

    Args:
        path: Path to the PNG file to convert
    """
    output_path = path.replace('png', 'svg')

    try:
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
        print(f"Successfully converted: {path} -> {output_path}")
    except Exception as e:
        print(f"Error converting {path}: {str(e)}")
        raise

@app.post('/backend/upload/{request_id}')
async def image_processing(request_id: str, data: Dict):
    img = data['data'].split(',')[1]
    name = data['name']
    if not os.path.exists(f'static/{request_id}'):
        os.mkdir(f'static/{request_id}')
    with open(f'static/{request_id}/{name}', 'wb') as f:
        f.write(base64.b64decode(img))
    png_to_svg(f'static/{request_id}/{name}')
    return JSONResponse({'url': f'http://{host}:{port}/static/{request_id}/{name.replace("png", "svg")}'})

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

