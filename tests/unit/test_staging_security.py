"""Staging requires explicit credentials just like production."""

import pytest

from api.config.security import get_api_secret_key, get_internal_api_token


@pytest.mark.parametrize("environment", ["stage", "staging", "production"])
@pytest.mark.parametrize("reader", [get_api_secret_key, get_internal_api_token])
def test_deployed_environments_require_credentials(environment, reader):
    """Deployed environments must not inherit development credentials."""
    with pytest.raises(RuntimeError, match="Missing required API setting"):
        reader({"ENV_NAME": environment})
