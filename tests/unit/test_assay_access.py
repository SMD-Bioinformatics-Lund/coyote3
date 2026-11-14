"""Paired scopes never grant an environment belonging to another assay."""

from copy import deepcopy
from types import SimpleNamespace

import mongomock
import pytest
from pydantic import ValidationError

from api.infra.mongo.assay_access import finding_scope_query, restrict_assay_access
from api.infra.mongo.repositories.reports import ReportRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.variants import VariantsRepository
from api.security.models import UserModel
from api.security.policy import PrincipalScope
from coyote3.contracts.schemas.assay_access import AssayAccessGrant
from coyote3.domain.identity.assay_access import grants_for, pair_allowed

GRANTS = [
    {"asp_id": "assay_a", "environments": ["production", "development", "validation"]},
    {"asp_id": "assay_b", "environments": ["production"]},
]


@pytest.mark.parametrize(
    "assay,environment,expected",
    [
        ("assay_a", "production", True),
        ("assay_a", "development", True),
        ("assay_a", "validation", True),
        ("assay_b", "production", True),
        ("assay_b", "development", False),
        ("assay_b", "validation", False),
        ("assay_c", "production", False),
        ("assay_a", "testing", False),
    ],
)
def test_pair_is_required_by_both_domain_and_host_policy(assay, environment, expected):
    actor = SimpleNamespace(
        roles=["user"],
        assay_access=deepcopy(GRANTS),
        asp_ids=["assay_a", "assay_b"],
        envs=["production", "development", "validation"],
        asp_groups=[],
    )
    assert pair_allowed(grants_for(actor), assay, environment) is expected
    assert PrincipalScope.from_user(actor).allows(assay, environment) is expected


def test_legacy_lists_and_explicit_empty_grants_never_supply_fallback_access():
    actor = SimpleNamespace(
        roles=["user"], asp_ids=["*"], envs=["production", "development"], asp_groups=[]
    )
    assert not PrincipalScope.from_user(actor).allows("assay_b", "development")
    actor.assay_access = []
    assert not PrincipalScope.from_user(actor).allows("assay_a", "production")
    actor.roles = ["superuser"]
    assert PrincipalScope.from_user(actor).allows("assay_b", "development")


@pytest.mark.parametrize(
    "changes",
    [
        {"roles": "not-superuser", "assay_access": []},
        {"roles": ["user"], "assay_access": [{"asp_id": "assay_a", "environments": "production"}]},
        {"roles": ["user"], "assay_access": "invalid"},
    ],
)
def test_malformed_persisted_grants_fail_closed(changes):
    assert grants_for(changes) == []


def test_authentication_intersects_explicit_grants_with_registered_group_restrictions():
    user = UserModel.from_auth_payload(
        {
            "_id": "reviewer",
            "username": "reviewer",
            "email": "reviewer@example.test",
            "fullname": "Synthetic",
            "roles": ["user"],
            "asp_groups": ["hematology"],
            "assay_access": GRANTS,
        },
        asp_docs=[
            {"asp_id": "assay_a", "asp_group": "hematology"},
            {"asp_id": "assay_b", "asp_group": "solid"},
        ],
    )
    assert user.asp_ids == ["assay_a"]


def test_direct_sample_queries_rows_and_totals_preserve_pairs_and_search_intersection():
    collection = mongomock.MongoClient().test.samples
    collection.insert_many(
        [
            {
                "name": f"{assay}-{env}",
                "asp_id": assay,
                "environment": env,
                "ingest_status": "ready",
            }
            for assay in ("assay_a", "assay_b")
            for env in ("production", "development", "validation")
        ]
    )
    query = SampleRepository._build_samples_query(
        user_assays=["assay_a", "assay_b"],
        user_envs=["production", "development", "validation"],
        report=False,
        search_str="",
        assay_access=GRANTS,
    )
    assert collection.count_documents(query) == 4
    assert not collection.find_one({"$and": [query, {"name": "assay_b-development"}]})
    assert (
        collection.count_documents(restrict_assay_access({"environment": "development"}, GRANTS))
        == 1
    )
    assert collection.count_documents(restrict_assay_access({}, [])) == 0


def test_report_pagination_and_search_use_the_paired_grants_before_counting():
    collection = mongomock.MongoClient().test.reports
    collection.insert_many(
        [
            {"report_id": f"{assay}-{env}", "asp_id": assay, "environment": env}
            for assay in ("assay_a", "assay_b")
            for env in ("production", "development")
        ]
    )
    repo = ReportRepository(SimpleNamespace(reports_collection=collection))
    repo.set_collection(collection)
    rows, total = repo.list_reports_page(
        asp_ids=["assay_a", "assay_b"],
        environments=["production", "development"],
        assay_access=GRANTS,
        search="development",
        page=1,
        per_page=1,
    )
    assert total == 1 and rows[0]["asp_id"] == "assay_a"


def test_patient_finding_inventory_does_not_count_a_foreign_assay_environment():
    db = mongomock.MongoClient().test
    for assay in ("assay_a", "assay_b"):
        for env in ("production", "development"):
            name = f"{assay}-{env}"
            db.samples.insert_one({"name": name, "asp_id": assay, "environment": env})
            db.variants.insert_one({"SAMPLE_ID": [name], "variant_class": "SNV"})
    adapter = SimpleNamespace(samples_collection=db.samples, variants_collection=db.variants)
    repo = VariantsRepository(adapter)
    repo.set_collection(db.variants)
    assert db.variants.count_documents(finding_scope_query(adapter, GRANTS)) == 3
    assert repo.get_dashboard_variant_counts(assay_access=GRANTS)["total_variants"] == 3
    assert repo.get_dashboard_variant_counts(assay_access=[])["total_variants"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"asp_id": "*", "environments": ["production"]},
        {"asp_id": "assay_a", "environments": ["unknown"]},
        {"asp_id": "assay_a", "environments": ["production", "production"]},
    ],
)
def test_invalid_scope_assignments_are_rejected(payload):
    with pytest.raises(ValidationError):
        AssayAccessGrant.model_validate(payload)


def test_authentication_projects_selectors_only_from_new_grants():
    actor = UserModel.from_auth_payload(
        {
            "_id": "reviewer",
            "username": "reviewer",
            "email": "reviewer@example.test",
            "fullname": "Synthetic",
            "roles": ["user"],
            "asp_ids": ["injected"],
            "environments": ["testing"],
            "assay_access": GRANTS,
        }
    )
    assert actor.asp_ids == ["assay_a", "assay_b"]
    assert actor.envs == ["development", "production", "validation"]
    assert actor.can_access_assay("assay_a", "development")
    assert not actor.can_access_assay("assay_b", "development")
    actor = UserModel.from_auth_payload(
        {
            "_id": "reviewer",
            "username": "reviewer",
            "email": "reviewer@example.test",
            "fullname": "Synthetic",
            "roles": ["user"],
            "asp_ids": ["assay_a"],
            "environments": ["production"],
        }
    )
    assert actor.asp_ids == [] and actor.envs == []
