# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM python:3.13-slim

WORKDIR /app

# Install common system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install ARM64-specific dependencies if needed
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
      libatlas-base-dev \
      && rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "app.py"]
