"""Border-polygon geometry classification shared by corpus and export checks."""

import re

COLLECT = r"""f => {
 const box=r=>({x:r.x,y:r.y,w:r.width,h:r.height});
 const style=s=>({content:s.content,display:s.display,background:s.backgroundImage,backgroundSize:s.backgroundSize,backgroundPosition:s.backgroundPosition,backgroundRepeat:s.backgroundRepeat,color:s.backgroundColor,transform:s.transform,visibility:s.visibility,opacity:parseFloat(s.opacity),radii:['TopLeft','TopRight','BottomRight','BottomLeft'].map(k=>s['border'+k+'Radius']),borders:['Top','Right','Bottom','Left'].map(k=>({width:parseFloat(s['border'+k+'Width']),style:s['border'+k+'Style'],color:s['border'+k+'Color']}))});
 const text=e=>{if(!e)return [];let w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),n,a=[];while(n=w.nextNode()){if(!n.textContent.trim())continue;let r=document.createRange();r.selectNodeContents(n);for(const b of r.getClientRects())if(b.width&&b.height)a.push({...box(b),text:n.textContent.trim().slice(0,100)})}return a};

 let elements=[f,...f.querySelectorAll('*')];let result=[];
 const hiddenElement=e=>{for(let n=e;n;n=n.parentElement){const s=getComputedStyle(n);if(s.display==='none'||['hidden','collapse'].includes(s.visibility)||parseFloat(s.opacity)<0.01)return true}const b=e.getBoundingClientRect();return !b.width&&!b.height};
 const matching=id=>elements.filter(e=>id&&e.id===id);
 const ref=id=>{const found=matching(id);return {id,count:found.length,...(found.length===1?{hidden:hiddenElement(found[0]),box:box(found[0].getBoundingClientRect()),cls:found[0].getAttribute('class')||'',text:text(found[0])}:{})}};
 for(let i=0;i<elements.length;i++){
 let e=elements[i],s=getComputedStyle(e),b=e.getBoundingClientRect(),before=getComputedStyle(e,'::before'),after=getComputedStyle(e,'::after');
 const key=(f.id||f.getAttribute('aria-labelledby'))+':'+i;
 let cls=typeof e.className==='string'?e.className:e.getAttribute('class')||'';
 let role=e.getAttribute('data-connector-role')||'';
 let known=/sd-arrow|sd-loop|sd-reference|sd-v2-(link|down|fork|relation)|branch|connector/.test(cls)||!!role||(f.id==='jev-decision-pipeline'&&cls.includes('sd-jev-'));
 let pseudo=[before,after].some(p=>p.content!=='none'&&p.content!=='normal'&&p.display!=='none');
 let thin=(b.width<=4||b.height<=4)&&b.width*b.height>0;
 let svg=e instanceof SVGElement;
 if(!(known||pseudo||thin||svg))continue;
 let hidden=hiddenElement(e);
 if(hidden&&!known)continue;
 let prev=e.previousElementSibling,next=e.nextElementSibling;
 let from=e.getAttribute('data-from'),to=e.getAttribute('data-to'),targets=matching(to),sources=matching(from);
 let following=e.parentElement.nextElementSibling;
 let loopNodes=role==='loop'?[...e.querySelectorAll('.sd-node')]:[];
 result.push({id:key,index:i,tag:e.tagName,role,hidden,sourceRef:ref(from),targetRef:ref(to),
 loopOrderValid:role==='loop'&&sources.length===1&&targets.length===1&&loopNodes.length>0&&sources[0]===loopNodes[loopNodes.length-1]&&targets[0]===loopNodes[0],
 targetIsLocal:targets.length===1&&!!next&&(next===targets[0]||next.contains(targets[0])),
 sourceInside:sources.length===1&&e.contains(sources[0]),targetInside:targets.length===1&&e.contains(targets[0]),
 lastSibling:e===e.parentElement.lastElementChild,
 following:following?{cls:following.getAttribute('class')||'',box:box(following.getBoundingClientRect()),text:text(following)}:null,svgData:svg?{path:e.getAttribute('d'),strokeWidth:e.getAttribute('stroke-width'),dasharray:e.getAttribute('stroke-dasharray')}:null,cls,box:box(b),style:style(s),before:style(before),after:style(after),svg,known,thin,
 prev:prev?{cls:prev.className,box:box(prev.getBoundingClientRect()),text:text(prev)}:null,
 next:next?{cls:next.className,box:box(next.getBoundingClientRect()),text:text(next)}:null,
 text:text(e),conditionText:e.matches('.sd-v2-outcome')?text(e.querySelector('.sd-v2-condition')):[],parent:e.parentElement.className,
 forkSource:e.matches('.sd-v2-fork')?box(e.previousElementSibling.lastElementChild.getBoundingClientRect()):null});
 }
 const jev=f.id==='jev-decision-pipeline'&&f.classList.contains('sd--jev')?(()=>{
  const selectors={inputs:'.sd-jev-signals > .sd-jev-inputs',judge:'.sd-jev-signals > .sd-jev-judge',input:'.sd-jev-signals > .sd-jev-input-link',transfer:'.sd-jev-transfer > .sd-jev-transfer-line',transferLabel:'.sd-jev-transfer > .sd-edge-label',policy:'.sd-jev-flow > .sd-jev-policy',policyLabel:'.sd-jev-policy > .sd-jev-boundary-label',authority:'.sd-jev-policy > .sd-jev-authority',fork:'.sd-jev-policy > .sd-jev-fork',stem:'.sd-jev-fork > .sd-jev-fork-stem',bus:'.sd-jev-fork > .sd-jev-fork-bus',shadowDrop:'.sd-jev-fork > .sd-jev-fork-drop--shadow',escalateDrop:'.sd-jev-fork > .sd-jev-fork-drop--escalate',shadow:'.sd-jev-outcomes > .sd-jev-shadow',escalate:'.sd-jev-outcomes > .sd-jev-escalate'};
  return Object.fromEntries(Object.entries(selectors).map(([name,selector])=>{const hits=[...f.querySelectorAll(selector)];return [name,{count:hits.length,...(hits.length===1?{box:box(hits[0].getBoundingClientRect()),hidden:hiddenElement(hits[0]),label:hits[0].innerText.trim().replace(/\s+/g,' ')}:{})}]}));
 })():null;
 const landscape=['sd-ethereum-account-fields','jib-build-workflow'].includes(f.id)?(()=>{
  const flows=[...f.children].filter(e=>e.classList.contains('sd-flow--linear-landscape'));
  return flows.map(flow=>[...flow.children].map(e=>({cls:e.getAttribute('class')||'',index:elements.indexOf(e),hidden:hiddenElement(e),box:box(e.getBoundingClientRect())})));
 })():null;
 let s=getComputedStyle(f),b=f.getBoundingClientRect();return {figure:f.id||f.getAttribute('aria-labelledby'),figureBox:box(b),contentWidth:b.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth),elements:result,jev,landscape};
}"""


