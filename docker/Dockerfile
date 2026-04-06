# Stage 1: Tailwind CSS Build
FROM node:20-alpine AS tailwind_builder

WORKDIR /app

COPY package.json ./
COPY tailwind.config.js ./
COPY scripts/sync-package-version.js ./scripts/sync-package-version.js
COPY coyote/__version__.py ./coyote/__version__.py
COPY coyote/static/css/tailwind.input.css ./coyote/static/css/tailwind.input.css
COPY coyote/static/js ./coyote/static/js
COPY coyote/templates ./coyote/templates
COPY coyote/blueprints ./coyote/blueprints

RUN npm install && npm run build:css

# Stage 2: Shared runtime base
FROM python:3.12.0-slim-bullseye as coyote3_runtime_base

LABEL base_image="python:3.12-slim"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote3"

# Set working directory
WORKDIR /app

# System environment variables (hardcoded, do not change often)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi
ARG GIT_COMMIT="unknown"
ARG BUILD_TIME="unknown"
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_TIME=${BUILD_TIME}

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

# Stage 3: Web runtime image
FROM coyote3_runtime_base as coyote3_web

EXPOSE 8000

COPY config/ ./config/
COPY wsgi.py ./
COPY deploy/gunicorn/gunicorn.conf.py ./gunicorn.conf.py
COPY coyote/ ./coyote/
COPY shared/ ./shared/
COPY CHANGELOG.md README.md LICENSE.txt ./
COPY --from=tailwind_builder /app/coyote/static/css/tailwind.css /app/coyote/static/css/tailwind.css

ENV SCRIPT_NAME="/coyote3"
CMD gunicorn --timeout 240 -w 2 --threads 2 -e SCRIPT_NAME=${SCRIPT_NAME} --log-level INFO --bind 0.0.0.0:8000 wsgi:app

# Stage 4: API runtime image
FROM coyote3_runtime_base as coyote3_api

EXPOSE 8001

COPY config/ ./config/
COPY asgi.py run_api.py ./
COPY api/ ./api/
COPY shared/ ./shared/
COPY coyote/__version__.py ./coyote/__version__.py
COPY coyote/static/data/ ./coyote/static/data/
COPY scripts/ ./scripts/

CMD python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --workers 4
