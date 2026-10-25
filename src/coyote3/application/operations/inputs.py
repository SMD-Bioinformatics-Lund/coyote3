"""Supported authored-content models shared with existing HTTP validation contracts.

These exports retain the authoritative validators and null/omission semantics.
They do not depend on persistence implementations. Their source modules remain
in coyote3.contracts while the SDK is distributed inside the application repository.
"""

from coyote3.contracts.auth import (
    ApiPasswordChangeRequest,
    ApiPasswordResetConfirmRequest,
    ApiProfileUpdateRequest,
    ApiUiSettingsUpdateRequest,
)
from coyote3.contracts.configuration_profiles import (
    ConfigurationProfileDraft,
    ConfigurationPromotionRequest,
    ConfigurationScope,
    ProfilePublication,
)
from coyote3.contracts.notifications import NotificationBroadcastRequest
from coyote3.contracts.public import (
    PublicAssayCatalogImportRequest,
    PublicAssayCatalogTransitionRequest,
    PublicAssayCatalogUpdateRequest,
)
from coyote3.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
    SampleField,
)
from coyote3.contracts.samples import ConfigurationApplyRequest
from coyote3.contracts.schemas.assay_groups import AssayGroupCreate, AssayGroupStatus
from coyote3.contracts.schemas.assay_setup import (
    AssaySetupAction,
    AssaySetupContent,
    AssaySetupUpdate,
)
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleTransition,
)
from coyote3.contracts.schemas.diagnoses import (
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)
from coyote3.contracts.schemas.query_rules import (
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
    "AssaySetupAction",
    "AssaySetupContent",
    "AssaySetupUpdate",
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
