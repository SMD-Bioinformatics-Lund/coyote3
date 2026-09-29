"""Check that installed packages retain the reference files used by bootstrap."""

import fnmatch
import json
import tomllib
from pathlib import Path


def test_reference_seeds_are_included_in_package_data():
    """Uncompressed and compressed reference seeds must survive wheel installation."""
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["api"]
    seeds = list((root / "api/config/bootstrap/reference").glob("*.ndjson*"))
    assets = list((root / "api/config/bootstrap/reference/vep_diagrams").iterdir())
    assert assets
    seeds.extend(assets)
    assert seeds
    for seed in seeds:
        path = seed.relative_to(root / "api").as_posix()
        assert any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns), path


def test_demo_rules_have_current_facts_valid_hashes_and_passing_embedded_cases():
    """Both demo analytes exercise language-based reporting without obsolete bindings."""
    from api.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
    from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    path = (
        Path(__file__).resolve().parents[2]
        / "api/config/bootstrap/demo_center/clinical_rule_sets.json"
    )
    for raw in json.loads(path.read_text()):
        document = ClinicalRuleSetDoc.model_validate(raw)
        assert document.test_cases
        assert document.content_hash == content_hash(document)
        assert validate_rule_set(document).valid
        assert "clinical_rule_set_id" not in json.dumps(raw)
