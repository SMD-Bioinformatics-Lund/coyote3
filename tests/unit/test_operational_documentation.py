"""Check operator-example validation without executing documented commands."""

from scripts.docs.check_operational_examples import check_document


def test_shell_examples_are_parsed_without_execution(tmp_path):
    """Even a shell example containing a write remains inert during validation."""
    marker = tmp_path / "must-not-be-created"
    document = tmp_path / "example.md"
    document.write_text(f"```bash\ntouch '{marker}'\n```\n")
    assert check_document(document, root=tmp_path) == []
    assert not marker.exists()


def test_removed_script_and_invalid_shell_include_document_locations(tmp_path):
    """A stale script path or unclosed shell construct is actionable in CI."""
    document = tmp_path / "example.md"
    document.write_text("Run `scripts/removed.py`.\n\n```bash\nif true; then\n```\n")
    errors = check_document(document, root=tmp_path)
    assert any("example.md:1: script does not exist" in error for error in errors)
    assert any("example.md:3: invalid shell syntax" in error for error in errors)


def test_json_data_paths_are_not_mistaken_for_javascript_scripts(tmp_path):
    """The .js suffix must not match the beginning of a .json resource name."""
    document = tmp_path / "example.md"
    document.write_text("Read `scripts/docs/catalog.json`.\n")
    assert check_document(document, root=tmp_path) == []


def test_migration_instructions_check_versioned_script_paths(tmp_path):
    """Separate migration folders receive the same stale-path checks as scripts."""
    document = tmp_path / "migration.md"
    document.write_text("Run `migrations_scripts/v2/removed.py`.\n")
    errors = check_document(document, root=tmp_path)
    assert len(errors) == 1
    assert "migrations_scripts/v2/removed.py" in errors[0]
