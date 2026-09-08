"""AI connector paint must fit its layout box without relaxing the audit."""
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright
from pipeline import AUDIT, gate


class AIConnectorGeometryTests(unittest.TestCase):
    def test_real_ai_proxy_attachment_and_overflow(self):
        import os
        root = Path(__file__).resolve().parents[3]
        if 'DIAGRAM_SITE' not in os.environ:
            self.skipTest('DIAGRAM_SITE must point to a fresh Jekyll production build')
        site = Path(os.environ['DIAGRAM_SITE'])
        compiled = (site / 'assets/css/jekyll-theme-chirpy.css').read_text()
        source = (root / 'assets/css/jekyll-theme-chirpy.scss').read_text()
        css = source.split('/* BEGIN AI GATEWAY V2 */', 1)[1].split('/* END AI GATEWAY V2 */', 1)[0]
        names = ['litellm-architecture', 'litellm-virtual-key-flow', 'llm-gateway-position',
                 'gateway-plane-compare', 'envoy-ai-gateway-crd-flow']
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 1000})
            for theme in ['light', 'dark']:
                for width in [360, 390, 625, 720]:
                    for name in names:
                        with self.subTest(theme=theme, width=width, figure=name):
                            html = (root / f'_includes/diagrams/static/ai/{name}.html').read_text()
                            page.set_content(f'<html data-mode="{theme}"><style>{compiled}\n{css}</style>'
                                             f'<main><div class="content">{html}</div></main></html>')
                            fig = page.locator('figure')
                            fig.evaluate('(e,w)=>{e.style.width=w+"px";e.style.maxWidth="none"}', width)
                            metrics = fig.evaluate(AUDIT)
                            self.assertTrue(gate(metrics), metrics)
                            for rail in page.locator('.sd-v2-rail:has(+ .sd-v2-adjunct)').all():
                                geometry = rail.evaluate('''e => {
                                  const p=e.querySelector('.sd-node--accent'), r=p.getBoundingClientRect();
                                  const a=e.nextElementSibling.querySelector('.sd-v2-relation').getBoundingClientRect();
                                  const mobile=getComputedStyle(e).gridTemplateColumns.split(' ').length===1;
                                  const s=getComputedStyle(p,'::before');
                                  return {mobile, gap:a.top-r.bottom,
                                    sourceGap:mobile ? parseFloat(s.right)-p.clientWidth : 0,
                                    height:r.height};
                                }''')
                                if not geometry['mobile']:
                                    self.assertAlmostEqual(geometry['gap'], 0, delta=1,
                                                           msg=f'{name}: {geometry}')
                                else:
                                    self.assertAlmostEqual(geometry['sourceGap'], 0, delta=1,
                                                           msg=f'{name}: {geometry}')
            browser.close()

    def test_vertical_connector_boxes_contain_arrowheads(self):
        root = Path(__file__).resolve().parents[3]
        source = (root / 'assets/css/jekyll-theme-chirpy.scss').read_text()
        css = source.split('/* BEGIN AI GATEWAY V2 */', 1)[1].split('/* END AI GATEWAY V2 */', 1)[0]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            for width in [294, 324, 625, 720]:
                with self.subTest(content_width=width):
                    page.set_content(f'''<style>
                    * {{ box-sizing: border-box; }}
                    figure {{ container-type:inline-size; --sd-accent:teal;
                              font-size:16px; width:{width + 48}px; }}
                    {css}</style>
                    <figure class="sd sd--gateway-v2"><div>Selectable text</div>
                    <div class="sd-v2-rail"><div>Application</div>
                    <div class="sd-v2-link" aria-hidden="true"></div>
                    <div>Proxy</div><div class="sd-v2-link" aria-hidden="true"></div>
                    <div>Provider</div></div>
                    <div class="sd-v2-down" aria-hidden="true"></div></figure>''')
                    metrics = page.locator('figure').evaluate(AUDIT)
                    self.assertTrue(gate(metrics), metrics)
                    # Real clipping remains a failure, even on a connector class.
                    page.locator('.sd-v2-down').evaluate("e=>{e.style.overflow='hidden';e.textContent='Clipped text'}")
                    self.assertFalse(gate(page.locator('figure').evaluate(AUDIT)))
            browser.close()


if __name__ == '__main__':
    unittest.main()
