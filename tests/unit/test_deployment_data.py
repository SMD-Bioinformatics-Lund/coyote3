"""Deployment data additions require an authenticated installation role."""

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest

from api.infra.mongo.repositories import deployment_data
from api.services.provisioning.deployment_data import DeploymentDataService
from coyote3.domain.exceptions import AppError
from scripts.bootstrap import bootstrap_database
from scripts.bootstrap.bootstrap_database import (
    DEFAULT_RBAC_DIR,
    DEFAULT_REFERENCE_DIR,
    build_seed_documents,
)


@pytest.mark.parametrize("roles", [[], ["viewer"], ["demo_installer"], ["SUPERUSER"]])
def test_role_check_precedes_any_seed_loading_or_database_access(roles):
    repository, loader = Mock(), Mock()
    service = DeploymentDataService(repository, loader)
    with pytest.raises(AppError) as error:
        service.install(
            user=SimpleNamespace(username="operator", roles=roles), modules=["application"]
        )
    assert error.value.status_code == 403
    assert not repository.mock_calls
    loader.assert_not_called()


@pytest.mark.parametrize("role", ["admin", "sys_admin", "superuser"])
def test_admin_provenance_comes_from_the_authenticated_principal(role):
    repository, loader = Mock(), Mock(return_value={"assay_groups": []})
    repository.pending.return_value = ["assay_groups"]
    repository.install.return_value = {"assay_groups": "loaded"}
    service = DeploymentDataService(repository, loader)
    result = service.install(
        user=SimpleNamespace(username="authenticated.admin", roles=[role]), modules=["application"]
    )
    loader.assert_called_once_with("system", "application")
    repository.install.assert_called_once_with(
        loader.return_value, scope="application", actor="authenticated.admin", force=False
    )
    assert result == {"collections": {"assay_groups": "loaded"}}


def test_populated_scope_skips_loading_and_writing():
    repository, loader = Mock(), Mock()
    repository.pending.return_value = []
    repository.skipped.return_value = {"assay_groups": "skipped"}
    service = DeploymentDataService(repository, loader)
    assert service.install(
        user=SimpleNamespace(username="admin", roles=["sys_admin"]), modules=["application"]
    ) == {"collections": {"assay_groups": "skipped"}}
    loader.assert_not_called()
    repository.install.assert_not_called()


def test_repository_preserves_records_captures_policy_revisions_and_audits(monkeypatch):
    """Application policies and knowledgebase publications retain their installation evidence."""
    application = mongomock.MongoClient().application
    knowledgebase = mongomock.MongoClient().knowledgebase
    repository = deployment_data.DeploymentDataRepository(
        application, knowledgebase, mongomock.MongoClient().identity
    )
    transactions, receipts = [], []

    def transaction(client, write):
        transactions.append(client)
        return write(None)

    monkeypatch.setattr(deployment_data, "run_transaction", transaction)
    monkeypatch.setattr(
        deployment_data, "enqueue_audit", lambda *args, **kwargs: receipts.append(kwargs)
    )
    documents = build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        actor="authenticated.admin",
        include_knowledgebase=False,
    )
    documents.update(
        hgnc_genes=[{"hgnc_id": "synthetic"}],
        vep_metadata=[{"id": "synthetic"}],
        vep_diagrams=[{"id": "synthetic.diagram"}],
    )
    knowledgebase.hgnc_genes.insert_one({"hgnc_id": "preserved"})
    before = list(knowledgebase.hgnc_genes.find())
    assert set(repository.pending("all")) == {
        "permissions",
        "roles",
        "assay_groups",
        "query_rule_sets",
        "vep_diagrams",
        "vep_metadata",
    }
    result = repository.install(documents, scope="all", actor="authenticated.admin")
    assert result["hgnc_genes"] == "skipped"
    assert set(result.values()) == {"loaded", "skipped"}
    assert len(transactions) == 4
    assert all(
        client in {application.client, repository.databases["identity"].client}
        for client in transactions
    )
    assert list(knowledgebase.hgnc_genes.find()) == before
    assert application.assay_groups.count_documents({}) == 5
    assert application.query_rule_sets.count_documents({}) == 6
    assert application.query_rule_revisions.count_documents({}) == 6
    assert {row["action"] for row in application.query_rule_revisions.find()} == {
        "baseline_captured"
    }
    assert {row["created_by"] for row in application.query_rule_sets.find()} == {"system"}
    assert {row["source"] for row in knowledgebase.versions.find()} == {
        "vep_metadata",
        "vep_diagrams",
    }
    assert len(receipts) == 4
    assert {event["actor"] for event in receipts} == {"authenticated.admin"}
    assert set(repository.install(documents, scope="all", actor="second.admin").values()) == {
        "skipped"
    }
    assert len(receipts) == 4
    assert len(transactions) == 4
    for database in (application, knowledgebase):
        for name in database.list_collection_names():
            assert set(database[name].index_information()) == {"_id_"}


