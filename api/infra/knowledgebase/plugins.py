"""Knowledgebase plugin registry for Mongo-backed annotation datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from api.config import get_enabled_knowledgebase_plugins
from api.infra.knowledgebase.brcaexchange import BRCAHandler
from api.infra.knowledgebase.civic import CivicHandler
from api.infra.knowledgebase.cosmic import CosmicHandler
from api.infra.knowledgebase.hgnc import HGNCHandler
from api.infra.knowledgebase.iarc_tp53 import IARCTP53Handler
from api.infra.knowledgebase.oncokb import OnkoKBHandler


@dataclass(frozen=True)
class KnowledgebasePlugin:
    """Describe one optional knowledgebase handler binding."""

    name: str
    handler_attr: str
    handler_cls: type
    index_name: str


KNOWLEDGEBASE_PLUGINS: tuple[KnowledgebasePlugin, ...] = (
    KnowledgebasePlugin("civic", "civic_handler", CivicHandler, "civic"),
    KnowledgebasePlugin("iarc_tp53", "iarc_tp53_handler", IARCTP53Handler, "iarc_tp53"),
    KnowledgebasePlugin("brca", "brca_handler", BRCAHandler, "brca"),
    KnowledgebasePlugin("oncokb", "oncokb_handler", OnkoKBHandler, "oncokb"),
    KnowledgebasePlugin("cosmic", "cosmic_handler", CosmicHandler, "cosmic"),
    KnowledgebasePlugin("hgnc", "hgnc_handler", HGNCHandler, "hgnc"),
)


def enabled_knowledgebase_plugins(config: dict[str, Any]) -> tuple[KnowledgebasePlugin, ...]:
    """Resolve which knowledgebase plugins are enabled for this runtime."""
    enabled = set(get_enabled_knowledgebase_plugins(config))
    if "all" in enabled:
        return KNOWLEDGEBASE_PLUGINS
    return tuple(plugin for plugin in KNOWLEDGEBASE_PLUGINS if plugin.name in enabled)
