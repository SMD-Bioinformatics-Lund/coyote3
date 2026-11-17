#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Verify a ready synthetic starter sample through an authenticated HTTP client."""

import argparse
import os

import httpx

from deploy.installer.transport import api_client, authenticate, logout, response_object


def check_demo_workflow(client: httpx.Client, *, username: str, password: str) -> int:
    """Read the current sample contract and revoke the check's session afterwards.

    Args:
        client: HTTP client targeting the deployment's public proxy URL.
        username: Synthetic deployment administrator username.
        password: Its current password, never printed or retained by this helper.

    Returns:
        Number of ready DEMO_STARTER_DNA samples on the filtered result page.

    Raises:
        RuntimeError: No ready synthetic starter sample is visible.
        httpx.HTTPError: Authentication, sample retrieval, or logout fails.
    """
    authenticate(client, username=username, password=password, provider="local")
    try:
        page = response_object(
            client.get("samples", params={"search_str": "DEMO_STARTER_DNA", "live_per_page": 100})
        )
        samples = page.get("live_samples")
        if not isinstance(samples, list) or not all(isinstance(sample, dict) for sample in samples):
            raise ValueError("The API response lacks the live sample stream")
        ready = sum(
            1
            for sample in samples
            if isinstance(sample.get("name"), str)
            and sample["name"].startswith("DEMO_STARTER_DNA")
            and sample.get("ingest_status") == "ready"
        )
        if not ready:
            raise RuntimeError("No ready DEMO_STARTER_DNA sample is visible")
        return ready
    finally:
        logout(client)


def main() -> None:
    """Read credentials from the CI environment and check the public proxy path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url", required=True, help="Public origin including deployment prefix"
    )
    args = parser.parse_args()
    username, password = os.getenv("ADMIN_USERNAME", ""), os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        parser.error("ADMIN_USERNAME and ADMIN_PASSWORD must be set")
    with api_client(args.api_url) as client:
        ready = check_demo_workflow(client, username=username, password=password)
    print(f"Composed workflow verified: {ready} ready DEMO_STARTER_DNA sample(s).")


if __name__ == "__main__":
    main()
