"""Resource hashing is a supplied capability and preserves existing persisted BSON digests."""

from concurrent.futures import ThreadPoolExecutor

from coyote.contracts.resource_integrity import resource_content_hash, using_resource_hasher
from coyote_mongo.resource_integrity import resource_content_hash as persisted_hash


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
