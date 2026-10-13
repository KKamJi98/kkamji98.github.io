#!/usr/bin/env python3
"""Render the authored FHD SVG through Aside only, keeping fresh build evidence.

Each invocation opens and closes its own verification tab. Native PNGs are
rendered 1:1 from the preserved-source SVG, never resized from an old image.
Automated rendering does not certify the separate visual/semantic review.
"""

import argparse
import json
import re
import struct
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from downloads import built_assets_snapshot, source_snapshot, validate_source
from fhd_reuse import native_inputs, style_hash
from pipeline import digest, fingerprint


def png_dimensions(raw):
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    return list(struct.unpack(">II", raw[16:24]))


def unused_png(include):
    return (
        "/assets/img/diagrams/fhd-unused/"
        + include.removeprefix("diagrams/").removesuffix(".html")
        + ".png"
    )


def windows_path(value):
    match = re.fullmatch(r"([a-zA-Z]):\\(.+)", value)
    if not match:
        raise ValueError("Aside did not return an absolute Windows artifact path")
    path = Path("/mnt") / match[1].lower() / match[2].replace("\\", "/")
    if not path.is_dir():
        raise ValueError("Aside artifact directory is inaccessible in WSL")
    return path


def build_guard(root, site):
    plan = validate_source(root)
    stamp = json.loads((site / ".diagram-download-build.json").read_text())
    if stamp["source"] != source_snapshot(root):
        raise ValueError("source changed; make a fresh verification build")
    html = {
        p.relative_to(site).as_posix(): digest(p.read_bytes())
        for p in sorted(site.rglob("*.html"))
    }
    if stamp["html"] != html or stamp["assets"] != built_assets_snapshot(site, plan):
        raise ValueError("built HTML/assets changed; make a fresh verification build")
    if not (site / "diagrams/fhd-proof/index.html").is_file():
        raise ValueError(
            "build with DIAGRAM_FHD_PROOF=1 to emit the same-source fixture"
        )
    return plan, stamp


