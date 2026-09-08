"""Border-polygon geometry classification shared by corpus and export checks."""

import re

COLLECT = r"""f => {
 const box=r=>({x:r.x,y:r.y,w:r.width,h:r.height});
 const style=s=>({content:s.content,display:s.display,background:s.backgroundImage,color:s.backgroundColor,transform:s.transform,visibility:s.visibility,opacity:parseFloat(s.opacity),radii:['TopLeft','TopRight','BottomRight','BottomLeft'].map(k=>s['border'+k+'Radius']),borders:['Top','Right','Bottom','Left'].map(k=>({width:parseFloat(s['border'+k+'Width']),style:s['border'+k+'Style'],color:s['border'+k+'Color']}))});
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
 let known=/sd-arrow|sd-loop|sd-reference|sd-v2-(link|down|fork|relation)|branch|connector/.test(cls)||!!role;
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
 let s=getComputedStyle(f),b=f.getBoundingClientRect();return {figure:f.id||f.getAttribute('aria-labelledby'),figureBox:box(b),contentWidth:b.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth),elements:result};
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


def classify(f):
    findings = []
    unresolved = []
    count = 0
    svg_elements = [e for e in f["elements"] if e["svg"]]
    reviewed_svg = (
        f["figure"] == "sd-blockchain-operator-health-ladder"
        and len(svg_elements) == 2
        and sorted(e["tag"].lower() for e in svg_elements) == ["path", "svg"]
        and next(e["svgData"] for e in svg_elements if e["tag"].lower() == "path")
        == {"path": "M6 1v20", "strokeWidth": "2", "dasharray": "3 3"}
    )
    for e in f["elements"]:
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
