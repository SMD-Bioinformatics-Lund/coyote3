#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Build approved Coyote brand assets from one vector source and outlined labels.

The canonical drawing is frontend/public/logos/coyote4-logo.svg. This blueprint
preserves its animal, ring, gradient and DNA. Package lettering is stored as
outlines so installed fonts cannot change the design. No network access occurs.
SVG export uses the standard library; --raster additionally requires CairoSVG
and Pillow. Generated assets are reviewed and committed, never built at startup.
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

# Approved package wordmarks, stored as SVG outlines rather than font dependencies.
WORDMARKS = {
    "api/src/coyote_api/config/assets/coyote-api-logo.svg": {
        "width": "765.572",
        "height": "106.56",
        "title": "Coyote API",
        "description": "Transparent Coyote API "
        "package logo using the "
        "approved howling coyote, "
        "purple and warm-orange "
        "ring, gradient Coyote "
        "lettering and DNA tail "
        "flourish. Lettering is "
        "outlined vector artwork "
        "with no external font "
        "dependencies.",
        "outline": "<g "
        'xmlns="http://www.w3.org/2000/svg" '
        'id="package-wordmark" '
        'fill="#705199" '
        'aria-label="API">\n'
        '    <path d="M528 0Q525 42 '
        "521.5 83.5Q518 125 514 "
        "164H233Q210 125 187.5 "
        "84.5Q165 44 142 0H7Q68 106 "
        "123.5 200.0Q179 294 231.5 "
        "379.0Q284 464 335.5 "
        "541.5Q387 619 439 "
        "693H556Q588 544 611.0 "
        "367.5Q634 191 655 0ZM470 "
        "561Q432 502 385.5 428.5Q339 "
        "355 287 264H504Q498 335 "
        "489.5 409.5Q481 484 470 "
        '561Z" '
        'transform="translate(642.000 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M427 700Q552 '
        "700 618.5 651.0Q685 602 685 "
        "511Q685 439 657.5 388.5Q630 "
        "338 581.5 306.0Q533 274 "
        "465.5 259.5Q398 245 317 "
        "245H263L204 0H78L241 683Q289 "
        "693 337.0 696.5Q385 700 427 "
        "700ZM415 594Q396 594 379.0 "
        "593.0Q362 592 345 590L288 "
        "351H339Q381 351 420.0 "
        "358.0Q459 365 489.0 "
        "381.5Q519 398 537.0 "
        "426.5Q555 455 555 499Q555 "
        "550 517.5 572.0Q480 594 415 "
        '594Z" '
        'transform="translate(691.856 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M244 '
        '693H370L204 0H78Z" '
        'transform="translate(737.836 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        "  </g>",
    },
    "core/docs/assets/coyote-core-logo.svg": {
        "width": "806.916",
        "title": "Coyote Core",
        "description": "Transparent Coyote Core package logo "
        "using the approved howling coyote, "
        "purple and warm-orange ring, gradient "
        "Coyote lettering and DNA tail flourish. "
        "Lettering is outlined vector artwork "
        "with no external font dependencies.",
        "outline": '<g xmlns="http://www.w3.org/2000/svg" '
        'id="package-wordmark" fill="#705199" '
        'aria-label="Core">\n'
        '    <path d="M600 30Q567 13 516.0 -1.0Q465 '
        "-15 392 -15Q328 -15 278.0 4.5Q228 24 193.0 "
        "61.0Q158 98 139.5 150.0Q121 202 121 267Q121 "
        "351 149.0 430.5Q177 510 230.0 572.0Q283 634 "
        "359.0 671.5Q435 709 531 709Q594 709 640.5 "
        "695.0Q687 681 722 661L674 560Q642 579 605.5 "
        "589.5Q569 600 523 600Q460 600 410.0 "
        "572.0Q360 544 324.5 498.5Q289 453 270.5 "
        "395.0Q252 337 252 277Q252 184 292.5 "
        "139.5Q333 95 411 95Q471 95 513.0 108.5Q555 "
        '122 585 136Z" transform="translate(642.000 '
        '153) scale(0.07600000 -0.07600000)" />\n'
        '    <path d="M288 -14Q195 -14 146.0 41.0Q97 '
        "96 97 186Q97 244 115.0 306.0Q133 368 170.0 "
        "419.0Q207 470 263.0 503.0Q319 536 395 "
        "536Q488 536 537.0 481.5Q586 427 586 337Q586 "
        "278 568.5 216.0Q551 154 514.5 103.0Q478 52 "
        "421.5 19.0Q365 -14 288 -14ZM380 434Q341 434 "
        "310.5 411.5Q280 389 259.5 354.0Q239 319 "
        "228.0 277.5Q217 236 217 197Q217 147 236.0 "
        "118.0Q255 89 303 89Q342 89 372.5 111.5Q403 "
        "134 423.5 168.5Q444 203 455.0 245.0Q466 287 "
        "466 325Q466 375 447.0 404.5Q428 434 380 "
        '434Z" transform="translate(688.056 153) '
        'scale(0.07600000 -0.07600000)" />\n'
        '    <path d="M460 416Q440 423 417.0 '
        "427.0Q394 431 363 431Q346 431 327.0 "
        "428.5Q308 426 295 422L194 0H73L193 499Q235 "
        "513 284.0 523.5Q333 534 390 534Q402 534 "
        "417.0 532.5Q432 531 446.5 529.0Q461 527 "
        '473.5 524.0Q486 521 495 517Z" '
        'transform="translate(730.844 153) '
        'scale(0.07600000 -0.07600000)" />\n'
        '    <path d="M97 189Q97 256 118.5 318.5Q140 '
        "381 180.5 429.5Q221 478 278.0 507.0Q335 536 "
        "406 536Q482 536 524.0 497.0Q566 458 566 "
        "397Q566 334 535.0 295.0Q504 256 454.5 "
        "234.0Q405 212 342.5 204.0Q280 196 216 "
        "194Q215 192 215 190V180Q215 89 330 89Q398 "
        "89 466 117L476 19Q452 8 408.0 -3.0Q364 -14 "
        "308 -14Q252 -14 212.0 2.0Q172 18 146.5 "
        "46.0Q121 74 109.0 110.5Q97 147 97 189ZM388 "
        "437Q358 437 331.0 425.0Q304 413 283.0 "
        "392.0Q262 371 246.5 342.5Q231 314 224 "
        "281Q344 285 398.5 310.0Q453 335 453 385Q453 "
        '405 438.5 421.0Q424 437 388 437Z" '
        'transform="translate(761.168 153) '
        'scale(0.07600000 -0.07600000)" />\n'
        "  </g>",
    },
    "services/atlas/src/coyote_atlas/assets/coyote-atlas-logo.svg": {
        "width": "830.676",
        "title": "Coyote Atlas",
        "description": "Transparent "
        "Coyote Atlas "
        "package logo "
        "using the "
        "approved howling "
        "coyote, purple "
        "and warm-orange "
        "ring, gradient "
        "Coyote lettering "
        "and DNA tail "
        "flourish. "
        "Lettering is "
        "outlined vector "
        "artwork with no "
        "external font "
        "dependencies.",
        "outline": "<g "
        'xmlns="http://www.w3.org/2000/svg" '
        'id="package-wordmark" '
        'fill="#705199" '
        'aria-label="Atlas">\n'
        '    <path d="M528 '
        "0Q525 42 521.5 "
        "83.5Q518 125 514 "
        "164H233Q210 125 "
        "187.5 84.5Q165 44 "
        "142 0H7Q68 106 123.5 "
        "200.0Q179 294 231.5 "
        "379.0Q284 464 335.5 "
        "541.5Q387 619 439 "
        "693H556Q588 544 "
        "611.0 367.5Q634 191 "
        "655 0ZM470 561Q432 "
        "502 385.5 428.5Q339 "
        "355 287 264H504Q498 "
        "335 489.5 409.5Q481 "
        '484 470 561Z" '
        'transform="translate(642.000 '
        "153) "
        "scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M218 '
        "661 344 681 306 "
        "523H477L453 "
        "423H282L232 216Q227 "
        "194 225.0 179.5Q223 "
        "165 223 153Q223 141 "
        "225.5 129.5Q228 118 "
        "235.5 109.5Q243 101 "
        "257.5 95.5Q272 90 "
        "297 90Q324 90 349.0 "
        "97.0Q374 104 393 "
        "112L402 15Q379 5 "
        "344.0 -4.0Q309 -13 "
        "262 -13Q176 -13 "
        "139.0 24.5Q102 62 "
        "102 127Q102 151 "
        "105.5 176.5Q109 202 "
        '116 231Z" '
        'transform="translate(691.856 '
        "153) "
        "scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M273 '
        "-10Q226 -9 193.5 "
        "2.0Q161 13 141.5 "
        "32.0Q122 51 113.5 "
        "77.0Q105 103 105 "
        "134Q105 166 112.5 "
        "201.5Q120 237 129 "
        "272L245 756L371 "
        "776Q340 645 309.0 "
        "515.5Q278 386 246 "
        "255Q241 234 235.0 "
        "213.5Q229 193 229 "
        "173Q229 156 229.5 "
        "141.5Q230 127 237.5 "
        "116.5Q245 106 260.0 "
        '99.0Q275 92 299 90Z" '
        'transform="translate(722.332 '
        "153) "
        "scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M530 '
        "203Q527 192 524.0 "
        "167.0Q521 142 521 "
        "120Q521 91 526.0 "
        "63.5Q531 36 542 "
        "8L434 -8Q422 16 415 "
        "43Q390 21 353.5 "
        "3.5Q317 -14 271 "
        "-14Q224 -14 190.5 "
        "1.5Q157 17 136.0 "
        "44.5Q115 72 105.0 "
        "109.0Q95 146 95 "
        "189Q95 262 121.0 "
        "325.0Q147 388 193.5 "
        "434.0Q240 480 304.0 "
        "506.5Q368 533 444 "
        "533Q483 533 522.5 "
        "526.5Q562 520 602 "
        "502ZM464 429Q445 433 "
        "421 433Q376 433 "
        "338.0 413.5Q300 394 "
        "272.5 361.5Q245 329 "
        "230.0 287.0Q215 245 "
        "215 199Q215 176 "
        "219.0 156.0Q223 136 "
        "232.5 121.0Q242 106 "
        "258.0 97.0Q274 88 "
        "299 88Q331 88 355.5 "
        "101.5Q380 115 401 "
        "138Q402 164 405.5 "
        "187.0Q409 210 415 "
        '233Z" '
        'transform="translate(744.980 '
        "153) "
        "scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M224 '
        "85Q272 85 300.0 "
        "100.5Q328 116 328 "
        "148Q328 174 310.0 "
        "189.5Q292 205 247 "
        "226Q223 237 202.5 "
        "249.0Q182 261 167.0 "
        "277.0Q152 293 143.0 "
        "314.5Q134 336 134 "
        "366Q134 444 191.0 "
        "490.0Q248 536 356 "
        "536Q406 536 445.5 "
        "525.5Q485 515 505 "
        "504L462 410Q445 420 "
        "413.0 429.5Q381 439 "
        "346 439Q329 439 "
        "312.5 436.0Q296 433 "
        "283.0 426.0Q270 419 "
        "261.5 406.5Q253 394 "
        "253 376Q253 353 "
        "271.5 338.5Q290 324 "
        "325 308Q358 293 "
        "381.0 279.0Q404 265 "
        "419.0 247.5Q434 230 "
        "441.0 208.5Q448 187 "
        "448 157Q448 120 "
        "433.0 88.5Q418 57 "
        "389.5 34.5Q361 12 "
        "319.0 -1.0Q277 -14 "
        "223 -14Q186 -14 "
        "156.5 -9.0Q127 -4 "
        "105.0 2.5Q83 9 68.0 "
        "16.0Q53 23 45 28L88 "
        "123Q95 119 108.5 "
        "112.5Q122 106 139.5 "
        "100.0Q157 94 178.5 "
        '89.5Q200 85 224 85Z" '
        'transform="translate(787.388 '
        "153) "
        "scale(0.07600000 "
        '-0.07600000)" />\n'
        "  </g>",
    },
    "services/demo/src/coyote_demo/assets/coyote-demo-logo.svg": {
        "width": "851.880",
        "title": "Coyote Demo",
        "description": "Transparent Coyote "
        "Demo package logo "
        "using the approved "
        "howling coyote, "
        "purple and "
        "warm-orange ring, "
        "gradient Coyote "
        "lettering and DNA "
        "tail flourish. "
        "Lettering is "
        "outlined vector "
        "artwork with no "
        "external font "
        "dependencies.",
        "outline": "<g "
        'xmlns="http://www.w3.org/2000/svg" '
        'id="package-wordmark" '
        'fill="#705199" '
        'aria-label="Demo">\n'
        '    <path d="M229 '
        "103Q240 101 254.5 "
        "100.5Q269 100 300 "
        "100Q372 100 430.0 "
        "123.0Q488 146 528.5 "
        "188.5Q569 231 591.0 "
        "290.5Q613 350 613 "
        "423Q613 502 568.0 "
        "548.0Q523 594 421 "
        "594Q395 594 379.5 "
        "593.0Q364 592 346 "
        "590ZM743 427Q743 334 "
        "713.0 254.0Q683 174 "
        "624.0 116.0Q565 58 "
        "476.5 25.0Q388 -8 271 "
        "-8Q229 -8 177.0 "
        "-3.5Q125 1 81 11L242 "
        "682Q291 693 341.0 "
        "696.5Q391 700 433 "
        "700Q509 700 567.0 "
        "680.5Q625 661 664.0 "
        "625.5Q703 590 723.0 "
        '539.5Q743 489 743 427Z" '
        'transform="translate(642.000 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M97 189Q97 '
        "256 118.5 318.5Q140 381 "
        "180.5 429.5Q221 478 "
        "278.0 507.0Q335 536 406 "
        "536Q482 536 524.0 "
        "497.0Q566 458 566 "
        "397Q566 334 535.0 "
        "295.0Q504 256 454.5 "
        "234.0Q405 212 342.5 "
        "204.0Q280 196 216 "
        "194Q215 192 215 "
        "190V180Q215 89 330 "
        "89Q398 89 466 117L476 "
        "19Q452 8 408.0 -3.0Q364 "
        "-14 308 -14Q252 -14 "
        "212.0 2.0Q172 18 146.5 "
        "46.0Q121 74 109.0 "
        "110.5Q97 147 97 "
        "189ZM388 437Q358 437 "
        "331.0 425.0Q304 413 "
        "283.0 392.0Q262 371 "
        "246.5 342.5Q231 314 224 "
        "281Q344 285 398.5 "
        "310.0Q453 335 453 "
        "385Q453 405 438.5 "
        '421.0Q424 437 388 437Z" '
        'transform="translate(695.352 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M193 '
        "501Q233 513 283.0 "
        "523.5Q333 534 393 "
        "534Q438 534 468.5 "
        "521.0Q499 508 520 "
        "484Q549 501 590.5 "
        "517.5Q632 534 685 "
        "534Q731 534 763.0 "
        "521.0Q795 508 815.0 "
        "485.0Q835 462 844.0 "
        "430.5Q853 399 853 "
        "362Q853 321 842 275L776 "
        "0H655L717 262Q722 281 "
        "726.5 303.5Q731 326 731 "
        "349Q731 365 727.5 "
        "380.5Q724 396 715.0 "
        "407.0Q706 418 690.5 "
        "425.0Q675 432 651 "
        "432Q625 432 600.0 "
        "422.0Q575 412 558 "
        "401Q562 382 562 360Q562 "
        "340 559.0 318.0Q556 296 "
        "551 275L485 0H364L426 "
        "262Q431 280 435.5 "
        "303.5Q440 327 440 "
        "350Q440 383 424.5 "
        "407.5Q409 432 366 "
        "432Q346 432 328.0 "
        "429.5Q310 427 295 "
        '423L194 0H73Z" '
        'transform="translate(735.100 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        '    <path d="M288 '
        "-14Q195 -14 146.0 "
        "41.0Q97 96 97 186Q97 "
        "244 115.0 306.0Q133 368 "
        "170.0 419.0Q207 470 "
        "263.0 503.0Q319 536 395 "
        "536Q488 536 537.0 "
        "481.5Q586 427 586 "
        "337Q586 278 568.5 "
        "216.0Q551 154 514.5 "
        "103.0Q478 52 421.5 "
        "19.0Q365 -14 288 "
        "-14ZM380 434Q341 434 "
        "310.5 411.5Q280 389 "
        "259.5 354.0Q239 319 "
        "228.0 277.5Q217 236 217 "
        "197Q217 147 236.0 "
        "118.0Q255 89 303 89Q342 "
        "89 372.5 111.5Q403 134 "
        "423.5 168.5Q444 203 "
        "455.0 245.0Q466 287 466 "
        "325Q466 375 447.0 "
        '404.5Q428 434 380 434Z" '
        'transform="translate(799.092 '
        "153) scale(0.07600000 "
        '-0.07600000)" />\n'
        "  </g>",
    },
}


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
    ET.SubElement(root, f"{{{SVG}}}title", {"id": "emblem-title"}).text = "Coyote4 emblem"
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


