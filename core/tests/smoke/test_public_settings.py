"""The independent public-core settings contract rejects deployment secrets."""

import pytest
from coyote.config.public import PublicSettings
from pydantic import ValidationError


def test_public_settings_are_immutable_and_do_not_echo_unrelated_secrets():
    settings = PublicSettings(oncokb_configured=True)
    assert settings.oncokb_configured
    assert not settings.clinpgx_configured
    with pytest.raises(ValidationError):
        settings.oncokb_configured = False
    with pytest.raises(ValidationError) as failure:
        PublicSettings(smtp_password="synthetic-secret")
    assert "synthetic-secret" not in str(failure.value)
