"""Check that the application owns installation data separately from the SDK."""

import fnmatch
import json
import tomllib
from pathlib import Path


def test_reference_seeds_are_host_data_excluded_from_the_sdk():
    """API deployment retains reference seeds without bundling them into the library."""
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["coyote3"]
    seeds = list((root / "api/bootstrap/catalogs/reference").glob("*.ndjson*"))
    assets = list((root / "api/bootstrap/catalogs/reference/vep_diagrams").iterdir())
    assert assets
    seeds.extend(assets)
    assert seeds
    for seed in seeds:
        assert seed.is_file()
        path = "config/bootstrap/" + seed.relative_to(root / "api/bootstrap/catalogs").as_posix()
        assert not any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns), path
    assert "COPY --chown=coyote3:coyote3 api/ ./api/" in (root / "docker/Dockerfile").read_text()


def test_demo_rules_have_current_facts_valid_hashes_and_passing_embedded_cases():
    """Both demo analytes exercise language-based reporting without obsolete bindings."""
    from coyote3.application.reporting.clinical_rules.validation import (
        content_hash,
        validate_rule_set,
    )
    from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    path = (
        Path(__file__).resolve().parents[2]
        / "api/bootstrap/catalogs/demo_center/clinical_rule_sets.json"
    )
    for raw in json.loads(path.read_text()):
        document = ClinicalRuleSetDoc.model_validate(raw)
        assert document.test_cases
        assert document.content_hash == content_hash(document)
        assert validate_rule_set(document).valid
        assert "clinical_rule_set_id" not in json.dumps(raw)
