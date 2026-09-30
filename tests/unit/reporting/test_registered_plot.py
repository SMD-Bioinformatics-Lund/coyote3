"""Report plot reads must retain the sample's registered artifact path."""

import base64

from api.domain.common.reporting import get_plot


def test_registered_plot_is_not_replaced_by_same_named_file(tmp_path, monkeypatch):
    """A same-named file in the working directory cannot replace the registered plot."""
    registered = tmp_path / "registered"
    registered.mkdir()
    plot = registered / "profile.png"
    plot.write_bytes(b"registered plot")
    (tmp_path / "profile.png").write_bytes(b"unrelated plot")
    monkeypatch.chdir(tmp_path)
    assert base64.b64decode(get_plot(str(plot))) == b"registered plot"
    assert get_plot("") is False
    assert get_plot(str(registered)) is False
    assert get_plot(str(registered / "missing.png")) is False
