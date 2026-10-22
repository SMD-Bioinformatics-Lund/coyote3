"""Common RNA helper functions for fusion filter/call normalization."""

from typing import Any, cast

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY


def create_fusioneffectlist(eff_names: list[str | None]) -> list[str]:
    """Normalize fusion effect labels into canonical values.

    Args:
        eff_names: Raw effect labels from request filters or stored payloads.

    Returns:
        list: Deduplicated canonical effect labels.
    """
    canonical_map = {
        "inframe": "in-frame",
        "in-frame": "in-frame",
        "outframe": "out-of-frame",
        "out-of-frame": "out-of-frame",
    }

    effects = []
    for effect in eff_names:
        if effect is None:
            continue
        key = str(effect).strip().lower()
        canonical = canonical_map.get(key)
        if canonical:
            effects.append(canonical)
    return list(dict.fromkeys(effects))


def create_fusioncallers(fuscallers: list[str]) -> list[str]:
    """Normalize fusion caller names into canonical values.

    Args:
        fuscallers: Raw caller names from request filters or stored payloads.

    Returns:
        list: Deduplicated canonical caller names.
    """
    return cast(
        list[str],
        CLINICAL_VOCABULARY.normalize_fusion_callers(fuscallers or [], reject_unknown=False),
    )


def get_selected_fusioncall(fusion: dict[str, Any]) -> dict[str, Any] | None:
    """Return the selected fusion call from a fusion payload.

    Args:
        fusion: Fusion payload containing a ``calls`` collection.

    Returns:
        Selected call payload when one is marked active; None when no call is selected.
    """
    for call in fusion.get("calls", []):
        if call.get("selected") == 1:
            return cast(dict[str, Any], call)
    return None


def get_fusion_callers(fusion: dict[str, Any]) -> list[str]:
    """Return unique caller names from a fusion payload.

    Args:
        fusion: Fusion payload containing a ``calls`` collection.

    Returns:
        list: Caller names discovered in the payload.
    """
    callers: list[str] = []
    for call in fusion.get("calls", []):
        caller_name = call.get("caller")
        if caller_name:
            callers.append(caller_name)
    return list(set(callers))
