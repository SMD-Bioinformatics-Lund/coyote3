ARG PYTHON_BASE_IMAGE=python:3.14.7-slim-bookworm
FROM ${PYTHON_BASE_IMAGE} AS coyote4_dependency_builder
WORKDIR /build
ENV PIP_PROGRESS_BAR=off

RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
      build-essential libxml2-dev libxslt1-dev zlib1g-dev libsasl2-dev libldap2-dev \
      libssl-dev libffi-dev libjpeg-dev libpq-dev liblcms2-dev libblas-dev \
      libatlas-base-dev libglib2.0-dev && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt && \
    pip install --no-cache-dir --no-index --ignore-installed --find-links=/wheels \
      --prefix=/opt/runtime -r requirements.txt

FROM ${PYTHON_BASE_IMAGE} AS coyote4_runtime_base
ARG PYTHON_BASE_IMAGE

LABEL base_image="${PYTHON_BASE_IMAGE}"
LABEL about.home="https://github.com/SMD-Bioinformatics-Lund/coyote3"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_PROGRESS_BAR=off
ARG GIT_COMMIT="unknown"
ARG BUILD_TIME="unknown"
ARG COYOTE4_UID=10001
ARG COYOTE4_GID=10001
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_TIME=${BUILD_TIME}

RUN apt-get update -o Acquire::Retries=5 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
    curl libxml2 libxslt1.1 zlib1g libsasl2-2 libldap-2.5-0 libssl3 libffi8 \
    libjpeg62-turbo libpq5 liblcms2-2 libblas3 libatlas3-base libglib2.0-0 \
    libpango-1.0-0 libpangoft2-1.0-0 fonts-dejavu-core && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY --from=coyote4_dependency_builder /opt/runtime/ /usr/local/
RUN python -c "from kombu.transport import get_transport_cls; get_transport_cls('redis')"

RUN groupadd --gid "${COYOTE4_GID}" coyote4 && \
    useradd --uid "${COYOTE4_UID}" --gid coyote4 --create-home coyote4 && \
    mkdir -p ./logs ./redis_data && chown -R coyote4:coyote4 /app

FROM ${PYTHON_BASE_IMAGE} AS coyote4_sdk_builder
WORKDIR /build
COPY pyproject.toml release.toml README.md LICENSE.txt COPYRIGHT.txt NOTICE.txt ./
COPY LICENSING.md THIRD_PARTY_NOTICES.md CHANGELOG.md MANIFEST.in package_build.py ./
COPY core/ ./core/
COPY api/ ./api/
COPY adapters/mongo/ ./adapters/mongo/
COPY services/atlas/ ./services/atlas/
COPY services/demo/ ./services/demo/
COPY scripts/release/build_sdk.py ./scripts/release/build_sdk.py
COPY .release/relay/ /opt/coyote-relay/
COPY .release/contracts/ /opt/coyote-contracts/
RUN python scripts/release/build_sdk.py --output-dir /wheels --relay-artifact /opt/coyote-relay --contracts-artifact /opt/coyote-contracts

FROM coyote4_runtime_base AS coyote4_server_files

EXPOSE 8001

COPY --chown=coyote4:coyote4 scripts/ ./scripts/
COPY --chown=coyote4:coyote4 deploy/installer/ ./deploy/installer/
COPY --chown=coyote4:coyote4 CHANGELOG.md README.md LICENSE.txt COPYRIGHT.txt NOTICE.txt ./
COPY --chown=coyote4:coyote4 LICENSING.md THIRD_PARTY_NOTICES.md ./
COPY --chown=coyote4:coyote4 release.toml ./

# Ordinary installations build their application wheel inside Docker.
FROM coyote4_server_files AS coyote4_source_api
LABEL coyote4.artifact.mode="source"
COPY --from=coyote4_sdk_builder /wheels/ /opt/coyote4-sdk/
RUN pip install --no-cache-dir --no-deps \
    /opt/coyote4-sdk/coyote_contracts-*.whl /opt/coyote4-sdk/coyote_core-*.whl /opt/coyote4-sdk/coyote_server-*.whl \
    /opt/coyote4-sdk/coyote_relay-*.whl \
    /opt/coyote4-sdk/coyote_atlas-*.whl
USER coyote4:coyote4
CMD ["python3", "-m", "uvicorn", "coyote_api.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

# Release CI can instead require an already tested, immutable wheel and record.
FROM coyote4_server_files AS coyote4_verified_api
ARG GIT_COMMIT="unknown"
ARG COYOTE4_ARTIFACT_MODE="production"
LABEL coyote4.artifact.mode="${COYOTE4_ARTIFACT_MODE}"
COPY --from=sdk_artifact / /opt/coyote4-sdk/
RUN python scripts/release/verify_sdk_artifact.py \
      --directory /opt/coyote4-sdk --release /app/release.toml \
      --mode "${COYOTE4_ARTIFACT_MODE}" --source-commit "${GIT_COMMIT}" && \
    pip install --no-cache-dir --no-deps \
      /opt/coyote4-sdk/coyote_contracts-*.whl /opt/coyote4-sdk/coyote_core-*.whl /opt/coyote4-sdk/coyote_server-*.whl \
      /opt/coyote4-sdk/coyote_relay-*.whl \
      /opt/coyote4-sdk/coyote_atlas-*.whl

USER coyote4:coyote4

CMD ["python3", "-m", "uvicorn", "coyote_api.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

# A separate image adds the guarded demonstration package to the reviewed application.
FROM coyote4_source_api AS demo_source
USER root
RUN pip install --no-cache-dir --no-deps /opt/coyote4-sdk/coyote_demo-*.whl
USER coyote4:coyote4

FROM coyote4_verified_api AS demo
USER root
RUN pip install --no-cache-dir --no-deps /opt/coyote4-sdk/coyote_demo-*.whl
USER coyote4:coyote4

# The default build remains the normal application without demonstration code.
FROM coyote4_verified_api AS coyote4_api
