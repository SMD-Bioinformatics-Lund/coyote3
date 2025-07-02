import re
import subprocess
from collections import defaultdict
from datetime import datetime
from math import floor, log10

from bson.objectid import ObjectId
from flask import current_app as app
from flask_login import current_user

from coyote.util.common_utility import CommonUtility


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
            ## effect = name.split("_", 1)[1]
            if name == "inframe":
                effects.append("in-frame")
            if name == "outframe":
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
