
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
