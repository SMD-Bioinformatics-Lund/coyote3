"""Shared core defaults remain isolated from deployment and presentation owners."""

import subprocess
import sys
from pathlib import Path

import pytest
from coyote.config.factory_defaults import FACTORY_CATALOG_PATH, factory_value, load_factory_catalog
from coyote.contracts.schemas.assay import ReportableTiersDoc
from coyote.contracts.schemas.governance import UserUiSettingsDoc


def test_factory_values_cannot_be_mutated_by_consumers():
    """Changing one list cannot change other analyses or later default instances."""
    tiers = ReportableTiersDoc()
    assert tiers.SNV == tiers.CNV == tiers.FUSION == tiers.TRANSLOCATION
    tiers.SNV.clear()
    assert tiers.CNV == factory_value("reporting.reportable_tiers")
    assert ReportableTiersDoc().SNV == tiers.CNV


def test_factory_lookup_rejects_undeclared_defaults():
    """An undeclared path fails rather than silently introducing another default."""
    with pytest.raises(KeyError):
        factory_value("filters.snv.missing")


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("[records]", "[unknown_records]", "exactly its declared sections"),
        ("max_page_size = 200", "max_page_size = 0", "positive integer"),
        ('dna = ["CNV_PROFILE"]', 'dna = ["CNV_PROFILE", "SNV"]', "cover dna exactly once"),
    ],
)
def test_invalid_factory_catalog_fails_before_consumption(tmp_path, before, after, message):
    """An inconsistent catalog cannot start the core library."""
    path = tmp_path / "factory.toml"
    text = FACTORY_CATALOG_PATH.read_text()
    assert before in text
    path.write_text(text.replace(before, after))
    with pytest.raises(ValueError, match=message):
        load_factory_catalog(path)


def test_core_catalog_excludes_host_and_presentation_defaults():
    """Reusable library defaults never pull in runtime or browser ownership."""
    assert not {"ui", "runtime", "runtime_defaults", "runtime_profiles", "product"} & set(
        load_factory_catalog()
    )


def test_unspecified_ui_preferences_are_not_synthesized():
    """Reading or updating a preference leaves frontend defaults unspecified."""
    assert UserUiSettingsDoc().model_dump() == {}
    assert UserUiSettingsDoc(theme="dark").model_dump() == {"theme": "dark"}
    assert UserUiSettingsDoc(theme=None).model_dump() == {}
    assert UserUiSettingsDoc(analysis_modern_view_tried=False).model_dump() == {
        "analysis_modern_view_tried": False
    }
    # Storage validates bounds; the frontend owns which sizes its selector offers.
    assert UserUiSettingsDoc(table_page_size=30).model_dump() == {"table_page_size": 30}
    with pytest.raises(ValueError):
        UserUiSettingsDoc(table_page_size=0)


def test_factory_catalog_loads_without_api_or_center_selection(tmp_path):
    """The installed core can obtain defaults without importing the API host."""
    source = Path(__file__).resolve().parents[2] / "src"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                f"import sys; sys.path.insert(0, {str(source)!r}); "
                "from coyote.config.factory_defaults import factory_value; "
                "assert factory_value('reporting.reportable_tiers'); "
                "assert not any(name == 'api' or name.startswith('api.') for name in sys.modules)"
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
