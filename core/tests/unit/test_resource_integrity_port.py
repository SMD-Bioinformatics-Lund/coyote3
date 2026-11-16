"""Resource hashing is a supplied capability and preserves existing persisted BSON digests."""

import subprocess
import sys


def test_standalone_library_fails_closed_without_a_codec():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from coyote.contracts.resource_integrity import resource_content_hash; resource_content_hash({})",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Configure a resource hasher" in result.stderr


def test_standalone_library_uses_injected_codec_without_database_imports():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import hashlib
import importlib.abc
import json
import sys

class RejectDatabaseImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'api', 'bson', 'pymongo', 'motor'}:
            raise AssertionError(fullname)

sys.meta_path.insert(0, RejectDatabaseImports())
from coyote.contracts.resource_integrity import configure_resource_hasher, resource_content_hash
configure_resource_hasher(lambda content: hashlib.sha256(json.dumps(content).encode()).hexdigest())
assert resource_content_hash({'synthetic': True}) == hashlib.sha256(
    json.dumps({'synthetic': True}).encode()
).hexdigest()
""",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
