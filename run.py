import logging.config
from logging import Logger
from typing import Dict, Any

from flask import Flask
import gunicorn.glogging
from coyote import init_app
from logging_setup import custom_logging
import os


if __name__ != "__main__":
    print("Setting up Gunicorn logging.")
    app: Flask = init_app()
    log_dir: str | Any = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    # custom_logging(log_dir, app.config.get("PRODUCTION", False), gunicorn_logging=True)
    app.secret_key = "SomethingSecret"

    # print(gunicorn.glogging.CONFIG_DEFAULTS)
    gunicorn_logger: Logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    app = init_app()
    log_dir = os.getenv("LOG_DIR", app.config.get("LOGS", "logs/prod"))
    custom_logging(log_dir, app.config.get("PRODUCTION", False), gunicorn_logging=False)
    app.secret_key = "SomethingSecret"
    app.run(host="0.0.0.0")


""" docker network error

docker stop $(docker ps -a -q); docker rm $(docker ps -a -q); docker volume rm $(docker volume ls -qf dangling=true)

docker network rm $(docker network ls -q)

sudo lsof -nP | grep LISTEN

sudo kill -9 1548

6428-22-val3-230123-SHM_S6_L001_001_combined.fastq_indexQ30.tsv
mongoimport --db='cll_genie' --collection='samples' --file='/home/ramsainanduri/Pipelines/Web_Developement/Main/cll_genie/data/Excelfile_post_analysis/sample_data.json'
mongo cll_genie --eval 'db.samples.find().forEach(function(doc){doc.date_added = new Date(); db.samples.save(doc);});'
"""
