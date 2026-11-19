#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Generate Coyote application and package logos from one vector blueprint.

The canonical drawing is frontend/public/logos/coyote4-logo.svg. This blueprint
preserves its animal, ring, gradient and DNA. New lettering uses the bundled Lato
Bold Italic font, converted to paths with fontTools. Existing approved labels and
the joined version-4 artwork retain their outlines. No network access occurs.
Optional --raster requires CairoSVG and Pillow. Assets are never built at startup.
"""

from __future__ import annotations

import argparse
import base64
import re
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SVG = "http://www.w3.org/2000/svg"
NS = {"s": SVG}
ET.register_namespace("", SVG)
SOURCE = Path("frontend/public/logos/coyote4-logo.svg")
MAIN_COPIES = (
    "api/src/coyote_api/config/assets/coyote4-logo.svg",
    "docs/assets/coyote4-logo.svg",
)
FAVICONS = (
    "api/src/coyote_api/config/assets/coyote4-favicon.ico",
    "frontend/public/logos/coyote4-favicon.ico",
    "docs/assets/coyote4-favicon.ico",
)

TAIL = "M380.74 94.091H394.093L413.14 136.309C422.664 119.618 428.555 104.891 431.5 94.091H444.853C436.016 124.527 424.922 151.036 415.104 168.709C410.195 177.545 415.104 181.473 424.922 185.4C474.013 205.036 543.03 192.273 607.716 164.782C621 159 633 153 643 148C640 160 629 177 613.454 186.577C546.537 213.873 464.195 209.945 400.376 183.436C389.576 178.95 392.522 169.936 398.413 158.891L406.267 144.164L380.74 94.091Z"

# Repository destinations are separate from the generic lettering blueprint.
# New names need no registration when exporting to --output-dir.
PACKAGE_ASSETS = (
    "api/src/coyote_api/config/assets/coyote-api-logo.svg",
    "core/docs/assets/coyote-core-logo.svg",
    "services/relay/src/coyote_relay/assets/coyote-relay-logo.svg",
    "services/demo/src/coyote_demo/assets/coyote-demo-logo.svg",
    "services/hop/src/coyote_hop/assets/coyote-hop-logo.svg",
)
FONT = Path(__file__).resolve().parent / "fonts/lato-bold-italic.woff"


def write_svg(root: ET.Element, destination: Path) -> None:
    """Write a self-contained SVG, creating its destination directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)


def package_logo(source: ET.Element, spec: dict[str, str]) -> ET.Element:
    """Apply an approved package label to the shared animal and wordmark.

    Args:
        source: Canonical application logo.
        spec: Approved title, description, view-box width and outlined label.

    Returns:
        Independent SVG tree with compact README dimensions.
    """
    root = deepcopy(source)
    root.set("viewBox", f"22 10 {spec['width']} 255")
    root.set("width", "320")
    root.set("height", spec.get("height", f"{320 * 255 / float(spec['width']):.2f}"))
    root.find("s:title", NS).text = spec["title"]
    root.find("s:desc", NS).text = spec["description"]
    for element in root.iter():
        if element.get("id") == "y-four-gradient":
            element.set("id", "tail-gradient")
        if element.get("fill") == "url(#y-four-gradient)":
            element.set("fill", "url(#tail-gradient)")
        if element.get("id") == "continuous-y-four":
            element.set("id", "continuous-y-tail")
            element.set("d", TAIL)
        if element.get("id") == "dna-in-ligature":
            element.find("s:path", NS).set("d", TAIL)
    root.append(ET.fromstring(spec["outline"]))
    return root


def lettering(
    label: str, *, cap_height: float = 52.668, baseline: float = 153, origin: float = 642
) -> dict[str, str]:
    """Outline a label using fixed font metrics, kerning and actual glyph bounds.

    Args:
        label: Display text; unsupported glyphs cause an error, not substitution.
        cap_height: Capital letter height in the blueprint's SVG coordinate units.
        baseline: Baseline in the same coordinate system.
        origin: Left edge of the first glyph's visible ink.

    Returns:
        Package-logo specification with self-contained paths and measured width.
    """
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont

    with TTFont(FONT) as font:
        cmap = font.getBestCmap()
        missing = [character for character in label if ord(character) not in cmap]
        if missing:
            raise ValueError("The bundled font does not support every character in --name")
        glyphs = font.getGlyphSet()
        scale = cap_height / font["OS/2"].sCapHeight
        kerning = {}
        if "kern" in font:
            for table in font["kern"].kernTables:
                if table.version == 0 and table.coverage & 1:
                    kerning.update(table.kernTable)
        group = ET.Element(
            f"{{{SVG}}}g",
            {
                "id": "package-wordmark",
                "fill": "#705199",
                "aria-label": label,
            },
        )
        cursor, right, previous = origin, origin, None
        for index, character in enumerate(label):
            name = cmap[ord(character)]
            glyph = glyphs[name]
            bounds = BoundsPen(glyphs)
            glyph.draw(bounds)
            if index == 0 and bounds.bounds:
                cursor -= bounds.bounds[0] * scale
            cursor += kerning.get((previous, name), 0) * scale
            pen = SVGPathPen(glyphs)
            glyph.draw(pen)
            if pen.getCommands():
                ET.SubElement(
                    group,
                    f"{{{SVG}}}path",
                    {
                        "d": pen.getCommands(),
                        "transform": f"translate({cursor:.6f} {baseline}) scale({scale:.9f} {-scale:.9f})",
                    },
                )
            if bounds.bounds:
                right = max(right, cursor + bounds.bounds[2] * scale)
            cursor += glyph.width * scale
            previous = name
    return {
        "width": f"{right + 24 - 22:.3f}",
        "title": f"Coyote {label}",
        "description": f"Coyote {label}: howling coyote, paired ring, gradient lettering "
        "and DNA flourish. Label outlined from bundled Lato Bold Italic.",
        "outline": ET.tostring(group, encoding="unicode"),
    }


