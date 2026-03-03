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

"""Shared schema validation constants for admin config flows."""

REQUIRED_SCHEMA_KEYS = [
    "_id",
    "schema_name",
    "schema_type",
    "description",
    "is_active",
    "version",
    "sections",
    "fields",
    "subschemas",
]

