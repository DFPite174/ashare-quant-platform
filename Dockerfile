# Dockerfile for A-Share Institutional Quant Platform Backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system build dependencies for Cython, OSQP, Clarabel
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and pyproject
COPY pyproject.toml .

# Install core quant & backend dependencies
RUN pip install --upgrade pip && \
    pip install \
    duckdb==1.5.5 \
    pyarrow==26.0.0 \
    pandas==2.2.3 \
    pydantic==2.14.1 \
    nautilus_trader==1.231.0 \
    tushare==1.4.29 \
    alphalens==0.4.8 \
    fastapi==0.162.0 \
    uvicorn==0.41.0 \
    scipy==1.15.3 \
    cvxpy==1.9.3 \
    pytest==9.1.1 \
    httpx

# Copy source code
COPY . .

EXPOSE 8000

CMD ["python", "scripts/run_server.py", "--host", "0.0.0.0", "--port", "8000"]
