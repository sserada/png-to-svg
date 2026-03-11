FROM python:3.10-slim
WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ./ ./

RUN useradd -m appuser && chown -R appuser:appuser /usr/src/app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/backend/presets || exit 1
CMD ["python", "main.py"]
