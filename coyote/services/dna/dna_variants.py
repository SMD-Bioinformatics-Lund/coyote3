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

"""Shared DNA variant helper utilities."""

from collections import defaultdict


def format_pon(variant: dict) -> defaultdict:
    """
    Format PON keys from variant INFO into nested map by class and numeric type.
    """
    pon = defaultdict(dict)
    for i in variant["INFO"]:
        if "PON_" in i:
            part = i.split("_")
            if len(part) == 3:
                numtype = part[1]
                vc = part[2]
                pon[vc][numtype] = variant["INFO"][i]
    return pon


def get_variant_nomenclature(data: dict) -> tuple[str, str]:
    """
    Pick nomenclature+value using the existing key-priority order.
    """
    nomenclature = "p"
    variant = ""

    var_nomenclature = {
        "var_p": "p",
        "var_c": "c",
        "var_g": "g",
        "fusionpoints": "f",
        "translocpoints": "t",
        "cnvvar": "cn",
    }

    for key, value in var_nomenclature.items():
        variant_value = data.get(key)
        if variant_value:
            nomenclature = value
            variant = variant_value
            break

    return nomenclature, variant
