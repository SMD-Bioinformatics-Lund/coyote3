"""API-owned extension singletons."""

from api.db.mongo.main import MongoAdapter
from api.infra.external.ldap import LdapManager
from api.utils.admin_utility import AdminUtility
from api.utils.common_utility import CommonUtility
from api.utils.dashboard_utility import DashBoardUtility
from api.utils.report.report_util import ReportUtility


class Utility:
    """Utility container used by API routes/services."""

    def init_util(self) -> None:
        """Handle init util.

        Returns:
            None.
        """
        self.common = CommonUtility()
        self.dashboard = DashBoardUtility()
        self.admin = AdminUtility()
        self.report = ReportUtility()


class _LazyHandlerProxy:
    """Minimal handler proxy that supports monkeypatching before runtime init."""

    def __getattr__(self, _name):
        """Handle __getattr__.

        Args:
                _name:  name.

        Returns:
                The __getattr__ result.
        """
        def _missing(*_args, **_kwargs):
            """Handle  missing.

            Args:
                    *_args:  args. Additional positional arguments.
                    **_kwargs:  kwargs. Additional keyword arguments.

            Returns:
                    The  missing result.
            """
            raise RuntimeError("Mongo handler used before API runtime initialization")

        return _missing


def _seed_adapter_slots(adapter: MongoAdapter) -> MongoAdapter:
    """Expose stable handler attributes for tests and lazy runtime bootstrap."""
    handler_names = (
        "annotation_handler",
        "aspc_handler",
        "asp_handler",
        "bam_service_handler",
        "biomarker_handler",
        "blacklist_handler",
        "brca_handler",
        "civic_handler",
        "cnv_handler",
        "cosmic_handler",
        "coverage2_handler",
        "coverage_handler",
        "expression_handler",
        "fusion_handler",
        "groupcov_handler",
        "hgnc_handler",
        "iarc_tp53_handler",
        "isgl_handler",
        "oncokb_handler",
        "permissions_handler",
        "reported_variants_handler",
        "rna_classification_handler",
        "rna_expression_handler",
        "rna_qc_handler",
        "roles_handler",
        "sample_handler",
        "schema_handler",
        "transloc_handler",
        "user_handler",
        "variant_handler",
        "vep_meta_handler",
    )
    for name in handler_names:
        if not hasattr(adapter, name):
            setattr(adapter, name, _LazyHandlerProxy())
    return adapter


store = _seed_adapter_slots(MongoAdapter())
ldap_manager = LdapManager()
util = Utility()
