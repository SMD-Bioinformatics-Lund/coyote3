FROM python:3.12.0-slim-bullseye as coyote3_app

LABEL base_image="python:3.12-slim"
LABEL about.home="https://github.com/Clinical-Genomics-Lund/coyote_3.0"
    
EXPOSE 8000
WORKDIR app

# Override with docker run:
# docker run -e FLASK_MONGO_URI=your_mongo_host:27017
ENV FLASK_MONGO_URI=mtlucmds1.lund.skane.se:27017

# Modify this if CDM runs under subpath, e.g:
# If CDM: domain.com/cdm2 -> ENV SCRIPT_NAME=/cdm2
ENV SCRIPT_NAME=""

# Override when starting with docker run, e.g:
# $ docker run -e COYOTE_LOG_LEVEL=DEBUG cdm:latest
ENV COYOTE_LOG_LEVEL="INFO"
    
ENV PYHTONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py

RUN apt-get update && apt-get install -y libxml2-dev libxslt1-dev zlib1g-dev libsasl2-dev libldap2-dev build-essential libssl-dev libffi-dev libjpeg-dev libpq-dev liblcms2-dev libblas-dev libatlas-base-dev libglib2.0-dev libpango1.0-0 less vim
COPY requirements.txt ./
RUN pip install --verbose --upgrade pip &&                 \
    pip install --verbose --no-cache-dir --requirement requirements.txt

RUN mkdir ./logs

COPY config/ ./config/
COPY config.py wsgi.py gunicorn.conf.py logging_setup.py ./
COPY coyote/ ./coyote/
COPY scripts ./scripts/

CMD gunicorn -w 2 -e SCRIPT_NAME=${SCRIPT_NAME} --log-level ${COYOTE_LOG_LEVEL} --bind 0.0.0.0:8000 wsgi:app

FROM mongo:3.4-xenial as cdm_mongo_dev
WORKDIR /data/cdm-db
EXPOSE 27017/tcp

# TODO: Sort this out: /Alex
#RUN mongod --fork --logpath /var/log/mongodb.log; \
#    mongorestore mongodump; \
#    mongod --shutdown;

CMD docker-entrypoint.sh mongod
