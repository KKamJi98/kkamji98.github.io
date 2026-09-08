"""Paint-aware connector checks for the canonical CSS connector families.

CDP exposes the transformed border quad of pseudo-elements. These checks are
geometric contracts, not a substitute for inspecting screenshot pixels.
"""

MARKERS = ".sd-v2-link, .sd-v2-down"

MARKER_DATA = r"""f => {
 const box=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
 const texts=e=>{if(!e)return [];const a=[],w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);while(w.nextNode()){if(!w.currentNode.textContent.trim())continue;const r=document.createRange();r.selectNodeContents(w.currentNode);for(const b of r.getClientRects())if(b.width&&b.height)a.push({left:b.left,right:b.right,top:b.top,bottom:b.bottom});}return a;};
 return [...f.querySelectorAll('.sd-v2-link, .sd-v2-down')].map(e=>({
   classes:e.className,box:box(e),previous:box(e.previousElementSibling),next:box(e.nextElementSibling),
   previousText:texts(e.previousElementSibling),nextText:texts(e.nextElementSibling),
   issuance:!!e.closest('.sd-v2-issuance-row'),
   outcome:e.matches('.sd-v2-outcome > .sd-v2-down')
 }));
}"""


def _box(quad):
    return dict(
        left=min(quad[::2]),
        right=max(quad[::2]),
        top=min(quad[1::2]),
        bottom=max(quad[1::2]),
    )


def _pseudo(cdp, node, kind, client):
    description = cdp.send("DOM.describeNode", {"nodeId": node, "depth": 1})["node"]
    candidate = next(
        (p for p in description.get("pseudoElements", []) if p["pseudoType"] == kind),
        None,
    )
    if candidate is None:
        return None
    parent = _box(cdp.send("DOM.getBoxModel", {"nodeId": node})["model"]["border"])
    quad = cdp.send("DOM.getBoxModel", {"backendNodeId": candidate["backendNodeId"]})[
        "model"
    ]["border"]
    result = _box(quad)
    for key in ("left", "right"):
        result[key] -= parent["left"] - client["left"]
    for key in ("top", "bottom"):
        result[key] -= parent["top"] - client["top"]
    return result


def _center(box, start, end):
    return (box[start] + box[end]) / 2


def _inspect_v2(page, selector):
    """Return blocking findings and measurements without modifying figure HTML."""
    figure = page.locator(selector)
    data = figure.evaluate(MARKER_DATA)
    issues, measured = [], []
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("DOM.enable")
        root = cdp.send("DOM.getDocument")["root"]["nodeId"]
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})[
            "nodeId"
        ]
        nodes = cdp.send("DOM.querySelectorAll", {"nodeId": node, "selector": MARKERS})[
            "nodeIds"
        ]
        if len(nodes) != len(data):
            raise ValueError("connector DOM inventory mismatch")
        for index, (item, element) in enumerate(zip(data, nodes)):
            if not item["box"]["width"] or not item["box"]["height"]:
                continue

            def issue(kind, **details):
                issues.append(
                    dict(kind=kind, connector=index, classes=item["classes"], **details)
                )

            previous, following = item["previous"], item["next"]
            if previous is None or following is None:
                issue("missing-endpoint")
                continue
            head = _pseudo(cdp, element, "after", item["box"])
            if head is None:
                issue("missing-arrowhead")
                continue
            dx = abs(
                _center(following, "left", "right") - _center(previous, "left", "right")
            )
            dy = abs(
                _center(following, "top", "bottom") - _center(previous, "top", "bottom")
            )
            start, end = ("left", "right") if dx > dy else ("top", "bottom")
            cross_start, cross_end = ("top", "bottom") if dx > dy else ("left", "right")
            low = min(item["box"][start], head[start])
            high = max(item["box"][end], head[end])
            before, after = low - previous[end], following[start] - high
            minimum = 8 if item["outcome"] else 6
            if before < minimum - 0.25:
                issue("source-clearance", gap=before, minimum=minimum)
            if after < minimum - 0.25:
                issue("target-clearance", gap=after, minimum=minimum)
            cross_delta = abs(
                _center(head, cross_start, cross_end)
                - _center(item["box"], cross_start, cross_end)
            )
            if cross_delta > 0.25:
                issue("arrowhead-axis", delta=cross_delta)
            if item["issuance"] or item["outcome"]:
                if abs(before - after) > 0.75:
                    issue("gap-centering", source=before, target=after)
            if item["issuance"]:
                if not item["previousText"] or not item["nextText"]:
                    issue("missing-text-endpoint")
                else:
                    text_before = low - max(t[end] for t in item["previousText"])
                    text_after = min(t[start] for t in item["nextText"]) - high
                    if min(text_before, text_after) < 5.75:
                        issue("text-clearance", source=text_before, target=text_after)
                    if abs(text_before - text_after) > 1.5:
                        issue("text-centering", source=text_before, target=text_after)
            measured.append(
                dict(
                    index=index,
                    axis=start,
                    source_gap=before,
                    target_gap=after,
                    cross_delta=cross_delta,
                    head=head,
                )
            )
        forks = cdp.send(
            "DOM.querySelectorAll", {"nodeId": node, "selector": ".sd-v2-fork"}
        )["nodeIds"]
        for index, fork_node in enumerate(forks):
            fork = figure.locator(".sd-v2-fork").nth(index)
            info = fork.evaluate(
                """f=>{
              const box=e=>{if(!e)return null;const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
              const source=f.closest('.sd-v2-request')?.querySelector('.sd-v2-request-row .sd-node--accent');
              return {box:box(f),source:box(source),mobile:getComputedStyle(f).gridTemplateColumns.split(' ').length===1,
                      border:parseFloat(getComputedStyle(f).borderLeftWidth),outcomes:[...f.querySelectorAll(':scope > .sd-v2-outcome')].map(box)};
            }"""
            )

            def finding(kind, **details):
                issues.append(dict(kind=kind, fork=index, **details))

            if info["source"] is None:
                finding("fork-missing-source")
                continue
            children = cdp.send(
                "DOM.querySelectorAll",
                {"nodeId": fork_node, "selector": ":scope > .sd-v2-outcome"},
            )["nodeIds"]
            if len(children) != len(info["outcomes"]) or not children:
                finding("fork-outcome-inventory")
                continue
            if info["mobile"]:
                if (
                    info["border"] <= 0
                    or abs(info["box"]["top"] - info["source"]["bottom"]) > 0.25
                ):
                    finding("side-bus-source-contact")
                for child, outcome in zip(children, info["outcomes"]):
                    branch = _pseudo(cdp, child, "before", outcome)
                    if (
                        branch is None
                        or branch["left"] > info["box"]["left"] + info["border"] + 0.25
                        or branch["right"] <= branch["left"]
                    ):
                        finding("side-bus-branch-contact")
                continue
            trunk = _pseudo(cdp, fork_node, "after", info["box"])
            bar = _pseudo(cdp, fork_node, "before", info["box"])
            if trunk is None or bar is None:
                finding("fork-missing-stroke")
                continue
            delta = abs(
                _center(trunk, "left", "right")
                - _center(info["source"], "left", "right")
            )
            if delta > 0.25:
                finding("fork-source-axis", delta=delta)
            if (
                abs(trunk["top"] - info["source"]["bottom"]) > 0.25
                or trunk["bottom"] < _center(bar, "top", "bottom") - 0.25
            ):
                finding("fork-trunk-contact")
            for child, outcome in zip(children, info["outcomes"]):
                branch = _pseudo(cdp, child, "before", outcome)
                if branch is None:
                    finding("fork-missing-branch")
                    continue
                delta = abs(
                    _center(branch, "left", "right") - _center(outcome, "left", "right")
                )
                if delta > 0.25:
                    finding("fork-branch-axis", delta=delta)
                if (
                    branch["top"] > bar["bottom"] + 0.25
                    or bar["left"] > branch["left"] + 0.25
                    or bar["right"] < branch["right"] - 0.25
                ):
                    finding("fork-branch-contact")
        return {"issues": issues, "markers": measured, "forks": len(forks)}
    finally:
        cdp.detach()


