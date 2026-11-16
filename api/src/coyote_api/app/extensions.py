# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Discover installed API extensions without importing optional distributions by name."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import entry_points

from fastapi import APIRouter
from fastapi.routing import APIRoute

API_ROUTER_ENTRY_POINT = "coyote.api.routers"


@dataclass(frozen=True, slots=True)
class ApiExtensions:
    """Retain the installed extension names and their validated router instances."""

    names: tuple[str, ...]
    routers: tuple[APIRouter, ...]


def _route_keys(router: APIRouter) -> set[tuple[str, str]]:
    """Normalize route parameter names when detecting overlapping HTTP operations.

    Args:
        router: Router whose concrete path and method registrations are inspected.

    Returns:
        HTTP method and parameter-normalized path pairs.
    """
    return {
        (method, re.sub(r"\{[^}]+\}", "{}", route.path_format))
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def load_api_extensions(existing: Iterable[APIRouter]) -> ApiExtensions:
    """Load installed router factories and reject conflicting or invalid registrations.

    Args:
        existing: Built-in routers already selected by the API host.

    Returns:
        Installed entry-point names and routers, in deterministic name order.
        No installed or enabled entry points produces an empty extension set.

    Raises:
        RuntimeError: An installed extension cannot load, duplicates a name or
            HTTP operation, or declares routes outside the versioned API.

    Notes:
        Installing an extension is a trusted code deployment. Extension routes
        run behind the same host middleware and retain their own authorization
        dependencies. A broken installation prevents startup; it is not silently
        treated as an absent optional package. A factory may explicitly return
        None to disable an installed extension through its reviewed configuration.
    """
    occupied = set().union(*(_route_keys(router) for router in existing))
    names: list[str] = []
    seen: set[str] = set()
    routers: list[APIRouter] = []
    for entry in sorted(entry_points(group=API_ROUTER_ENTRY_POINT), key=lambda item: item.name):
        if entry.name in seen:
            raise RuntimeError(f"Duplicate API extension name: {entry.name}")
        seen.add(entry.name)
        try:
            factory = entry.load()
            selected = factory()
            if selected is None:
                continue
            candidates = tuple(selected)
        except Exception as exc:
            raise RuntimeError(f"Cannot load installed API extension: {entry.name}") from exc
        if not candidates or any(not isinstance(router, APIRouter) for router in candidates):
            raise RuntimeError(f"API extension {entry.name} must provide APIRouter instances")
        for router in candidates:
            local: set[tuple[str, str]] = set()
            for route in router.routes:
                if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
                    raise RuntimeError(f"API extension {entry.name} declares a non-versioned route")
                keys = {
                    (method, re.sub(r"\{[^}]+\}", "{}", route.path_format))
                    for method in route.methods
                }
                if keys & (occupied | local):
                    raise RuntimeError(
                        f"API extension {entry.name} conflicts with an existing HTTP operation"
                    )
                local.update(keys)
            occupied.update(local)
            routers.append(router)
        names.append(entry.name)
    return ApiExtensions(names=tuple(names), routers=tuple(routers))
