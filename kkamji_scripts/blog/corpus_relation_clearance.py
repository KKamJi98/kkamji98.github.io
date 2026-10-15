"""Source-scoped relation clearance; no compiler imports or artwork writes.

Merge scoped_profile(include) before measure/draw. Call repair_relations after
manual_relation_fixes and before complete_relation_labels (on either side of
complete_group_boundaries). Geometry evidence is
not native pixel approval. In particular, the Pod Identity sibling gap is 6px.

The caller must measure row captions with the same 12px insets used at draw
and negotiate a fitting density before drawing. A postlayout font reduction is
not a substitute for that contract. Tests isolate the confirmed source density;
the production author-loop integration is a separate Main-owned gate.
"""
from __future__ import annotations

SCOPES = {
    112: "diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html",
    117: "diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html",
    215: "diagrams/static/kubernetes/horizontal-pod-autoscaling.html",
    227: "diagrams/static/kubernetes/mysql-kubernetes-deployment.html",
    231: "diagrams/static/kubernetes/pod-identity-workflow.html",
    265: "diagrams/static/project/rememberme/waf_alarm_workflow.html",
    297: "diagrams/static/sap-c02/dns-global-traffic-decision-layers.html",
}


def scoped_profile(include):
    """Return fresh opt-in measure/draw settings for an exact catalog include."""
    if include == SCOPES[215]:
        return {"edge_widths": {"root.0.1": 168},
                "edge_label_insets": {"root.0.1.3": 12}}
    if include == SCOPES[265]:
        return {"edge_widths": {"root.0.1": 180},
                "edge_label_insets": {"root.0.1.7": 12}}
    return {}


