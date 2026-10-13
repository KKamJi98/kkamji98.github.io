"""Fail-closed per-source freshness for verified Aside FHD renders."""

import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pipeline import digest, fingerprint, png_dimensions

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fhd_svg import source_fragment

REQUIRED = {
    "schema",
    "include",
    "original_source_sha256",
    "svg_sha256",
    "font_sha256",
    "images",
    "http_style_sha256",
    "renderer_js_sha256",
    "browser",
}
FONT = "assets/fonts/deterministic-export/NotoSansKR[wght].ttf"
PROOF = "diagrams/fhd-proof/index.html"


class Styles(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.active = False
        self.styles = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.active = True
            self.styles.append("")

    def handle_data(self, data):
        if self.active:
            self.styles[-1] += data

    def handle_endtag(self, tag):
        if tag == "style":
            self.active = False


def style_hash(html):
    styles = Styles(html).styles
    if len(styles) != 1 or not styles[0]:
        raise ValueError("proof fixture style is absent or ambiguous")
    return digest(styles[0].encode())


def renderer_literal(path):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "RENDER"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError("sealed renderer JS is missing")


def native_inputs(root, site, include, browser, renderer):
    if not re.fullmatch(r"diagrams/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\.html", include):
        raise ValueError("include is not a canonical local diagram path")
    if not isinstance(browser, str) or not browser.strip():
        raise ValueError("observed browser identity is missing")
    svg_rel = "assets/img/diagrams/fhd-svg/" + include.removeprefix(
        "diagrams/"
    ).replace(".html", ".svg")
    svg_raw = (root / svg_rel).read_bytes()
    if svg_raw != (site / svg_rel).read_bytes():
        raise ValueError("built SVG differs from its exact authored source bytes")
    svg = ET.fromstring(svg_raw)
    original = source_fragment((root / "_includes" / include).read_text()).encode()
    if svg.get("data-source-sha256") != digest(original):
        raise ValueError("original source differs from the SVG provenance")
    images = {}
    for image in svg.findall("{http://www.w3.org/2000/svg}image"):
        href = image.get("href", "")
        url = urlsplit(href)
        path = unquote(url.path).lstrip("/")
        if (
            url.scheme
            or url.netloc
            or url.query
            or url.fragment
            or not path.startswith("assets/")
        ):
            raise ValueError("source image is not an exact same-origin asset")
        built = (site / path).resolve()
        source = (root / path).resolve()
        if not built.is_relative_to(site.resolve()) or not source.is_relative_to(
            root.resolve()
        ):
            raise ValueError("source image escapes the sealed root")
        if source.read_bytes() != built.read_bytes():
            raise ValueError("built source image differs")
        images[href] = digest(built.read_bytes())
    font = (root / FONT).read_bytes()
    if font != (site / FONT).read_bytes():
        raise ValueError("built pinned font differs")
    return {
        "schema": 1,
        "include": include,
        "original_source_sha256": digest(original),
        "svg_sha256": digest(svg_raw),
        "font_sha256": digest(font),
        "images": images,
        "http_style_sha256": style_hash((site / PROOF).read_text()),
        "renderer_js_sha256": digest(renderer.encode()),
        "browser": browser,
    }


def accepts(receipt, current):
    old = receipt.get("per_source_inputs")
    return (
        receipt.get("automated_status") == "passed"
        and not receipt.get("metrics", {}).get("issues")
        and isinstance(old, dict)
        and set(old) == REQUIRED
        and set(current) == REQUIRED
        and old == current
        and receipt.get("per_source_fingerprint") == fingerprint(old)
    )


def receipt_is_current(receipt, inputs, stamp):
    if (
        not accepts(receipt, inputs)
        or receipt.get("metrics", {}).get("browser") != inputs["browser"]
    ):
        return False
    current_build = fingerprint(stamp)
    if receipt.get("build_identity") == current_build:
        return True
    observed = receipt.get("revalidation_observation", {})
    return (
        receipt.get("validated_build_identity") == current_build
        and observed.get("fixture_sha256") == stamp["html"][PROOF]
        and observed.get("font_sha256") == stamp["assets"][FONT]
        and observed.get("browser") == inputs["browser"]
    )


def check_png(directory, receipt):
    raw = (directory / "diagram.png").read_bytes()
    if digest(raw) != receipt["png_sha256"] or png_dimensions(raw) != [1920, 1080]:
        raise ValueError("cached PNG changed or is not exact FHD")


def migrate(root, site, out, metadata, renderer):
    """Derive old inputs from preserved evidence; skip any missing/changed source.

    This explicit migration keeps the original receipt bytes in a separate backup.
    It never changes the original render build identity or certifies failed PNGs.
    """
    old_stamp = json.loads((metadata / "build-stamp.json").read_text())
    sealed_renderer = metadata / "fhd-export-source.py"
    if (
        digest(sealed_renderer.read_bytes())
        != old_stamp["source"]["kkamji_scripts/blog/static_png/fhd_export.py"]
    ):
        raise ValueError("preserved renderer differs from the sealed old build")
    if renderer_literal(sealed_renderer) != renderer:
        raise ValueError("native rendering JS changed; rerender instead of migrating")
    backups = metadata / "original-receipts"
    backups.mkdir(exist_ok=True)
    result = {"migrated": [], "rerender": []}
    for path in sorted(out.glob("[0-9]*/receipt.json")):
        original_receipt = path.read_bytes()
        receipt = json.loads(original_receipt)
        if receipt.get("automated_status") != "passed":
            continue
        try:
            if receipt.get("build_identity") != fingerprint(old_stamp):
                raise ValueError("receipt is not from the preserved old build")
            actual_fixture = Path(receipt["artifact"]).parent / "fixture.html"
            actual_font = Path(receipt["artifact"]).parent / "pinned-font.ttf"
            if (
                digest(actual_fixture.read_bytes()) != old_stamp["html"][PROOF]
                or digest(actual_font.read_bytes()) != receipt["font_sha256"]
            ):
                raise ValueError("actual HTTP/font evidence differs from sealed inputs")
            current = native_inputs(
                root, site, receipt["include"], receipt["metrics"]["browser"], renderer
            )
            svg_rel = "assets/img/diagrams/fhd-svg/" + receipt["include"].removeprefix(
                "diagrams/"
            ).replace(".html", ".svg")
            if (
                receipt["svg_sha256"] != current["svg_sha256"]
                or receipt["source_sha256"] != current["original_source_sha256"]
                or old_stamp["source"][svg_rel] != current["svg_sha256"]
                or receipt["font_sha256"] != current["font_sha256"]
                or old_stamp["assets"][FONT] != current["font_sha256"]
                or style_hash(actual_fixture.read_text())
                != current["http_style_sha256"]
            ):
                raise ValueError("old per-source inputs differ")
            for href, image_sha in current["images"].items():
                image_path = unquote(urlsplit(href).path).lstrip("/")
                if old_stamp["assets"].get(image_path) != image_sha:
                    raise ValueError("old source image differs")
            check_png(path.parent, receipt)
            backup = backups / (str(receipt["index"]).zfill(3) + ".json")
            if backup.exists() and backup.read_bytes() != original_receipt:
                raise ValueError("original receipt backup has different bytes")
            backup.write_bytes(original_receipt)
            receipt.update(
                per_source_inputs=current,
                per_source_fingerprint=fingerprint(current),
                migration={
                    "source_build_identity": fingerprint(old_stamp),
                    "original_receipt_sha256": digest(original_receipt),
                },
            )
            path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            result["migrated"].append(receipt["index"])
        except (OSError, KeyError, ValueError) as error:
            result["rerender"].append({"index": receipt["index"], "reason": str(error)})
    return result


def revalidate(root, site, out, stamp, renderer, observed):
    """Require a fresh Aside observation, then compare every rendering input."""
    if (
        observed.get("fixture_sha256") != stamp["html"][PROOF]
        or observed.get("font_sha256") != stamp["assets"][FONT]
        or not observed.get("browser")
    ):
        raise ValueError(
            "fresh Aside HTTP/font/browser observation is missing or stale"
        )
    result = {"accepted": [], "rerender": []}
    for path in sorted(out.glob("[0-9]*/receipt.json")):
        receipt = json.loads(path.read_text())
        try:
            current = native_inputs(
                root, site, receipt["include"], observed["browser"], renderer
            )
            if not accepts(receipt, current):
                raise ValueError("failed, missing, or changed per-source inputs")
            check_png(path.parent, receipt)
            receipt.update(
                validated_build_identity=fingerprint(stamp),
                revalidation_observation=observed,
                reuse_reason="exact per-source input bytes unchanged; original render build retained",
            )
            path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            result["accepted"].append(receipt["index"])
        except (OSError, KeyError, ValueError) as error:
            result["rerender"].append({"index": receipt["index"], "reason": str(error)})
    return result
