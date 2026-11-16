"""Check that the application owns installation data separately from the SDK."""

import fnmatch
import json
import tomllib
from pathlib import Path

from coyote_atlas.bundle import ReferenceBundle
from coyote_demo.resources import DEMO_CENTER


def test_reference_seeds_are_atlas_data_excluded_from_the_sdk_and_server():
    """Atlas owns snapshots while application installation catalogs remain server resources."""
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "core/pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["coyote"]
    reference = ReferenceBundle.packaged().directory
    seeds = list(reference.glob("*.ndjson*"))
    assets = list((reference / "vep_diagrams").iterdir())
    assert assets
    seeds.extend(assets)
    assert seeds
    for seed in seeds:
        assert seed.is_file()
        path = "data/reference/" + seed.relative_to(reference).as_posix()
        assert not any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns), path
    assert not list((root / "api/src/coyote_api/bootstrap/catalogs/reference").glob("*.gz"))
    server = tomllib.loads((root / "pyproject.toml").read_text())
    assert "bootstrap/catalogs/**/*" in server["tool"]["setuptools"]["package-data"]["coyote_api"]
    dockerfile = (root / "docker/Dockerfile").read_text()
    assert "COPY --chown=coyote4:coyote4 api/ ./api/" not in dockerfile
    assert "/opt/coyote4-sdk/coyote_atlas-*.whl" in dockerfile
    assert "/opt/coyote4-sdk/coyote_core-*.whl" in dockerfile


def test_demo_rules_have_current_facts_valid_hashes_and_passing_embedded_cases():
    """Both demo analytes exercise language-based reporting without obsolete bindings."""
    from coyote.application.reporting.clinical_rules.validation import (
        content_hash,
        validate_rule_set,
    )
    from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    path = DEMO_CENTER / "clinical_rule_sets.json"
    for raw in json.loads(path.read_text()):
        document = ClinicalRuleSetDoc.model_validate(raw)
        assert document.test_cases
        assert document.content_hash == content_hash(document)
        assert validate_rule_set(document).valid
        assert "clinical_rule_set_id" not in json.dumps(raw)
