#!/usr/bin/env bash
set -e

echo "=== Running Backend Tests ==="
cd backend
pip install -r requirements-dev.txt -q
python -m pytest tests/ -v
cd ..

echo ""
echo "=== Running Frontend Tests ==="
cd frontend
npm ci --silent
npm run test

echo ""
echo "=== All tests passed ==="
