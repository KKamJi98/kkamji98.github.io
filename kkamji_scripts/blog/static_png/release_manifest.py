"""Fast source/PNG consistency gate for normal diagram commits."""

import argparse
import json
from pathlib import Path
import subprocess

MANIFEST = "docs/diagram-export-release.json"
DIAGRAM_SOURCE_SUFFIXES = (".svg", ".drawio", ".spec.json")
DIAGRAM_REFERENCE_DOCS = (
    "docs/diagram-catalog.json",
    "docs/diagram-downloads.json",
    "docs/diagram-webp-release.json",
    MANIFEST,
)


def _png_path(root, value):
    if not value.startswith("/assets/img/diagrams/") or any(
        p in (".", "..") for p in value.split("/")
    ):
        raise ValueError("invalid public PNG path")
    path = (root / value.lstrip("/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("public PNG escapes repository")
    return path


def record_checked(root, rows, out):
    """Called only after the adapter's complete fresh check succeeds."""
    from downloads import source_snapshot
    from pipeline import digest, fingerprint, png_dimensions

    entries = []
    browsers = set()
    for row in rows:
        directory = out / fingerprint(row)[:24]
        receipt = json.loads(
            (directory / (row["figure"] + "-1920x1080-light.json")).read_text()
        )
        if (
            receipt["quality_status"] != "passed"
            or receipt["font_policy"]["profile"] != "deterministic-export"
        ):
            raise ValueError("unverified export receipt")
        raw = _png_path(root, row["png"]).read_bytes()
        if png_dimensions(raw) != [1920, 1080] or receipt.get("png_dimensions") != [1920, 1080]:
            raise ValueError("PNG must be exactly 1920 x 1080")
        if digest(raw) != receipt["png_sha256"]:
            raise ValueError("PNG changed after check")
        entries.append(
            {k: row[k] for k in ("post", "include", "figure", "page", "png")}
            | {
                "png_sha256": receipt["png_sha256"],
                "dimensions": receipt["png_dimensions"],
                "include_sha256": digest(
                    (root / "_includes" / row["include"]).read_bytes()
                ),
                "receipt_sha256": digest(
                    (directory / (row["figure"] + "-1920x1080-light.json")).read_bytes()
                ),
            }
        )
        browsers.add(receipt["inputs"]["browser"])
    if len(browsers) != 1:
        raise ValueError("mixed browser versions in release")
    snapshot = source_snapshot(root)
    manifest = {
        "schema": 1,
        "status": "export-and-check-passed",
        "reference_count": len(entries),
        "post_count": len({e["post"] for e in entries}),
        "font_profile": "deterministic-export",
        "production_identical": False,
        "theme": "light",
        "browser": browsers.pop(),
        "source_fingerprint": fingerprint(snapshot),
        "automated_quality": "connector-paint-font-and-layout-checks-passed",
        "visual_review": "see connector review evidence for scope and limitations",
        "inputs": {
            p: h
            for p, h in snapshot.items()
            if p.startswith("kkamji_scripts/blog/static_png/")
            or p
            in (
                "docs/diagram-catalog.json",
                "docs/diagram-downloads.json",
                "assets/css/jekyll-theme-chirpy.scss",
                "assets/fonts/static-png/lock.json",
                "assets/fonts/deterministic-export/lock.json",
                "assets/fonts/deterministic-export/fontconfig.conf",
                "_plugins/diagram-downloads.rb",
            )
        },
        "entries": entries,
    }
    (root / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def _diagram_bound_image(root, path):
    """assets/img mixes diagram inputs with ordinary post covers and photos.

    Diagram outputs, vector or Draw.io sources, catalogued originals and any
    image a diagram include references are render inputs. Other images behave
    like prose: they reach the site but do not demand a diagram reexport.
    """
    if path.startswith("assets/img/diagrams/") or path.endswith(DIAGRAM_SOURCE_SUFFIXES):
        return True
    for name in DIAGRAM_REFERENCE_DOCS:
        doc = root / name
        if doc.is_file() and path in doc.read_text(errors="replace"):
            return True
    includes = root / "_includes"
    return includes.is_dir() and any(
        path in include.read_text(errors="replace")
        for include in includes.rglob("*.html") if include.is_file()
    )


def staged_requires_verification(root):
    root = Path(root)
    paths = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
    ).splitlines()
    # Keep this in sync with source_snapshot's sealed render inputs. Posts are
    # handled separately below so ordinary prose edits do not force a reexport.
    # Mapped PNGs are excluded from that snapshot, but must still enter the
    # gate: verify_staged checks their hashes against the release manifest.
    prefixes = (
        "_includes/",
        "_layouts/",
        "_sass/",
        "_plugins/",
        "_data/",
        "assets/css/",
        "assets/js/",
        "assets/fonts/",
        "kkamji_scripts/blog/static_png/",
        "docs/diagram-native-additions/",
    )
    exact = {
        "_config.yml",
        "Gemfile",
        "Gemfile.lock",
        "docs/diagram-catalog.json",
        "docs/diagram-downloads.json",
        "docs/diagram-fhd-reviews.json",
        "docs/diagram-webp-release.json",
        "docs/diagram-native-additions.json",
        MANIFEST,
        "kkamji_scripts/blog/fhd_svg.py",
    }
    from downloads import FHD_AUTHOR_INPUTS
    exact.update(FHD_AUTHOR_INPUTS)
    if any(path in exact or path.startswith(prefixes) for path in paths):
        return True
    if any(path.startswith("assets/img/") and _diagram_bound_image(root, path) for path in paths):
        return True
    if any(path.startswith("_posts/") for path in paths):
        diff = subprocess.check_output(
            ["git", "diff", "--cached", "--unified=0", "--", "_posts"],
            cwd=root,
            text=True,
        )
        from downloads import INCLUDE

        changed_lines = "\n".join(
            line[1:] for line in diff.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )
        # Removing/replacing a diagram cover must trigger too, even if the new
        # image path no longer belongs to this corpus: the removed line still
        # carries the diagram URL. Ordinary covers and prose stay out, so a new
        # post with a regular image.path does not demand a diagram reexport.
        import re
        return (INCLUDE.search(changed_lines) is not None
                or '/assets/img/diagrams/' in changed_lines
                or re.search(r"""^\s*["']?arc_diagram_fixed_fhd["']?\s*:""", changed_lines, re.M) is not None)
    return False


def verify_staged(root):
    from downloads import source_snapshot, validate_source
    from pipeline import digest, fingerprint, png_dimensions

    root = Path(root).resolve()
    helper = root / '_includes/diagrams/download.html'
    if ((root / 'docs/diagram-webp-release.json').exists()
            or helper.is_file() and '.webp' in helper.read_text()):
        from webp_release import verify_staged as verify_webp_staged
        return verify_webp_staged(root)
    plan = validate_source(root)
    payload = json.loads((root / MANIFEST).read_text())
    snapshot = source_snapshot(root)
    if payload.get("status") != "export-and-check-passed":
        raise ValueError("release manifest is not checked")
    if payload.get("source_fingerprint") != fingerprint(snapshot):
        raise ValueError(
            "source fingerprint changed; build, export and release-check again"
        )
    catalog = json.loads((root / 'docs/diagram-catalog.json').read_text())['diagrams']
    if (root / 'kkamji_scripts/blog/fhd_svg.py').is_file() and payload.get('schema') != 2:
        raise ValueError('FHD sources require a fully reviewed schema 2 release')
    if payload.get('schema') == 2:
        if (payload.get('source_count') != len(catalog) or payload.get('visual_review') != 'all-sources-passed'
                or payload.get('semantic_review') != 'all-sources-passed'):
            raise ValueError('full FHD source visual/semantic review is incomplete')
        review_file = root / 'docs/diagram-fhd-reviews.json'
        if payload.get('review_file') != 'docs/diagram-fhd-reviews.json' or digest(review_file.read_bytes()) != payload.get('review_file_sha256'):
            raise ValueError('FHD review evidence changed or is missing')
        reviews = json.loads(review_file.read_text()).get('sources', [])
        by_include = {row['include']: row for row in reviews}
        if (len(by_include) != len(reviews) or set(by_include) != {row['include'] for row in catalog}
                or any(row.get('visual_status') != 'passed' or row.get('semantic_status') != 'passed'
                       or not row.get('notes') or not row.get('reviewed_at') for row in reviews)):
            raise ValueError('FHD visual/semantic review coverage is incomplete')
        for include, review in by_include.items():
            svg = root / 'assets/img/diagrams/fhd-svg' / include.removeprefix('diagrams/').replace('.html', '.svg')
            if review.get('svg_sha256') != digest(svg.read_bytes()):
                raise ValueError('FHD authored SVG differs from its visual review')
    expected = {e["png"]: e for e in plan["entries"]}
    actual = {e["png"]: e for e in payload["entries"]}
    if (
        len(actual) != len(payload["entries"])
        or set(actual) != set(expected)
        or payload.get("reference_count") != len(expected)
        or payload.get("post_count") != plan["post_count"]
    ):
        raise ValueError("release entry coverage differs from source")
    required = set(snapshot) | {MANIFEST}
    if payload.get('schema') == 2:
        required.add('docs/diagram-fhd-reviews.json')
        unused = payload.get('unused_entries', [])
        if len({row['include'] for row in unused}) != len(unused) or {row['include'] for row in unused} != set(plan['unused_includes']):
            raise ValueError('unused FHD source coverage differs')
        for row in unused:
            expected_png = '/assets/img/diagrams/fhd-unused/' + row['include'].removeprefix('diagrams/').removesuffix('.html') + '.png'
            if row['png'] != expected_png:
                raise ValueError('unused FHD PNG identity differs')
            raw = _png_path(root, row['png']).read_bytes()
            if png_dimensions(raw) != [1920,1080] or row.get('dimensions') != [1920,1080] or digest(raw) != row['png_sha256']:
                raise ValueError('unused FHD PNG changed or invalid')
            required.add(row['png'].lstrip('/'))
            if by_include[row['include']].get('png_sha256') != row['png_sha256']:
                raise ValueError('unused PNG differs from its visual review')
    for png, row in actual.items():
        if any(row[k] != expected[png][k] for k in ("post", "include", "figure")):
            raise ValueError("release entry identity differs from source")
        raw = _png_path(root, png).read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or digest(raw) != row["png_sha256"]:
            raise ValueError("public PNG changed or is invalid: " + png)
        if png_dimensions(raw) != [1920, 1080] or row.get("dimensions") != [1920, 1080]:
            raise ValueError("public PNG is not exact FHD: " + png)
        if payload.get('schema') == 2 and by_include[row['include']].get('png_sha256') != row['png_sha256']:
            raise ValueError('occurrence PNG differs from its visual review')
        required.add(png.lstrip("/"))
    tracked = set(
        subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
        .decode()
        .split("\0")
    )
    missing = required - tracked
    local_artifacts = {
        p
        for p in missing
        if p in snapshot
        and (
            p == "Gemfile.lock"
            or any(part in (".jekyll-cache", "_site") for part in Path(p).parts)
        )
    }
    if local_artifacts:
        ignored = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            cwd=root,
            input="\0".join(sorted(local_artifacts)).encode() + b"\0",
            capture_output=True,
        )
        if ignored.returncode not in (0, 1):
            raise ValueError("cannot verify local artifact ignore policy")
        confirmed = set(ignored.stdout.decode().split("\0")) & local_artifacts
        required -= confirmed
    if not required.issubset(tracked):
        raise ValueError("validated input or PNG is absent from index")
    changed = subprocess.run(
        ["git", "diff", "--quiet", "--"] + [":(literal)" + p for p in sorted(required)],
        cwd=root,
    )
    if changed.returncode:
        raise ValueError("index differs from validated working-tree bytes")
    return {"references": len(expected), "passed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--if-staged", action="store_true")
    args = parser.parse_args()
    try:
        if args.if_staged and not staged_requires_verification(args.root):
            print(json.dumps({"skipped": True, "reason": "no staged diagram changes"}))
        else:
            print(json.dumps(verify_staged(args.root)))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, "Diagram release blocked: " + str(error) + "\n")
