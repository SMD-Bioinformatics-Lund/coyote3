# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Database-document contract namespace.

Import document models from their explicit schema module. Registry helpers are
also imported from ``coyote.contracts.schemas.registry``. This initializer remains
dependency-free so a narrow schema import cannot load the complete contract
registry and create a domain/schema cycle.
"""
