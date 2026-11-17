# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Workspace reads and writes use distinct grants and the current sample scope."""

import pytest
from coyote.application.operations.samples import Sample
from coyote.domain.exceptions import AppError

pytest_plugins = ["api_test_support.sdk_runtime"]


def test_scoped_viewer_reads_workspace_without_gaining_mutation_permissions(sdk):
    sdk.grants.clear()
    sdk.grants.add("sample:view")
    catalog = sdk.services.catalog.return_value
    catalog.edit_context_payload.return_value = {"sample": sdk.sample, "comments": []}
    reference = Sample(sdk.runtime, sdk.services, "demo")
    assert reference.edit_context()["sample"]["name"] == "SYNTHETIC_001"
    with pytest.raises(AppError) as denied:
        reference.apply_genelists({"form_data": {"snvlists": []}})
    assert denied.value.status_code == 403
    assert sdk.services.catalog.call_count == 1


@pytest.mark.parametrize("grants", [set(), {"sample:edit:own"}])
def test_workspace_requires_explicit_read_permission(sdk, grants):
    sdk.grants.clear()
    sdk.grants.update(grants)
    with pytest.raises(AppError) as denied:
        Sample(sdk.runtime, sdk.services, "demo").edit_context()
    assert denied.value.status_code == 403
    sdk.services.catalog.assert_not_called()


def test_viewer_cannot_read_another_sample_environment(sdk):
    sdk.grants.clear()
    sdk.grants.add("sample:view")
    sdk.sample["environment"] = "production"
    with pytest.raises(AppError) as denied:
        Sample(sdk.runtime, sdk.services, "demo").edit_context()
    assert denied.value.status_code == 403
    sdk.services.catalog.assert_not_called()
