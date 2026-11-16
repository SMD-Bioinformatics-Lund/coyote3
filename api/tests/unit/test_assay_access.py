"""Paired scopes never grant an environment belonging to another assay."""

from copy import deepcopy
from types import SimpleNamespace

import mongomock
import pytest
from api_test_support.mongo_settings import mongo_runtime
from coyote.domain.identity.assay_access import grants_for, pair_allowed
from coyote_api.security.models import UserModel
from coyote_api.security.policy import PrincipalScope
from coyote_mongo.assay_access import finding_scope_query
from coyote_mongo.repositories.reports import ReportRepository
from coyote_mongo.repositories.variants import VariantsRepository

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


def test_report_pagination_and_search_use_the_paired_grants_before_counting():
    collection = mongomock.MongoClient().test.reports
    collection.insert_many(
        [
            {"report_id": f"{assay}-{env}", "asp_id": assay, "environment": env}
            for assay in ("assay_a", "assay_b")
            for env in ("production", "development")
        ]
    )
    repo = ReportRepository(SimpleNamespace(app=mongo_runtime(), reports_collection=collection))
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
    adapter = SimpleNamespace(
        app=mongo_runtime(), samples_collection=db.samples, variants_collection=db.variants
    )
    repo = VariantsRepository(adapter)
    repo.set_collection(db.variants)
    assert db.variants.count_documents(finding_scope_query(adapter, GRANTS)) == 3
    assert repo.get_dashboard_variant_counts(assay_access=GRANTS)["total_variants"] == 3
    assert repo.get_dashboard_variant_counts(assay_access=[])["total_variants"] == 0


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
