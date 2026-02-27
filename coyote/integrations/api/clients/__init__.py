"""Legacy API client mixin placeholders."""

from coyote.integrations.api.clients.admin import AdminApiClientMixin
from coyote.integrations.api.clients.auth import AuthApiClientMixin
from coyote.integrations.api.clients.common import CommonApiClientMixin
from coyote.integrations.api.clients.coverage import CoverageApiClientMixin
from coyote.integrations.api.clients.dashboard import DashboardApiClientMixin
from coyote.integrations.api.clients.dna import DnaApiClientMixin
from coyote.integrations.api.clients.home import HomeApiClientMixin
from coyote.integrations.api.clients.internal import InternalApiClientMixin
from coyote.integrations.api.clients.public import PublicApiClientMixin
from coyote.integrations.api.clients.rna import RnaApiClientMixin

__all__ = [
    "AdminApiClientMixin",
    "AuthApiClientMixin",
    "CommonApiClientMixin",
    "CoverageApiClientMixin",
    "DashboardApiClientMixin",
    "DnaApiClientMixin",
    "HomeApiClientMixin",
    "InternalApiClientMixin",
    "PublicApiClientMixin",
    "RnaApiClientMixin",
]