def repair_relations(layout, figure, include):
    """Repair a supported Layout in place; leave all other sources untouched."""
    if include not in SCOPES.values():
        return layout
    expected_figure = {
        SCOPES[112]: "jenkins-ci-workflow",
        SCOPES[117]: "kubernetes-gitops-loop",
        SCOPES[227]: "sd-kubernetes-mysql-kubernetes-deployment",
        SCOPES[231]: "pod-identity-workflow",
        SCOPES[297]: "dns-global-traffic-decision-layers",
    }.get(include)
    if expected_figure is None:
        return layout  # These two sources need premeasure profiles only.
    if figure.attrs.get("id") != expected_figure:
        raise ValueError("Relation repair requires the exact source figure for " + include)
    done = getattr(layout, "_relation_clearance_repaired", frozenset())
    if include in done:
        return layout
    if include == SCOPES[112]:
        key = "root.0.2.1.2.3"
        elements = {e.key: e for e in [figure, *figure.descendants()]}
        boxes = {box["source"]: box for box in layout.boxes}
        edge = next(e for e in layout.connectors if e["source"] == key)
        labels = [e.text() for e in elements[key].children if "sd-edge-label" in e.classes]
        required = {"root.0.2.0.2.2", "root.0.2.1.2.2", "root.0.2.1.2.4"}
        if not required <= boxes.keys():
            raise ValueError("Jenkins repair requires the real Registry, CD and K8S source boxes")
        registry = boxes["root.0.2.0.2.2"]
        cd = boxes["root.0.2.1.2.2"]
        target = boxes["root.0.2.1.2.4"]
        if len(labels) != 2 or edge.get("from") != [cd["source"]] or edge.get("to") != [target["source"]]:
            raise ValueError("Jenkins repair requires the original CD input and two source labels")
        if any(e["source"] == key + ".image-pull" for e in layout.connectors):
            raise ValueError("Jenkins image-pull input already exists without the repair marker")
        sy = registry["y"] + registry["height"] / 2
        ty = target["y"] + target["height"] / 2
        bus = (registry["x"] + registry["width"] + target["x"]) / 2
        cd_width = cd["x"] + cd["width"] - target["x"]
        size = layout.detail_size
        # Retain the original CD route; its wide inter-row strip can hold this
        # first label on one line. The registry caption belongs below its card.
        cd_bounds = (target["x"], edge["points"][2][1] - 2 * size, cd_width)
        lane = next(g for g in layout.groups if g["source"] == "root.0.2.0")
        # The first baseline is y + size: ty - 80 put its glyph ink on the
        # lane's bottom stroke. Use the measured empty corridor BELOW the lane.
        pull_y = max(lane["y"] + lane["height"] + 12, ty - 40)
        pull_bounds = (registry["x"], pull_y, registry["width"])
        cd_lines = layout.wrap(labels[0], cd_width, size, source=key)
        pull_lines = layout.wrap(labels[1], registry["width"], size, source=key)
        edge.update(label=labels[0], origin=key, meaning_bounds=cd_bounds)
        layout.connectors.append({
            "source": key + ".image-pull", "origin": key,
            "label": labels[1], "from": [registry["source"]], "to": [target["source"]],
            "points": [[registry["x"] + registry["width"] + 12, sy], [bus, sy],
                       [bus, ty - 24], [target["x"] - 12, ty - 24]],
            "meaning_bounds": pull_bounds,
        })
        layout.texts = [t for t in layout.texts if t["source"] != key]
        # Both paragraphs retain their real semantic arrow origin, so semantic
        # and character coverage gates see the complete source text in order.
        layout.add_text(cd_lines, *cd_bounds[:2], size, cd_width, key)
        layout.add_text(pull_lines, *pull_bounds[:2], size, registry["width"], key)
    elif include == SCOPES[117]:
        pull = next(e for e in layout.connectors if e['source'].endswith('.image-pull'))
        pull['points'] = [[x, y - 24 if i >= len(pull['points']) - 2 else y]
                          for i, (x, y) in enumerate(pull['points'])]
        boxes = {box["source"]: box for box in layout.boxes}
        cluster = boxes["root.0.2.1.2.4"]
        key = "root.0.2.1.2.3"
        elements = {e.key: e for e in [figure, *figure.descendants()]}
        labels = [e for e in elements[key].children if "sd-edge-label" in e.classes]
        runs = [t for t in layout.texts if t["source"] == key and t["x"] == cluster["x"]]
        if len(labels) != 2 or "".join("".join(t["text"].split()) for t in runs) != "".join(labels[0].text().split()):
            raise ValueError("GitOps repair requires the existing separate CD caption")
        top_key = "root.0.2.1.1"
        top_edge = next(e for e in layout.connectors if e["source"] == top_key)
        top_runs = [t for t in layout.texts if t["source"] == top_key]
        top_label = elements[top_key].text()
        if (top_edge["label"] != top_label
                or " ".join(t["text"] for t in top_runs) != top_label
                or not top_label.endswith(": Pull Request")):
            raise ValueError("GitOps repair requires the original top Pull Request caption")
        frame = next(g for g in layout.groups if g["source"] == "root.0.2.1")
        first = top_runs[0]
        width = frame["x"] + frame["width"] - first["x"] - 24
        # Keep the action together, reserve the physical-font right inset and
        # move these two lines 8px up into the existing title-to-flow corridor.
        prefix, _, action = top_label.rpartition(": ")
        top_lines = [line for part in (prefix + ":", action)
                     for line in layout.wrap(part, width, first["size"], source=top_key)]
        for text in runs:
            text["y"] = round(text["y"] - 34, 3)
        layout.texts = [t for t in layout.texts if t["source"] != top_key]
        layout.add_text(top_lines, first["x"], first["y"] - first["size"] - 8,
                        first["size"], width, top_key)
    elif include == SCOPES[227]:
        elements = {e.key: e for e in [figure, *figure.descendants()]}
        boxes = {b["source"]: b for b in layout.boxes}
        key, flow_key, pod_key = "root.0.3", "root.0.4", "root.0.4.0"
        edge = next(e for e in layout.connectors if e["source"] == key)
        if (edge.get("from") != ["root.0.2"] or edge.get("to") != [flow_key]
                or edge.get("label") != elements[key].text()
                or not edge["label"].endswith("Pod에 주입하고 mount")
                or pod_key not in boxes or "MySQL Pod" not in elements[pod_key].text()):
            raise ValueError("MySQL repair requires the original injection relation and actual Pod")
        pod = boxes[pod_key]
        start = list(edge["points"][0])
        target = [pod["x"] + pod["width"] / 2, pod["y"] - 12]
        middle = (start[1] + target[1]) / 2
        edge.update(to=[pod_key], points=[start, [start[0], middle],
                                         [target[0], middle], target])
        # The source is an unlabelled sequence, not an ownership boundary.
        # Only complete_group_boundaries' synthetic frame may be removed; an
        # explicit labelled/owned frame and every real input lane stay intact.
        flow = elements[flow_key]
        if flow.classes == {"sd-flow"} and flow.attrs == {"class": "sd-flow"}:
            layout.groups = [g for g in layout.groups
                             if not (g["source"] == flow_key and g.get("relation_boundary"))]
    elif include == SCOPES[231]:
        key = "root.0.2.1"
        frame = next(g for g in layout.groups if g["source"] == key)
        bounds = layout.group_bounds[key]
        # root.0.5 is an external note, NOT an EKS descendant. Expanding just
        # this frame leaves 12.994px below its glyph ink and a 6px sibling gap.
        height = max(frame["height"], 530)
        a_key = "root.0.2.1.2.0.1.1"
        legend = [t for t in layout.texts
                  if t["source"] in (a_key, a_key + ".legend.meaning")]
        if len(legend) != 2 or {t["text"] for t in legend} != {"A", "retrieve credentials"}:
            raise ValueError("Pod Identity repair requires the original A legend pair")
        worker_note = next(t for t in layout.texts if t['source'] == 'root.0.2.1.2.0.2')
        worker_frame = next(g for g in layout.groups if g['source'] == 'root.0.2.1.2.0')
        worker_note['x'] = max(worker_note['x'], worker_frame['x'] + 24)
        worker_note['y'] -= 6
        frame["height"] = bounds["height"] = height
        # A's former 964 baseline crosses the enlarged bottom stroke at 960.
        # The measured 912.4..960 corridor is empty LEFT of the external note.
        # Inset A inside the outer frame, above that stroke; B/S3 stay fixed.
        dx = frame["x"] + 24 - min(t["x"] for t in legend)
        dy = frame["y"] + height - 20 - max(t["y"] for t in legend)
        for text in legend:
            text["x"] = round(text["x"] + dx, 3)
            text["y"] = round(text["y"] + dy, 3)
    elif include == SCOPES[297]:
        edge = next(e for e in layout.connectors if e["source"] == "root.0.2.2.3.0")
        points = edge["points"]
        if (edge.get("from") != ["root.0.2.2.1"]
                or edge.get("to") != ["root.0.2.2.3.1"]
                or len(points) != 4 or points[1][0] != points[2][0]
                or points[1][0] not in (1856, 1872)):
            raise ValueError("CloudFront repair requires its own four-point origin route")
        # Keep both 12px node standoffs and every y coordinate. Crossing this
        # lane horizontally is intentional; following its vertical stroke is not.
        edge["points"] = [[x, y] if i in (0, 3) else [1872, y]
                          for i, (x, y) in enumerate(points)]
    layout._relation_clearance_repaired = done | {include}
    return layout
