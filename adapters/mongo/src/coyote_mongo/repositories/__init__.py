# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Collection-scoped MongoDB handlers."""

from coyote_mongo.repositories.annotations import AnnotationsRepository
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from coyote_mongo.repositories.assay_panels import ASPRepository
from coyote_mongo.repositories.bam_records import BamServiceRepository
from coyote_mongo.repositories.biomarkers import BiomarkerRepository
from coyote_mongo.repositories.blacklist import BlacklistRepository
from coyote_mongo.repositories.copy_number_variants import CNVsRepository
from coyote_mongo.repositories.d4_coverage import D4CoverageRepository
from coyote_mongo.repositories.d4_coverage_blacklist import D4CoverageBlacklistRepository
from coyote_mongo.repositories.expression import ExpressionRepository
from coyote_mongo.repositories.fusions import FusionsRepository
from coyote_mongo.repositories.gene_lists import ISGLRepository
from coyote_mongo.repositories.permissions import PermissionsRepository
from coyote_mongo.repositories.reported_variants import ReportedVariantsRepository
from coyote_mongo.repositories.reports import ReportRepository
from coyote_mongo.repositories.rna_classification import RNAClassificationRepository
from coyote_mongo.repositories.rna_expression import RNAExpressionRepository
from coyote_mongo.repositories.rna_quality import RNAQCRepository
from coyote_mongo.repositories.roles import RolesRepository
from coyote_mongo.repositories.samples import SampleRepository
from coyote_mongo.repositories.translocations import TranslocsRepository
from coyote_mongo.repositories.users import UsersRepository
from coyote_mongo.repositories.variants import VariantsRepository
from coyote_mongo.repositories.vep_metadata import VEPMetaRepository

__all__ = [
    "ASPConfigRepository",
    "ASPRepository",
    "AnnotationsRepository",
    "BamServiceRepository",
    "BiomarkerRepository",
    "BlacklistRepository",
    "CNVsRepository",
    "D4CoverageRepository",
    "ExpressionRepository",
    "FusionsRepository",
    "D4CoverageBlacklistRepository",
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
