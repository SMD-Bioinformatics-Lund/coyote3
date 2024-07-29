class Utility:
    """
    This class is used to store all the utility classes that are used in the
    """

    def __init__(self):
        self.variant = None
        self.common = None

    def init_util(self):
        from coyote.blueprints.dna.util import DNAUtility
        from coyote.util.common_utility import CommonUtility
        from coyote.blueprints.home.util import HomeUtility
        from coyote.blueprints.fusions.util import FusionUtility
        from coyote.blueprints.userprofile.util import ProfileUtility
        from coyote.blueprints.dashboard.util import DashBoardUtility

        self.dna = DNAUtility()
        self.common = CommonUtility()
        self.main = HomeUtility()
        self.fusion = FusionUtility()
        self.rna = FusionUtility()
        self.profile = ProfileUtility()
        self.dashboard = DashBoardUtility()
