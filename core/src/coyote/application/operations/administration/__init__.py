# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized administration operations grouped by managed resource."""

from .assay_configurations import AssayConfigurations
from .assay_groups import AssayGroups
from .assay_setups import AssaySetups
from .assays import Assays
from .catalog import CatalogAuthoring
from .diagnoses import Diagnoses
from .gene_lists import GeneLists
from .permissions import Permissions
from .reference_data import ReferenceData
from .roles import Roles
from .samples import SampleAdministration
from .services import AdministrationServices
from .users import Users

__all__ = [
    "Users",
    "Roles",
    "Permissions",
    "Assays",
    "AssayGroups",
    "Diagnoses",
    "AssayConfigurations",
    "GeneLists",
    "SampleAdministration",
    "AssaySetups",
    "CatalogAuthoring",
    "ReferenceData",
    "AdministrationServices",
]
