"""Low-level handler dependency getters."""

from api.extensions import store


def get_store():
    """Return the shared application store."""
    return store


def get_user_handler():
    """Return the shared user handler."""
    return store.user_handler


def get_roles_handler():
    """Return the shared roles handler."""
    return store.roles_handler


def get_assay_panel_handler():
    """Return the shared assay-panel handler."""
    return store.assay_panel_handler


def get_sample_handler():
    """Return the shared sample handler."""
    return store.sample_handler


def get_gene_list_handler():
    """Return the shared gene-list handler."""
    return store.gene_list_handler
