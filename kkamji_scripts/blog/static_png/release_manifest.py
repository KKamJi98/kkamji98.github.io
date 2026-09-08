"""Fast source/PNG consistency gate for normal diagram commits."""

import argparse
import json
from pathlib import Path
import subprocess

MANIFEST = "docs/diagram-export-release.json"


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
    from pipeline import digest, fingerprint

    entries = []
    browsers = set()
    for row in rows:
        directory = out / fingerprint(row)[:24]
        receipt = json.loads(
            (directory / (row["figure"] + "-625-light.json")).read_text()
        )
        if (
            receipt["quality_status"] != "passed"
            or receipt["font_policy"]["profile"] != "deterministic-export"
        ):
            raise ValueError("unverified export receipt")
        raw = _png_path(root, row["png"]).read_bytes()
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
                    (directory / (row["figure"] + "-625-light.json")).read_bytes()
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


def staged_requires_verification(root):
    paths = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
    ).splitlines()
    prefixes = (
        "_includes/diagrams/",
        "assets/css/",
        "assets/fonts/",
        "assets/img/diagrams/",
        "kkamji_scripts/blog/static_png/",
    )
    exact = {
        "docs/diagram-catalog.json",
        "docs/diagram-downloads.json",
        MANIFEST,
        "_plugins/diagram-downloads.rb",
    }
    if any(path in exact or path.startswith(prefixes) for path in paths):
        return True
    if any(path.startswith("_posts/") for path in paths):
        diff = subprocess.check_output(
            ["git", "diff", "--cached", "--unified=0", "--", "_posts"],
            cwd=root,
            text=True,
        )
        return any(
            line.startswith(("+", "-")) and "{% include diagrams/" in line
            for line in diff.splitlines()
        )
    return False


def verify_staged(root):
    from downloads import source_snapshot, validate_source
    from pipeline import digest, fingerprint

    root = Path(root).resolve()
    plan = validate_source(root)
    payload = json.loads((root / MANIFEST).read_text())
    snapshot = source_snapshot(root)
    if payload.get("status") != "export-and-check-passed":
        raise ValueError("release manifest is not checked")
    if payload.get("source_fingerprint") != fingerprint(snapshot):
        raise ValueError(
            "source fingerprint changed; build, export and release-check again"
        )
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
    for png, row in actual.items():
        if any(row[k] != expected[png][k] for k in ("post", "include", "figure")):
            raise ValueError("release entry identity differs from source")
        raw = _png_path(root, png).read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or digest(raw) != row["png_sha256"]:
            raise ValueError("public PNG changed or is invalid: " + png)
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
