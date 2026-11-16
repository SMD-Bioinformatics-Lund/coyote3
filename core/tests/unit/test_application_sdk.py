import subprocess
import sys

import pytest
from coyote.application.operations.models import TierChange


def test_group_deactivation_rejects_assignment_intent():
    with pytest.raises(ValueError, match="Group deactivation requires apply=false"):
        TierChange(
            resource_type="small_variant",
            resource_ids=["finding-1"],
            tier=2,
            apply=True,
            deactivation_scope="group",
        )


def test_importing_supported_sdk_does_not_load_server_or_storage_runtime():
    script = "\nimport importlib.abc\nimport sys\nclass Block(importlib.abc.MetaPathFinder):\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname.split('.')[0] in {'fastapi', 'starlette', 'bson', 'pymongo', 'celery', 'redis'}:\n            raise AssertionError(fullname)\n        if fullname.startswith(('coyote_api.app', 'coyote_api.infra', 'coyote_api.security', 'coyote_api.interfaces', 'coyote_pyclient')) and not fullname.startswith('coyote.application'):\n            raise AssertionError(fullname)\nsys.meta_path.insert(0, Block())\nfrom coyote.application.operations import CoyoteApplication, AnalysisQuery, TierChange\nfrom coyote.application.operations.inputs import QueryRuleDraft, ClinicalRuleTransition\nassert AnalysisQuery().parameters == {}\n"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
