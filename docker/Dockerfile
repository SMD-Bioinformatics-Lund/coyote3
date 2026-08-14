FROM python:3.12-slim-bookworm AS coyote3_runtime_base

LABEL base_image="python:3.12-slim"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote3"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG GIT_COMMIT="unknown"
ARG BUILD_TIME="unknown"
ARG COYOTE3_UID=10001
ARG COYOTE3_GID=10001
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_TIME=${BUILD_TIME}

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev zlib1g-dev libsasl2-dev libldap2-dev \
    build-essential libssl-dev libffi-dev libjpeg-dev libpq-dev \
    liblcms2-dev libblas-dev libatlas-base-dev libglib2.0-dev \
    libpango-1.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid "${COYOTE3_GID}" coyote3 && \
    useradd --uid "${COYOTE3_UID}" --gid coyote3 --create-home coyote3 && \
    mkdir -p ./logs ./redis_data && chown -R coyote3:coyote3 /app

FROM coyote3_runtime_base AS coyote3_api

EXPOSE 8001

COPY --chown=coyote3:coyote3 api/ ./api/
COPY --chown=coyote3:coyote3 clinical_reporting_rules/ ./clinical_reporting_rules/
COPY --chown=coyote3:coyote3 scripts/ ./scripts/
COPY --chown=coyote3:coyote3 demo_data/ ./demo_data/
COPY --chown=coyote3:coyote3 CHANGELOG.md README.md LICENSE.txt NOTICE.txt ./

USER coyote3:coyote3

CMD python3 -m uvicorn api.app.main:app --host 0.0.0.0 --port 8001 --workers 1
