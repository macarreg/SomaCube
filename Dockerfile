# Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

# Compile YASS for Linux
RUN cd backend/yass && make

WORKDIR /app/backend
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]