#!/usr/bin/env python3
"""Read-only full-corpus connector gate, including isolated unused includes."""
import argparse
from collections import Counter, defaultdict
from functools import partial
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer

from connector_audit import inspect_connectors
from corpus import Figures
from downloads import (
    ROOT,
    built_plan,
    validate_source,
    source_snapshot,
    built_assets_snapshot,
)
from pipeline import QuietHandler, digest, load_bundle, deterministic_css, await_assets


def install_export_css(page, css):
    page.evaluate(
        "css=>{const style=document.createElement('style');style.textContent=css;document.head.appendChild(style)}",
        css,
    )


def verify_seal(root, site, plan):
    stamp_path = site / ".diagram-download-build.json"
    stamp = json.loads(stamp_path.read_text())
    if stamp["source"] != source_snapshot(root):
        raise ValueError("source differs from stamped build")
    if stamp["assets"] != built_assets_snapshot(site, plan):
        raise ValueError("built assets changed")
    current = {
        str(p.relative_to(site)): digest(p.read_bytes())
        for p in sorted(site.rglob("*.html"))
    }
    if stamp["html"] != current:
        raise ValueError("built HTML changed")
    return digest(stamp_path.read_bytes())


def resolve_output(root, site, out):
    """Return the canonical external report path without touching source/build bytes."""
    out = out.resolve()
    if any(out.is_relative_to(path.resolve()) for path in (root, site)):
        raise ValueError("--out must be outside the source root and built site")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--site", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    root, site = args.root.resolve(), args.site.resolve()
    if root != ROOT.resolve():
        p.error("--root must be the executing checkout: " + str(ROOT.resolve()))
    try:
        out = resolve_output(root, site, args.out)
    except (ValueError, OSError, RuntimeError) as error:
        p.error(str(error))
    plan = validate_source(root)
    seal = verify_seal(root, site, plan)
    entries = built_plan(root, site, plan)
    for name in plan["unused_includes"]:
        html = (root / "_includes" / name).read_text()
        if "{%" in html or "{{" in html:
            raise ValueError("unused include needs a real Liquid harness: " + name)
        ids = Figures(html).ids
        if len(ids) != 1:
            raise ValueError("unused include needs unique figure: " + name)
        entries.append(
            {
                "include": name,
                "figure": ids[0],
                "post": None,
                "page": None,
                "html": html,
            }
        )
    entries.sort(key=lambda e: (e["page"] or "__unused__/" + e["include"], e["figure"]))
    bundle = load_bundle(root / "assets/fonts/static-png/lock.json")
    export = load_bundle(root / "assets/fonts/deterministic-export/lock.json")
    css = deterministic_css(export)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(site))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    results = []
    expected = len(entries) * 8
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = None
            page = None
            loaded = None
            for index, entry in enumerate(entries):
                if context is None or index % 20 == 0:
                    if context:
                        context.close()
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 1000},
                        device_scale_factor=2,
                        java_script_enabled=False,
                        locale="ko-KR",
                        timezone_id="UTC",
                    )

                    def route(request):
                        url = request.request.url
                        if url.startswith(origin + "/"):
                            if request.request.resource_type == "script":
                                request.abort()
                            else:
                                request.continue_()
                        elif url in export or url in bundle:
                            resource = export.get(url) or bundle[url]
                            request.fulfill(
                                body=resource["body"],
                                content_type=resource["content_type"],
                            )
                        elif url.startswith("data:"):
                            request.continue_()
                        else:
                            request.abort()

                    context.route("**/*", route)
                    page = context.new_page()
                    loaded = None
                assert page is not None
                if entry["page"]:
                    if loaded != entry["page"]:
                        page.goto(
                            origin + "/" + entry["page"],
                            wait_until="load",
                            timeout=30000,
                        )
                        install_export_css(page, css)
                        loaded = entry["page"]
                else:
                    page.goto(origin + "/", wait_until="load", timeout=30000)
                    page.set_content(
                        '<html><head><base href="'
                        + origin
                        + '/"><link rel="stylesheet" href="/assets/css/jekyll-theme-chirpy.css"><style>body{margin:0;padding:16px}</style></head><body><div id="main-wrapper"><main><div class="content">'
                        + entry["html"]
                        + "</div></main></div></body></html>",
                        wait_until="load",
                    )
                    install_export_css(page, css)
                    loaded = None
                figure_id = entry["figure"]
                selector = (
                    'figure.sd[id="'
                    + figure_id
                    + '"], figure.sd:not([id])[aria-labelledby="'
                    + figure_id
                    + '"]'
                )
                figure = page.locator(selector)
                if figure.count() != 1:
                    raise ValueError("non-unique rendered figure: " + figure_id)
                figure.locator("img").evaluate_all(
                    '(xs)=>xs.forEach(x=>x.loading="eager")'
                )
                for theme in ("light", "dark"):
                    for width in (360, 390, 625, 720):
                        row = {k: v for k, v in entry.items() if k != "html"}
                        row.update(
                            theme=theme,
                            width=width,
                            surface=(
                                "built-article" if entry["page"] else "isolated-unused"
                            ),
                            width_kind=(
                                "native-viewport"
                                if width < 400
                                else "exact-figure-content"
                            ),
                        )
                        try:
                            page.set_viewport_size(
                                {
                                    "width": width if width < 400 else 1280,
                                    "height": 1000,
                                }
                            )
                            page.evaluate(
                                '(t)=>document.documentElement.setAttribute("data-mode",t)',
                                theme,
                            )
                            if width < 400:
                                page.locator(".content").first.evaluate(
                                    '(e,w)=>{e.style.removeProperty("width");e.style.removeProperty("max-width");if(w){e.style.width=w+"px";e.style.maxWidth="none"}}',
                                    width - 32 if entry["page"] is None else None,
                                )
                            else:
                                extra = figure.evaluate(
                                    "e=>{const s=getComputedStyle(e);return parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+parseFloat(s.borderLeftWidth)+parseFloat(s.borderRightWidth)}"
                                )
                                page.locator(".content").first.evaluate(
                                    '(e,w)=>{e.style.width=w+"px";e.style.maxWidth=w+"px"}',
                                    width + extra,
                                )
                            await_assets(figure)
                            figure.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                            await_assets(figure)
                            content = figure.evaluate(
                                "e=>{const s=getComputedStyle(e);return e.getBoundingClientRect().width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth)}"
                            )
                            if width >= 400 and abs(content - width) > 0.05:
                                raise ValueError(
                                    "incorrect content width: " + str(content)
                                )
                            measurements = inspect_connectors(page, selector)
                            row.update(
                                content_width=content,
                                measurements=measurements,
                                status="failed" if measurements["issues"] else "passed",
                            )
                        except Exception as error:
                            row.update(status="error", error=str(error))
                        results.append(row)
                if index % 20 == 0:
                    print(
                        json.dumps(
                            {"scanned_occurrences": index + 1, "cases": len(results)}
                        ),
                        flush=True,
                    )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    if verify_seal(root, site, plan) != seal:
        raise ValueError("build seal changed during scan")
    includes = defaultdict(list)
    for row in results:
        includes[row["include"]].append(row)
    summary = {
        "components": len(includes),
        "used_occurrences": plan["reference_count"],
        "unused_includes": len(plan["unused_includes"]),
        "expected_cases": expected,
        "cases": len(results),
        "statuses": dict(Counter(r["status"] for r in results)),
        "passed": len(results) == expected
        and all(r["status"] == "passed" for r in results),
    }
    report = {
        "summary": summary,
        "build_seal_sha256": seal,
        "visual_review": "not-performed-by-this-scanner",
        "font_glyph_verification": "separate export/check gate",
        "include_status": {
            name: {
                "cases": len(rows),
                "passed": all(r["status"] == "passed" for r in rows),
            }
            for name, rows in sorted(includes.items())
        },
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
