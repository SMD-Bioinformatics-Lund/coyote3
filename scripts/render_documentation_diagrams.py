"""Render documentation SVGs from reviewed card and relationship definitions.

Run from the repository root. The renderer uses only the Python standard library;
SVG output embeds its typography and palette for GitHub and MkDocs portability.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import textwrap
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/docs/diagrams.json"
DESTINATION = ROOT / "docs/assets/diagrams"
STEP = 20
WIDTH = 1360
CARD_WIDTH = 320
Point = tuple[int, int]
Box = tuple[int, int, int, int]


def wrap(value: str, width: int, size: int = 16, max_pixels: int | None = None) -> list[str]:
    """Wrap labels without dropping words or truncating identifiers.

    Args:
        value: Plain text to wrap; whitespace is normalized by textwrap.
        width: Initial maximum characters per line, reduced when glyphs need more room.
        size: Font size in SVG pixels for the width estimate.
        max_pixels: Available text width; defaults to 280 for compact card labels.

    Returns:
        Ordered text lines, including split identifiers when a single token is too long.
    """
    lines = textwrap.wrap(value, width=width, break_long_words=True, break_on_hyphens=False)
    limit = max_pixels if max_pixels is not None else 280 if width <= 34 else math.inf
    while width > 4 and any(text_width(line, size) > limit for line in lines):
        width -= 1
        lines = textwrap.wrap(value, width=width, break_long_words=True, break_on_hyphens=False)
    return lines


def text_width(value: str, size: int) -> float:
    """Estimate Arial text width for card wrapping and label padding.

    Args:
        value: A single line of text.
        size: Font size in SVG pixels.

    Returns:
        Approximate width in pixels. Browser inspection remains necessary for exact bounds.
    """
    narrow = set("ilI.,:;'!| ")
    wide = set("MWmw@→↔")
    return size * sum(
        0.3 if char in narrow else 0.9 if char in wide else 0.68 if char.isupper() else 0.56
        for char in value
    )


def inside(point: Point, box: Box, margin: int = 0) -> bool:
    """Return whether a point touches a rectangle expanded by a given margin.

    Args:
        point: Coordinates in the SVG routing grid.
        box: Rectangle expressed as x, y, width, and height.
        margin: Additional clearance in SVG pixels; zero includes the rectangle boundary.

    Returns:
        True when the point lies inside or on the expanded boundary.
    """
    x, y, width, height = box
    return (
        x - margin <= point[0] <= x + width + margin
        and y - margin <= point[1] <= y + height + margin
    )


def intersects(first: Box, second: Box, margin: int = 0) -> bool:
    """Check rectangle overlap, optionally reserving clearance around the first.

    Args:
        first: Candidate label rectangle as x, y, width, and height.
        second: Existing card or label rectangle in the same coordinates.
        margin: Required clearance around the candidate, in SVG pixels.

    Returns:
        True for overlapping interiors; touching unexpanded edges do not overlap.
    """
    x, y, width, height = first
    a, b, w, h = second
    return (
        x - margin < a + w
        and x + width + margin > a
        and y - margin < b + h
        and y + height + margin > b
    )


def port(box: Box, side: str) -> tuple[Point, Point]:
    """Return a card boundary attachment and its outside routing-grid point.

    Args:
        box: Card rectangle as x, y, width, and height.
        side: One of left, right, top, or bottom.

    Returns:
        Boundary point followed by the point 60 SVG pixels outside that boundary.

    Raises:
        KeyError: If the side is not supported.
    """
    x, y, width, height = box
    cx, cy = x + width // 2, y + (height // 40) * 20
    attachments = {
        "left": ((x, cy), (x - 60, cy)),
        "right": ((x + width, cy), (x + width + 60, cy)),
        "top": ((cx, y), (cx, y - 60)),
        "bottom": ((cx, y + height), (cx, y + height + 60)),
    }
    return attachments[side]


def route(
    start: Point, end: Point, boxes: list[Box], used: set[Point], bottom: int, top: int
) -> tuple[float, list[Point]]:
    """Find an orthogonal path around cards, preferring few bends and unused lanes.

    Args:
        start: Grid point outside the source card.
        end: Grid point outside the destination card.
        boxes: Card rectangles that connectors must avoid.
        used: Grid points used by previous connectors, penalized to separate routes.
        bottom: Maximum routing y coordinate in SVG pixels.
        top: Minimum routing y coordinate below the diagram introduction.

    Returns:
        Routing cost and ordered grid points from start to end.

    Raises:
        ValueError: If no route fits within the diagram's reserved gutters.
    """
    initial = (start[0], start[1], -1)
    costs = {initial: 0.0}
    previous: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    queue = [(0.0, initial)]
    while queue:
        _, state = heapq.heappop(queue)
        x, y, direction = state
        if (x, y) == end:
            points = [(x, y)]
            cursor = state
            while cursor != initial:
                cursor = previous[cursor]
                points.append((cursor[0], cursor[1]))
            return costs[state], list(reversed(points))
        for next_direction, (dx, dy) in enumerate(((STEP, 0), (0, STEP), (-STEP, 0), (0, -STEP))):
            point = (x + dx, y + dy)
            if not (20 <= point[0] <= WIDTH - 20 and top <= point[1] <= bottom):
                continue
            if any(inside(point, box, 20) for box in boxes):
                continue
            successor = (point[0], point[1], next_direction)
            cost = costs[state] + STEP + (35 if direction not in {-1, next_direction} else 0)
            cost += 65 if point in used and point not in {start, end} else 0
            if cost >= costs.get(successor, math.inf):
                continue
            costs[successor] = cost
            previous[successor] = state
            heuristic = abs(point[0] - end[0]) + abs(point[1] - end[1])
            heapq.heappush(queue, (cost + heuristic, successor))
    raise ValueError(f"Cannot route {start} to {end}")


def simplify(points: list[Point]) -> list[Point]:
    """Remove intermediate points on straight segments.

    Args:
        points: Nonempty ordered orthogonal connector coordinates.

    Returns:
        Endpoints and bend points suitable for an SVG path.
    """
    result = [points[0]]
    for index in range(1, len(points) - 1):
        before, current, after = result[-1], points[index], points[index + 1]
        if before[0] == current[0] == after[0] or before[1] == current[1] == after[1]:
            continue
        result.append(current)
    result.append(points[-1])
    return result


def text_lines(lines: list[str], x: float, y: float, css_class: str, spacing: int = 24) -> str:
    """Emit separately positioned text lines for reliable SVG bounds inspection.

    Args:
        lines: Plain text lines, escaped before insertion in SVG markup.
        x: Left text anchor in SVG pixels.
        y: Baseline of the first line in SVG pixels.
        css_class: Embedded typography class applied to each line.
        spacing: Baseline distance in SVG pixels.

    Returns:
        Newline-separated SVG text elements, or an empty string for no lines.
    """
    return "\n".join(
        f'<text x="{x:g}" y="{y + index * spacing:g}" class="{css_class}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def render(definition: dict[str, Any]) -> str:
    """Lay out one diagram with uniform cards and obstacle-routed relationships.

    Args:
        definition: Title, description, nodes, directed edges, and optional notes.
            Optional layout rows reference node indices; spans allocate one to three columns.

    Returns:
        A standalone accessible SVG with embedded styles.

    Raises:
        ValueError: If the layout omits or duplicates a node, exceeds three columns,
            or a connector or label cannot be placed without card overlap.
    """
    title = wrap(definition["title"], 76)
    description = wrap(definition["description"], 140)
    header_end = 48 + len(title) * 32 + len(description) * 24
    start_y = math.ceil((header_end + 80) / STEP) * STEP
    cards = []
    boxes: list[Box] = [(0, 0, 0, 0)] * len(definition["nodes"])
    row_y = start_y
    nodes = definition["nodes"]
    layout = definition.get(
        "layout", [list(range(i, min(i + 3, len(nodes)))) for i in range(0, len(nodes), 3)]
    )
    if sorted(index for row in layout for index in row) != list(range(len(nodes))):
        raise ValueError("Layout must contain every node exactly once")
    for row in layout:
        column = 0
        row_height = 0
        for index in row:
            node = nodes[index]
            span = definition.get("spans", {}).get(str(index), 1)
            width = CARD_WIDTH + (span - 1) * 440
            heading = wrap(node["title"], int(28 * width / CARD_WIDTH), 19, width - 40)
            detail = [
                line
                for value in node["lines"]
                for line in wrap(value, int(34 * width / CARD_WIDTH), 16, width - 40)
            ]
            height = max(120, math.ceil((46 + len(heading) * 25 + len(detail) * 23) / STEP) * STEP)
            row_height = max(row_height, height)
            x = 80 + column * 440
            boxes[index] = (x, row_y, width, height)
            cards.append(
                f'<g class="card" data-node="{index}"><rect x="{x}" y="{row_y}" width="{width}" height="{height}" rx="10"/>'
            )
            cards.append(text_lines(heading, x + 20, row_y + 34, "name", 25))
            cards.append(text_lines(detail, x + 20, row_y + 54 + len(heading) * 25, "detail", 23))
            cards.append("</g>")
            column += span
        if column > 3:
            raise ValueError("Card spans exceed the three-column layout")
        row_y += row_height + 140
    bottom = row_y - 60
    used: set[Point] = set()
    paths = []
    label_specs = []
    for edge in definition["edges"]:
        source, target = boxes[edge["source"]], boxes[edge["target"]]
        dx, dy = target[0] - source[0], target[1] - source[1]
        if edge["source"] == edge["target"]:
            candidates = [("right", "bottom")]
        elif dy == 0:
            candidates = [("right", "left")] if dx > 0 else [("left", "right")]
            candidates += [("bottom", "bottom"), ("top", "top")]
        else:
            candidates = [("bottom", "top")] if dy > 0 else [("top", "bottom")]
        options = []
        for source_side, target_side in candidates:
            attachment, departure = port(source, source_side)
            arrival, approach = port(target, target_side)
            cost, points = route(departure, approach, boxes, used, bottom, start_y - 60)
            options.append((cost, [attachment, *points, arrival]))
        _, points = min(options, key=lambda item: item[0])
        used.update(points[1:-1])
        compact = simplify(points)
        command = "M" + " L".join(f"{x} {y}" for x, y in compact)
        css = "edge optional" if edge["dashed"] else "edge"
        paths.append(
            f'<path d="{command}" class="{css}" data-source="{edge["source"]}" data-target="{edge["target"]}"/>'
        )
        if edge["label"]:
            label_specs.append((edge["label"], compact))
    labels = []
    label_boxes: list[Box] = []
    for value, points in label_specs:
        placed = False
        for chars in (18, 12, 9):
            lines = wrap(value, chars)
            width = math.ceil(max(text_width(line, 14) for line in lines)) + 16
            height = len(lines) * 18 + 10
            for a, b in sorted(
                zip(points, points[1:]),
                key=lambda pair: -(abs(pair[1][0] - pair[0][0]) + abs(pair[1][1] - pair[0][1])),
            ):
                for fraction in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9):
                    cx, cy = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
                    box = (int(cx - width / 2), int(cy - height / 2), width, height)
                    if box[0] < 8 or box[0] + width > WIDTH - 8:
                        continue
                    if any(intersects(box, other, 8) for other in boxes + label_boxes):
                        continue
                    label_boxes.append(box)
                    labels.append(
                        f'<g class="edge-label"><rect x="{box[0]}" y="{box[1]}" width="{width}" height="{height}" rx="5"/>'
                    )
                    labels.append(text_lines(lines, box[0] + 8, box[1] + 18, "label", 18))
                    labels.append("</g>")
                    placed = True
                    break
                if placed:
                    break
            if placed:
                break
        if not placed:
            raise ValueError(f"No label position: {value}")
    notes = [note for note in definition["notes"] if note not in definition["description"]]
    note_lines = [line for note in notes for line in wrap(note, 140)]
    height = bottom + 40 + len(note_lines) * 24
    styles = """text{font-family:Arial,Helvetica,sans-serif;fill:#302b38}
.heading{font-size:26px;font-weight:700}.subtitle,.note{font-size:16px;fill:#625a6b}
.card rect{fill:#fff;stroke:#cfc6da;stroke-width:1.5}.name{font-size:19px;font-weight:700;fill:#52366d}
.detail{font-size:16px}.edge{fill:none;stroke:#78638d;stroke-width:2;stroke-linejoin:round;stroke-linecap:round;marker-end:url(#arrow)}
.optional{stroke-dasharray:6 5}.edge-label rect{fill:#faf9fc;stroke:#e7e1ec}.label{font-size:14px;fill:#52366d}"""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(definition["title"])}</title>
<desc id="desc">{escape(definition["description"])}</desc>
<defs><style>{styles}</style><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#78638d"/></marker></defs>
<rect width="{WIDTH}" height="{height}" rx="12" fill="#faf9fc"/>
{text_lines(title, 40, 44, "heading", 32)}
{text_lines(description, 40, 52 + len(title) * 32, "subtitle")}
{"\n".join(paths)}
{"\n".join(cards)}
{"\n".join(labels)}
{text_lines(note_lines, 40, bottom + 24, "note")}
</svg>
'''


def main() -> None:
    """Write SVGs, or verify checked-in output with --check without changing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    definitions = json.loads(SOURCE.read_text())
    stale = []
    for name, definition in definitions.items():
        svg = render(definition)
        path = DESTINATION / f"{name}.svg"
        if args.check:
            if not path.exists() or path.read_text() != svg:
                stale.append(name)
        else:
            path.write_text(svg)
    if stale:
        raise SystemExit("Stale SVGs: " + ", ".join(stale))
    print(f"{'Checked' if args.check else 'Rendered'} {len(definitions)} documentation diagrams")


if __name__ == "__main__":
    main()
