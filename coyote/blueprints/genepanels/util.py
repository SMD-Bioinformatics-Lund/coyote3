from functools import lru_cache
from datetime import datetime
from collections import defaultdict, OrderedDict
from typing import Dict, Tuple, List, Generator, Any
from copy import deepcopy
from coyote.extensions import store


class GenePanelUtility:
    """
    Utility class for Gene Panel blueprint
    """

    @staticmethod
    def format_genepanel_list(panels: list[dict], assay: str) -> list[dict]:
        """
        Format gene panel list
        """
        # {'genes': ['BRCA1', 'BRCA2'], 'type': 'genelist', 'name': 'brca', 'displayname': 'Ovarian', 'assays': ['gmsonco'], 'last_updated': {'change': 'Created', 'version': 1.0, 'timestamp': '2023-07-11 11:59:05', 'user': 'viktor'}}
        formatted_panels = []
        for panel in panels:
            new_panel = deepcopy(panel)
            new_panel["id"] = str(new_panel["_id"])
            if "genes" in new_panel:
                new_panel["no_of_genes"] = len(new_panel["genes"])
                new_panel.pop("genes")
            new_panel["version"] = new_panel["last_updated"]["version"]
            new_panel["timestamp"] = new_panel["last_updated"]["timestamp"]
            new_panel["user"] = new_panel["last_updated"]["user"]
            new_panel.pop("last_updated")
            formatted_panels.append(new_panel)
            if "assays" in new_panel:
                _assays = [a for a in new_panel["assays"] if a != assay]
                if len(_assays) > 0:
                    new_panel["other_assays"] = ",".join(_assays)
                else:
                    new_panel["other_assays"] = "-"
                new_panel.pop("assays")

        return formatted_panels

    @staticmethod
    def validate_panel_name(name, genepanel_id=None):
        return not store.panel_handler.validate_panel_field("name", name, genepanel_id)

    @staticmethod
    def validate_panel_displayname(displayname, genepanel_id=None):
        return not store.panel_handler.validate_panel_field(
            "displayname", displayname, genepanel_id
        )

    @staticmethod
    def validate_panel_version(genepanel_id, form_version):
        """
        Validate the version of a panel
        """
        latest_version = store.panel_handler.get_latest_genepanel_version(genepanel_id)
        return float(latest_version) >= float(form_version)
