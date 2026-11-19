# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit CLI and environment inputs for standalone Relay API connections."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import httpx
from pydantic import BaseModel, ConfigDict, field_validator

ENVIRONMENT_KEYS = MappingProxyType(
    {
        "base_url": "COYOTE_RELAY_API_URL",
        "auth": "COYOTE_RELAY_AUTH",
        "token": "COYOTE_RELAY_TOKEN",
        "username": "COYOTE_RELAY_USERNAME",
        "password": "COYOTE_RELAY_PASSWORD",
        "provider": "COYOTE_RELAY_PROVIDER",
        "ca_bundle": "COYOTE_RELAY_CA_BUNDLE",
    }
)
TOKEN_MAX_LENGTH = 16384


def configured_value(
    name: str,
    explicit: str | None,
    *,
    environment: Mapping[str, str] | None = None,
) -> str | None:
    """Select an explicit CLI value before the package's named environment value.

    Args:
        name: Supported option name from ``ENVIRONMENT_KEYS``.
        explicit: CLI value, including an explicitly empty value; None selects environment.
        environment: Input environment, or the current process environment when omitted.

    Returns:
        Selected string without altering password whitespace, or None when unset.

    Raises:
        KeyError: The option has no declared environment setting.
    """
    variable = ENVIRONMENT_KEYS[name]
    if explicit is not None:
        return explicit
    return (os.environ if environment is None else environment).get(variable)


class ApiConnection(BaseModel):
    """Validated API destination and optional trusted CA file, without host settings."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    base_url: str
    ca_bundle: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        """Reject unsafe destinations without including the supplied URL in errors.

        Args:
            value: HTTP(S) application origin with an optional deployment prefix.

        Returns:
            Validated URL without a trailing slash, preserving the mount prefix.

        Raises:
            ValueError: The destination is absent or contains credentials, query,
                fragment, whitespace, control characters or invalid URL syntax.
        """
        message = (
            "Supply --base-url or COYOTE_RELAY_API_URL as an HTTP(S) application URL "
            "without credentials, query, fragment or whitespace"
        )
        if not value or any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError(message)
        try:
            url = httpx.URL(value)
            if (
                url.scheme not in {"http", "https"}
                or not url.host
                or url.userinfo
                or url.query
                or url.fragment
            ):
                raise ValueError(message)
        except (ValueError, httpx.InvalidURL):
            raise ValueError(message) from None
        return value.rstrip("/")

    @classmethod
    def resolve(
        cls,
        *,
        base_url: str | None = None,
        ca_bundle: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> ApiConnection:
        """Resolve command-line overrides against Relay's own connection variables.

        Args:
            base_url: Explicit application URL; None reads ``COYOTE_RELAY_API_URL``.
            ca_bundle: Explicit CA bundle; None reads ``COYOTE_RELAY_CA_BUNDLE``.
            environment: Explicit mapping for embedded use, or current environment.

        Returns:
            Immutable connection settings; no files, credentials or network are accessed.

        Raises:
            ValueError: The selected API URL is missing or invalid.
        """
        return cls(
            base_url=configured_value("base_url", base_url, environment=environment) or "",
            ca_bundle=configured_value("ca_bundle", ca_bundle, environment=environment) or None,
        )


def read_token(
    *,
    token: str | None = None,
    token_file: str | None = None,
    token_env: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Read one explicit credential source, falling back only to Relay's token variable.

    Args:
        token: Explicit bearer, service or internal credential; never logged here.
        token_file: Explicit local file containing one credential and optional final newline.
        token_env: Explicit environment-variable name; an absent value does not fall back.
        environment: Input environment, or the current process environment when omitted.

    Returns:
        A header-safe credential without surrounding whitespace.

    Raises:
        ValueError: Sources conflict, or the selected credential is missing, oversized
            or contains unsafe header characters. Errors never contain the credential.
        OSError: The selected local credential file cannot be read.
    """
    if sum(value is not None for value in (token, token_file, token_env)) > 1:
        raise ValueError("Choose only one of --token, --token-file or --token-env")
    values = os.environ if environment is None else environment
    if token_file is not None:
        with Path(token_file).expanduser().open(encoding="utf-8") as stream:
            token = stream.read(TOKEN_MAX_LENGTH + 1)
    elif token_env is not None:
        token = values.get(token_env, "")
    elif token is None:
        token = configured_value("token", None, environment=values)
    token = (token or "").strip()
    if (
        not token
        or len(token) > TOKEN_MAX_LENGTH
        or not token.isascii()
        or any(ord(char) < 32 or ord(char) == 127 or char in '"\\' for char in token)
    ):
        raise ValueError(
            "Supply a valid token using --token, --token-file, --token-env or COYOTE_RELAY_TOKEN"
        )
    return token
