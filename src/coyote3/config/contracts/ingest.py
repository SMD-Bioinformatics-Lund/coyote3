"""Application-owned ingest parser and collection payload contracts."""

from __future__ import annotations

from dataclasses import dataclass

from coyote3.config.factory_defaults import factory_value


@dataclass(frozen=True)
class AnalysisPreloadContract:
    """Map supported analyses to internal parser payload names.

    Manifest field names are application capabilities and are resolved against this
    stable application contract by :func:`manifest_file_preload_keys`.
    """

    preload_keys_by_omics: dict[str, dict[str, str | None]]


ANALYSIS_PRELOAD_CONTRACT = AnalysisPreloadContract(
    preload_keys_by_omics={
        omics: {
            **mapping,
            **dict.fromkeys(factory_value("contracts.non_database_analyses")[omics]),
        }
        for omics, mapping in factory_value("contracts.analysis_preload").items()
    }
)
