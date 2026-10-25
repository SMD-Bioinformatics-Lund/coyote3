#!/usr/bin/env python3
"""Export the canonical FastAPI OpenAPI contract without starting runtime services."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_schema() -> dict:
    """Build the real API's schema without entering its database/worker lifespan.

    Returns:
        FastAPI-generated OpenAPI document using the selected center vocabulary.
    """
    os.environ.setdefault("ENV_NAME", "test")
    os.environ.setdefault("TESTING", "1")
    from api.app.main import create_api_app

    schema = create_api_app().openapi()
    # Hosts and deployment descriptions do not change the HTTP data contract.
    schema.pop("servers", None)
    schema["info"] = {"title": "Coyote3 API", "version": "1"}
    return schema


def main() -> None:
    """Write deterministic JSON for the actual server routes and Pydantic schemas."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(export_schema(), sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
