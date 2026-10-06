"""Release importer validation, protected records, backups, and seed integrity."""

import base64
import copy
import gzip
import hashlib
import json

import mongomock
import pytest
from bson import decode_all

from api.contracts.schemas.reference import VepMetadataDoc
from scripts.knowledgebase import update_vep_metadata as importer


@pytest.fixture
def policy():
    """Load the reviewed application labels and group membership."""
    return json.loads(importer.POLICY.read_text())


@pytest.fixture
def document():
    """Use a bundled reference document without connecting to MongoDB."""
    with gzip.open(importer.SEED, "rt") as stream:
        row = next(row for row in map(json.loads, stream) if row["vep_id"] == "113")
    diagram = row["consequence_diagram"]
    content = (importer.SEED.parent / "vep_diagrams" / diagram["sha256"]).read_bytes()
    diagram["data_base64"] = base64.b64encode(content).decode()
    return row


def source_table(document):
    """Generate literal source rows with the website renderer's scalar syntax."""
    rows = []
    for term, entry in document["conseq_translations"].items():
        fields = {
            "term": term,
            "desc": entry["desc"],
            "acc": entry["so_term"][3:],
            "impact": entry["impact"],
        }
        rows.append(
            "{" + ",".join(f"'{key}' => {json.dumps(value)}" for key, value in fields.items()) + "}"
        )
    return "my $data = [" + ",".join(rows) + "];"


def test_consequence_parser_preserves_groups_ontology_and_quotes(document, policy):
    translated, groups = importer.consequences(source_table(document), policy)
    assert translated == document["conseq_translations"]
    assert groups == document["consequence_groups"]
    assert "3'" in translated["splice_acceptor_variant"]["desc"]


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "missing", "impact", "ontology"])
def test_consequence_parser_rejects_invalid_source(document, policy, mutation):
    text = source_table(document)
    if mutation == "unknown":
        text = text.replace('"stop_gained"', '"unknown_term"')
    elif mutation == "duplicate":
        policy["consequence_groups"]["other"].append("stop_gained")
    elif mutation == "missing":
        text = text.replace("'desc'", "'removed'")
    elif mutation == "impact":
        text = text.replace('"HIGH"', '"SEVERE"')
    else:
        text = text.replace('"0001587"', '"invalid"')
    with pytest.raises(ValueError):
        importer.consequences(text, policy)


def test_incomplete_source_rejected(policy):
    with pytest.raises(ValueError):
        importer.consequences("<html>Access denied</html>", policy)
    with pytest.raises(ValueError):
        importer.variant_classes("<html>Access denied</html>", policy)


def test_variant_class_parser_uses_only_ontology_rows(document, policy):
    rows = "".join(
        f"<tr><td></td><td>{term}</td><td>{entry['desc']}</td><td>{entry['so_term']}</td></tr>"
        for term, entry in document["variant_class_translations"].items()
    )
    assert (
        importer.variant_classes("<table>" + rows + "</table>", policy)
        == document["variant_class_translations"]
    )
    with pytest.raises(ValueError, match="duplicate"):
        importer.variant_classes("<table>" + rows + rows + "</table>", policy)


def test_cache_fields_are_release_specific_and_preserve_additional_sources():
    rows = [
        ["Source", "Version (GRCh38)", "Version (GRCh37)"],
        ["Ensembl database version", "116", "116"],
        ["Genome assembly", "GRCh38.p14", "GRCh37.p13"],
        ["PolyPhen", "2.2.3", "2.2.2"],
        ["gnomAD exomes", "v4.1", "v4.1"],
        ["gnomAD genomes", "v4.1", "v4.1"],
        ["MANE Version", "v1.5", "n/a"],
    ]
    text = (
        "<table>"
        + "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
        + "</table>"
    )
    result = importer.cache_metadata(text, 116)
    assert result["GRCh38"]["polyphen"] == "2.2.3"
    assert result["GRCh38"]["nhlbi_esp"] == ""
    assert result["GRCh38"]["assembly_accession"] == ""
    assert result["GRCh38"]["published_sources"]["MANE Version"] == "v1.5"
    assert result["GRCh37"]["gnomad"] == "gnomAD exomes: v4.1; gnomAD genomes: v4.1"
    templated = importer.cache_metadata(
        text.replace("<td>116</td>", "<td>[[SPECIESDEFS::ENSEMBL_VERSION]]</td>"), 116
    )
    for build in ("GRCh37", "GRCh38"):
        assert templated[build]["published_sources"]["Ensembl database version"] == "116"
    with pytest.raises(ValueError, match="release mismatch"):
        importer.cache_metadata(text, 115)
    with pytest.raises(ValueError, match="assembly mismatch"):
        importer.cache_metadata(text.replace("GRCh38.p14", "GRCh37.p14"), 116)


