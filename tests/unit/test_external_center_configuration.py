"""Verify persistent center configuration selection and validated release staging."""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY, load_clinical_vocabulary
from coyote3.config.loaders.filter_flags import load_filter_flag_metadata
from scripts.deployment.prepare_center_config import FILES, prepare

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("explicit", [None, "", "   ", "override"])
@pytest.mark.parametrize("from_dotenv", [False, True])
def test_host_directory_selects_both_policy_and_application_paths(tmp_path, explicit, from_dotenv):
    """Host tools inherit the mount source unless an explicit process path overrides it."""
    host = tmp_path / "host-center"
    override = tmp_path / "process-center"
    for directory in (host, override):
        directory.mkdir()
        for name in FILES:
            shutil.copyfile(ROOT / "config/examples/center" / name, directory / name)
    env = dict(os.environ, COYOTE3_RUNTIME_ROOT=str(tmp_path))
    env.pop("COYOTE3_CENTER_CONFIG_DIR", None)
    env.pop("COYOTE3_CENTER_CONFIG_HOST_DIR", None)
    settings = {
        "COYOTE3_CENTER_CONFIG_HOST_DIR": str(tmp_path / "unmounted-host")
        if explicit == "override"
        else str(host)
    }
    if explicit is not None:
        settings["COYOTE3_CENTER_CONFIG_DIR"] = (
            str(override) if explicit == "override" else explicit
        )
    if from_dotenv:
        (tmp_path / ".env").write_text(
            "\n".join(f"{key}='{value}'" for key, value in settings.items()) + "\n"
        )
    else:
        env.update(settings)
    expected = override if explicit == "override" else host
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api.config.paths import CENTER_CONFIG_DIR; "
            "from coyote3.config.selection import center_policy_path; "
            "from pathlib import Path; "
            f"assert CENTER_CONFIG_DIR == Path({str(expected)!r}); "
            "assert center_policy_path('clinical_vocabulary.toml', Path('unused')) "
            "== CENTER_CONFIG_DIR / 'clinical_vocabulary.toml'",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("exists", [False, True])
