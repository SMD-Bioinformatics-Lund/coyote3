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

from collections import defaultdict
import re
from math import floor, log10
import subprocess
from datetime import datetime
from flask_login import current_user
from bson.objectid import ObjectId
from coyote.util.common_utility import CommonUtility
from flask import current_app as app


class RNAUtility:
    """
    Utility class for RNA blueprint
    """

    @staticmethod
    def create_fusiongenelist(list_names):

        fusion_genes = []
        for name in list_names:
            list_name = name.split("_", 1)[1]

            if list_name != "FCknown" and list_name != "mitelman":
                fusion_genes.extend(fusion_lists[list_name])

        return fusion_genes

    @staticmethod
    def create_fusioneffectlist(eff_names):
        """
        This function translates filter-names in template to what is annotated. More verbose?
        """
        effects = []
        for name in eff_names:
            effect = name.split("_", 1)[1]
            if effect == "inframe":
                effects.append("in-frame")
            if effect == "outframe":
                effects.append("out-of-frame")

        return effects

    @staticmethod
    def create_fusioncallers(fuscallers):
        callers = []

        for callername in fuscallers:
            caller = callername.split("_", 1)[1]
            if caller == "arriba":
                callers.append("arriba")
            if caller == "fusioncatcher":
                callers.append("fusioncatcher")
            if caller == "starfusion":
                callers.append("starfusion")
        return callers
