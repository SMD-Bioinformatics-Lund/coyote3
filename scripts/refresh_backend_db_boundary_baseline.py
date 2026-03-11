"""Refresh baseline used by backend DB-boundary contract tests."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "tests" / "contract" / "fixtures" / "backend_db_boundary_baseline.json"

STORE_TARGET_DIRS = (ROOT / "api" / "routes", ROOT / "api" / "core")
MONGO_LEAK_TARGET_DIRS = (ROOT / "api" / "routes", ROOT / "api" / "core", ROOT / "api" / "domain")

STORE_PATTERN = re.compile(r"\bstore\.")
MONGO_IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+(pymongo|bson|motor|flask_pymongo)\b")
OBJECT_ID_PATTERN = re.compile(r"\bObjectId\s*\(")


def _iter_py_files(target_dirs: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for target_dir in target_dirs:
        files.extend(target_dir.rglob("*.py"))
    return sorted(files)


def _count_store_usage_by_file() -> dict[str, int]:
    counts: Counter[str] = Counter()
    for py_file in _iter_py_files(STORE_TARGET_DIRS):
        text = py_file.read_text(encoding="utf-8")
        hits = len(STORE_PATTERN.findall(text))
        if hits:
            counts[py_file.relative_to(ROOT).as_posix()] = hits
    return dict(sorted(counts.items()))


def _count_mongo_leaks_by_file() -> dict[str, int]:
    counts: Counter[str] = Counter()
    for py_file in _iter_py_files(MONGO_LEAK_TARGET_DIRS):
        hits = 0
        for line in py_file.read_text(encoding="utf-8").splitlines():
            if MONGO_IMPORT_PATTERN.search(line):
                hits += 1
            if OBJECT_ID_PATTERN.search(line):
                hits += 1
        if hits:
            counts[py_file.relative_to(ROOT).as_posix()] = hits
    return dict(sorted(counts.items()))


def main() -> None:
    store_usage = _count_store_usage_by_file()
    mongo_leaks = _count_mongo_leaks_by_file()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "store_usage_total": sum(store_usage.values()),
        "mongo_leak_usage_total": sum(mongo_leaks.values()),
        "store_usage_by_file": store_usage,
        "mongo_leak_usage_by_file": mongo_leaks,
    }

    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote baseline: {BASELINE_PATH}")
    print(
        "Totals:",
        f"store_usage_total={payload['store_usage_total']}",
        f"mongo_leak_usage_total={payload['mongo_leak_usage_total']}",
    )


if __name__ == "__main__":
    main()
