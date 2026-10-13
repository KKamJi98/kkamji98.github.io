#!/usr/bin/env python3
"""Seal FHD exports only after all sources have independent recorded reviews."""

import argparse
import json
import shutil
from pathlib import Path

from downloads import built_plan, source_snapshot, webp_url
from fhd_export import RENDER, build_guard, unused_png
from fhd_reuse import native_inputs, receipt_is_current
from pipeline import digest, fingerprint, png_dimensions
from release_manifest import MANIFEST


def checked_sources(root, site, out, reviews):
    plan, stamp = build_guard(root, site)
    catalog = json.loads((root / "docs/diagram-catalog.json").read_text())["diagrams"]
    payload = json.loads(reviews.read_text())
    records = payload.get("sources", [])
    by_include = {row["include"]: row for row in records}
    if len(by_include) != len(records) or set(by_include) != {
        row["include"] for row in catalog
    }:
        raise ValueError(
            "visual/semantic review coverage differs from the full source catalog"
        )
    checked = {}
    browsers = set()
    for index, record in enumerate(catalog):
        directory = out / str(index).zfill(3)
        receipt_file = directory / "receipt.json"
        receipt = json.loads(receipt_file.read_text())
        svg = (
            root
            / "assets/img/diagrams/fhd-svg"
            / record["include"].removeprefix("diagrams/").replace(".html", ".svg")
        )
        raw = (directory / "diagram.png").read_bytes()
        if (
            receipt.get("automated_status") != "passed"
            or receipt.get("metrics", {}).get("issues")
            or receipt.get("include") != record["include"]
            or receipt.get("index") != index
            or receipt.get("svg_sha256") != digest(svg.read_bytes())
            or not receipt_is_current(
                receipt,
                native_inputs(
                    root,
                    site,
                    record["include"],
                    receipt.get("metrics", {}).get("browser"),
                    RENDER,
                ),
                stamp,
            )
            or receipt.get("png_sha256") != digest(raw)
            or png_dimensions(raw) != [1920, 1080]
            or receipt.get("png_dimensions") != [1920, 1080]
        ):
            raise ValueError("FHD render receipt failed or stale: " + record["include"])
        review = by_include[record["include"]]
        if (
            review.get("visual_status") != "passed"
            or review.get("semantic_status") != "passed"
            or review.get("png_sha256") != digest(raw)
            or review.get("svg_sha256") != digest(svg.read_bytes())
            or not review.get("notes")
            or not review.get("reviewed_at")
        ):
            raise ValueError(
                "rendered visual/semantic review missing or stale: " + record["include"]
            )
        browsers.add(receipt["metrics"]["browser"])
        checked[record["include"]] = dict(
            receipt, receipt_sha256=digest(receipt_file.read_bytes())
        )
    if len(browsers) != 1:
        raise ValueError("mixed browser versions in the FHD render release")
    return plan, stamp, checked, browsers.pop()


def unused_outputs(root, plan):
    """Keep native paths when a former body figure is now used as a cover."""
    baseline = root / MANIFEST
    previous = json.loads(baseline.read_text()) if baseline.is_file() else {}
    rows = previous.get("entries", []) + previous.get("unused_entries", [])
    result = []
    for include in plan["unused_includes"]:
        paths = sorted({row["png"] for row in rows if row["include"] == include})
        for png in paths or [unused_png(include)]:
            webp_url(png)  # Validate the preserved public native path.
            result.append((include, png))
    if len({png for _include, png in result}) != len(result):
        raise ValueError("preserved unused native output collision")
    return result


def promote(root, site, out, reviews):
    """Copy reviewed native outputs only after every source gate passes."""
    plan, _stamp, sources, _browser = checked_sources(root, site, out, reviews)
    destinations = [(row["include"], row["png"]) for row in plan["entries"]]
    destinations += unused_outputs(root, plan)
    for include, png in destinations:
        source = out / str(sources[include]["index"]).zfill(3) / "diagram.png"
        for directory in (root, site):
            destination = directory / png.lstrip("/")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            raw = destination.read_bytes()
            if digest(raw) != sources[include]["png_sha256"] or png_dimensions(raw) != [
                1920,
                1080,
            ]:
                raise ValueError("promoted occurrence differs from reviewed native PNG")
    return {
        "sources": len(sources),
        "outputs": len(destinations),
        "status": "reviewed-native-promoted",
    }


def record(root, site, out, reviews):
    plan, stamp, sources, browser = checked_sources(root, site, out, reviews)
    rows = built_plan(root, site, plan)
    entries = []
    for row in rows:
        source = sources[row["include"]]
        raw = (root / row["png"].lstrip("/")).read_bytes()
        if raw != (out / str(source["index"]).zfill(3) / "diagram.png").read_bytes():
            raise ValueError(
                "public occurrence PNG differs from the reviewed source: " + row["png"]
            )
        if raw != (site / row["png"].lstrip("/")).read_bytes():
            raise ValueError(
                "built occurrence PNG differs from the reviewed source: " + row["png"]
            )
        entries.append(
            {key: row[key] for key in ("post", "include", "figure", "page", "png")}
            | {
                "png_sha256": digest(raw),
                "dimensions": [1920, 1080],
                "include_sha256": digest(
                    (root / "_includes" / row["include"]).read_bytes()
                ),
                "receipt_sha256": source["receipt_sha256"],
            }
        )
    unused = []
    for include, png in unused_outputs(root, plan):
        source = sources[include]
        raw = (root / png.lstrip("/")).read_bytes()
        if (
            digest(raw) != source["png_sha256"]
            or raw != (site / png.lstrip("/")).read_bytes()
        ):
            raise ValueError("unused-source PNG differs from its reviewed render")
        unused.append(
            {
                "include": include,
                "png": png,
                "dimensions": [1920, 1080],
                "png_sha256": digest(raw),
            }
        )
    relative_reviews = reviews.relative_to(root).as_posix()
    payload = {
        "schema": 2,
        "status": "export-and-check-passed",
        "source_count": len(sources),
        "reference_count": len(entries),
        "post_count": plan["post_count"],
        "theme": "light",
        "font_profile": "deterministic-export",
        "production_identical": False,
        "browser": browser,
        "source_fingerprint": fingerprint(source_snapshot(root)),
        "build_identity": fingerprint(stamp),
        "automated_quality": "FHD source, paint, pinned font, PNG, and freshness checks passed",
        "visual_review": "all-sources-passed",
        "semantic_review": "all-sources-passed",
        "review_file": relative_reviews,
        "review_file_sha256": digest(reviews.read_bytes()),
        "entries": entries,
        "unused_entries": unused,
    }
    (root / MANIFEST).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    return {
        "sources": len(sources),
        "references": len(entries),
        "unused": len(unused),
        "status": "checked",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument(
        "--promote",
        action="store_true",
        help="copy all reviewed native PNGs before sealing",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    reviews = args.reviews.resolve()
    if (
        not reviews.is_relative_to(root)
        or reviews.relative_to(root).as_posix() != "docs/diagram-fhd-reviews.json"
    ):
        parser.error(
            "reviews must be the tracked docs/diagram-fhd-reviews.json evidence"
        )
    if args.promote:
        print(
            json.dumps(promote(root, args.site.resolve(), args.out.resolve(), reviews))
        )
    print(json.dumps(record(root, args.site.resolve(), args.out.resolve(), reviews)))


if __name__ == "__main__":
    main()
