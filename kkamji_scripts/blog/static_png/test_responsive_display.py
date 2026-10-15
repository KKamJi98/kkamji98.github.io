"""Static display contracts, not browser geometry or raster visual approval.

FHD source/export coordinates remain native. Only opt-in article image CSS is
responsive; covers and the user-selected standalone viewer are separate.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fhd_svg import FONT, author


ROOT = Path(__file__).resolve().parents[3]
STYLESHEET = ROOT / "assets/css/jekyll-theme-chirpy.scss"
FIXED_FHD_SELECTORS = {
    ".diagram-download.diagram-download--fixed-fhd > img.diagram-inline",
    "#main-wrapper main .content .diagram-download.diagram-download--fixed-fhd > img.diagram-inline",
}
RESPONSIVE_SIZE = {
    "width": "100%",
    "min-width": "0",
    "max-width": "100%",
    "height": "auto",
    "min-height": "0",
    "max-height": "none",
    "aspect-ratio": "16 / 9",
}


def style_rules():
    """Inspect declaration blocks; deliberately do not emulate the CSS cascade."""
    text = re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(), flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selectors = [selector.strip() for selector in match[1].split(",")]
        declarations = {}
        for declaration in match[2].split(";"):
            if ":" in declaration:
                name, value = declaration.split(":", 1)
                declarations[name.strip()] = value.strip().removesuffix(" !important")
        yield selectors, declarations


def inline_rules():
    return [
        (selectors, declarations)
        for selectors, declarations in style_rules()
        if any(re.search(r"(?:^|[\s>])img\.diagram-inline$", s) for s in selectors)
        and not set(selectors) <= FIXED_FHD_SELECTORS
    ]


def test_every_inline_image_rule_scales_proportionally_to_article_width():
    rules = inline_rules()
    assert rules, "the opt-in inline image needs an explicit responsive rule"
    for selectors, declarations in rules:
        for name, value in RESPONSIVE_SIZE.items():
            assert declarations.get(name) == value, (selectors, name, declarations.get(name))
        assert declarations.get("object-fit") == "contain"


def test_inline_container_does_not_force_image_scrolling():
    rules = [d for selectors, d in style_rules() if ".diagram-download" in selectors]
    assert rules, "the article image container needs explicit width bounds"
    for declarations in rules:
        assert declarations.get("width") == "100%"
        assert declarations.get("min-width") == "0"
        assert declarations.get("max-width") == "100%"
        assert declarations.get("overflow-x", "visible") == "visible"
        assert "scrollbar-gutter" not in declarations
        assert "overscroll-behavior-inline" not in declarations


def test_author_report_separates_native_canvas_from_responsive_display(tmp_path):
    # An empty catalog exercises only report metadata, not artwork generation.
    font_path = tmp_path / FONT
    font_path.parent.mkdir(parents=True)
    font_path.symlink_to(ROOT / FONT)
    catalog = tmp_path / "docs/diagram-catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"diagrams": []}))
    budgets = tmp_path / "kkamji_scripts/blog/static_png/fhd-font-budgets.json"
    budgets.parent.mkdir(parents=True)
    budgets.write_text(json.dumps({"sources": {}}))
    report = tmp_path / "display-report.json"

    assert author(tmp_path, check=True, report=report) == 0
    payload = json.loads(report.read_text())
    assert payload["canvas"] == [1920, 1080]
    assert payload["display"] == "responsive-proportional"
    assert payload["entries"] == []


def test_responsive_sizing_is_opt_in_for_body_diagrams_not_covers_or_viewers():
    allowed = {
        ".diagram-download > img.diagram-inline",
        "#main-wrapper main .content .diagram-download > img.diagram-inline",
    }
    for selectors, declarations in style_rules():
        if set(selectors) <= FIXED_FHD_SELECTORS:
            continue  # Explicit fixed-FHD sizing has its own strict contract tests.
        responsive = all(declarations.get(k) == v for k, v in RESPONSIVE_SIZE.items())
        if responsive or any("diagram-inline" in s and s.endswith("img.diagram-inline") for s in selectors):
            assert set(selectors) <= allowed, selectors
    # Covers, icon images and standalone viewers must not become body diagrams
    # merely because they use WebP or have a native 1920 x 1080 canvas.
    assert {s for selectors, _ in inline_rules() for s in selectors} == allowed


def test_source_and_export_css_keep_native_fhd_coordinates():
    rules = {s: d for selectors, d in style_rules() for s in selectors}
    native = {
        "width": "1920px",
        "min-width": "1920px",
        "max-width": "1920px",
        "height": "1080px",
        "min-height": "1080px",
        "max-height": "1080px",
    }
    for selector in (
        "figure.sd.sd--fhd",
        "figure.sd.sd--fhd > svg.sd-fhd-artwork",
    ):
        for name, value in native.items():
            assert rules[selector][name] == value


def test_mapped_semantic_source_stays_clipped_without_native_width_leak():
    rules = {s: d for selectors, d in style_rules() for s in selectors}
    selector = "figure.sd.sd--fhd:has(+ .diagram-download > img.diagram-inline)"
    for name in ("width", "min-width", "max-width", "height", "min-height", "max-height"):
        assert rules[selector][name] == "1px"
    clip = rules["figure.sd:has(+ .diagram-download > img.diagram-inline)"]
    assert clip["overflow"] == "hidden"
    assert clip["clip-path"] == "inset(50%)"
    assert clip.get("display") != "none"
    assert clip.get("visibility") != "hidden"