def bounds(q):
    return dict(
        x=min(q[::2]),
        y=min(q[1::2]),
        w=max(q[::2]) - min(q[::2]),
        h=max(q[1::2]) - min(q[1::2]),
    )


def union(bs):
    return dict(
        x=min(b["x"] for b in bs),
        y=min(b["y"] for b in bs),
        w=max(b["x"] + b["w"] for b in bs) - min(b["x"] for b in bs),
        h=max(b["y"] + b["h"] for b in bs) - min(b["y"] for b in bs),
    )


def center(b, axis):
    return b[axis] + b["w" if axis == "x" else "h"] / 2


# This contract applies only to the reviewed Jev figure. No generic pseudo or
# unknown connector is approved by it; missing nodes are inventoried separately.
_JEV_CLASSES = {
    "input": "sd-jev-input-link",
    "transfer": "sd-jev-transfer-line",
    "stem": "sd-jev-fork-stem",
    "bus": "sd-jev-fork-bus",
    "shadowDrop": "sd-jev-fork-drop sd-jev-fork-drop--shadow",
    "escalateDrop": "sd-jev-fork-drop sd-jev-fork-drop--escalate",
}


def _jev_connectors(f):
    findings, unresolved = [], []
    anchors = f.get("jev")
    if not isinstance(anchors, dict):
        return [{"id": f["figure"], "type": "jev-inventory-missing"}], [], set()

    def defect(name, kind, **detail):
        findings.append({"id": "jev:" + name, "type": "jev-" + kind, **detail})

    def aligned(name, a, b, tolerance=1):
        if abs(a - b) > tolerance:
            defect(name, "off-axis", actual=a, expected=b)

    def visible(name):
        item = anchors.get(name, {})
        box = item.get("box", {})
        if item.get("count") != 1 or item.get("hidden") or box.get("w", 0) <= 0 or box.get("h", 0) <= 0:
            defect(name, "missing-or-hidden", count=item.get("count"))
            return None
        return box

    boxes = {name: visible(name) for name in (
        "inputs", "judge", "input", "transfer", "transferLabel", "policy",
        "policyLabel", "authority", "fork", "stem", "bus", "shadowDrop",
        "escalateDrop", "shadow", "escalate",
    )}
    labels = {
        "inputs": "State Typed Questions", "judge": "Jev 실행 권한 없음",
        "transferLabel": "typed answers", "policyLabel": "실행 권한 판단",
        "authority": "Deterministic Policy 코드와 정책이 결정",
        "shadow": "Shadow 실행 없이 비교", "escalate": "Escalate 사람 / 상위 제어",
    }
    for name, expected in labels.items():
        if anchors.get(name, {}).get("label") != expected:
            defect(name, "wrong-label", expected=expected, actual=anchors.get(name, {}).get("label"))

    consumed = set()
    elements = {}
    for name, cls in _JEV_CLASSES.items():
        matches = [e for e in f["elements"] if e["cls"] == cls]
        if len(matches) != 1:
            defect(name, "connector-inventory", count=len(matches))
        else:
            elements[name] = matches[0]
            consumed.add(matches[0]["id"])

    def opaque(color):
        return color == "rgb(51, 65, 85)"

    for name, e in elements.items():
        if e.get("hidden") or e.get("box", {}).get("w", 0) <= 0 or e.get("box", {}).get("h", 0) <= 0:
            defect(name, "missing-or-hidden-paint")
        st = e.get("style", {})
        background = st.get("background")
        if name in ("input", "shadowDrop", "escalateDrop"):
            shaft = (isinstance(background, str)
                     and background.count("rgb(51, 65, 85)") == 2
                     and background.startswith("linear-gradient(")
                     and st.get("backgroundSize") == "2px 100%"
                     and st.get("backgroundPosition") in ("50% 50%", "center center")
                     and st.get("backgroundRepeat") == "no-repeat")
        else:
            shaft = opaque(st.get("color"))
        dimensions = e["box"]
        if (name in ("transfer", "bus") and not 1.5 <= dimensions["h"] <= 2.5
            or name == "stem" and not 1.5 <= dimensions["w"] <= 2.5
            or name in ("input", "shadowDrop", "escalateDrop") and not 7 <= dimensions["w"] <= 9):
            shaft = False
        if not shaft:
            defect(name, "missing-shaft")
        if name in ("input", "transfer", "shadowDrop", "escalateDrop"):
            p = [p for p in e.get("pseudos", []) if p.get("type") == "after"]
            head = e.get("after", {})
            sides = head.get("borders", [])
            main_side = 3 if name == "transfer" else 0  # left or top triangle edge
            if (len(p) != 1 or not p[0].get("quad") or len(sides) != 4
                or head.get("content") in ("none", "normal")
                or head.get("display") == "none"
                or head.get("visibility") in ("hidden", "collapse")
                or head.get("opacity", 1) < 0.01
                or not opaque(sides[main_side].get("color"))
                or not 5.75 <= sides[main_side].get("width", 0) <= 6.25
                or sides[main_side].get("style") in ("none", "hidden")
                or any(not 3.75 <= sides[i].get("width", 0) <= 4.25
                       for i in ((0, 2) if name == "transfer" else (1, 3)))
                or any(opaque(sides[i].get("color")) and sides[i].get("width", 0) > 0
                       for i in range(4) if i != main_side)):
                defect(name, "missing-or-malformed-arrowhead")
            else:
                head_box = bounds(p[0]["quad"])
                shaft_box = e["box"]
                expected = (6, 8) if name == "transfer" else (8, 6)
                if (abs(head_box["w"] - expected[0]) > 0.5 or
                    abs(head_box["h"] - expected[1]) > 0.5):
                    defect(name, "malformed-arrowhead-geometry", bounds=head_box)
                axis = "y" if name == "transfer" else "x"
                aligned(name + ":head", center(head_box, axis), center(shaft_box, axis))
                if name == "transfer":
                    aligned(name + ":head-tip", head_box["x"] + head_box["w"], shaft_box["x"] + shaft_box["w"])
                else:
                    aligned(name + ":head-tip", head_box["y"] + head_box["h"], shaft_box["y"] + shaft_box["h"])
        # Extra painted pseudos can turn a single stroke into a second arrow.
        for p in e.get("pseudos", []):
            if p.get("type") != "after" or name in ("stem", "bus"):
                defect(name, "unexpected-pseudo", pseudo=p.get("type"))
        if name in ("stem", "bus") and e.get("pseudos"):
            defect(name, "unexpected-fork-paint")

    b = {name: box for name, box in boxes.items() if box is not None}
    if len(b) == len(boxes):
        aligned("input", center(b["input"], "x"), center(b["inputs"], "x"))
        aligned("input", center(b["input"], "x"), center(b["judge"], "x"))
        if not (3 <= b["input"]["y"] - b["inputs"]["y"] - b["inputs"]["h"] <= 6
                and 3 <= b["judge"]["y"] - b["input"]["y"] - b["input"]["h"] <= 6):
            defect("input", "card-clearance")
        aligned("transfer", center(b["transfer"], "y"), center(b["judge"], "y"))
        aligned("transfer", center(b["transfer"], "y"), center(b["authority"], "y"))
        if not (4 <= b["transfer"]["x"] - b["judge"]["x"] - b["judge"]["w"] <= 8
                and 6 <= b["authority"]["x"] - b["transfer"]["x"] - b["transfer"]["w"] <= 24):
            defect("transfer", "card-clearance")
        if not (b["transferLabel"]["y"] + b["transferLabel"]["h"] <= b["transfer"]["y"] - 4):
            defect("transfer", "label-clearance")
        aligned("fork", center(b["stem"], "x"), center(b["authority"], "x"))
        aligned("fork", center(b["stem"], "x"), center(b["bus"], "x"))
        if not (3 <= b["stem"]["y"] - b["authority"]["y"] - b["authority"]["h"] <= 6
                and b["stem"]["y"] <= center(b["bus"], "y") <= b["stem"]["y"] + b["stem"]["h"]):
            defect("fork", "broken-stem-bus")
        for drop, card in (("shadowDrop", "shadow"), ("escalateDrop", "escalate")):
            aligned(drop, center(b[drop], "x"), center(b[card], "x"))
            if not (b["bus"]["x"] - 1 <= center(b[drop], "x") <= b["bus"]["x"] + b["bus"]["w"] + 1
                    and b[drop]["y"] <= center(b["bus"], "y") <= b[drop]["y"] + b[drop]["h"]
                    and 3 <= b[card]["y"] - b[drop]["y"] - b[drop]["h"] <= 6):
                defect(drop, "broken-bus-drop-or-card-clearance")
        aligned("fork", b["shadow"]["y"], b["escalate"]["y"])

    # No second horizontal stroke, or unreviewed Jev pseudo, can hide in a
    # decorative wrapper. Other figures retain the original generic behavior.
    for e in f["elements"]:
        if e["id"] in consumed:
            continue
        cls = e.get("cls", "")
        st = e.get("style", {})
        border = st.get("borders", [])
        extra_border = (len(border) == 4 and e["box"]["w"] > 4 and
                        any(border[i].get("width", 0) >= 1.5 and
                            border[i].get("style") not in ("none", "hidden") and
                            border[i].get("color") not in (None, "transparent", "rgba(0, 0, 0, 0)")
                            for i in (0, 2)))
        extra_line = (e["box"]["h"] <= 4 and e["box"]["w"] > 4 and
                      (st.get("color") not in (None, "transparent", "rgba(0, 0, 0, 0)") or
                       isinstance(st.get("background"), str) and "gradient(" in st["background"]))
        if extra_border or extra_line or "sd-jev-" in cls and e.get("pseudos"):
            unresolved.append({"id": e["id"], "reason": "extra Jev stroke or pseudo"})
    return findings, unresolved, consumed