def test_empty_payloads_do_not_publish_success(monkeypatch):
    repository = deployment_data.DeploymentDataRepository(
        mongomock.MongoClient().application,
        mongomock.MongoClient().knowledgebase,
        mongomock.MongoClient().identity,
    )
    audit = Mock()
    monkeypatch.setattr(deployment_data, "enqueue_audit", audit)
    assert set(repository.install({}, scope="all", actor="admin").values()) == {"empty"}
    audit.assert_not_called()


def test_reference_installation_does_not_require_application_transactions():
    """A separate knowledgebase retains ordered inserts and reference publication records."""
    application = mongomock.MongoClient().application
    knowledgebase = mongomock.MongoClient().knowledgebase
    repository = deployment_data.DeploymentDataRepository(
        application, knowledgebase, mongomock.MongoClient().identity
    )
    result = repository.install(
        {
            "hgnc_genes": [{"hgnc_id": "synthetic"}],
            "vep_metadata": [{"id": "synthetic"}],
            "vep_diagrams": [{"id": "synthetic.diagram"}],
        },
        scope="knowledgebase",
        actor="authenticated.admin",
    )
    assert set(result.values()) == {"loaded"}
    assert knowledgebase.versions.count_documents({}) == 3
    assert application.list_collection_names() == []


@pytest.fixture
def fresh_installation(monkeypatch):
    """Keep initial-account creation real while isolating endpoints and large reference files."""
    client = mongomock.MongoClient()
    databases = {name: client[name] for name in ("primary", "identity", "knowledgebase", "bam")}
    args = Namespace(
        username="emergency",
        email="emergency@example.org",
        password="emergency-example",
        sys_admin_username="operator",
        sys_admin_email="operator@example.org",
        sys_admin_password="operator-example",
        mongo_uri="mongodb://unused",
        identity_mongo_uri="",
        db="primary",
        identity_db="identity",
        role_id="superuser",
        rbac_dir=str(DEFAULT_RBAC_DIR),
        reference_dir=str(DEFAULT_REFERENCE_DIR),
        skip_users=False,
        skip_application=False,
        skip_knowledgebase=False,
        skip_demo=False,
    )
    documents = build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        actor="system",
        include_knowledgebase=False,
    )
    documents.update(hgnc_genes=[{"hgnc_id": "synthetic"}], vep_metadata=[{"vep_id": "103"}])
    loader = Mock(return_value=documents)
    monkeypatch.setattr(bootstrap_database, "parse_args", lambda: args)
    monkeypatch.setattr(bootstrap_database, "build_seed_documents", loader)
    monkeypatch.setattr(
        "api.infra.mongo.connections.MongoConnections",
        lambda *args, **kwargs: SimpleNamespace(databases=databases, close=lambda: None),
    )
    monkeypatch.setattr(
        "api.infra.seed.diagrams.load_seed_diagrams",
        lambda *args: [{"_id": "asset"}],
    )
    monkeypatch.setattr(
        "api.infra.mongo.transactions.run_transaction", lambda client, write: write(None)
    )
    monkeypatch.setattr(deployment_data, "run_transaction", lambda client, write: write(None))
    monkeypatch.setattr(deployment_data, "enqueue_audit", lambda *args, **kwargs: None)
    demo = Mock()
    demo.install_starter.return_value = {"status": "installed"}
    monkeypatch.setattr("scripts.bootstrap.demo_service.build_demo_service", lambda *args: demo)
    return databases, args, loader, demo