def main() -> None:
    """Export to a review directory, or explicitly replace repository assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--output-dir", type=Path, help="Export for review outside the source tree"
    )
    destination.add_argument("--write", action="store_true", help="Replace the maintained assets")
    parser.add_argument(
        "--raster", action="store_true", help="Also render ICO and PNG with CairoSVG/Pillow"
    )
    args = parser.parse_args()
    output = ROOT if args.write else args.output_dir.resolve()
    source_bytes = (ROOT / SOURCE).read_bytes()
    source = ET.fromstring(source_bytes)
    for relative in MAIN_COPIES:
        root = deepcopy(source)
        if relative.startswith("docs/"):
            root.set("width", "320")
            root.set("height", "115")
        write_svg(root, output / relative)
    for relative, spec in WORDMARKS.items():
        write_svg(package_logo(source, spec), output / relative)
    animal = emblem(source)
    write_svg(animal, output / "frontend/public/logos/coyote4-emblem.svg")
    if args.raster:
        export_raster(output, animal, source_bytes)
    error_path = Path("deploy/compose/nginx/error-pages/unavailable.html")
    page = (ROOT / error_path).read_text()
    page = re.sub(
        r"data:image/svg\+xml;base64,[A-Za-z0-9+/=]+",
        "data:image/svg+xml;base64," + base64.b64encode(source_bytes).decode(),
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
    print("Brand assets exported; review the output before committing.")


if __name__ == "__main__":
    main()
