"""Connector failures must be blocking, not merely recorded diagnostics."""

import unittest
from pipeline import gate


class ConnectorGateTests(unittest.TestCase):
    def test_arrow_clearance_failure_rejects_otherwise_clean_figure(self):
        metrics = {
            key: []
            for key in (
                "overflow",
                "small",
                "hidden",
                "unselectable",
                "broken",
                "interaction",
            )
        }
        metrics["connector_issues"] = [
            {"kind": "target-clearance", "gap": 0, "minimum": 8}
        ]
        self.assertFalse(gate(metrics))

    def test_export_rejects_painted_arrow_touching_target(self):
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile

        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            site = temp / "site"
            site.mkdir()
            (site / "index.html").write_text(
                """<!doctype html><html><head><style>
              * {box-sizing:border-box} body {margin:0}
              figure {margin:0;padding:16px;width:100%;background:white;color:black}
              .sd-title {font-size:22px} .sd-label {font-size:16px} .sd-detail,code {font-size:14px}
              .sd-v2-issuance-row {display:grid;grid-template-columns:minmax(0,1fr) 24px minmax(0,1fr);align-items:center}
              .sd-v2-link {position:relative;width:24px;height:2px;background:teal}
              .sd-v2-link::after {content:"";position:absolute;right:0;top:50%;width:8px;height:8px;border-right:2px solid teal;border-top:2px solid teal;transform:translateY(-50%) rotate(45deg)}
              </style></head><body><main><div class="content">
              <figure class="sd sd--gateway-v2" id="fixture">
              <figcaption class="sd-title">Connector test</figcaption>
              <div class="sd-v2-issuance-row"><span class="sd-detail">Source</span><div class="sd-v2-link" aria-hidden="true"></div><span class="sd-detail">Target boundary</span></div>
              <p class="sd-detail">한국어 <code>code</code></p>
              </figure></div></main></body></html>"""
            )
            command = [
                sys.executable,
                str(Path(__file__).with_name("pipeline.py")),
                "--site",
                str(site),
                "--page",
                "index.html",
                "--figure",
                "fixture",
                "--out",
                str(temp / "out"),
                "--font-profile",
                "deterministic-export",
            ]
            env = dict(
                os.environ,
                FONTCONFIG_FILE=str(
                    root / "assets/fonts/deterministic-export/fontconfig.conf"
                ),
            )
            result = subprocess.run(
                command, env=env, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            import json

            receipt = json.loads((temp / "out/fixture-625-light.json").read_text())
            self.assertTrue(receipt["quality"]["desktop"]["connector_issues"])
            balanced = (
                (site / "index.html")
                .read_text()
                .replace(
                    "</style>",
                    """
              .sd-v2-issuance-row {grid-template-columns:max-content minmax(40px,1fr) max-content}
              .sd-v2-link {width:16px;justify-self:center}
              .sd-v2-link::after {right:2px}
              </style>""",
                )
            )
            (site / "index.html").write_text(balanced)
            result = subprocess.run(
                command, env=env, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                command + ["--check"],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_export_rejects_generic_chevron_intruding_into_card(self):
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            site = temp / "site"
            site.mkdir()
            (site / "index.html").write_text(
                """<!doctype html><html><head><style>
              *{box-sizing:border-box}body{margin:0}figure{margin:0;padding:16px;width:100%;background:white;color:black}
              .sd-title{font-size:22px}.sd-label{font-size:16px}.sd-detail,code{font-size:14px}
              .sd-node{border:1px solid gray;padding:8px}
              .sd-arrow{display:flex;min-height:36px;flex-direction:column;align-items:center;justify-content:center;gap:3.2px}
              .sd-edge-label{font-size:14px;line-height:21.7px}
              .sd-arrow::after{content:"";width:10.4px;height:10.4px;border-right:2px solid teal;border-bottom:2px solid teal;transform:rotate(45deg)}
              </style></head><body><main><div class="content"><figure class="sd" id="fixture">
              <figcaption class="sd-title">Nested connector test</figcaption><section class="sd-lane">
              <div class="sd-node"><strong class="sd-label">Source</strong></div>
              <div class="sd-arrow"><span class="sd-edge-label">Forward</span></div>
              <div class="sd-node"><strong class="sd-label">Target</strong></div></section>
              <p class="sd-detail">한국어 <code>code</code></p></figure></div></main></body></html>"""
            )
            command = [
                sys.executable,
                str(Path(__file__).with_name("pipeline.py")),
                "--site",
                str(site),
                "--page",
                "index.html",
                "--figure",
                "fixture",
                "--out",
                str(temp / "out"),
                "--font-profile",
                "deterministic-export",
            ]
            env = dict(
                os.environ,
                FONTCONFIG_FILE=str(
                    root / "assets/fonts/deterministic-export/fontconfig.conf"
                ),
            )
            result = subprocess.run(
                command, env=env, capture_output=True, text=True, timeout=60
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            import json

            receipt = json.loads((temp / "out/fixture-625-light.json").read_text())
            self.assertTrue(receipt["quality"]["desktop"]["connector_issues"])


if __name__ == "__main__":
    unittest.main()
