
# ==========================================
# Stage 1: Tailwind CSS Build
# ==========================================

FROM node:20-alpine AS tailwind_builder

WORKDIR /app

# Copy frontend dependencies
COPY package.json package-lock.json ./
COPY tailwind.config.js ./

# Copy version synchronization script
COPY scripts/sync-package-version.js ./scripts/sync-package-version.js
COPY coyote/__version__.py ./coyote/__version__.py

# Copy frontend source files
COPY coyote/static/css/tailwind.input.css ./coyote/static/css/tailwind.input.css
COPY coyote/static/js ./coyote/static/js
COPY coyote/templates ./coyote/templates
COPY coyote/blueprints ./coyote/blueprints

# Install dependencies and build Tailwind CSS
RUN npm ci && npm run build:css


# ==========================================
# Stage 2: Coyote3 Production Application
# ==========================================

FROM python:3.12.0-slim-bullseye AS coyote3_app

LABEL base_image="python:3.12-slim-bookworm"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote3"

WORKDIR /app

EXPOSE 8000

# ------------------------------------------
# Python and Flask environment
# ------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi.py \
    SCRIPT_NAME=/coyote3

# ------------------------------------------
# Build metadata
# ------------------------------------------

ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

ENV GIT_COMMIT=${GIT_COMMIT} \
    BUILD_TIME=${BUILD_TIME}

# ------------------------------------------
# System dependencies
# ------------------------------------------

# Use archived Debian 11 repositories.
# Bullseye reached end-of-life on 31 August 2026.
RUN printf '%s\n' \
    'deb http://archive.debian.org/debian bullseye main' \
    'deb [check-valid-until=no] http://archive.debian.org/debian-security bullseye-security main' \
    > /etc/apt/sources.list \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libsasl2-dev \
        libldap2-dev \
        build-essential \
        libssl-dev \
        libffi-dev \
        libjpeg-dev \
        libpq-dev \
        liblcms2-dev \
        libblas-dev \
        libatlas-base-dev \
        libglib2.0-dev \
        libpango1.0-0 \
        less \
        vim \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------
# Python dependencies
# ------------------------------------------

COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# ------------------------------------------
# Application directories
# ------------------------------------------

RUN mkdir -p /app/logs /app/redis_data

# ------------------------------------------
# Application source
# ------------------------------------------

COPY config/ ./config/

COPY config.py \
     wsgi.py \
     gunicorn.conf.py \
     logging_setup.py \
     ./

COPY coyote/ ./coyote/
COPY docs/ ./docs/

COPY CHANGELOG.md README.md LICENSE.txt ./

# ------------------------------------------
# Tailwind CSS build output
# ------------------------------------------

COPY --from=tailwind_builder \
    /app/coyote/static/css/tailwind.css \
    /app/coyote/static/css/tailwind.css

# ------------------------------------------
# Production runtime configuration
# ------------------------------------------

# SECRET_KEY, COYOTE3_FERNET_KEY, MongoDB,
# Redis and other application configuration
# are provided by install.sh at runtime.

# ------------------------------------------
# Gunicorn
# ------------------------------------------

CMD ["sh", "-c", "exec gunicorn --timeout 240 --workers 2 --threads 2 --log-level INFO --bind 0.0.0.0:8000 wsgi:app"]