def collect_geometry(page, selector):
    from connector_geometry import COLLECT, bounds

    figure = page.locator(selector)
    geometry = figure.evaluate(COLLECT)
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("DOM.enable")
        root = cdp.send("DOM.getDocument")["root"]["nodeId"]
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})[
            "nodeId"
        ]
        nodes = [node] + cdp.send(
            "DOM.querySelectorAll", {"nodeId": node, "selector": "*"}
        )["nodeIds"]
        for element in geometry["elements"]:
            if element.get("hidden"):
                continue
            index = element["index"]
            if index >= len(nodes):
                raise ValueError("paint inventory changed during capture")
            description = cdp.send(
                "DOM.describeNode", {"nodeId": nodes[index], "depth": 1}
            )["node"]
            if description["nodeName"].lower() != element["tag"].lower():
                raise ValueError("paint node identity mismatch")
            pseudos = [
                p
                for p in description.get("pseudoElements", [])
                if p["pseudoType"] in ("before", "after")
            ]
            if not pseudos:
                continue
            parent = bounds(
                cdp.send("DOM.getBoxModel", {"nodeId": nodes[index]})["model"]["border"]
            )
            dx, dy = (
                parent["x"] - element["box"]["x"],
                parent["y"] - element["box"]["y"],
            )
            for pseudo in pseudos:
                model = cdp.send(
                    "DOM.getBoxModel", {"backendNodeId": pseudo["backendNodeId"]}
                )["model"]

                def viewport(quad):
                    return [
                        value - (dx if i % 2 == 0 else dy)
                        for i, value in enumerate(quad)
                    ]

                element.setdefault("pseudos", []).append(
                    {
                        "type": pseudo["pseudoType"],
                        "quad": viewport(model["border"]),
                        "innerQuad": viewport(model["padding"]),
                    }
                )
        return geometry
    finally:
        cdp.detach()


def inspect_connectors(page, selector):
    from connector_geometry import classify

    geometry = collect_geometry(page, selector)
    classify(geometry)
    specific = _inspect_v2(page, selector)
    unresolved = geometry["unresolved"]
    issues = (
        geometry["findings"]
        + specific["issues"]
        + [dict(kind="unresolved-connector", **row) for row in unresolved]
    )
    return {
        "issues": issues,
        "markers": specific["markers"],
        "forks": specific["forks"],
        "connector_count": geometry["connectorCount"],
        "role_measurements": [
            {
                "id": e["id"],
                "role": e["role"],
                "source": e.get("sourceRef", {}).get("id"),
                "target": e.get("targetRef", {}).get("id"),
                "metrics": e.get("roleMetrics", e.get("gapMetrics", {})),
            }
            for e in geometry["elements"]
            if e.get("role")
        ],
        "unresolved": unresolved,
    }
