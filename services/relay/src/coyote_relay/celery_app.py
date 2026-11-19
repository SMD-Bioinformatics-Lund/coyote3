# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Ingestion worker application composed from the installed server host settings."""

from coyote_api.infra.task_queue import create_celery_app

celery_app = create_celery_app("coyote-relay", include=("coyote_relay.tasks",))
