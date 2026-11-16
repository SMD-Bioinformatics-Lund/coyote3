#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Maintain standard Shields.io README badges from project metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[2]
START = "<!-- badges:start -->"
END = "<!-- badges:end -->"
PROJECTS = {"core": "core", "server": ".", "client": "clients/python"}
EXTERNAL_BADGE = re.compile(
    r"(?m)^.*(?:img\.shields\.io/|actions/workflows/[^\s)]+/badge\.svg)[^\n]*\n"
)


def badge(label: str, value: str, color: str = "4F46A5", logo: str | None = None) -> str:
    """Link an original Shields.io flat badge with its optional technology logo.

    Args:
        label: Left-side metadata name.
        value: Right-side metadata value.
        color: Six-digit hexadecimal value background, without a hash.
        logo: Shields.io logo identifier; omitted for badges without a logo.

    Returns:
        Markdown image with escaped static-badge fields and standard flat styling.

    Raises:
        ValueError: The requested color is not a hexadecimal RGB value.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        raise ValueError("Badge color must be a six-digit RGB value")
    fields = [
        quote(field.replace("-", "--").replace("_", "__"), safe="") for field in (label, value)
    ]
    query = {"style": "flat"}
    if logo:
        query.update(logo=logo, logoColor="white")
    alt = f"{label}: {value}".replace("[", "\\[").replace("]", "\\]")
    return f"![{alt}](https://img.shields.io/badge/{'-'.join(fields)}-{color}?{urlencode(query)})"


def readmes(root: Path) -> list[Path]:
    """Find maintained READMEs, including untracked work and excluding ignored output.

    Args:
        root: Working tree whose Git index and ignore rules define maintained files.

    Returns:
        Sorted existing README paths without build, dependency or cache directories.

    Raises:
        subprocess.CalledProcessError: Git cannot enumerate the working tree.
    """
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        text=True,
    )
    return sorted(
        {
            root / name
            for name in output.split("\0")
            if name
            and Path(name).name == "README.md"
            and (root / name).is_file()
            and not any(
                part in {"build", "dist", "site", "node_modules", ".pytest_cache"}
                or part.endswith(".egg-info")
                for part in Path(name).parts
            )
        }
    )


def generate(root: Path, *, check: bool = False) -> list[str]:
    """Generate standard README badge links, or identify drift without writing files.

    Args:
        root: Repository containing release and project metadata.
        check: Report outdated assets or Markdown without modifying them.

    Returns:
        Repository-relative files requiring updates.

    Raises:
        ValueError: The Dockerfile does not declare its default Python base image.
    """
    release = tomllib.loads((root / "release.toml").read_text())
    metadata = {
        name: tomllib.loads((root / directory / "pyproject.toml").read_text())["project"]
        for name, directory in PROJECTS.items()
    }
    frontend = json.loads((root / "frontend/package.json").read_text())
    runtime = re.search(
        r"PYTHON_BASE_IMAGE=python:([0-9.]+)", (root / "docker/Dockerfile").read_text()
    )
    if runtime is None:
        raise ValueError("docker/Dockerfile must declare the default Python base image")
    react = "React " + re.search(r"[0-9]+", frontend["dependencies"]["react"])[0]
    outputs: dict[Path, str] = {}

    logos = {
        "python-runtime": "python",
        "python": "python",
        "fastapi": "fastapi",
        "pydantic": "pydantic",
        "react": "react",
        "typescript": "typescript",
        "mongo": "mongodb",
        "celery": "celery",
        "redis": "redis",
        "compose": "docker",
        "vite": "vite",
        "tailwind": "tailwindcss",
        "pytest": "pytest",
        "vitest": "vitest",
        "node": "nodedotjs",
    }

    def image(key: str, label: str, value: str, color: str = "4F46A5") -> str:
        """Use the established technology logo and the original Shields.io renderer."""
        return badge(label, value, color, logos.get(key))

    version = image("application", "Coyote4", release["application_version"])
    license_badge = image("license", "License", metadata["core"]["license"], "2E7D32")
    scope = {
        name: image(name, "Scope", title)
        for name, title in {
            "synthetic": "Synthetic data",
            "tests": "Tests and fixtures",
            "migration": "Legacy migration tools",
            "catalogs": "Installation catalogs",
            "icons": "Icon assets",
            "branding": "Brand assets",
        }.items()
    }
    stack = [
        ("python-runtime", "Python", runtime[1], "3776AB"),
        ("fastapi", "API", "FastAPI", "009688"),
        ("pydantic", "Contracts", "Pydantic 2", "E92063"),
        (
            "react",
            "UI",
            react,
            "087EA4",
        ),
        ("typescript", "Language", "TypeScript", "3178C6"),
        ("mongo", "Database", "MongoDB", "47A248"),
        ("celery", "Tasks", "Celery", "37814A"),
        ("redis", "Broker & Cache", "Redis", "DC382D"),
        ("compose", "Deploy", "Docker Compose", "2496ED"),
        ("vite", "Build", "Vite", "646CFF"),
        ("tailwind", "Styles", "Tailwind CSS", "06B6D4"),
        ("mkdocs", "Documentation", "MkDocs", "624080"),
        ("pytest", "Backend tests", "pytest", "0A9EDC"),
        ("vitest", "Frontend tests", "Vitest", "6E9F18"),
        ("playwright", "Browser tests", "Playwright", "2EAD33"),
    ]
    stack_badges = [image(*entry) for entry in stack]
    domain_badges = [
        image(*entry)
        for entry in [
            ("domain", "Domain", "Clinical Genomics", "1F6FEB"),
            ("dna", "DNA", "Supported", "1E90FF"),
            ("rna", "RNA", "Supported", "20B2AA"),
            ("origin", "Analysis", "Somatic & Germline", "8B5E3C"),
            ("snapshots", "Reports", "Immutable Snapshots", "6B5B95"),
        ]
    ]
    security_badges = [
        image("rbac", "Security", "Casbin RBAC", "2E8B57"),
        image("audit", "Audit", "Enabled", "2E8B57"),
    ]

    component: dict[str, list[str]] = {}
    for directory, name in (
        ("core", "core"),
        ("api", "server"),
        ("adapters/mongo", "server"),
        ("clients/python", "client"),
    ):
        meta = metadata[name]
        component[directory] = [
            image("version", meta["name"], meta["version"]),
            image("python", "Python", meta["requires-python"], "3776AB"),
            image("license", "License", meta["license"], "2E7D32"),
        ]
    component["frontend"] = [
        image("version", "Coyote4", frontend["version"]),
        image("node", "Node", frontend["engines"]["node"], "339933"),
        image("react", "UI", react, "087EA4"),
        license_badge,
    ]
    for path in readmes(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text()
        body = re.sub(
            re.escape(START) + r".*?" + re.escape(END) + r"\n*", "", source, flags=re.DOTALL
        )
        body = EXTERNAL_BADGE.sub("", body)
        if relative == "README.md":
            body = re.sub(
                r"## Project Status and Technology\n.*?(?=## Start here)", "", body, flags=re.DOTALL
            )
            badges = [version, license_badge]
        elif relative.startswith("migrations_scripts/"):
            badges = [scope["migration"]]
        elif "bootstrap/demo_data/" in relative:
            badges = [scope["synthetic"]]
        elif relative.startswith("tests/"):
            badges = [scope["tests"]]
        elif "bootstrap/catalogs/" in relative:
            badges = [scope["catalogs"]]
        elif relative.startswith("frontend/public/icons/"):
            badges = [scope["icons"]]
        elif relative.startswith("frontend/public/logos/"):
            badges = [scope["branding"]]
        else:
            owner = next((name for name in component if relative.startswith(name + "/")), None)
            badges = component[owner] if owner else [version, license_badge]
        block = START + "\n" + " ".join(badges)
        if relative == "README.md":
            workflows = (
                "[Quality Checks](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml?query=branch%3Aapi) "
                "[Bootstrap and Ingest](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/bootstrap-and-ingest-check.yml?query=branch%3Aapi)"
            )
            block = START + "\n\n### Build and validation\n\n" + workflows + " "
            block += " ".join(badges)
            for title, group in (
                ("Core Stack", stack_badges),
                ("Domain & Capabilities", domain_badges),
                ("Security & Governance", security_badges),
            ):
                block += f"\n\n### {title}\n\n" + " ".join(group)
        block += "\n" + END
        heading, rest = body.split("\n", 1)
        outputs[path] = heading + "\n\n" + block + "\n\n" + rest.lstrip("\n")
    changed = []
    for path, content in outputs.items():
        if not path.exists() or path.read_text() != content:
            changed.append(path.relative_to(root).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
    return changed


def main() -> int:
    """Generate maintained badge files or reject stale README metadata in check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = generate(ROOT, check=args.check)
    if args.check and changed:
        print("Outdated badges: " + ", ".join(changed))
        return 1
    print(f"[ok] README badges {'checked' if args.check else 'generated'} ({len(changed)} updates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
