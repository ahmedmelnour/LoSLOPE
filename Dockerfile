# syntax=docker/dockerfile:1
# LoSLOPE — single image: build the React frontend, then run the FastAPI
# backend which serves that built SPA plus the API/WebSocket.

# --- Stage 1: build the frontend ------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend runtime ---------------------------------------------
FROM python:3.12-slim
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Place the built SPA where the backend expects it (../frontend/dist).
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
# Render (and most hosts) inject $PORT; fall back to 8000 locally.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
