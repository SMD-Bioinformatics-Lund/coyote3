"""Reference installation uses the installed provider without a silent data fallback."""

from types import SimpleNamespace

import pytest
from coyote_api.bootstrap import references


@pytest.mark.parametrize("count", [0, 2])
def test_missing_or_ambiguous_reference_provider_is_rejected(monkeypatch, count):
    monkeypatch.setattr(
        references, "entry_points", lambda **_: [SimpleNamespace(name="atlas")] * count
    )
    with pytest.raises(RuntimeError, match="exactly one"):
        references.reference_bundle()


def test_selected_reference_factory_is_loaded(monkeypatch):
    bundle = object()
    entry = SimpleNamespace(name="atlas", load=lambda: lambda: bundle)
    monkeypatch.setattr(references, "entry_points", lambda **_: [entry])
    assert references.reference_bundle() is bundle