_LANDSCAPE_FIGURES = {"sd-ethereum-account-fields", "jib-build-workflow"}
_LANDSCAPE_COLOR = "rgb(51, 65, 85)"


def _landscape_connectors(f):
    """Paint/geometry contract for the two opted-in 625px three-card rows only."""
    findings = []

    def defect(name, kind):
        findings.append({"id": name, "type": "landscape-" + kind})

    rows = f.get("landscape")
    if not isinstance(rows, list) or len(rows) != 1 or len(rows[0]) != 5:
        defect(f["figure"], "inventory")
        return findings
    row = rows[0]
    arrows = [e for e in f["elements"] if "sd-arrow" in e.get("cls", "").split()]
    if len(arrows) != 2:
        defect(f["figure"], "arrow-inventory")
    for i, slot in enumerate(row):
        expected = "sd-arrow" if i % 2 else "sd-node"
        if expected not in slot.get("cls", "").split() or slot.get("hidden"):
            defect(f["figure"] + ":" + str(i), "missing-or-hidden-slot")
    for i in (1, 3):
        slot = row[i]
        name = f["figure"] + ":" + str(slot.get("index", i))
        matched = [e for e in arrows if e["id"] == name]
        if len(matched) != 1 or slot.get("cls") != "sd-arrow":
            defect(name, "arrow-inventory")
            continue
        e = matched[0]
        box = e.get("box", {})
        left, right = row[i - 1].get("box", {}), row[i + 1].get("box", {})
        if e.get("hidden") or box.get("w", 0) <= 0 or box.get("h", 0) <= 0:
            defect(name, "missing-or-hidden-arrow")
            continue
        st = e.get("style", {})
        if (st.get("background") != "linear-gradient(rgb(51, 65, 85), rgb(51, 65, 85))"
            or st.get("backgroundSize") != "48px 2px"
            or st.get("backgroundPosition") not in ("50% 50%", "center center")
            or st.get("backgroundRepeat") != "no-repeat"):
            defect(name, "missing-or-shifted-shaft")
        shaft = {"x": center(box, "x") - 24, "y": center(box, "y") - 1, "w": 48, "h": 2}
        if (not 95 <= box["w"] <= 97 or box["h"] < 150
            or not left or not right
            or left["x"] + left["w"] > shaft["x"] - 4
            or shaft["x"] + shaft["w"] > right["x"] - 4
            or abs(left["x"] + left["w"] - box["x"]) > 1
            or abs(box["x"] + box["w"] - right["x"]) > 1
            or abs(center(left, "y") - center(box, "y")) > 1
            or abs(center(right, "y") - center(box, "y")) > 1):
            defect(name, "shaft-card-clearance")

        head = e.get("after", {})
        sides = head.get("borders", [])
        pseudos = [p for p in e.get("pseudos", []) if p.get("type") == "after" and p.get("quad")]
        transform = re.fullmatch(r"matrix\(([^)]+)\)", head.get("transform", ""))
        matrix = []
        if transform:
            try:
                matrix = [float(n.strip()) for n in transform.group(1).split(",")]
            except ValueError:
                pass
        visible = (len(pseudos) == 1 and len(sides) == 4
                   and head.get("content") not in (None, "none", "normal")
                   and head.get("display") != "none"
                   and head.get("visibility") not in ("hidden", "collapse")
                   and head.get("opacity", 1) >= 0.01
                   and len(matrix or []) == 6
                   and all(abs(matrix[j] - v) < 0.02 for j, v in enumerate(
                       (0.7071, -0.7071, 0.7071, 0.7071, 0, 0)))
                   and all(sides[j].get("style") not in ("none", "hidden")
                           and 1.75 <= sides[j].get("width", 0) <= 2.25
                           and sides[j].get("color") == _LANDSCAPE_COLOR for j in (1, 2))
                   and all(sides[j].get("width", 0) == 0 or
                           sides[j].get("color") in ("transparent", "rgba(0, 0, 0, 0)")
                           for j in (0, 3)))
        if not visible:
            defect(name, "missing-or-wrong-caret")
            continue
        caret = bounds(pseudos[0]["quad"])
        if (not 14 <= caret["w"] <= 16 or not 14 <= caret["h"] <= 16
            or abs(center(caret, "x") - (center(box, "x") + 23.2)) > 1
            or abs(center(caret, "y") - center(shaft, "y")) > 1
            or caret["x"] > shaft["x"] + shaft["w"] - 2
            or caret["x"] + caret["w"] <= shaft["x"] + shaft["w"]
            or not left or not right
            or left["x"] + left["w"] > caret["x"] - 4
            or caret["x"] + caret["w"] > right["x"] - 4):
            defect(name, "caret-geometry-or-card-clearance")
        if any(p.get("type") == "before" and p.get("quad") for p in e.get("pseudos", [])):
            defect(name, "unexpected-caret")
    return findings