def test_invalid_inherited_host_directory_fails_startup(tmp_path, exists):
    """Missing host policies must not silently select bundled clinical defaults."""
    host = tmp_path / "host-center"
    if exists:
        host.mkdir()
    result = subprocess.run(
        [sys.executable, "-c", "import api"],
        cwd=ROOT,
        env={
            **os.environ,
            "COYOTE3_RUNTIME_ROOT": str(tmp_path),
            "COYOTE3_CENTER_CONFIG_DIR": "",
            "COYOTE3_CENTER_CONFIG_HOST_DIR": str(host),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Required center configuration file is missing" in result.stderr


@pytest.mark.parametrize("valid", [True, False])
def test_optional_report_wording_is_validated_and_recorded_in_release(tmp_path, valid):
    """A center release retains optional report wording only after successful validation."""
    source = tmp_path / "source"
    source.mkdir()
    for name in FILES:
        shutil.copyfile(ROOT / "config/examples/center" / name, source / name)
    wording = (
        '[empty_results]\nSNV = "Synthetic no findings"\n'
        if valid
        else '[empty_results]\nSNVV = "Typo"\n'
    )
    (source / "report_presentation.toml").write_text(wording)
    destination = tmp_path / "release"
    if not valid:
        with pytest.raises(subprocess.CalledProcessError):
            prepare(str(source), destination, None, ".")
        assert not destination.exists()
        return
    prepare(str(source), destination, None, ".")
    assert (destination / "report_presentation.toml").read_text() == wording
    manifest = json.loads((destination / "manifest.json").read_text())
    assert "report_presentation.toml" in manifest["sha256"]


@pytest.mark.parametrize("key", ["required_aspc_fields", "unrecognized_setting"])
def test_unused_vocabulary_settings_are_rejected(tmp_path, key):
    """Inactive or misspelled settings cannot appear to configure runtime behavior."""
    source = (ROOT / "config/examples/center/clinical_vocabulary.toml").read_text()
    path = tmp_path / "vocabulary.toml"
    path.write_text(source.replace("[snv]", f'[snv]\n{key} = ["example"]'))
    with pytest.raises(RuntimeError, match="Unknown clinical vocabulary key"):
        load_clinical_vocabulary(path)


def test_configuration_release_is_independent_and_never_overwritten(tmp_path, monkeypatch):
    """A validated copy survives source edits and cannot be overwritten by an upgrade."""
    monkeypatch.setenv("AUTHENTICATION_PROVIDERS", "local")
    source = tmp_path / "source"
    source.mkdir()
    for name in FILES:
        shutil.copyfile(ROOT / "config/examples/center" / name, source / name)
    destination = tmp_path / "release"
    prepare(str(source), destination, None, ".")
    assert {p.name for p in destination.iterdir()} == {*FILES, "manifest.json"}
    original = (destination / "contact.toml").read_text()
    (source / "contact.toml").write_text("invalid = [")
    assert (destination / "contact.toml").read_text() == original
    with pytest.raises(FileExistsError):
        prepare(str(source), destination, None, ".")
    with pytest.raises(subprocess.CalledProcessError):
        prepare(str(source), tmp_path / "invalid-release", None, ".")
    assert not (tmp_path / "invalid-release").exists()


def test_external_directory_never_overrides_application_collection_mapping(tmp_path):
    """All center assets resolve externally while physical collections remain software-owned."""
    for name in FILES:
        shutil.copyfile(ROOT / "config/examples/center" / name, tmp_path / name)
    (tmp_path / "collections.toml").write_text("malformed = [")
    (tmp_path / "clinical_capabilities.toml").write_text("malformed = [")
    (tmp_path / "clinical_query_defaults.toml").write_text("malformed = [")
    (tmp_path / "clinical_query_policy.toml").write_text("malformed = [")
    (tmp_path / "clinical_query_seed.toml").write_text("malformed = [")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from api.config.paths import CENTER_CONFIG_DIR,COLLECTIONS_CONFIG_PATH; "
                "from api.config.collections import load_collection_mapping; "
                "from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY; "
                "from coyote3.config.clinical_query_policy import CLINICAL_QUERY_POLICY; "
                "from coyote3.config.clinical_query_policy import load_clinical_query_policy; "
                "from api.bootstrap.paths import CLINICAL_QUERY_SEED_PATH; "
                "assert CLINICAL_QUERY_SEED_PATH.parent != CENTER_CONFIG_DIR; "
                "assert load_clinical_query_policy(CLINICAL_QUERY_SEED_PATH).snv.exceptions; "
                "assert 'wes' in CLINICAL_VOCABULARY.assay_families; "
                "assert CLINICAL_QUERY_POLICY.snv.default_somatic_policy == 'paired'; "
                "assert load_collection_mapping()['primary']['samples_collection']=='samples'; "
                "assert COLLECTIONS_CONFIG_PATH.parent != CENTER_CONFIG_DIR"
            ),
        ],
        cwd=ROOT,
        env=dict(os.environ, COYOTE3_CENTER_CONFIG_DIR=str(tmp_path)),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    (tmp_path / "contact.toml").unlink()
    result = subprocess.run(
        [sys.executable, "-c", "import api.config.paths"],
        cwd=ROOT,
        env=dict(os.environ, COYOTE3_CENTER_CONFIG_DIR=str(tmp_path)),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "contact.toml" in result.stderr


@pytest.mark.parametrize("revision", [None, "main", "v1.0", "abc123"])
def test_git_source_requires_immutable_commit_before_fetch(tmp_path, revision):
    """A moving Git ref cannot silently change a deployment's clinical policy."""
    with pytest.raises(ValueError, match="40-character"):
        prepare("https://github.com/example/center.git", tmp_path / "release", revision, ".")


def test_caller_flags_validate_registry_and_keep_analysis_scopes_separate(tmp_path):
    """An SNV caller override is exposed only in its registered analysis namespace."""
    path = tmp_path / "flags.yaml"
    path.write_text(
        "callers:\n  snv:\n    mutect2:\n      terms:\n        custom:\n          severity: warn\n"
    )
    vocabulary = replace(CLINICAL_VOCABULARY, snv_callers=("mutect2",), cnv_callers=("cnvkit",))
    result = load_filter_flag_metadata(path, vocabulary)
    assert result["callers"]["snv"]["mutect2"]["terms"]["CUSTOM"]["severity"] == "warn"
    assert "cnv" not in result["callers"]
    assert "cnvkit" in result["caller_options"]["cnv"]
    path.write_text("callers:\n  cnv:\n    mutect2: {}\n")
    with pytest.raises(ValueError, match="unconfigured cnv callers"):
        load_filter_flag_metadata(path, vocabulary)
    path.write_text("exact:\n  FAIL:\n    severity: misleading\n")
    with pytest.raises(ValueError):
        load_filter_flag_metadata(path)


def test_dna_caller_registries_are_optional_and_do_not_enable_fusion_callers(tmp_path):
    """Merged DNA provenance needs no registry; fusion retains implemented caller choices."""
    source = (ROOT / "config/examples/center/clinical_vocabulary.toml").read_text()
    assert CLINICAL_VOCABULARY.snv_callers == ()
    assert CLINICAL_VOCABULARY.cnv_callers == ()
    assert CLINICAL_VOCABULARY.translocation_callers == ()
    for analysis in ("snv", "cnv", "translocation"):
        source = source.replace(f"[{analysis}]\ncallers = []", "")
    path = tmp_path / "vocabulary.toml"
    path.write_text(source)
    assert load_clinical_vocabulary(path).snv_callers == ()
    path.write_text(source + '\n[fusion]\ncallers = ["unknown"]\n')
    with pytest.raises(RuntimeError, match="Application-owned clinical definitions"):
        load_clinical_vocabulary(path)


@pytest.mark.parametrize("include_wording", [True, False])
def test_git_source_extracts_only_configuration_at_the_requested_commit(
    tmp_path, monkeypatch, include_wording
):
    """Git content is read as files, without checking out or running repository code."""
    calls = []
    run = subprocess.run

    def fake_run(command, **kwargs):
        """Record Git operations while retaining real application configuration validation."""
        if command[0] == "git":
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)
        return run(command, **kwargs)

    def fake_output(command, **kwargs):
        """Return synthetic repository files for exact commit-qualified paths."""
        calls.append(command)
        if "ls-tree" in command:
            assert kwargs == {"text": True}
            names = (*FILES, "report_presentation.toml") if include_wording else FILES
            return "\n".join(f"center/{name}" for name in names)
        assert command[-1].startswith("a" * 40 + ":center/")
        return (ROOT / "config/examples/center" / command[-1].rsplit("/", 1)[1]).read_bytes()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "check_output", fake_output)
    prepare("https://github.com/example/center.git", tmp_path / "release", "a" * 40, "center")
    assert sum("show" in command for command in calls) == len(FILES) + int(include_wording)
    assert (tmp_path / "release/report_presentation.toml").exists() == include_wording
    assert not any("checkout" in command for command in calls)
