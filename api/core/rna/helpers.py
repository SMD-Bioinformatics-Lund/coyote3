"""Shared RNA helper functions for fusion filter/call normalization."""


def create_fusioneffectlist(eff_names: list) -> list:
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


def create_fusioncallers(fuscallers: list) -> list:
    """Normalize fusion caller names into canonical values.

    Args:
        fuscallers: Raw caller names from request filters or stored payloads.

    Returns:
        list: Deduplicated canonical caller names.
    """
    canonical_map = {
        "arriba": "arriba",
        "fusioncatcher": "fusioncatcher",
        "fusion-catcher": "fusioncatcher",
        "fusion_catcher": "fusioncatcher",
        "starfusion": "starfusion",
        "star-fusion": "starfusion",
        "star_fusion": "starfusion",
    }

    callers = []
    for caller_name in fuscallers or []:
        if caller_name is None:
            continue

        caller = str(caller_name).strip()
        if "_" in caller and caller.startswith("fusioncaller_"):
            caller = caller.split("_", 1)[1]
        key = caller.lower()

        canonical = canonical_map.get(key)
        if canonical:
            callers.append(canonical)
    return list(dict.fromkeys(callers))


def get_selected_fusioncall(fusion: list) -> dict:
    """Return the selected fusion call from a fusion payload.

    Args:
        fusion: Fusion payload containing a ``calls`` collection.

    Returns:
        dict: Selected call payload when one is marked active.
    """
    for call in fusion.get("calls", []):
        if call.get("selected") == 1:
            return call
    return None  # type: ignore


def get_fusion_callers(fusion: list) -> list:
    """Return unique caller names from a fusion payload.

    Args:
        fusion: Fusion payload containing a ``calls`` collection.

    Returns:
        list: Caller names discovered in the payload.
    """
    callers = []
    for call in fusion.get("calls", []):
        caller_name = call.get("caller")
        if caller_name:
            callers.append(caller_name)
    return list(set(callers))
