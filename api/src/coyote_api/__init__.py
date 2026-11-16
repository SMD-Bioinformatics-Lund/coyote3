# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP application and workers consuming the independent Coyote core and adapter."""

from coyote_api.config.bootstrap import configure_center_from_environment

configure_center_from_environment()
