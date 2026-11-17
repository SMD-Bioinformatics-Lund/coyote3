"""Fast public manifest validation without configured clinical services."""

import pytest
from coyote.contracts.manifests import parse_yaml_payload
from coyote.contracts.resource_metadata import SampleMetadata
from coyote.contracts.sample_manifest import SampleManifest

pytestmark = pytest.mark.smoke


def test_yaml_to_manifest_to_metadata(manifest_payload) -> None:
    import yaml

    manifest = SampleManifest.model_validate(parse_yaml_payload(yaml.safe_dump(manifest_payload)))
    metadata = SampleMetadata(
        name=manifest.name, asp_id=manifest.asp_id, environment=manifest.environment
    )
    assert metadata.name == "SYNTHETIC-CASE"
    assert manifest.files["vcf_files"].path == "variants.vcf.gz"