def named_logo(source: ET.Element, name: str) -> ET.Element:
    """Reuse approved label outlines when present; generate all other names."""
    for relative in PACKAGE_ASSETS:
        if not (ROOT / relative).is_file():
            continue
        existing = ET.parse(ROOT / relative).getroot()
        label = existing.find(".//*[@id='package-wordmark']")
        if label is not None and label.get("aria-label", "").casefold() == name.casefold():
            return package_logo(
                source,
                {
                    "width": existing.get("viewBox").split()[2],
                    "height": existing.get("height"),
                    "title": existing.find("s:title", NS).text,
                    "description": existing.find("s:desc", NS).text,
                    "outline": ET.tostring(label, encoding="unicode"),
                },
            )
    return package_logo(source, lettering(name))


def application_logo(source: ET.Element, version: int) -> ET.Element:
    """Preserve the joined four; use measured numeral outlines for other versions."""
    if version == 4:
        root = deepcopy(source)
        root.set("width", "320")
        root.set("height", "115")
        return root
    spec = lettering(str(version), cap_height=113, baseline=216, origin=620)
    spec["title"] = f"Coyote{version}"
    spec["description"] = f"Coyote{version} application logo with the shared animal, ring and DNA."
    return package_logo(source, spec)


def black_and_white(source: ET.Element) -> ET.Element:
    """Create black print artwork with white DNA, retaining luminance masks."""
    root = deepcopy(source)
    for child in root:
        if child.tag == f"{{{SVG}}}defs":
            continue  # Changing mask whites or fade stops would erase the artwork.
        dna = child.get("id") == "recognizable-dna-double-helix"
        for element in child.iter():
            for attribute in ("fill", "stroke"):
                if element.get(attribute) not in {None, "none"}:
                    element.set(attribute, "#ffffff" if dna else "#000000")
            element.attrib.pop("opacity", None)
    description = root.find("s:desc", NS)
    description.text = (description.text or "") + " Black-and-white edition for printing on white."
    return root


def emblem(source: ET.Element) -> ET.Element:
    """Extract the approved animal and ring with their clipping definitions."""
    root = ET.Element(
        f"{{{SVG}}}svg",
        {
            "viewBox": "25 23 224 224",
            "width": "512",
            "height": "512",
            "role": "img",
            "aria-labelledby": "emblem-title emblem-description",
        },
    )
    ET.SubElement(root, f"{{{SVG}}}title", {"id": "emblem-title"}).text = "Coyote emblem"
    ET.SubElement(
        root, f"{{{SVG}}}desc", {"id": "emblem-description"}
    ).text = "Howling coyote inside a purple and warm orange ring on a transparent background."
    definitions = ET.SubElement(root, f"{{{SVG}}}defs")
    definitions.append(deepcopy(source.find(".//*[@id='warm-fur-clip']")))
    for identifier in ("paired-purple-orange-ring", "original-howling-coyote"):
        root.append(deepcopy(source.find(f".//*[@id='{identifier}']")))
    return root


def export_raster(output: Path, animal: ET.Element, source: bytes) -> None:
    """Render transparent browser icons and the email logo.

    Args:
        output: Output tree with repository-relative asset paths.
        animal: Animal and ring SVG tree.
        source: Canonical application SVG bytes.

    Raises:
        ImportError: CairoSVG or Pillow is not installed for this optional export.
    """
    import cairosvg
    from PIL import Image

    png = cairosvg.svg2png(bytestring=ET.tostring(animal), output_width=512, output_height=512)
    icon = BytesIO()
    Image.open(BytesIO(png)).save(
        icon, format="ICO", sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)]
    )
    for relative in FAVICONS:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(icon.getvalue())
    target = output / "api/src/coyote_api/config/assets/coyote4-email-logo.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(cairosvg.svg2png(bytestring=source, output_width=1422, output_height=510))


