# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Supported in-process application SDK; importing it initializes no runtime services.

The host supplies authenticated execution and service capabilities. Remote callers
use the independent coyote_pyclient distribution instead. Submodules other than these
exports are implementation details.
"""

from coyote.application.common.analysis_query import AnalysisQuery
from coyote.application.operations.account import Account, PasswordRecovery
from coyote.application.operations.administration import (
    AdministrationServices,
    AssayConfigurations,
    AssayGroups,
    Assays,
    AssaySetups,
    CatalogAuthoring,
    Diagnoses,
    GeneLists,
    Permissions,
    ReferenceData,
    Roles,
    SampleAdministration,
    Users,
)
from coyote.application.operations.application import ApplicationServices, CoyoteApplication
from coyote.application.operations.clinical import ClinicalServices, Findings, SmallVariants
from coyote.application.operations.clinical_rules import ClinicalRules
from coyote.application.operations.coverage import Coverage
from coyote.application.operations.governance import (
    ConfigurationProfiles,
    ConfigurationPromotions,
    QueryRules,
)
from coyote.application.operations.ingest import Ingestion, IngestJobs, IngestSubmissionServices
from coyote.application.operations.internal_references import (
    InternalReferences,
    InternalReferenceServices,
)
from coyote.application.operations.knowledgebase import Knowledgebase
from coyote.application.operations.maintenance import MaintenanceExecution, MaintenanceServices
from coyote.application.operations.models import (
    CsvExport,
    Download,
    FileArtifact,
    FindingPage,
    FlagChange,
    IngestResult,
    ReportPreview,
    ReportPreviewBundle,
    SampleMutation,
    SampleRecord,
    SampleSearch,
    SavedReport,
    TierChange,
)
from coyote.application.operations.notifications import Notifications
from coyote.application.operations.public import PublicApplication
from coyote.application.operations.reporting import ReportingServices
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.application.operations.samples import Sample, Samples
from coyote.application.operations.system import (
    Controls,
    Credentials,
    Dashboard,
    OperationsServices,
    Traceability,
)
from coyote.contracts.operations import OperationResult
from coyote.contracts.resource_integrity import (
    ResourceHasher,
    configure_resource_hasher,
    using_resource_hasher,
)
from coyote.domain.exceptions import AppError

__all__ = [
    "ResourceHasher",
    "configure_resource_hasher",
    "using_resource_hasher",
    "Account",
    "AdministrationServices",
    "AnalysisQuery",
    "AppError",
    "ApplicationRuntime",
    "ApplicationServices",
    "AssayConfigurations",
    "AssayGroups",
    "AssaySetups",
    "Assays",
    "CatalogAuthoring",
    "ClinicalRules",
    "ClinicalServices",
    "ConfigurationProfiles",
    "ConfigurationPromotions",
    "Controls",
    "Coverage",
    "CoyoteApplication",
    "Credentials",
    "CsvExport",
    "Dashboard",
    "Diagnoses",
    "Download",
    "FileArtifact",
    "FindingPage",
    "Findings",
    "FlagChange",
    "GeneLists",
    "IngestJobs",
    "IngestResult",
    "IngestSubmissionServices",
    "Ingestion",
    "InternalReferenceServices",
    "InternalReferences",
    "Knowledgebase",
    "MaintenanceExecution",
    "MaintenanceServices",
    "Notifications",
    "OperationResult",
    "OperationsServices",
    "PasswordRecovery",
    "Permissions",
    "PublicApplication",
    "QueryRules",
    "ReferenceData",
    "ReportPreview",
    "ReportPreviewBundle",
    "ReportingServices",
    "Roles",
    "Sample",
    "SampleAdministration",
    "SampleMutation",
    "SampleRecord",
    "SampleSearch",
    "Samples",
    "SavedReport",
    "SmallVariants",
    "TierChange",
    "Traceability",
    "Users",
]