def test_first_installation_defaults_to_all_modules_and_system_provenance(fresh_installation):
    databases, _, loader, demo = fresh_installation
    assert bootstrap_database.main() == 0
    identity, application = databases["identity"], databases["primary"]
    assert identity.users.count_documents({}) == 2
    assert {row["created_by"] for row in identity.users.find()} == {"system"}
    assert identity.users.count_documents({"must_change_password": True}) == 2
    assert application.assay_groups.count_documents({}) == 5
    assert application.query_rule_sets.count_documents({}) == 6
    assert databases["knowledgebase"].hgnc_genes.count_documents({}) == 1
    assert loader.call_args.kwargs["actor"] == "system"
    demo.install_starter.assert_called_once_with("system")


def test_existing_accounts_prevent_unauthenticated_additions_even_to_empty_modules(
    fresh_installation, monkeypatch
):
    databases, _, loader, demo = fresh_installation
    assert bootstrap_database.main() == 0
    users = list(databases["identity"].users.find())
    databases["primary"].assay_groups.delete_many({})
    databases["knowledgebase"].hgnc_genes.delete_many({})
    loader.reset_mock()
    demo.reset_mock()
    monkeypatch.setattr(
        bootstrap_database.getpass, "getpass", Mock(side_effect=AssertionError("unexpected prompt"))
    )
    assert bootstrap_database.main() == 0
    assert list(databases["identity"].users.find()) == users
    assert databases["primary"].assay_groups.count_documents({}) == 0
    assert databases["knowledgebase"].hgnc_genes.count_documents({}) == 0
    loader.assert_not_called()
    demo.install_starter.assert_not_called()


def test_skip_flags_control_fresh_modules(fresh_installation):
    databases, args, _, demo = fresh_installation
    args.skip_knowledgebase = args.skip_demo = True
    assert bootstrap_database.main() == 0
    assert databases["identity"].users.count_documents({}) == 2
    assert databases["primary"].assay_groups.count_documents({}) == 5
    assert databases["knowledgebase"].list_collection_names() == []
    demo.install_starter.assert_not_called()


def test_skipping_users_can_disable_all_bootstrap_writes(fresh_installation):
    databases, args, loader, demo = fresh_installation
    args.skip_users = args.skip_application = args.skip_knowledgebase = args.skip_demo = True
    assert bootstrap_database.main() == 0
    assert all(not database.list_collection_names() for database in databases.values())
    loader.assert_not_called()
    demo.install_starter.assert_not_called()


def test_partial_target_cannot_create_accounts_or_seed_data(fresh_installation):
    databases, _, loader, demo = fresh_installation
    databases["identity"].roles.insert_one({"role_id": "unrecognized"})
    with pytest.raises(ValueError, match="Partial"):
        bootstrap_database.main()
    assert databases["identity"].users.count_documents({}) == 0
    loader.assert_not_called()
    demo.install_starter.assert_not_called()


def test_failed_initial_module_must_be_resumed_through_api(fresh_installation):
    databases, _, loader, demo = fresh_installation
    demo.install_starter.side_effect = RuntimeError("synthetic ingest failure")
    with pytest.raises(RuntimeError, match="synthetic ingest"):
        bootstrap_database.main()
    assert databases["identity"].users.count_documents({}) == 2
    demo.reset_mock()
    loader.reset_mock()
    assert bootstrap_database.main() == 0
    loader.assert_not_called()
    demo.install_starter.assert_not_called()


