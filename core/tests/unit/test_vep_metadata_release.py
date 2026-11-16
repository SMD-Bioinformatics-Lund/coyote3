"""Equivalent VEP release spellings must select the same consequence metadata."""

import pytest
from coyote.config.database_versions import vep_metadata_release


@pytest.mark.parametrize("value", [113, 113.0, "113", "113.0", "v113.0", "113.0.0"])
def test_equivalent_releases(value):
    assert vep_metadata_release(value) == "113"


def test_nonzero_minor_release_is_preserved():
    assert vep_metadata_release("113.1") == "113.1"
