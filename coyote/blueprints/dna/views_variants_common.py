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

"""Shared helpers for DNA variant list/detail routes."""

from coyote.errors.exceptions import AppError
from coyote.integrations.api.api_client import ApiRequestError


def raise_api_page_error(sample_id: str, page: str, exc: ApiRequestError) -> None:
    raise AppError(
        status_code=exc.status_code or 502,
        message=f"Failed to load {page}.",
        details=f"Sample {sample_id}: {exc}",
    )
