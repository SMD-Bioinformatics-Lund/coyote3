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

"""
Coyote3 Shared Module
=====================================

This module provides shared extension objects used by the Flask web app,
primarily login/session handling and template/view utilities.

It serves as a central point for initializing and managing these
shared resources.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from flask_login import LoginManager
from coyote.util import Utility

# -------------------------------------------------------------------------
# Shared Variables and Objects
# -------------------------------------------------------------------------
login_manager = LoginManager()
util = Utility()