def classify(f):
    findings = []
    unresolved = []
    count = 0
    jev_consumed = set()
    if f.get("figure") == "jev-decision-pipeline":
        jev_findings, jev_unresolved, jev_consumed = _jev_connectors(f)
        findings.extend(jev_findings)
        unresolved.extend(jev_unresolved)
        count += len(jev_consumed)
    svg_elements = [e for e in f["elements"] if e["svg"]]
    reviewed_svg = (
        f["figure"] == "sd-blockchain-operator-health-ladder"
        and len(svg_elements) == 2
        and sorted(e["tag"].lower() for e in svg_elements) == ["path", "svg"]
        and next(e["svgData"] for e in svg_elements if e["tag"].lower() == "path")
        == {"path": "M6 1v20", "strokeWidth": "2", "dasharray": "3 3"}
    )
    for e in f["elements"]:
        if e["id"] in jev_consumed:
            continue
        cl = e["cls"]
        if e.get("hidden"):
            findings.append({"id": e["id"], "type": "hidden-connector"})
            count += 1
            continue
        paint = []
        for p in e.get("pseudos", []):
            st = e.get(p["type"], {})
            borders = st.get("borders", [])
            if (
                st.get("visibility") in ("hidden", "collapse")
                or st.get("opacity", 1) < 0.01
            ):
                findings.append(
                    {
                        "id": e["id"],
                        "type": "invisible-connector-pseudo",
                        "pseudo": p["type"],
                    }
                )
                p["paintPolygons"] = []
                continue
            if p.get("quad"):
                q = p["quad"]
                inner = p.get("innerQuad", q)
                polygons = []
                if st.get("color") not in ("rgba(0, 0, 0, 0)", "transparent", None):
                    polygons.append(q)
                for side, border in enumerate(borders):
                    if (
                        border["width"] > 0
                        and border["style"] != "none"
                        and border["color"] != "rgba(0, 0, 0, 0)"
                    ):
                        a = side * 2
                        b = ((side + 1) % 4) * 2
                        polygons.append(
                            q[a : a + 2]
                            + q[b : b + 2]
                            + inner[b : b + 2]
                            + inner[a : a + 2]
                        )
                p["paintPolygons"] = polygons
                paint.extend(bounds(q) for q in polygons)
        standalone = bool(
            re.search(r"(?:^| )(sd-arrow(?:--both)?|sd-v2-link|sd-v2-down)(?: |$)", cl)
        )
        classes = set(cl.split())
        if ("sd-loop" in classes and e.get("role") != "loop") or (
            "sd-reference" in classes and e.get("role") != "reference-note"
        ):
            unresolved.append(
                {
                    "id": e["id"],
                    "reason": "canonical structural connector is missing its role",
                }
            )
        if standalone:
            painted = {
                p["type"] for p in e.get("pseudos", []) if p.get("paintPolygons")
            }
            required = {"before", "after"} if "sd-arrow--both" in classes else {"after"}
            for head in required:
                expected_sides = (
                    (0, 3)
                    if head == "before"
                    else ((0, 1) if "sd-v2-link" in classes else (1, 2))
                )
                borders = e.get(head, {}).get("borders", [])
                if len(borders) != 4 or any(
                    borders[i]["width"] <= 0
                    or borders[i]["style"] in ("none", "hidden")
                    or borders[i]["color"] in ("transparent", "rgba(0, 0, 0, 0)")
                    for i in expected_sides
                ):
                    findings.append(
                        {
                            "id": e["id"],
                            "type": "incomplete-visible-caret",
                            "pseudo": head,
                        }
                    )
            if not required.issubset(painted):
                findings.append({"id": e["id"], "type": "missing-visible-arrowhead"})
            if (
                classes.intersection({"sd-v2-link", "sd-v2-down"})
                and e["style"].get("background") in (None, "none")
                and e["style"].get("color") in (None, "transparent", "rgba(0, 0, 0, 0)")
            ):
                findings.append({"id": e["id"], "type": "missing-visible-shaft"})
        if "sd-v2-fork" in classes and not paint:
            border = e["style"]["borders"][3]
            if (
                not border["width"]
                or border["style"] in ("none", "hidden")
                or border["color"] == "rgba(0, 0, 0, 0)"
            ):
                findings.append({"id": e["id"], "type": "missing-visible-fork"})
        if "sd-v2-outcome" in classes and paint and e.get("conditionText"):
            gap = min(
                (
                    max(b["x"] - t["x"] - t["w"], t["x"] - b["x"] - b["w"], 0) ** 2
                    + max(b["y"] - t["y"] - t["h"], t["y"] - b["y"] - b["h"], 0) ** 2
                )
                ** 0.5
                for b in paint
                for t in e["conditionText"]
            )
            e["conditionClearance"] = gap
            if gap < 4:
                findings.append(
                    {
                        "id": e["id"],
                        "type": "branch-condition-clearance",
                        "gap": gap,
                        "minimum": 4,
                    }
                )
        if "sd-arrow" in cl and e["text"]:
            labelmetrics = []
            for p in e.get("pseudos", []):
                if p.get("paintPolygons"):
                    distances = []
                    for q in p["paintPolygons"]:
                        b = bounds(q)
                        for t in e["text"]:
                            distances.append(
                                (
                                    max(
                                        b["x"] - t["x"] - t["w"],
                                        t["x"] - b["x"] - b["w"],
                                        0,
                                    )
                                    ** 2
                                    + max(
                                        b["y"] - t["y"] - t["h"],
                                        t["y"] - b["y"] - b["h"],
                                        0,
                                    )
                                    ** 2
                                )
                                ** 0.5
                            )
                    gap = min(distances)
                    labelmetrics.append(
                        {"pseudo": p["type"], "minimumPaintToOwnText": gap}
                    )
                    if gap < 4:
                        findings.append(
                            {
                                "id": e["id"],
                                "class": cl,
                                "type": "arrow-own-label-clearance",
                                "pseudo": p["type"],
                                "clearance": gap,
                            }
                        )
            e["ownLabelMetrics"] = labelmetrics
        from connector_roles import resolve_role

        role_result = resolve_role(e)
        if role_result is not None:
            findings.extend(role_result["findings"])
            unresolved.extend(role_result["unresolved"])
            if role_result["handled"]:
                count += e.get("role") != "reference-note"
                continue
        structural = bool(
            re.search(
                r"sd-v2-(fork|relation|outcome|adjunct)|sd-loop|branch|connector", cl
            )
        ) or (bool(paint) and e["parent"] == "sd-v2-rail")
        if not (standalone or structural or e["svg"]):
            if paint:
                unresolved.append(
                    {
                        "id": e["id"],
                        "reason": "unclassified painted pseudo; may be decoration",
                        "class": cl,
                    }
                )
            continue
        count += 1
        if e["svg"]:
            if reviewed_svg:
                e["disposition"] = (
                    "retained: canonical SVG is an intentionally dashed M6 1v20 authentication-boundary marker (stroke 2, dasharray 3 3); continuous edge attachment not intended"
                )
                if e["tag"].lower() == "path":
                    b = e["box"]
                    e["paintBounds"] = {
                        "x": b["x"] - 1,
                        "y": b["y"],
                        "w": 2,
                        "h": b["h"],
                    }
            else:
                unresolved.append(
                    {
                        "id": e["id"],
                        "reason": "SVG connector semantics require path/topology review",
                        "class": cl,
                    }
                )
            continue
        if standalone:
            if "sd-v2-" in cl:
                paint.append(e["box"])
            if not paint:
                unresolved.append(
                    {"id": e["id"], "reason": "standalone arrow has no measured paint"}
                )
                continue
            b = union(paint)
            e["paintBounds"] = b
            prev, nxt = e["prev"], e["next"]
            if not prev or not nxt:
                unresolved.append({"id": e["id"], "reason": "missing sibling endpoint"})
                continue
            horizontal = abs(center(prev["box"], "x") - center(nxt["box"], "x")) > abs(
                center(prev["box"], "y") - center(nxt["box"], "y")
            )
            axis = "x" if horizontal else "y"
            size = "w" if horizontal else "h"

            # Node boundary is meaningful; plain text siblings use actual rendered text ranges.
            def endpoint(n):
                # Only actual text-only endpoint classes use Range bounds. Structural lane,
                # flow and grid wrappers define the node gap, not their inset descendant text.
                return (
                    union(n["text"])
                    if str(n["cls"]) in ("sd-detail", "sd-label", "sd-edge-label")
                    and n["text"]
                    else n["box"]
                )

            a, z = endpoint(prev), endpoint(nxt)
            lo = a[axis] + a[size]
            hi = z[axis]
            gap = hi - lo
            clearance = [b[axis] - lo, hi - b[axis] - b[size]]
            offset = center(b, axis) - (lo + hi) / 2

            def rectangle_distance(u, v):
                return (
                    max(u["x"] - v["x"] - v["w"], v["x"] - u["x"] - u["w"], 0) ** 2
                    + max(u["y"] - v["y"] - v["h"], v["y"] - u["y"] - u["h"], 0) ** 2
                ) ** 0.5

            distances = [rectangle_distance(b, a), rectangle_distance(b, z)]
            e["gapMetrics"] = {
                "axis": axis,
                "gap": gap,
                "clearances": clearance,
                "endpointDistances": distances,
                "centerOffset": offset,
                "endpointBounds": [a, z],
            }
            if gap > 0:
                if min(distances) < 4:
                    findings.append(
                        {
                            "id": e["id"],
                            "class": cl,
                            "type": "standalone-endpoint-clearance",
                            "clearance": clearance,
                            "endpointDistances": distances,
                            "threshold": 4,
                            "paintBounds": b,
                            "endpointBounds": [a, z],
                        }
                    )
                # Labels within sd-arrow deliberately allocate space with its head. Do not demand geometric head centering there.
                if not e["text"] and abs(offset) > 3:
                    findings.append(
                        {
                            "id": e["id"],
                            "class": cl,
                            "type": "standalone-gap-off-center",
                            "offset": offset,
                            "gap": gap,
                            "paintBounds": b,
                            "endpointBounds": [a, z],
                        }
                    )
            else:
                unresolved.append(
                    {
                        "id": e["id"],
                        "reason": "siblings do not define a positive standalone gap",
                    }
                )
        elif "sd-v2-fork" in cl:
            p = {v["type"]: v for v in e.get("pseudos", []) if v.get("quad")}
            if "after" in p and e["forkSource"]:
                stem = bounds(p["after"]["quad"])
                src = e["forkSource"]
                delta = center(stem, "x") - center(src, "x")
                separation = stem["y"] - (src["y"] + src["h"])
                e["junction"] = {
                    "sourceCenterDelta": delta,
                    "sourceSeparation": separation,
                }
                if abs(delta) > 1 or abs(separation) > 1:
                    findings.append(
                        {
                            "id": e["id"],
                            "class": cl,
                            "type": "fork-source-misalignment",
                            "delta": delta,
                            "separation": separation,
                            "source": src,
                            "stem": stem,
                        }
                    )
                outcomes = [v for v in f["elements"] if "sd-v2-outcome" in v["cls"]]
                if outcomes:
                    right = outcomes[-1]
                    rp = next(
                        (
                            v
                            for v in right.get("pseudos", [])
                            if v["type"] == "before" and v.get("quad")
                        ),
                        None,
                    )
                    if rp:
                        branch = bounds(rp["quad"])
                        shift = center(branch, "x") - center(stem, "x")
                        overlap = min(
                            branch["x"] + branch["w"], stem["x"] + stem["w"]
                        ) - max(branch["x"], stem["x"])
                        if abs(shift) > 1:
                            findings.append(
                                {
                                    "id": e["id"],
                                    "class": cl,
                                    "type": "fork-junction-lateral-offset",
                                    "centerShift": shift,
                                    "strokeOverlap": overlap,
                                    "stem": stem,
                                    "branch": branch,
                                }
                            )
            # Mobile fork is intentionally a border rail rather than a centered edge.
        elif "sd-v2-relation" in cl:
            e["disposition"] = (
                "attached relation; intentional endpoint contact excluded from standalone clearance rule"
            )
        else:
            unresolved.append(
                {
                    "id": e["id"],
                    "reason": "nonstandard branch topology needs semantic review",
                }
            )

    # Explicit topology checks: attached branch borders are never standalone markers.
    def rectgap(a, b):
        return (
            max(a["x"] - b["x"] - b["w"], b["x"] - a["x"] - a["w"], 0) ** 2
            + max(a["y"] - b["y"] - b["h"], b["y"] - a["y"] - a["h"], 0) ** 2
        ) ** 0.5

    def strips(e):
        return [
            bounds(q) for p in e.get("pseudos", []) for q in p.get("paintPolygons", [])
        ]

    def resolve(e, note):
        e["disposition"] = note
        unresolved[:] = [u for u in unresolved if u["id"] != e["id"]]

    rail = [
        e
        for e in f["elements"]
        if e["parent"] == "sd-v2-rail" and strips(e) and not e["known"]
    ]
    adjunct = next(
        (e for e in f["elements"] if e["cls"] == "sd-v2-adjunct" and strips(e)), None
    )
    if len(rail) == 2 and adjunct:
        chain = rail + [adjunct]
        for a, b in zip(chain, chain[1:]):
            gap = min(rectgap(x, y) for x in strips(a) for y in strips(b))
            a["attachedNextGap"] = gap
            av = [x for x in strips(a) if x["w"] <= 2.01 and x["h"] > x["w"]]
            bv = [x for x in strips(b) if x["w"] <= 2.01 and x["h"] > x["w"]]
            if av and bv:
                offset = center(av[0], "x") - center(bv[0], "x")
                a["attachedStrokeCenters"] = [center(av[0], "x"), center(bv[0], "x")]
                a["attachedStrokeCenterDelta"] = offset
                if abs(offset) > 0.5:
                    findings.append(
                        {
                            "id": a["id"],
                            "class": a["cls"],
                            "type": "attached-rail-centerline-offset",
                            "next": b["id"],
                            "offset": offset,
                            "strokeBounds": [av[0], bv[0]],
                        }
                    )
            if gap > 0.5:
                findings.append(
                    {
                        "id": a["id"],
                        "class": a["cls"],
                        "type": "attached-rail-discontinuity",
                        "next": b["id"],
                        "gap": gap,
                    }
                )
        for e in chain:
            resolve(
                e,
                "measured border-rail adjacency; intentional card attachment excluded from crowding rule",
            )
    for relation in [
        e for e in f["elements"] if e["cls"] == "sd-v2-relation" and strips(e)
    ]:
        sources = [
            n["box"]
            for e in f["elements"]
            for n in [e.get("prev"), e.get("next")]
            if n and "sd-node--accent" in str(n["cls"])
        ]
        p = next(
            (
                p
                for p in relation.get("pseudos", [])
                if p["type"] == "before" and p.get("quad")
            ),
            None,
        )
        if sources and p and relation.get("next"):
            source = sources[0]
            stem = bounds(p["quad"])
            target = relation["next"]["box"]
            metrics = {
                "sourceGap": stem["y"] - source["y"] - source["h"],
                "targetGap": target["y"] - stem["y"] - stem["h"],
                "sourceCenterOffset": center(stem, "x") - center(source, "x"),
            }
            relation["attachedEndpoints"] = metrics
            if abs(metrics["sourceGap"]) > 1 or abs(metrics["targetGap"]) > 1:
                findings.append(
                    {
                        "id": relation["id"],
                        "class": relation["cls"],
                        "type": "attached-relation-endpoint-discontinuity",
                        **metrics,
                    }
                )
    fork = next((e for e in f["elements"] if e["cls"] == "sd-v2-fork"), None)
    if fork:
        railpaint = strips(fork)
        if fork["style"]["borders"][3]["width"]:
            b = fork["box"]
            railpaint.append(
                dict(
                    x=b["x"], y=b["y"], w=fork["style"]["borders"][3]["width"], h=b["h"]
                )
            )
        for e in f["elements"]:
            if "sd-v2-outcome" in e["cls"] and strips(e) and railpaint:
                gap = min(rectgap(a, b) for a in strips(e) for b in railpaint)
                e["forkRailGap"] = gap
                if gap > 1:
                    findings.append(
                        {
                            "id": e["id"],
                            "class": e["cls"],
                            "type": "fork-branch-discontinuity",
                            "gap": gap,
                        }
                    )
                resolve(
                    e,
                    "measured outcome branch to fork rail adjacency; condition label interrupts the visual path intentionally",
                )
    if f.get("figure") in _LANDSCAPE_FIGURES:
        findings.extend(_landscape_connectors(f))
    f.update(
        connectorCount=count,
        findings=findings,
        unresolved=unresolved,
        status=(
            "confirmed defect"
            if findings
            else "unresolved" if unresolved else "retained" if count else "no-connector"
        ),
    )