RENDER = r"""
const config = CONFIG;
let proof;
try {
  proof = await openTab(config.base + '/diagrams/fhd-proof/');
  console.log((await snapshot(proof, {selector:'#proof-index'})).tree);
  const fontHref = await proof.locator('#proof-font').getAttribute('href');
  const fontURL = new URL(fontHref, config.base).href;
  if (new URL(fontURL).origin !== new URL(config.base).origin) throw Error('cross-origin font');
  const fontResponse = await fetch(fontURL);
  if (!fontResponse.ok) throw Error('font fetch failed');
  const font = Buffer.from(await fontResponse.arrayBuffer());
  if (font.length !== config.fontBytes) throw Error('pinned font byte count differs');
  const fontData = font.toString('base64');
  await proof.locator('body').evaluate((e,p) => {
    window.fhdPinnedFont = p;
    document.fonts.load('28px "SD FHD Sans"','가나다 ABC 123').then(()=>{e.dataset.fhdFontsReady='true';});
  },fontData);
  await proof.locator('body[data-fhd-fonts-ready="true"]').waitFor({state:'attached',timeout:30000});
  const directory = './artifacts/' + config.directory;
  await fs.mkdir(directory, {recursive:true});
  const fixtureResponse=await fetch(proof.url());
  if(!fixtureResponse.ok)throw Error('fixture HTTP read failed');
  await fs.writeFile(directory+'/fixture.html',Buffer.from(await fixtureResponse.arrayBuffer()));
  await fs.writeFile(directory + '/pinned-font.ttf', font);
  const results = [];
  for (const target of config.targets) {
    const selector = '.proof-card[data-index="'+target.index+'"]';
    console.log((await snapshot(proof, {selector, showHidden:true})).tree);
    const card = proof.locator(selector);
    const source = await card.evaluate(e => ({include:e.dataset.include,
      hash:e.querySelector('svg').dataset.sourceSha256,
      images:[...e.querySelectorAll('svg image')].map(i=>i.getAttribute('href'))}));
    if (source.include !== target.include || source.hash !== target.source_sha256) throw Error('source identity differs');
    const images = {};
    for (const href of new Set(source.images)) {
      const url = new URL(href, config.base);
      if (url.origin !== new URL(config.base).origin || !url.pathname.startsWith('/assets/')) throw Error('untrusted SVG image');
      const response = await fetch(url.href);
      if (!response.ok) throw Error('source image fetch failed: '+href);
      const type = (response.headers.get('content-type')||'').split(';')[0];
      if (!['image/png','image/jpeg','image/webp','image/svg+xml'].includes(type)) throw Error('unsupported source image type');
      const bytes = Buffer.from(await response.arrayBuffer());
      images[href] = 'data:'+type+';base64,'+bytes.toString('base64');
    }
    const metrics = await card.evaluate((e,p) => {
      const svg = e.querySelector('svg');
      const rect = svg.getBoundingClientRect();
      const issues = [];
      if (rect.width !== 1920 || rect.height !== 1080 || svg.getAttribute('viewBox') !== '0 0 1920 1080') issues.push('canvas-dimensions');
      if (svg.querySelector('script,foreignObject,a,animate,animateTransform,set')) issues.push('active-svg');
      for (const t of svg.querySelectorAll('text')) {
        const r=t.getBBox();
        if (r.x<31 || r.y<31 || r.x+r.width>1889 || r.y+r.height>1049) issues.push('text-outside:'+t.dataset.source);
        if (Number(t.getAttribute('font-size'))<14) issues.push('small-text:'+t.dataset.source);
        const owner=[...svg.querySelectorAll('rect[data-node]')].find(n=>n.dataset.node===t.dataset.source);
        if(owner){const b=owner.getBBox();if(r.x<b.x-0.5||r.y<b.y-0.5||r.x+r.width>b.x+b.width+0.5||r.y+r.height>b.y+b.height+0.5)issues.push('text-outside-node:'+t.dataset.source);}
      }
      for (const edge of svg.querySelectorAll('path[data-edge]')) {
        if (!edge.getAttribute('data-from') || !edge.getAttribute('data-to') || getComputedStyle(edge).stroke==='none' || Number(getComputedStyle(edge).strokeWidth)<2) issues.push('unpainted-edge:'+edge.dataset.edge);
      }
      const clone=svg.cloneNode(true);
      const ns='http://www.w3.org/2000/svg';
      const defs=document.createElementNS(ns,'defs'),style=document.createElementNS(ns,'style');
      style.textContent='@font-face{font-family:FHD;src:url(data:font/ttf;base64,'+window.fhdPinnedFont+');font-weight:100 900}text{font-family:FHD}';
      defs.appendChild(style);clone.insertBefore(defs,clone.firstChild);
      clone.removeAttribute('aria-hidden');
      for(const i of clone.querySelectorAll('image')) i.setAttribute('href',p.images[i.getAttribute('href')]);
      const old=document.getElementById('fhd-export-canvas');if(old)old.remove();
      const canvas=document.createElement('canvas');canvas.id='fhd-export-canvas';canvas.width=1920;canvas.height=1080;
      canvas.style.display='none';document.body.appendChild(canvas);
      const image=new Image();const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml'}));
      image.onload=()=>{canvas.getContext('2d').drawImage(image,0,0);canvas.dataset.fhdReady='true';URL.revokeObjectURL(url);};
      image.onerror=()=>{canvas.dataset.fhdError='true';URL.revokeObjectURL(url);};image.src=url;
      return {issues,canvas:[rect.width,rect.height],viewBox:svg.getAttribute('viewBox'),nodes:svg.querySelectorAll('[data-node]').length,
        edges:svg.querySelectorAll('path[data-edge]').length,text:svg.querySelectorAll('text').length,
        browser:navigator.userAgent,fontFamily:getComputedStyle(svg.querySelector('text')).fontFamily};
    },{images});
    await proof.locator('#fhd-export-canvas[data-fhd-ready="true"]').waitFor({state:'attached',timeout:30000});
    const result=await proof.locator('#fhd-export-canvas').evaluate(c=>({data:c.toDataURL('image/png'),size:[c.width,c.height],white:[...c.getContext('2d').getImageData(0,0,1,1).data]}));
    if (result.size[0]!==1920||result.size[1]!==1080) throw Error('PNG canvas differs');
    if (result.white.join(',')!=='255,255,255,255') throw Error('PNG white background differs');
    const filename=String(target.index).padStart(3,'0')+'.png';
    await fs.writeFile(directory+'/'+filename,Buffer.from(result.data.split(',')[1],'base64'));
    results.push({...target,metrics,filename});
  }
  await fs.writeFile(directory+'/batch.json',JSON.stringify({results},null,2));
  console.log('FHD_RESULT='+JSON.stringify({directory:pwd+'\\artifacts\\'+config.directory,count:results.length}));
} finally {if (proof) await closeTab(proof);}
"""


