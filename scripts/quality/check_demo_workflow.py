#!/usr/bin/env python3
"""Verify a ready synthetic starter sample through an authenticated HTTP client."""

import argparse
import os

from coyote3_client import CoyoteClient


def check_demo_workflow(client: CoyoteClient, *, username: str, password: str) -> int:
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
    client.login(username=username, password=password, provider="local")
    try:
        page = client.samples.list(search="DEMO_STARTER_DNA", per_page=100)
        ready = sum(
            1
            for sample in page.items
            if sample.name.startswith("DEMO_STARTER_DNA") and sample.ingest_status == "ready"
        )
        if not ready:
            raise RuntimeError("No ready DEMO_STARTER_DNA sample is visible")
        return ready
    finally:
        client.logout()


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
    with CoyoteClient(args.api_url) as client:
        ready = check_demo_workflow(client, username=username, password=password)
    print(f"Composed workflow verified: {ready} ready DEMO_STARTER_DNA sample(s).")


if __name__ == "__main__":
    main()