def test_service_rejects_temporary_password_before_any_data_access():
    repository, loader = Mock(), Mock()
    service = DeploymentDataService(repository, loader)
    with pytest.raises(AppError, match="Change your temporary password"):
        service.install(
            user=SimpleNamespace(username="admin", roles=["sys_admin"], must_change_password=True),
            modules=["application"],
            force=True,
        )
    assert not repository.mock_calls
    loader.assert_not_called()


def test_force_is_limited_to_explicit_modules():
    repository, loader, demo = Mock(), Mock(return_value={}), Mock()
    repository.install.return_value = {"assay_groups": "repaired"}
    service = DeploymentDataService(repository, loader, demo)
    service.install(
        user=SimpleNamespace(username="admin", roles=["admin"]), modules=["application"], force=True
    )
    repository.install.assert_called_once_with({}, scope="application", actor="admin", force=True)
    demo.install_starter.assert_not_called()


def test_force_identity_repairs_grants_without_touching_users(monkeypatch):
    client = mongomock.MongoClient()
    repository = deployment_data.DeploymentDataRepository(
        client.primary, client.knowledgebase, client.identity
    )
    monkeypatch.setattr(deployment_data, "run_transaction", lambda client, write: write(None))
    monkeypatch.setattr(deployment_data, "enqueue_audit", lambda *args, **kwargs: None)
    client.identity.users.insert_one(
        {"username": "admin", "password": "unchanged-hash", "roles": ["admin"]}
    )
    client.identity.roles.insert_many(
        [
            {
                "role_id": "admin",
                "permissions": ["center:extra"],
                "system_managed": True,
                "is_active": False,
            },
            {"role_id": "center", "permissions": ["center:private"]},
        ]
    )
    before = list(client.identity.users.find())
    repository.install(
        {"roles": [{"role_id": "admin", "permissions": ["bundled:grant"], "created_by": "system"}]},
        scope="identity",
        actor="authenticated.admin",
        force=True,
    )
    assert list(client.identity.users.find()) == before
    role = client.identity.roles.find_one({"role_id": "admin"})
    assert set(role["permissions"]) == {"center:extra", "bundled:grant"}
    assert role["is_active"] is False
    assert role["updated_by"] == "system"
    assert client.identity.roles.find_one({"role_id": "center"})["permissions"] == [
        "center:private"
    ]


def test_force_application_preserves_center_scopes_and_query_history(monkeypatch):
    from copy import deepcopy

    from api.infra.mongo.repositories.query_rule_revisions import QueryRuleRevisionRepository

    client = mongomock.MongoClient()
    repository = deployment_data.DeploymentDataRepository(
        client.primary, client.knowledgebase, client.identity
    )
    monkeypatch.setattr(deployment_data, "run_transaction", lambda client, write: write(None))
    monkeypatch.setattr(deployment_data, "enqueue_audit", lambda *args, **kwargs: None)
    documents = build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        actor="system",
        include_knowledgebase=False,
    )
    repository.install(documents, scope="application", actor="system")
    published = client.primary.query_rule_sets.find_one({"content.exceptions.0": {"$exists": True}})
    source = next(
        row for row in documents["query_rule_sets"] if row["scope_key"] == published["scope_key"]
    )
    source["content"]["exceptions"] = []
    center = deepcopy(
        next(
            row
            for row in documents["query_rule_sets"]
            if row["scope_key"] != published["scope_key"]
        )
    )
    client.primary.query_rule_sets.update_many(
        {"scope_key": center["scope_key"]},
        {"$set": {"system_installed": False, "created_by": "center.editor"}},
    )
    before_center = list(client.primary.query_rule_sets.find({"scope_key": center["scope_key"]}))
    client.primary.assay_groups.insert_one({"group_id": "center_only", "display_name": "Keep"})
    client.primary.assay_groups.update_one(
        {"group_id": "hematology"}, {"$set": {"is_active": False}}
    )
    repository.install(documents, scope="application", actor="maintenance.admin", force=True)
    assert (
        list(client.primary.query_rule_sets.find({"scope_key": center["scope_key"]}))
        == before_center
    )
    retained = list(
        client.primary.query_rule_sets.find({"scope_key": published["scope_key"]}).sort(
            "version", 1
        )
    )
    assert [row["status"] for row in retained] == ["retired", "published"]
    history = QueryRuleRevisionRepository(
        SimpleNamespace(query_rule_revisions_collection=client.primary.query_rule_revisions)
    )
    assert len(history.list_for_version(str(retained[0]["_id"]))) == 2
    assert retained[1]["created_by"] == "system"
    assert retained[1]["updated_by"] == "system"
    assert (
        client.primary.assay_groups.find_one({"group_id": "center_only"})["display_name"] == "Keep"
    )
    assert client.primary.assay_groups.find_one({"group_id": "hematology"})["is_active"] is False


