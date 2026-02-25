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

# Stage 2: App Build
FROM python:3.12.0-slim-bullseye as coyote3_app

LABEL base_image="python:3.12-slim"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote3"

# Expose Flask app port
EXPOSE 8000

# Set working directory
WORKDIR /app

# System environment variables (hardcoded, do not change often)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py
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

# Copy source code
COPY config/ ./config/
COPY config.py wsgi.py gunicorn.conf.py logging_setup.py .coyote3_env ./
COPY .coyote3_env ./.env
COPY coyote/ ./coyote/
COPY docs/ ./docs/
COPY CHANGELOG.md README.md LICENSE.txt ./

# Copy pre-built Tailwind output into runtime image
COPY --from=tailwind_builder /app/coyote/static/css/tailwind.css /app/coyote/static/css/tailwind.css

# Runtime environment variables that should be overridden by docker-compose.yml or .env file
ENV SCRIPT_NAME="/coyote3"

# Gunicorn command (you can override with `command:` in docker-compose if needed)
#CMD ["gunicorn", "--timeout", "120", "-w", "2", "-e", "SCRIPT_NAME", "--log-level", "INFO", "--bind", "0.0.0.0:8000", "wsgi:app"]
CMD gunicorn --timeout 240 -w 2 --threads 2 -e SCRIPT_NAME=${SCRIPT_NAME} --log-level INFO --bind 0.0.0.0:8000 wsgi:app
