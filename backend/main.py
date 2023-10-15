import os
import base64
import uvicorn
import cairosvg

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from PIL import Image

# Load environment variables
load_dotenv()

# Create FastAPI instance
app = FastAPI(docs_url='/api/docs')

# Validate environment variables
host = os.getenv("HOST")
port = os.getenv("PORT")

# Origin for CORS
origins = [
        'http://localhost:5173',
        f'http://{host}:{port}',
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
    png = open(path, 'rb').read()
    size = Image.open(path).size
    print(f"size: {size}")

    svg = f"""
    <svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg">
        <image href="data:image/png;base64,{base64.b64encode(png).decode()}" x="0" y="0" height="100%" width="100%"/>
    </svg>
    """
    with open(path.replace('png', 'svg'), 'w') as f:
        f.write(svg)

@app.post('/backend/{request_id}')
async def image_processing(request_id: str, data: Dict):
    img = data['data'].split(',')[1]
    name = data['name']
    if not os.path.exists(f'static/{request_id}'):
        os.mkdir(f'static/{request_id}')
    with open(f'static/{request_id}/{name}', 'wb') as f:
        f.write(base64.b64decode(img))
    png_to_svg(f'static/{request_id}/{name}')
    return JSONResponse({'url': f'http://{host}:{port}/static/{request_id}/{name.replace("png", "svg")}'})

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(port))

