# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""API contract namespace.

Import response models from their explicit module, for example
``coyote.contracts.dna`` or ``coyote.contracts.schemas.samples``. Keeping this
package initializer dependency-free prevents schema/domain import cycles during
CLI tools, migrations, and focused tests.
"""
