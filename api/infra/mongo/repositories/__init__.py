"""Collection-scoped MongoDB handlers."""

from api.infra.mongo.repositories.annotations import AnnotationsRepository
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.bam_records import BamServiceRepository
from api.infra.mongo.repositories.biomarkers import BiomarkerRepository
from api.infra.mongo.repositories.blacklist import BlacklistRepository
from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.coverage import CoverageRepository
from api.infra.mongo.repositories.expression import ExpressionRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from api.infra.mongo.repositories.grouped_coverage import GroupCoverageRepository
from api.infra.mongo.repositories.permissions import PermissionsRepository
from api.infra.mongo.repositories.reported_variants import ReportedVariantsRepository
from api.infra.mongo.repositories.reports import ReportRepository
from api.infra.mongo.repositories.rna_classification import RNAClassificationRepository
from api.infra.mongo.repositories.rna_expression import RNAExpressionRepository
from api.infra.mongo.repositories.rna_quality import RNAQCRepository
from api.infra.mongo.repositories.roles import RolesRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.translocations import TranslocsRepository
from api.infra.mongo.repositories.users import UsersRepository
from api.infra.mongo.repositories.variants import VariantsRepository
from api.infra.mongo.repositories.vep_metadata import VEPMetaRepository

__all__ = [
    "ASPConfigRepository",
    "ASPRepository",
    "AnnotationsRepository",
    "BamServiceRepository",
    "BiomarkerRepository",
    "BlacklistRepository",
    "CNVsRepository",
    "CoverageRepository",
    "ExpressionRepository",
    "FusionsRepository",
    "GroupCoverageRepository",
    "ISGLRepository",
    "PermissionsRepository",
    "RNAClassificationRepository",
    "RNAExpressionRepository",
    "RNAQCRepository",
    "ReportedVariantsRepository",
    "ReportRepository",
    "RolesRepository",
    "SampleRepository",
    "TranslocsRepository",
    "UsersRepository",
    "VEPMetaRepository",
    "VariantsRepository",
]
