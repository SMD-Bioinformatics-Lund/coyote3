# -*- coding: utf-8 -*-
"""
Gunicorn Configuration for Coyote3
==================================

This file contains the Gunicorn configuration for the Coyote3 application,
including logging setup.

Author: Coyote3 authors.
License: Copyright (c) 2025 Coyote3 authors. All rights reserved.
"""

import os

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import logging_setup

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
