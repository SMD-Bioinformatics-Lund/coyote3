# Stage 1: App Build
FROM python:3.12.0-slim-bullseye as coyote3_app

LABEL base_image="python:3.12-slim"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote_3.0"

# Expose Flask app port
EXPOSE 8000

# Set working directory
WORKDIR /app

# System environment variables (hardcoded, do not change often)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev zlib1g-dev libsasl2-dev libldap2-dev \
    build-essential libssl-dev libffi-dev libjpeg-dev libpq-dev \
    liblcms2-dev libblas-dev libatlas-base-dev libglib2.0-dev \
    libpango1.0-0 less vim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Create logs directory
RUN mkdir ./logs
RUN mkdir ./redis_data

# Copy source code
COPY config/ ./config/
COPY config.py wsgi.py gunicorn.conf.py logging_setup.py ./
COPY coyote/ ./coyote/
COPY scripts/ ./scripts/

# Runtime environment variables that should be overridden by docker-compose.yml or .env file
ENV SCRIPT_NAME=""
ENV COYOTE_LOG_LEVEL="INFO"
# NOTE: Mongo settings (FLASK_MONGO_HOST etc) will be passed dynamically via docker-compose env_file

# Gunicorn command (you can override with `command:` in docker-compose if needed)
CMD ["gunicorn", "--timeout", "120", "-w", "2", "-e", "SCRIPT_NAME", "--log-level", "INFO", "--bind", "0.0.0.0:8000", "wsgi:app"]

# (Optional) Stage 2: MongoDB Dev Stage (you probably don't need it unless developing Mongo inside same build)
# FROM mongo:3.4-xenial as cdm_mongo_dev
# WORKDIR /data/cdm-db
# EXPOSE 27017/tcp

# CMD ["docker-entrypoint.sh", "mongod"]