def render_batch(root, site, out, base, targets, stamp):
    config = {
        "base": base,
        "directory": "fhd-batch-" + str(targets[0]["index"]),
        "targets": targets,
        "fontBytes": (root / "assets/fonts/deterministic-export/NotoSansKR[wght].ttf")
        .stat()
        .st_size,
    }
    code = RENDER.replace("CONFIG", json.dumps(config, ensure_ascii=False), 1)
    completed = subprocess.run(
        ["aside", "repl", "--host", "local", code],
        check=False,
        text=True,
        capture_output=True,
        timeout=135,
    )
    log = out / ("batch-" + str(targets[0]["index"]) + ".log")
    log.write_text(completed.stdout + completed.stderr)
    if completed.returncode:
        raise ValueError("Aside batch failed; see " + str(log))
    marker = re.search(r"^FHD_RESULT=(.+)$", completed.stdout, re.MULTILINE)
    if not marker:
        raise ValueError("Aside did not return artifact metadata; see " + str(log))
    artifact = windows_path(json.loads(marker[1])["directory"])
    if (
        digest((artifact / "fixture.html").read_bytes())
        != stamp["html"]["diagrams/fhd-proof/index.html"]
    ):
        raise ValueError("served fixture bytes differ from the fresh build")
    if digest((artifact / "pinned-font.ttf").read_bytes()) != digest(
        (root / "assets/fonts/deterministic-export/NotoSansKR[wght].ttf").read_bytes()
    ):
        raise ValueError("rendered font bytes differ from the pinned source")
    results = json.loads((artifact / "batch.json").read_text())["results"]
    if [r["index"] for r in results] != [r["index"] for r in targets]:
        raise ValueError("Aside batch coverage differs")
    saved = []
    for result in results:
        raw = (artifact / result["filename"]).read_bytes()
        dimensions = png_dimensions(raw)
        if dimensions != [1920, 1080]:
            raise ValueError("PNG is not exact FHD")
        directory = out / str(result["index"]).zfill(3)
        directory.mkdir(parents=True, exist_ok=True)
        png = directory / "diagram.png"
        png.write_bytes(raw)
        receipt = {
            **result,
            "png_sha256": digest(raw),
            "png_dimensions": dimensions,
            "build_identity": fingerprint(stamp),
            "artifact": str(artifact / result["filename"]),
            "font_sha256": digest((artifact / "pinned-font.ttf").read_bytes()),
            "automated_status": "passed"
            if not result["metrics"]["issues"]
            else "failed",
            "visual_review": "not-run",
            "semantic_review": "not-run",
        }
        inputs = native_inputs(
            root, site, result["include"], result["metrics"]["browser"], RENDER
        )
        if inputs["http_style_sha256"] != style_hash(
            (artifact / "fixture.html").read_text()
        ):
            raise ValueError("actual HTTP proof style differs from sealed render input")
        receipt.update(
            per_source_inputs=inputs, per_source_fingerprint=fingerprint(inputs)
        )
        (directory / "receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        )
        saved.append(receipt)
    build_guard(root, site)
    return saved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int)
    parser.add_argument("--batch-size", type=int, choices=range(1, 11), default=8)
    args = parser.parse_args(argv)
    parsed = urlsplit(args.base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or not parsed.port
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        parser.error("--base-url must be the approved local HTTP verification server")
    root, site, out = args.root.resolve(), args.site.resolve(), args.out.resolve()
    plan, stamp = build_guard(root, site)
    catalog = json.loads((root / "docs/diagram-catalog.json").read_text())["diagrams"]
    if args.count is None:
        args.count = len(catalog) - args.start
    if args.start < 0 or args.count < 1 or args.start + args.count > len(catalog):
        parser.error("requested source range is invalid")
    targets = []
    for index in range(args.start, args.start + args.count):
        record = catalog[index]
        svg = (
            root
            / "assets/img/diagrams/fhd-svg"
            / record["include"].removeprefix("diagrams/").replace(".html", ".svg")
        )
        source = re.search(r'data-source-sha256="([a-f0-9]{64})"', svg.read_text())
        if not source:
            raise ValueError("missing authored SVG source hash")
        targets.append(
            {
                "index": index,
                "include": record["include"],
                "source_sha256": source[1],
                "svg_sha256": digest(svg.read_bytes()),
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for offset in range(0, len(targets), args.batch_size):
        batch = render_batch(
            root,
            site,
            out,
            args.base_url.rstrip("/"),
            targets[offset : offset + args.batch_size],
            stamp,
        )
        # Native outputs stay in the review cache until all manual gates pass.
        build_guard(root, site)
        results.extend(batch)
        print(
            json.dumps(
                {
                    "rendered": len(results),
                    "requested": len(targets),
                    "automated_passed": sum(
                        r["automated_status"] == "passed" for r in results
                    ),
                    "visual_review": 0,
                    "semantic_review": 0,
                }
            ),
            flush=True,
        )
    report = {
        "build_identity": fingerprint(stamp),
        "requested": len(targets),
        "sources": results,
        "automated_passed": sum(r["automated_status"] == "passed" for r in results),
        "visual_review": 0,
        "semantic_review": 0,
        "mapped_occurrences": len(plan["entries"]),
    }
    (out / ("render-" + str(args.start) + "-" + str(args.count) + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return int(report["automated_passed"] != len(targets))


if __name__ == "__main__":
    raise SystemExit(main())
