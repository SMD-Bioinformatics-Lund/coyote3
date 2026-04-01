"""Centralized Jinja filter registration entrypoint."""

from importlib import import_module, reload

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
    reloaded_modules: list[str] = []
    for module in FILTER_MODULES:
        loaded = import_module(module)
        reload(loaded)
        reloaded_modules.append(module)
    app.logger.debug("Registered filter modules: %s", ", ".join(reloaded_modules))
