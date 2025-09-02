# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# BLAS/LAPACK via OpenBLAS; gfortran is needed if you build SciPy from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    gfortran \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "app.py"]

