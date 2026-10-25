"""Resource hashing is a supplied capability and preserves existing persisted BSON digests."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from api.infra.mongo.resource_integrity import resource_content_hash as persisted_hash
from coyote3.contracts.resource_integrity import resource_content_hash, using_resource_hasher


def test_standalone_library_fails_closed_without_a_codec():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from coyote3.contracts.resource_integrity import resource_content_hash; resource_content_hash({})",
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
from coyote3.contracts.resource_integrity import configure_resource_hasher, resource_content_hash
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


def test_scoped_hashers_are_isolated_and_restore_the_host_codec():
    content = {"version": 1, "enabled": True, "value": None}
    original = resource_content_hash(content)

    def use_codec(label):
        """Use one explicitly injected codec in an independent execution context."""
        with using_resource_hasher(lambda content: label):
            assert resource_content_hash(content) == label
            return resource_content_hash(content)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(use_codec, ["first", "second"])) == ["first", "second"]
    assert resource_content_hash(content) == original == persisted_hash(content)


def test_codec_is_restored_after_failure():
    try:
        with using_resource_hasher(lambda content: "temporary"):
            raise RuntimeError("synthetic")
    except RuntimeError:
        pass
    assert resource_content_hash({}) == persisted_hash({})
