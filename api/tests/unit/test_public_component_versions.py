"""About metadata reports actual installed SDK distributions separately from the app release."""

from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

from coyote_api.services import public_pages


def test_about_uses_independent_installed_component_versions(monkeypatch):
    versions = {"coyote-core": "1.1.2"}
    monkeypatch.setattr(public_pages, "version", versions.__getitem__)
    references = SimpleNamespace(
        software_versions=lambda: {}, reference_versions=lambda: {}, knowledgebase_status=lambda: {}
    )
    application = public_pages.PublicPages(
        {"APP_VERSION": "4.0.0", "ENV_NAME": "test"}, references
    ).about()["application"]
    assert application["version"] == "4.0.0"
    assert application["sdk_version"] == "1.1.2"


def test_absent_component_does_not_report_the_application_version(monkeypatch):
    def absent(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(public_pages, "version", absent)
    assert public_pages._installed_version("coyote-core") is None
