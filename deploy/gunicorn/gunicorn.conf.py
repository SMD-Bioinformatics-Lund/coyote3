# -*- coding: utf-8 -*-
"""
Gunicorn Configuration for Coyote3
==================================

This file contains the Gunicorn configuration for the Coyote3 application,
including logging setup.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

#  Copyright (c) 2025 Coyote3 Project Authors All rights reserved. \n
#  This source file is part of the Coyote3 codebase. The Coyote3 project provides a framework for genomic data analysis, interpretation, reporting, and clinical diagnostics. \n
#  Unauthorized use, distribution, or modification of this software or its components is strictly prohibited without prior written permission from the copyright holders.
#

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging_setup
import os

log_dir = os.getenv("LOG_DIR", "logs/prod")


def when_ready(server):
    """
    Gunicorn server lifecycle hook: Executes once the server is ready to accept requests.

    This function is used to perform post-startup configurations such as
    initializing structured logging for the Gunicorn server. It is typically
    referenced via the `when_ready` config setting in a Gunicorn configuration file.

    Args:
        server: The Gunicorn Arbiter instance representing the running server.
                This is passed automatically by Gunicorn during startup.

    Side Effects:
        Initializes and configures the logging system by calling
        `logging_setup.setup_gunicorn_logging`.

    Example:
        Add the following to your Gunicorn config:
            when_ready = mymodule.when_ready
    """
    logging_setup.setup_gunicorn_logging(log_dir, is_production=True)


def post_worker_stop(worker, worker_pid, exit_code) -> None:
    """
    post_worker_stop(worker, worker_pid, exit_code) -> None

    Gunicorn worker lifecycle hook that executes after a worker process stops.

    Args:
        worker: The Gunicorn worker instance that has stopped.
        worker_pid: The process ID of the stopped worker.
        exit_code: The exit code returned by the worker process.

    Side Effects:
        Stops asynchronous logging for the worker by calling
        `logging_setup.stop_async_logging()`.

    This function is typically referenced via the `post_worker_stop` config
    setting in a Gunicorn configuration file.
    """
    logging_setup.stop_async_logging()

