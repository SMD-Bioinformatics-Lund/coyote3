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

"""Facade module for common blueprint routes."""

from coyote.blueprints.common import views_genes  # noqa: F401
from coyote.blueprints.common import views_sample_comments  # noqa: F401
from coyote.blueprints.common import views_tiered_variants  # noqa: F401
