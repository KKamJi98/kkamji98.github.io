"""Coordinate-only clearance repair for the existing Pod Identity custom layout.

Call repair_pod_identity_clearance(layout, figure) once after the custom builder
has resolved its source edges. It mutates and returns that same Layout, without
importing the compiler. It never measures/reflows cards, changes typography or
writes artwork. This is not an opt-in for external legend/text containment.

The seven painted frames reserve 24px around actual descendant cards/frames,
leaving 22px between their existing 2px strokes. Static geometry does not prove
native glyph containment or pixel-level visual quality; Main owns those gates.
"""

from __future__ import annotations


INCLUDE = "diagrams/static/kubernetes/pod-identity-workflow.html"
INSET = 24
CLOUD = "root.0.2.0"
CLUSTER = "root.0.2.1"
REGISTRATION = CLOUD + ".1.0"
VALIDATION = CLOUD + ".1.1"
CONTROL = CLUSTER + ".1"
WORKER = CLUSTER + ".2.0"
EXCHANGE = CLUSTER + ".2.1"
PAINTED_GROUPS = (CLOUD, CLUSTER, REGISTRATION, VALIDATION, CONTROL, WORKER, EXCHANGE)
WORKER_EDGES = tuple(WORKER + ".1." + str(i) for i in (1, 3))
EXCHANGE_EDGES = tuple(EXCHANGE + ".1." + str(i) for i in (1, 3, 5, 7))
# Source ancestry alone would mistake these deliberately external legends for
# child cards. Only their inline .meaning markers follow translated arrows.
EXTERNAL_LEGENDS = frozenset(
    key for edge in WORKER_EDGES + EXCHANGE_EDGES
    for key in (edge, edge + ".legend.meaning")
)


def _translate(layout, prefix, dy):
    """Translate a real subtree, keeping arrow points and unpainted bounds in sync."""
    seen = set()
    for rect in layout.boxes + layout.groups + list(layout.group_bounds.values()):
        if id(rect) not in seen and (rect["source"] == prefix or rect["source"].startswith(prefix + ".")):
            rect["y"] += dy
            seen.add(id(rect))
    for text in layout.texts:
        if (text["source"] == prefix or text["source"].startswith(prefix + ".")) and text["source"] not in EXTERNAL_LEGENDS:
            text["y"] = round(text["y"] + dy, 3)
    for edge in layout.connectors:
        if edge["source"].startswith(prefix + "."):
            edge["points"] = [[x, y + dy] for x, y in edge["points"]]


def repair_pod_identity_clearance(layout, figure):
    """Repair only this custom builder's painted hierarchy, in place and idempotently.

    Accept the parsed semantic figure and its complete original custom Layout.
    Unsupported or incomplete figures fail before any coordinate is changed.
    Existing node sizes, text runs, directed identities and 12px arrow standoffs
    are retained. Integration belongs immediately before the builder's return.
    """
    if figure.attrs.get("id") != "pod-identity-workflow":
        raise ValueError("Pod Identity repair requires its exact semantic figure")
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    groups = {g["source"]: g for g in layout.groups}
    boxes = {b["source"]: b for b in layout.boxes}
    expected_nodes = {key for key, e in elements.items() if layout.kind(e) == "node"}
    expected_edges = {key for key, e in elements.items() if layout.kind(e) == "edge"}
    if (set(groups) != set(PAINTED_GROUPS) or set(boxes) != expected_nodes
            or len(groups) != len(layout.groups) or len(boxes) != len(layout.boxes)
            or {e["source"] for e in layout.connectors} != expected_edges
            or len(layout.connectors) != len(expected_edges)):
        raise ValueError("Pod Identity repair requires every original painted frame/card/edge")
    if getattr(layout, "_pod_identity_clearance_repaired", False):
        return layout

    # Keep the Cloud bottom and peer lanes aligned. Move the Cloud subtree up
    # by its 19px deficit, then recover the outer frame's original bottom.
    cloud_bottom = groups[CLOUD]["y"] + groups[CLOUD]["height"]
    validation_bottom = groups[VALIDATION]["y"] + groups[VALIDATION]["height"]
    cloud_lift = max(0, INSET - (cloud_bottom - validation_bottom))
    _translate(layout, CLOUD, -cloud_lift)
    groups[CLOUD]["height"] += cloud_lift

    # Three true child-card bottoms had only 8px geometric clearance.
    for key in (REGISTRATION, CONTROL, EXCHANGE):
        group = groups[key]
        bottom = max(b["y"] + b["height"] for b in layout.boxes
                     if b["source"].startswith(key + "."))
        group["height"] = max(group["height"], bottom + INSET - group["y"])

    # Inset the lane frames horizontally without resizing or rewrapping cards.
    # Headings track the changed left edge; card text stays exactly as authored.
    for parent, children in ((CLOUD, (REGISTRATION, VALIDATION)),
                             (CLUSTER, (CONTROL, WORKER, EXCHANGE))):
        outer = groups[parent]
        for key in children:
            group = groups[key]
            left = max(group["x"], outer["x"] + INSET)
            right = min(group["x"] + group["width"], outer["x"] + outer["width"] - INSET)
            dx = left - group["x"]
            group.update(x=left, width=right - left)
            for text in layout.texts:
                if text["source"] == key + ".0":
                    text["x"] = round(text["x"] + dx, 3)

    # Control Plane expansion consumes 16px. Move both lower peer lanes by the
    # same amount, retaining the original 20px sibling corridor and all cards.
    control_bottom = groups[CONTROL]["y"] + groups[CONTROL]["height"]
    lower_shift = max(0, control_bottom + 20 - groups[WORKER]["y"])
    for key in (WORKER, EXCHANGE):
        _translate(layout, key, lower_shift)
    # The numeric legend belongs outside the exchange frame, not in the cache.
    for text in layout.texts:
        if text["source"] in {key for edge in EXCHANGE_EDGES
                              for key in (edge, edge + ".legend.meaning")}:
            text["y"] = round(text["y"] + 2 * lower_shift, 3)
        elif text["source"] == "root.0.5":
            text["y"] = round(text["y"] + lower_shift / 2, 3)

    # Only the signed request's source moved. Its S3 target and x=668 corridor
    # stay fixed; do not translate the target or turn this into a Role request.
    signed = next(e for e in layout.connectors if e["source"] == "root.0.3")
    source_box = boxes[WORKER + ".1.4"]
    sy = source_box["y"] + source_box["height"] / 2
    signed["points"][0][1] = sy
    signed["points"][1][1] = sy

    for key in PAINTED_GROUPS:
        layout.group_bounds[key] = dict(groups[key])
    layout.profile["group_insets"] = {
        **layout.profile.get("group_insets", {}),
        **dict.fromkeys(PAINTED_GROUPS, INSET),
    }
    layout._pod_identity_clearance_repaired = True
    return layout