def test_seed_merge_preserves_103_and_untouched_releases(tmp_path, document):
    path = tmp_path / "seed.gz"
    protected = {**document, "vep_id": "103"}
    path.write_bytes(gzip.compress((json.dumps(protected) + "\n").encode()))
    importer.merge_seed([document], path)
    with gzip.open(path, "rt") as stream:
        rows = list(map(json.loads, stream))
    assert rows[0] == protected
    assert rows[1]["vep_id"] == "113"
    assert "_id" not in rows[1]
    with pytest.raises(ValueError, match="protected"):
        importer.merge_seed([protected], path)


def test_install_backs_up_preserves_ids_and_protected_release(tmp_path, document, monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    original = {**document, "_id": "existing"}
    protected = {**document, "vep_id": "103", "_id": "protected"}
    collection.insert_many([copy.deepcopy(original), copy.deepcopy(protected)])
    monkeypatch.setattr(importer, "run_transaction", lambda client, operation: operation(None))
    new = {**document, "created_by": "reference-test"}
    backup = tmp_path / "backup.bson"
    importer.install(collection, [new], backup)
    assert decode_all(backup.read_bytes()) == [original]
    assert collection.find_one({"vep_id": "113"})["_id"] == "existing"
    assert collection.find_one({"vep_id": "103"}) == protected
    with pytest.raises(FileExistsError):
        importer.install(collection, [new], backup)
    with pytest.raises(ValueError):
        importer.install(collection, [protected], tmp_path / "forbidden.bson")


def test_install_refuses_concurrent_replacement(tmp_path, document, monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    collection.insert_one(copy.deepcopy(document))

    def concurrent_change(client, operation):
        """Simulate another importer committing after this importer's backup."""
        collection.update_one({"vep_id": "113"}, {"$set": {"created_by": "another-writer"}})
        operation(None)

    monkeypatch.setattr(importer, "run_transaction", concurrent_change)
    with pytest.raises(RuntimeError, match="changed after backup"):
        importer.install(collection, [document], tmp_path / "backup.bson")
    assert collection.find_one()["created_by"] == "another-writer"


def test_all_seed_releases_have_exhaustive_nonoverlapping_groups():
    with gzip.open(importer.SEED, "rt") as stream:
        documents = list(map(json.loads, stream))
    assert {int(row["vep_id"]) for row in documents} == set(range(98, 117))
    for row in documents:
        VepMetadataDoc.model_validate(row)
        assigned = [term for terms in row["consequence_groups"].values() for term in terms]
        assert len(assigned) == len(set(assigned))
        assert set(assigned) == set(row["conseq_translations"])
        for group, terms in row["consequence_groups"].items():
            assert all(row["conseq_translations"][term]["group"] == group for term in terms)
        assert {info["ensembl_version"] for info in row["db_info"].values()} == {int(row["vep_id"])}


def test_seed_provenance_records_every_downloaded_release():
    manifest = json.loads(importer.SEED.with_name("vep_metadata.sources.json").read_text())
    assert manifest.pop("policy_sha256") == hashlib.sha256(importer.POLICY.read_bytes()).hexdigest()
    assert set(map(int, manifest)) == set(range(98, 117)) - {103}
    for release, sources in manifest.items():
        assert {"ConsequenceTable.pm", "classification.html", "vep_cache.html"} <= set(sources)
        assert set(sources) <= {
            "ConsequenceTable.pm",
            "classification.html",
            "vep_cache.html",
            "consequences.jpg",
            "consequences.png",
            "consequences.svg",
        }
        for source in sources.values():
            assert source["url"].startswith("https://raw.githubusercontent.com/Ensembl/")
            assert len(source["sha256"]) == 64
        assert ("/ensembl/modules/" in sources["ConsequenceTable.pm"]["url"]) == (
            int(release) < 100
        )
