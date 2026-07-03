#!/bin/bash
set -e

. /root/.profile

echo "==> Installing frontend dependencies..."
cd frontend
npm ci

echo "==> Building Next.js frontend (static export)..."
NEXT_OUTPUT=export npm run build

echo "==> Frontend build complete. Output in frontend/out/"
cd ..
