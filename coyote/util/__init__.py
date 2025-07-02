class Utility:
    """
    This class is used to store all the utility classes that are used in the
    """

    def __init__(self):
        pass

    def init_util(self):
        from coyote.blueprints.admin.util import AdminUtility
        from coyote.blueprints.coverage.util import CoverageUtility
        from coyote.blueprints.dashboard.util import DashBoardUtility
        from coyote.blueprints.dna.util import DNAUtility
        from coyote.blueprints.home.util import HomeUtility
        from coyote.blueprints.rna.util import RNAUtility
        from coyote.blueprints.userprofile.util import ProfileUtility
        from coyote.util.common_utility import CommonUtility
        from coyote.util.report.report_util import ReportUtility

        self.dna = DNAUtility()
        self.common = CommonUtility()
        self.main = HomeUtility()
        self.rna = RNAUtility()
        self.profile = ProfileUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
        self.coverage = CoverageUtility()
        self.report = ReportUtility()
