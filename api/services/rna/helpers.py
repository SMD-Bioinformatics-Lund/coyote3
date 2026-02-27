#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""Shared RNA helper functions for fusion filter/call normalization."""


def create_fusioneffectlist(eff_names: list) -> list:
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
    for call in fusion.get("calls", []):
        if call.get("selected") == 1:
            return call
    return None  # type: ignore


def get_fusion_callers(fusion: list) -> list:
    callers = []
    for call in fusion.get("calls", []):
        caller_name = call.get("caller")
        if caller_name:
            callers.append(caller_name)
    return list(set(callers))
