"""Package-local synthetic records and fake ports for independent tests."""

from __future__ import annotations


def _settings(**overrides: object) -> dict:
    settings = {
        "id": "SAMPLE_1",
        "asp_id": "hema_gmsv1",
        "diagnosis_id": "hem",
        "max_freq": 1.0,
        "min_freq": 0.1,
        "max_control_freq": 0.05,
        "min_depth": 250,
        "min_alt_reads": 10,
        "max_popfreq": 0.05,
        "filter_conseq": ["missense_variant"],
        "filter_genes": [],
        "disp_pos": [],
    }
    settings.update(overrides)
    return settings
