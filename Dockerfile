FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ENV NEXT_OUTPUT=export
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/out ./frontend/out

# Set environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Start the app
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
