# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Set workdir
WORKDIR /app

# Install system dependencies (if any needed, add here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app code
COPY . .

# Expose port
EXPOSE 5001

# Entrypoint
CMD ["python", "app.py"]
