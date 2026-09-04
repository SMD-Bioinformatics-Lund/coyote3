"""Knowledgebase plugin registry for Mongo-backed annotation datasets."""

from __future__ import annotations

from dataclasses import dataclass

from api.infra.knowledgebase.brcaexchange import BRCARepository
from api.infra.knowledgebase.civic import CivicRepository
from api.infra.knowledgebase.cosmic import CosmicRepository
from api.infra.knowledgebase.hgnc import HGNCRepository
from api.infra.knowledgebase.iarc_tp53 import IARCTP53Repository
from api.infra.knowledgebase.oncokb import OnkoKBRepository
from api.infra.knowledgebase.versions import KnowledgebaseVersionRepository


@dataclass(frozen=True)
class KnowledgebasePlugin:
    """Describe one built-in knowledgebase repository binding."""

    name: str
    repository_attr: str
    repository_cls: type
    index_name: str


BUILTIN_KNOWLEDGEBASE_REPOSITORIES: tuple[KnowledgebasePlugin, ...] = (
    KnowledgebasePlugin("civic", "civic_repository", CivicRepository, "civic"),
    KnowledgebasePlugin("iarc_tp53", "iarc_tp53_repository", IARCTP53Repository, "iarc_tp53"),
    KnowledgebasePlugin("brca", "brca_repository", BRCARepository, "brca"),
    KnowledgebasePlugin("oncokb", "oncokb_repository", OnkoKBRepository, "oncokb"),
    KnowledgebasePlugin("cosmic", "cosmic_repository", CosmicRepository, "cosmic"),
    KnowledgebasePlugin(
        "knowledgebase_versions",
        "knowledgebase_version_repository",
        KnowledgebaseVersionRepository,
        "knowledgebase_versions",
    ),
    KnowledgebasePlugin("hgnc", "hgnc_repository", HGNCRepository, "hgnc"),
)
