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
    Callback executed when the Gunicorn server is ready.

    This function sets up logging for the Gunicorn server using the
    `setup_gunicorn_logging` function from the `logging_setup` module.

    :param server: The Gunicorn server instance.
    """
    logging_setup.setup_gunicorn_logging(log_dir, is_production=True)
