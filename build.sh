#!/bin/bash
# Build script for the Next.js frontend.
# Railpack detects and runs this automatically before starting the Python app.
# The FastAPI backend serves the static export from frontend/out/ at /.

set -e

echo "==> Installing frontend dependencies..."
cd frontend
npm ci

echo "==> Building Next.js frontend (static export)..."
NEXT_OUTPUT=export npm run build

echo "==> Frontend build complete. Output in frontend/out/"
cd ..
