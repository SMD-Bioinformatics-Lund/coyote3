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

"""Facade module for DNA variant list/detail/plot routes."""

from coyote.blueprints.dna import views_variants_detail  # noqa: F401
from coyote.blueprints.dna import views_variants_list  # noqa: F401
from coyote.blueprints.dna import views_variants_plot  # noqa: F401