def test_force_reference_preserves_external_releases_and_unrelated_genes():
    from api.infra.mongo.repositories.knowledgebase_publications import record_reference_publication

    client = mongomock.MongoClient()
    repository = deployment_data.DeploymentDataRepository(
        client.primary, client.knowledgebase, client.identity
    )
    documents = {
        "hgnc_genes": [
            {"hgnc_id": "HGNC:synthetic", "created_by": "system", "gene_name": "Baseline"}
        ]
    }
    repository.install(documents, scope="knowledgebase", actor="system")
    client.knowledgebase.hgnc_genes.update_one({}, {"$set": {"gene_name": "Changed"}})
    client.knowledgebase.hgnc_genes.insert_one({"hgnc_id": "center_only", "gene_name": "Keep"})
    repository.install(documents, scope="knowledgebase", actor="admin", force=True)
    assert (
        client.knowledgebase.hgnc_genes.find_one({"hgnc_id": "HGNC:synthetic"})["gene_name"]
        == "Baseline"
    )
    assert (
        client.knowledgebase.hgnc_genes.find_one({"hgnc_id": "center_only"})["gene_name"] == "Keep"
    )
    record_reference_publication(
        client.knowledgebase, source="hgnc_genes", release="center_release"
    )
    before = list(client.knowledgebase.hgnc_genes.find())
    result = repository.install(documents, scope="knowledgebase", actor="admin", force=True)
    assert result["hgnc_genes"] == "preserved"
    assert list(client.knowledgebase.hgnc_genes.find()) == before


def test_force_recovers_system_reference_batch_before_publication_receipt():
    client = mongomock.MongoClient()
    repository = deployment_data.DeploymentDataRepository(
        client.primary, client.knowledgebase, client.identity
    )
    client.knowledgebase.hgnc_genes.insert_one({"hgnc_id": "first", "created_by": "system"})
    documents = {
        "hgnc_genes": [
            {"hgnc_id": "first", "created_by": "system", "gene_name": "Restored"},
            {"hgnc_id": "second", "created_by": "system", "gene_name": "Missing"},
        ]
    }
    result = repository.install(documents, scope="knowledgebase", actor="admin", force=True)
    assert result["hgnc_genes"] == "repaired"
    assert client.knowledgebase.hgnc_genes.count_documents({}) == 2
    assert client.knowledgebase.versions.find_one({"source": "hgnc_genes", "release": "bundled"})


def test_force_preserves_unknown_reference_collection_without_bundled_provenance():
    client = mongomock.MongoClient()
    repository = deployment_data.DeploymentDataRepository(
        client.primary, client.knowledgebase, client.identity
    )
    client.knowledgebase.hgnc_genes.insert_one(
        {"hgnc_id": "center_gene", "created_by": "center.importer"}
    )
    before = list(client.knowledgebase.hgnc_genes.find())
    result = repository.install(
        {"hgnc_genes": [{"hgnc_id": "bundled_gene", "created_by": "system"}]},
        scope="knowledgebase",
        actor="admin",
        force=True,
    )
    assert result["hgnc_genes"] == "preserved"
    assert list(client.knowledgebase.hgnc_genes.find()) == before
