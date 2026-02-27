"""API-owned extension singletons."""

from api.db.mongo import MongoAdapter
from api.services.ldap import LdapManager
from api.utils.admin_utility import AdminUtility
from api.utils.common_utility import CommonUtility
from api.utils.dashboard_utility import DashBoardUtility
from api.utils.report.report_util import ReportUtility


class Utility:
    """Utility container used by API routes/services."""

    def init_util(self) -> None:
        self.common = CommonUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
        self.report = ReportUtility()


store = MongoAdapter()
ldap_manager = LdapManager()
util = Utility()

