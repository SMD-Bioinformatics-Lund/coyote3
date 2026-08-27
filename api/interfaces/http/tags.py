"""OpenAPI tag taxonomy for the Coyote3 HTTP API."""

from __future__ import annotations

TAG_SYSTEM = "System & Health"
TAG_AUTH = "Authentication"
TAG_DASHBOARD = "Dashboard"
TAG_NOTIFICATIONS = "Notifications"
TAG_PUBLIC = "Public Catalog"

TAG_CLINICAL_SAMPLES = "Clinical Samples"
TAG_DNA_VARIANTS = "DNA Small Variants"
TAG_DNA_CNV = "DNA Copy Number"
TAG_RNA_FUSIONS = "RNA Fusions"
TAG_STRUCTURAL_VARIANTS = "Structural Variants"
TAG_COVERAGE = "Coverage"
TAG_BIOMARKERS = "Biomarkers"
TAG_REPORTING = "Reporting"

TAG_KNOWLEDGEBASE = "Knowledgebases & Annotations"

TAG_ADMIN_OPERATIONS = "Admin: Operations"
TAG_ADMIN_ASSAYS = "Admin: Assays & Gene Lists"
TAG_ADMIN_USERS = "Admin: Users"
TAG_ADMIN_ACCESS = "Admin: Roles & Permissions"
TAG_INTERNAL = "Internal Ingest & Maintenance"

OPENAPI_TAGS = [
    {
        "name": TAG_AUTH,
        "description": "Session creation, logout, current-user context, and password workflows.",
    },
    {
        "name": TAG_DASHBOARD,
        "description": "Operational, workload, assay, and review summary metrics.",
    },
    {
        "name": TAG_NOTIFICATIONS,
        "description": "Administrative notification broadcasts to selected users, roles, or all active users.",
    },
    {
        "name": TAG_CLINICAL_SAMPLES,
        "description": "Sample list, sample context, comments, file/QC metadata, and settings.",
    },
    {
        "name": TAG_DNA_VARIANTS,
        "description": "SNV and small indel review, filtering, exports, actions, and lookups.",
    },
    {
        "name": TAG_DNA_CNV,
        "description": "Copy-number variant lists, detail contexts, and CNV-specific actions.",
    },
    {
        "name": TAG_RNA_FUSIONS,
        "description": "RNA fusion findings, selected-call state, comments, and exports.",
    },
    {
        "name": TAG_STRUCTURAL_VARIANTS,
        "description": "DNA translocation and structural breakpoint review workflows.",
    },
    {
        "name": TAG_COVERAGE,
        "description": "Coverage plots, gene/exon/probe views, and coverage blacklist management.",
    },
    {
        "name": TAG_BIOMARKERS,
        "description": "Sample biomarker summaries and molecular context payloads.",
    },
    {
        "name": TAG_REPORTING,
        "description": "Report preview, snapshot, save, HTML/PDF artifact, and context endpoints.",
    },
    {
        "name": TAG_KNOWLEDGEBASE,
        "description": (
            "Gene information, tiered variant search, annotations, external knowledgebases "
            "(OncoKB, ClinPGx, CIViC, IARC TP53, BRCA Exchange), and variant evidence."
        ),
    },
    {
        "name": TAG_PUBLIC,
        "description": "Unauthenticated public catalog, matrix, gene, and assay reference endpoints.",
    },
    {
        "name": TAG_ADMIN_OPERATIONS,
        "description": "Audit events, schema diagnostics, runtime controls, and maintenance operations.",
    },
    {
        "name": TAG_ADMIN_ASSAYS,
        "description": "ASP, ASPC, ISGL, and admin sample resource configuration.",
    },
    {
        "name": TAG_ADMIN_USERS,
        "description": "User-account management, invites, provider state, and profile metadata.",
    },
    {
        "name": TAG_ADMIN_ACCESS,
        "description": "Role and permission policy management.",
    },
]

OPENAPI_TAG_NAMES = tuple(tag["name"] for tag in OPENAPI_TAGS)

__all__ = [
    "OPENAPI_TAGS",
    "OPENAPI_TAG_NAMES",
    "TAG_ADMIN_ACCESS",
    "TAG_ADMIN_ASSAYS",
    "TAG_ADMIN_OPERATIONS",
    "TAG_ADMIN_USERS",
    "TAG_AUTH",
    "TAG_BIOMARKERS",
    "TAG_CLINICAL_SAMPLES",
    "TAG_COVERAGE",
    "TAG_DASHBOARD",
    "TAG_DNA_CNV",
    "TAG_DNA_VARIANTS",
    "TAG_INTERNAL",
    "TAG_KNOWLEDGEBASE",
    "TAG_NOTIFICATIONS",
    "TAG_PUBLIC",
    "TAG_REPORTING",
    "TAG_RNA_FUSIONS",
    "TAG_STRUCTURAL_VARIANTS",
    "TAG_SYSTEM",
]
