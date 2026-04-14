"""
Coyote3 Utility Module
=====================================

This module provides utility classes and helper methods for common operations
across the Coyote3 project, such as configuration management, data formatting,
serialization, and reporting. These utilities are designed to support genomic
data analysis, interpretation, and clinical diagnostics workflows.
"""


class Utility:
    """
    Utility class that aggregates and initializes all utility classes used across the Coyote3 project.

    After calling `init_util()`, instances of shared utility classes (for example `CommonUtility`)
    are available as attributes of this class.
    """

    def __init__(self):
        """__init__."""
        pass

    def init_util(self) -> None:
        """
        Initializes and attaches all utility class instances as attributes of this Utility object.

        After calling this method, each utility instance is accessible as an attribute:
            self.common, self.report, self.main,
            self.dashboard, self.admin, self.login
        """
        from coyote.blueprints.dashboard.util import DashBoardUtility
        from coyote.util.admin_utility import AdminUtility
        from coyote.util.common_utility import CommonUtility

        self.common = CommonUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
