# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Portable record identities, independent of provider formats and driver classes."""


class RecordIdentity(str):
    """String identity distinguished from free text for host-owned serialization.

    Adapters select the identity format. The core imposes no hexadecimal, UUID,
    integer-key or database-driver requirement. Keeping identity semantics through
    record copies lets a host preserve its immutable resource digest encoding.
    """
