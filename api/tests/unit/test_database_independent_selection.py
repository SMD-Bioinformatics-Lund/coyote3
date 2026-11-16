"""Adapters own executable queries and provider IDs; core selections are plain values."""

import subprocess
import sys
from pathlib import Path


def test_clinical_selection_runs_without_database_drivers_or_runtime_adapters():
    script = """
import importlib.abc
import sys
class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = ('bson', 'pymongo', 'fastapi', 'starlette', 'coyote_api.app', 'coyote_api.infra')
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Clinical selection imported a runtime adapter: ' + fullname)
sys.meta_path.insert(0, BlockRuntime())
from coyote.domain.selection import RecordField, Selection
from coyote.domain.dna.varqueries import build_query
query = build_query('example', {
    'id': 'sample', 'min_freq': 0, 'max_freq': 1, 'max_control_freq': 0.05,
    'min_depth': 20, 'min_alt_reads': 5, 'max_popfreq': 0.01,
    'filter_genes': ['TP53'], 'filter_conseq': ['missense_variant']
})
assert isinstance(query, Selection)
assert query.criteria[RecordField.SAMPLE] == 'sample'
assert '$' not in query.model_dump_json()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