def positive_version(value: str) -> int:
    """Accept a positive major version for the application wordmark."""
    if not value.isascii() or not value.isdecimal() or int(value) < 1:
        raise argparse.ArgumentTypeError("Version must be a positive major number, such as 4 or 5")
    return int(value)


def asset_path(path: str | Path, monochrome: bool) -> Path:
    """Keep print variants separate from the color assets."""
    path = Path(path)
    return path.with_stem(path.stem + "-bw") if monochrome else path


def main() -> None:
    """Export one logo, or explicitly refresh the registered application assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output-dir", type=Path, help="Directory for generated assets")
    destination.add_argument(
        "--write", action="store_true", help="Update registered repository assets"
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--version", type=positive_version, help="Application major version (default: 4)"
    )
    selection.add_argument("--name", help="Package label, such as hop, Relay or pyClient")
    selection.add_argument(
        "--all", action="store_true", help="Export the current registered asset set"
    )
    parser.add_argument(
        "--mono",
        action="store_true",
        help="Black artwork and white DNA for printing; adds -bw to filenames",
    )
    parser.add_argument(
        "--raster",
        action="store_true",
        help="Also render PNG; --all also renders ICO (requires CairoSVG/Pillow)",
    )
    args = parser.parse_args()
    version = args.version or 4
    name = args.name.strip() if args.name is not None else None
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") if name else None
    if args.name is not None and not slug:
        parser.error("--name must contain a letter or digit for the output filename")
    if args.write and version != 4:
        parser.error(
            "Use --output-dir for a future application version; current repository assets are v4"
        )
    registered = next(
        (
            path
            for path in PACKAGE_ASSETS
            if Path(path).name == f"coyote-{slug}-logo.svg" and (ROOT / path).is_file()
        ),
        None,
    )
    if args.write and name and not registered:
        parser.error("Use --output-dir for a new package; review the logo before integrating it")
    if args.all and args.mono and args.raster:
        parser.error("Use a single logo selection for monochrome PNG output")
    try:
        if args.raster:
            import cairosvg

            if args.all:
                from PIL import Image  # noqa: F401
        source = ET.parse(ROOT / SOURCE).getroot()
        root = named_logo(source, name) if name else application_logo(source, version)
    except (ImportError, ValueError) as exc:
        parser.error(str(exc))
    if args.mono:
        root = black_and_white(root)
    output = ROOT if args.write else args.output_dir.resolve()
    if args.all:
        for relative in MAIN_COPIES:
            logo = deepcopy(root)
            current = ET.parse(ROOT / relative).getroot()
            for dimension in ("width", "height"):
                logo.set(dimension, current.get(dimension))
            write_svg(logo, output / asset_path(relative, args.mono))
        for relative in PACKAGE_ASSETS:
            if not (ROOT / relative).is_file():
                continue  # Optional package sources may live outside this checkout.
            existing = ET.parse(ROOT / relative).getroot()
            label = existing.find(".//*[@id='package-wordmark']").get("aria-label")
            logo = named_logo(source, label)
            if args.mono:
                logo = black_and_white(logo)
            write_svg(logo, output / asset_path(relative, args.mono))
        animal = emblem(source)
        if args.mono:
            animal = black_and_white(animal)
        write_svg(
            animal,
            output / asset_path("frontend/public/logos/coyote4-emblem.svg", args.mono),
        )
        if args.raster:
            export_raster(output, animal, ET.tostring(source))
        if not args.mono:
            error_path = Path("deploy/compose/nginx/error-pages/unavailable.html")
            page = (ROOT / error_path).read_text()
            page = re.sub(
                r"data:image/svg\+xml;base64,[A-Za-z0-9+/=]+",
                "data:image/svg+xml;base64," + base64.b64encode(ET.tostring(source)).decode(),
                page,
            )
            icon = output / FAVICONS[0] if args.raster else ROOT / FAVICONS[0]
            page = re.sub(
                r"data:image/x-icon;base64,[A-Za-z0-9+/=]+",
                "data:image/x-icon;base64," + base64.b64encode(icon.read_bytes()).decode(),
                page,
            )
            (output / error_path).parent.mkdir(parents=True, exist_ok=True)
            (output / error_path).write_text(page)
    else:
        filename = f"coyote-{slug}-logo.svg" if name else f"coyote{version}-logo.svg"
        targets = (
            ([registered] if name else [str(SOURCE), *MAIN_COPIES]) if args.write else [filename]
        )
        for relative in targets:
            target = output / asset_path(relative, args.mono)
            logo = deepcopy(root)
            if args.write:
                current = ET.parse(ROOT / relative).getroot()
                for dimension in ("width", "height"):
                    logo.set(dimension, current.get(dimension))
            write_svg(logo, target)
            if args.raster:
                target.with_suffix(".png").write_bytes(
                    cairosvg.svg2png(bytestring=ET.tostring(logo), output_width=1280)
                )
    print("Brand assets exported; review the output before committing.")


if __name__ == "__main__":
    main()
