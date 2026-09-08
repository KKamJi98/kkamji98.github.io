"""Explicit semantic roles for connectors whose endpoints cross DOM groups."""

import math


def _bounds(quads):
    xs = [x for q in quads for x in q[::2]]
    ys = [y for q in quads for y in q[1::2]]
    return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def _distance(a, b):
    return math.hypot(
        max(a["x"] - b["x"] - b["w"], b["x"] - a["x"] - a["w"], 0),
        max(a["y"] - b["y"] - b["h"], b["y"] - a["y"] - a["h"], 0),
    )


def resolve_role(element):
    role = element.get("role", "")
    if not role:
        return None
    classes = set(element["cls"].split())
    output = {"handled": True, "findings": [], "unresolved": []}

    def unresolved(reason):
        output["unresolved"].append(
            {"id": element["id"], "reason": reason, "role": role}
        )
        return output

    if role not in ("continuation", "reference", "reference-note", "loop"):
        return unresolved("unknown connector role")
    if role == "continuation":
        target = element.get("following")
        structural = {
            "sd-grid",
            "sd-band",
            "sd-lane",
            "sd-loop",
            "sd-node",
            "sd-stack",
            "sd-flow",
        }
        if (
            "sd-arrow" not in classes
            or "sd-flow" not in element["parent"].split()
            or not element.get("lastSibling")
            or element.get("next") is not None
            or element.get("prev") is None
            or not target
            or not structural.intersection(target["cls"].split())
        ):
            return unresolved(
                "continuation must terminate its flow before an explicit following group"
            )
        element["next"] = target
        element["disposition"] = (
            "explicit following-group continuation; target members remain alternatives"
        )
        output["handled"] = False
        return output

    source = element.get("sourceRef", {})
    target = element.get("targetRef", {})
    if source.get("count") != 1 or target.get("count") != 1:
        return unresolved("named connector endpoints are missing or ambiguous")
    for endpoint in (source, target):
        box = endpoint.get("box", {})
        if (
            "sd-node" not in endpoint.get("cls", "").split()
            or endpoint.get("hidden", False)
            or box.get("w", 0) <= 0
            or box.get("h", 0) <= 0
        ):
            return unresolved("named connector endpoint is not a visible node")
    if role == "loop":
        if "sd-loop" not in classes or element.get("loopOrderValid") is not True:
            return unresolved("loop must connect its last action to its first action")
        from connector_loop import inspect_loop

        checked = inspect_loop(element)
        output["findings"] = [
            {"id": element["id"], "type": code, "metrics": checked["metrics"]}
            for code in checked["findings"]
        ]
        output["unresolved"] = [
            {"id": element["id"], "reason": code} for code in checked["unresolved"]
        ]
        element["roleMetrics"] = checked["metrics"]
        element["disposition"] = (
            "declared rounded return or self-action; painted contacts checked"
        )
        return output

    polygons = [
        q for p in element.get("pseudos", []) for q in p.get("paintPolygons", [])
    ]
    if role == "reference-note":
        if (
            "sd-reference" not in classes
            or "sd-arrow" in classes
            or not element.get("text")
        ):
            return unresolved("reference note needs explicit text and no arrow class")
        if polygons:
            output["findings"].append(
                {"id": element["id"], "type": "reference-note-painted-glyph"}
            )
        element["disposition"] = "named non-edge reference annotation"
        return output

    if (
        "sd-arrow" not in classes
        or not element.get("targetIsLocal")
        or not element.get("next")
    ):
        return unresolved(
            "reference target must belong to the following local boundary"
        )
    painted = {p["type"] for p in element.get("pseudos", []) if p.get("paintPolygons")}
    required = {"after", "before"} if "sd-arrow--both" in classes else {"after"}
    if not required.issubset(painted):
        return unresolved("reference direction has a missing painted arrowhead")
    box = _bounds(polygons)
    boundaries = [element["next"]]
    if element.get("prev") is not None:
        boundaries.append(element["prev"])
    distances = [_distance(box, boundary["box"]) for boundary in boundaries]
    if min(distances) < 4:
        output["findings"].append(
            {
                "id": element["id"],
                "type": "reference-local-boundary-clearance",
                "distances": distances,
                "minimum": 4,
            }
        )
    element["roleMetrics"] = {
        "localBoundaryDistances": distances,
        "source": source["id"],
        "target": target["id"],
        "remoteSourceAttachmentRequired": False,
    }
    element["disposition"] = (
        "named incoming reference; no physically routed source bus asserted"
    )
    return output
