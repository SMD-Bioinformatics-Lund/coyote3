#!/usr/bin/env python3
"""Assert that a composed API stack exposes an ingested sample as ready."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _sample_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "samples", "live_samples"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    nested = payload.get("payload")
    return _sample_rows(nested) if nested is not None else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--bearer-token", required=True)
    parser.add_argument("--sample-name", required=True)
    args = parser.parse_args()

    url = f"{args.api_base_url.rstrip('/')}/api/v1/samples?show_all_profiles=true"
    request = Request(url, headers={"Authorization": f"Bearer {args.bearer_token}"})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - CLI URL supplied by CI
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as error:
        print(f"Unable to verify composed sample workflow: {error}", file=sys.stderr)
        return 1

    rows = _sample_rows(payload)
    matches = [
        row
        for row in rows
        if str(row.get("name") or row.get("sample_name") or "").startswith(args.sample_name)
    ]
    if not matches:
        print(
            f"No ingested sample beginning '{args.sample_name}' was returned by /samples",
            file=sys.stderr,
        )
        return 1
    if not any(str(row.get("ingest_status") or "").lower() == "ready" for row in matches):
        print(
            f"Ingested sample '{args.sample_name}' was returned but is not ready: {matches}",
            file=sys.stderr,
        )
        return 1
    print(
        f"Composed workflow verified: {len(matches)} ready sample(s) matched '{args.sample_name}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
