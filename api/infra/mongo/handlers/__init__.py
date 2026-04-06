"""Collection-scoped MongoDB handlers."""

from api.infra.mongo.handlers.annotations import AnnotationsHandler
from api.infra.mongo.handlers.assay_configurations import ASPConfigHandler
from api.infra.mongo.handlers.assay_panels import ASPHandler
from api.infra.mongo.handlers.bam_records import BamServiceHandler
from api.infra.mongo.handlers.biomarkers import BiomarkerHandler
from api.infra.mongo.handlers.blacklist import BlacklistHandler
from api.infra.mongo.handlers.copy_number_variants import CNVsHandler
from api.infra.mongo.handlers.coverage import CoverageHandler
from api.infra.mongo.handlers.expression import ExpressionHandler
from api.infra.mongo.handlers.fusions import FusionsHandler
from api.infra.mongo.handlers.gene_lists import ISGLHandler
from api.infra.mongo.handlers.grouped_coverage import GroupCoverageHandler
from api.infra.mongo.handlers.permissions import PermissionsHandler
from api.infra.mongo.handlers.query_profiles import QueryProfilesHandler
from api.infra.mongo.handlers.reported_variants import ReportedVariantsHandler
from api.infra.mongo.handlers.reports import ReportHandler
from api.infra.mongo.handlers.rna_classification import RNAClassificationHandler
from api.infra.mongo.handlers.rna_expression import RNAExpressionHandler
from api.infra.mongo.handlers.rna_quality import RNAQCHandler
from api.infra.mongo.handlers.roles import RolesHandler
from api.infra.mongo.handlers.samples import SampleHandler
from api.infra.mongo.handlers.translocations import TranslocsHandler
from api.infra.mongo.handlers.users import UsersHandler
from api.infra.mongo.handlers.variants import VariantsHandler
from api.infra.mongo.handlers.vep_metadata import VEPMetaHandler

__all__ = [
    "ASPConfigHandler",
    "ASPHandler",
    "AnnotationsHandler",
    "BamServiceHandler",
    "BiomarkerHandler",
    "BlacklistHandler",
    "CNVsHandler",
    "CoverageHandler",
    "ExpressionHandler",
    "FusionsHandler",
    "GroupCoverageHandler",
    "ISGLHandler",
    "PermissionsHandler",
    "QueryProfilesHandler",
    "RNAClassificationHandler",
    "RNAExpressionHandler",
    "RNAQCHandler",
    "ReportedVariantsHandler",
    "ReportHandler",
    "RolesHandler",
    "SampleHandler",
    "TranslocsHandler",
    "UsersHandler",
    "VEPMetaHandler",
    "VariantsHandler",
]
