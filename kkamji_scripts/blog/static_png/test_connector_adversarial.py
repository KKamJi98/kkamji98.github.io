import os
import threading
import unittest
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from pipeline import (
    QuietHandler,
    load_bundle,
    deterministic_css,
    await_assets,
    AUDIT,
    gate,
)
from connector_audit import inspect_connectors

CASES = [
    (
        "key-missing-caret-side",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-link::after{border-top-color:transparent!important}",
        None,
    ),
    ("mobile-positive", "litellm-gateway", "litellm-virtual-key-flow", None, None),
    (
        "mobile-condition-negative",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-outcome::before{width:20px!important}",
        None,
    ),
    ("loop-positive", "gitops-kubernetes-4w", "gitops-control-loop", None, None),
    (
        "loop-invisible-head",
        "gitops-kubernetes-4w",
        "gitops-control-loop",
        ".sd-loop::after{opacity:0!important}",
        None,
    ),
    (
        "loop-invisible-rail",
        "gitops-kubernetes-4w",
        "gitops-control-loop",
        ".sd-loop::before{visibility:hidden!important}",
        None,
    ),
    (
        "loop-missing-role-and-paint",
        "gitops-kubernetes-4w",
        "gitops-control-loop",
        ".sd-loop::before,.sd-loop::after{content:none!important}",
        "document.querySelector('.sd-loop').removeAttribute('data-connector-role')",
    ),
    ("key-positive", "litellm-gateway", "litellm-virtual-key-flow", None, None),
    (
        "key-invisible-head",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-link::after{opacity:0!important}",
        None,
    ),
    (
        "key-invisible-shaft",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-link{background:none!important}",
        None,
    ),
    (
        "key-invisible-fork",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-fork::before,.sd-v2-fork::after{opacity:0!important}",
        None,
    ),
    (
        "key-condition-regression",
        "litellm-gateway",
        "litellm-virtual-key-flow",
        ".sd-v2-outcome::before{height:16px!important}",
        None,
    ),
    ("reference-positive", "valut-vso-in-k8s-8w", "vault-secrets-operator", None, None),
    (
        "reference-caption-source",
        "valut-vso-in-k8s-8w",
        "vault-secrets-operator",
        None,
        "document.querySelector('[data-connector-role=reference]').setAttribute('data-from','vault-secrets-operator-title')",
    ),
    (
        "reference-invisible-head",
        "valut-vso-in-k8s-8w",
        "vault-secrets-operator",
        "[data-connector-role=reference]::after{opacity:0!important}",
        None,
    ),
]


class AdversarialConnectorTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("DIAGRAM_SITE"), "fresh built articles required"
    )
    def test_reviewed_positive_and_negative_articles(self):
        root = Path(__file__).resolve().parents[3]
        site = Path(os.environ["DIAGRAM_SITE"])
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(site))
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        fonts = load_bundle(root / "assets/fonts/deterministic-export/lock.json")
        bundle = load_bundle(root / "assets/fonts/static-png/lock.json")
        bundle.update(fonts)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for name, post, fid, css, js in CASES:
                    with self.subTest(name=name):
                        page = browser.new_page(
                            viewport={
                                "width": 360 if name.startswith("mobile") else 1280,
                                "height": 1000,
                            },
                            device_scale_factor=2,
                        )

                        def route(r):
                            u = r.request.url
                            if r.request.resource_type == "script":
                                r.abort()
                            elif u.startswith(base + "/"):
                                r.continue_()
                            elif u in bundle:
                                r.fulfill(
                                    body=bundle[u]["body"],
                                    content_type=bundle[u]["content_type"],
                                )
                            else:
                                r.abort()

                        page.route("**/*", route)
                        page.goto(base + "/posts/" + post + "/", wait_until="load")
                        page.add_style_tag(content=deterministic_css(fonts))
                        f = page.locator("#" + fid)
                        if not name.startswith("mobile"):
                            f.evaluate(
                                '(f)=>{const s=getComputedStyle(f);f.style.width=(625+parseFloat(s.paddingLeft)+parseFloat(s.paddingRight)+2)+"px";f.style.maxWidth="none"}'
                            )
                        if css:
                            page.add_style_tag(content=css)
                        if js:
                            page.evaluate(js)
                        f.scroll_into_view_if_needed()
                        await_assets(f)
                        result = inspect_connectors(page, "#" + fid)
                        metrics = f.evaluate(AUDIT)
                        metrics["connector_issues"] = result["issues"]
                        self.assertEqual(
                            gate(metrics), name.endswith("-positive"), result
                        )
                        page.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
