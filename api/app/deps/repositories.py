"""Low-level repository dependency getters."""

from api.app.container import store


def get_store():
    """Return the shared application store."""
    return store


def get_user_repository():
    """Return the shared user repository."""
    return store.user_repository


def get_roles_repository():
    """Return the shared roles repository."""
    return store.roles_repository


def get_permissions_repository():
    """Return the permissions repository."""
    return store.permissions_repository


def get_assay_panel_repository():
    """Return the assay-panel repository."""
    return store.assay_panel_repository


def get_sample_repository():
    """Return the sample repository."""
    return store.sample_repository


def get_gene_list_repository():
    """Return the shared gene-list repository."""
    return store.gene_list_repository
