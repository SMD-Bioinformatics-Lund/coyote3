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

    After calling `init_util()`, instances of various utility classes (DNAUtility, CommonUtility, etc.)
    are available as attributes of this class.
    """

    def __init__(self):
        pass

    def init_util(self) -> None:
        """
        Initializes and attaches all utility class instances as attributes of this Utility object.

        After calling this method, each utility instance is accessible as an attribute:
            self.dna, self.common, self.report, self.main, self.rna,
            self.profile, self.dashboard, self.admin, self.coverage
        """
        from coyote.blueprints.dna.util import DNAUtility
        from coyote.util.common_utility import CommonUtility
        from coyote.util.report.report_util import ReportUtility
        from coyote.blueprints.home.util import HomeUtility
        from coyote.blueprints.rna.util import RNAUtility
        from coyote.blueprints.userprofile.util import ProfileUtility
        from coyote.blueprints.dashboard.util import DashBoardUtility
        from coyote.blueprints.admin.util import AdminUtility
        from coyote.blueprints.coverage.util import CoverageUtility
        from coyote.blueprints.common.util import BPCommonUtility

        self.dna = DNAUtility()
        self.common = CommonUtility()
        self.main = HomeUtility()
        self.rna = RNAUtility()
        self.profile = ProfileUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
        self.coverage = CoverageUtility()
        self.report = ReportUtility()
        self.bpcommon = BPCommonUtility()
