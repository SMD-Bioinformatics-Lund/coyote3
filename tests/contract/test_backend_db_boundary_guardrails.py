"""Contract guardrails for backend database-boundary migration."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


BASELINE_PATH = Path("tests/contract/fixtures/backend_db_boundary_baseline.json")

STORE_TARGET_DIRS = (Path("api/routes"), Path("api/core"))
MONGO_LEAK_TARGET_DIRS = (Path("api/routes"), Path("api/core"), Path("api/domain"))

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
            counts[py_file.as_posix()] = hits
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
            counts[py_file.as_posix()] = hits
    return dict(sorted(counts.items()))


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _assert_not_above_baseline(category: str, current: dict[str, int], baseline: dict[str, int]) -> None:
    offenders: list[str] = []

    for file_path, current_count in current.items():
        baseline_count = baseline.get(file_path, 0)
        if current_count > baseline_count:
            offenders.append(
                f"{file_path}: current={current_count}, baseline={baseline_count}, "
                f"delta=+{current_count - baseline_count}"
            )

    assert not offenders, (
        f"{category} exceeded migration baseline. "
        "No new direct coupling is allowed until debt is burned down.\n"
        + "\n".join(offenders)
    )


def test_store_usage_in_routes_core_does_not_increase():
    baseline = _load_baseline()["store_usage_by_file"]
    current = _count_store_usage_by_file()
    _assert_not_above_baseline("store.* usage in api/routes+api/core", current, baseline)


def test_mongo_specific_leaks_do_not_increase():
    baseline = _load_baseline()["mongo_leak_usage_by_file"]
    current = _count_mongo_leaks_by_file()
    _assert_not_above_baseline("Mongo-specific leaks in backend layers", current, baseline)
