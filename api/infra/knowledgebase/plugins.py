"""Knowledgebase plugin registry for Mongo-backed annotation datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.config import get_enabled_knowledgebase_plugins
from api.infra.knowledgebase.brcaexchange import BRCARepository
from api.infra.knowledgebase.civic import CivicRepository
from api.infra.knowledgebase.cosmic import CosmicRepository
from api.infra.knowledgebase.hgnc import HGNCRepository
from api.infra.knowledgebase.iarc_tp53 import IARCTP53Repository
from api.infra.knowledgebase.oncokb import OnkoKBRepository


@dataclass(frozen=True)
class KnowledgebasePlugin:
    """Describe one optional knowledgebase repository binding."""

    name: str
    repository_attr: str
    repository_cls: type
    index_name: str


KNOWLEDGEBASE_PLUGINS: tuple[KnowledgebasePlugin, ...] = (
    KnowledgebasePlugin("civic", "civic_repository", CivicRepository, "civic"),
    KnowledgebasePlugin("iarc_tp53", "iarc_tp53_repository", IARCTP53Repository, "iarc_tp53"),
    KnowledgebasePlugin("brca", "brca_repository", BRCARepository, "brca"),
    KnowledgebasePlugin("oncokb", "oncokb_repository", OnkoKBRepository, "oncokb"),
    KnowledgebasePlugin("cosmic", "cosmic_repository", CosmicRepository, "cosmic"),
    KnowledgebasePlugin("hgnc", "hgnc_repository", HGNCRepository, "hgnc"),
)


def enabled_knowledgebase_plugins(config: dict[str, Any]) -> tuple[KnowledgebasePlugin, ...]:
    """Resolve which knowledgebase plugins are enabled for this runtime."""
    enabled = set(get_enabled_knowledgebase_plugins(config))
    if "all" in enabled:
        return KNOWLEDGEBASE_PLUGINS
    return tuple(plugin for plugin in KNOWLEDGEBASE_PLUGINS if plugin.name in enabled)
