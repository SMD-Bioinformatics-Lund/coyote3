"""About metadata reports actual installed SDK distributions separately from the app release."""

from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

from api.services import public_pages


def test_about_uses_independent_installed_component_versions(monkeypatch):
    versions = {"Coyote3": "4.1.2", "coyote3-client": "1.3.0"}
    monkeypatch.setattr(public_pages, "version", versions.__getitem__)
    references = SimpleNamespace(
        software_versions=lambda: {}, reference_versions=lambda: {}, knowledgebase_status=lambda: {}
    )
    application = public_pages.PublicPages(
        {"APP_VERSION": "4.0.0", "ENV_NAME": "test"}, references
    ).about()["application"]
    assert application["version"] == "4.0.0"
    assert application["sdk_version"] == "4.1.2"
    assert application["client_sdk_version"] == "1.3.0"


def test_absent_component_does_not_report_the_application_version(monkeypatch):
    def absent(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(public_pages, "version", absent)
    assert public_pages._installed_version("coyote3-client") is None
