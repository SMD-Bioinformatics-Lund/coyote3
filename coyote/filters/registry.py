#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""Centralized Jinja filter registration entrypoint."""

from importlib import import_module


FILTER_MODULES = [
    "coyote.blueprints.admin.filters",
    "coyote.blueprints.common.filters",
    "coyote.blueprints.dashboard.filters",
    "coyote.blueprints.dna.filters",
    "coyote.blueprints.home.filters",
    "coyote.blueprints.public.filters",
    "coyote.blueprints.rna.filters",
]


def register_filters(app) -> None:
    """
    Import all filter modules explicitly so filter registration does not depend
    on blueprint/view import side effects.
    """
    for module in FILTER_MODULES:
        import_module(module)
    app.logger.debug(f"Registered filter modules: {', '.join(FILTER_MODULES)}")

