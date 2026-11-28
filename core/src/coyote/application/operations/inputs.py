# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Supported authored-content models shared with existing HTTP validation contracts.

These exports retain the authoritative validators and null/omission semantics.
They do not depend on persistence implementations. Reusable field selections and clinical request models are
owned by coyote.contracts.
"""

from coyote.contracts.auth import (
    ApiPasswordChangeRequest,
    ApiPasswordResetConfirmRequest,
    ApiProfileUpdateRequest,
    ApiUiSettingsUpdateRequest,
)
from coyote.contracts.configuration_profiles import (
    ConfigurationProfileDraft,
    ConfigurationPromotionRequest,
    ConfigurationScope,
    ProfilePublication,
)
from coyote.contracts.notifications import NotificationBroadcastRequest
from coyote.contracts.public import (
    PublicAssayCatalogImportRequest,
    PublicAssayCatalogTransitionRequest,
    PublicAssayCatalogUpdateRequest,
)
from coyote.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
    SampleField,
)
from coyote.contracts.samples import ConfigurationApplyRequest
from coyote.contracts.schemas.assay_groups import AssayGroupCreate, AssayGroupStatus
from coyote.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleTransition,
)
from coyote.contracts.schemas.diagnoses import (
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)
from coyote.contracts.schemas.query_rules import (
    QueryConditionTest,
    QueryRuleDraft,
    QueryRulePreview,
    QueryRuleSampleSearch,
    QueryRuleScope,
    QueryRuleTransition,
    QueryRuleUpdate,
)

__all__ = [
    "ApiPasswordChangeRequest",
    "ApiPasswordResetConfirmRequest",
    "ApiProfileUpdateRequest",
    "ApiUiSettingsUpdateRequest",
    "AssayField",
    "AssayGroupCreate",
    "AssayGroupStatus",
    "ClinicalRuleDecision",
    "ClinicalRuleDraftCreate",
    "ClinicalRuleDraftUpdate",
    "ClinicalRuleImportRequest",
    "ClinicalRuleTransition",
    "ConfigurationApplyRequest",
    "ConfigurationField",
    "ConfigurationProfileDraft",
    "ConfigurationPromotionRequest",
    "ConfigurationScope",
    "DiagnosisAssociationUpdate",
    "DiagnosisCreate",
    "DiagnosisField",
    "DiagnosisUpdate",
    "GeneListField",
    "GroupField",
    "NotificationBroadcastRequest",
    "ProfilePublication",
    "PublicAssayCatalogImportRequest",
    "PublicAssayCatalogTransitionRequest",
    "PublicAssayCatalogUpdateRequest",
    "QueryConditionTest",
    "QueryRuleDraft",
    "QueryRulePreview",
    "QueryRuleSampleSearch",
    "QueryRuleScope",
    "QueryRuleTransition",
    "QueryRuleUpdate",
    "SampleField",
    "SharedDiagnosisCreate",
    "SharedDiagnosisUpdate",
]
