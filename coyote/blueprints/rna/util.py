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

"""
This file contains utility functions and classes for RNA blueprint processing,
including helpers for fusion gene list creation, effect translation, and fusion caller extraction.
It is part of the Coyote3 genomic data analysis framework.
"""


class RNAUtility:
    """
    Utility class for RNA blueprint processing.

    Provides static methods to create fusion gene lists, translate effect names,
    and extract fusion callers from provided input lists. These utilities are
    used in the Coyote3 genomic data analysis framework to assist with RNA
    fusion gene analysis and reporting.
    """

    # TODO: Incomplete functionality, needs to be completed with actual fusion lists and effects.
    @staticmethod
    def create_fusiongenelist(list_names):
        """
        Creates a list of fusion genes from the provided list of fusion gene list names.

        Args:
            list_names (list of str): List of fusion gene list names, each expected to be in the format 'prefix_listname'.

        Returns:
            list: Combined list of fusion genes from the specified lists, excluding 'FCknown' and 'mitelman'.
        """
        fusion_genes = []
        for name in list_names:
            list_name = name.split("_", 1)[1]

            if list_name != "FCknown" and list_name != "mitelman":
                fusion_genes.extend(fusion_lists[list_name])

        return fusion_genes

    @staticmethod
    def create_fusioneffectlist(eff_names: list) -> list:
        """

        Translates effect names from input list to standardized format.

        Args:
            eff_names (list of str): List of effect names, expected to include 'in-frame' and 'out-of-frame'.

        Returns:
            list: Standardized list of effects, e.g., ['inframe', 'outframe'].
        """
        effects = []
        for effect in eff_names:
            if effect == "in-frame":
                effects.append("inframe")
            elif effect == "out-of-frame":
                effects.append("outframe")

        return effects

    # TODO: Unnecessary redundancy, The terms are already standardized in the input. Can also be controlled via configs
    @staticmethod
    def create_fusioncallers(fuscallers: list) -> list:
        """
        Extracts and standardizes fusion caller names from a list of prefixed caller names.

        Args:
            fuscallers (list of str): List of fusion caller names, each expected in the format 'prefix_callername'.

        Returns:
            list: List of recognized fusion caller names, e.g., 'arriba', 'fusioncatcher', 'starfusion'.
        """
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

    @staticmethod
    def get_selected_fusioncall(fusion: list) -> dict:
        """
        Retrieve the selected fusion call from the fusion data.

        This method iterates through the `calls` field of the fusion data to find
        and return the call marked as selected. A call is considered selected if
        its `selected` field is set to 1.

        Args:
            fusion (list): A list containing fusion call data.

        Returns:
            dict: The selected fusion call if found, otherwise None.
        """
        for call in fusion.get("calls", []):
            if call.get("selected") == 1:
                return call
        return None  # type: ignore

    @staticmethod
    def get_fusion_callers(fusion: list) -> list:
        """
        Retrieve the list of fusion callers from the fusion data.

        This method extracts the names of all fusion callers present in the `calls`
        field of the fusion data.

        Args:
            fusion (list): A list containing fusion call data.

        Returns:
            list: A list of fusion caller names.
        """
        callers = []
        for call in fusion.get("calls", []):
            caller_name = call.get("caller")
            if caller_name:
                callers.append(caller_name)
        return list(set(callers))
