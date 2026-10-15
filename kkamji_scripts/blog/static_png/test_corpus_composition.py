"""Selected serial boundaries share extents; tier titles keep word spacing."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'kkamji_scripts/blog'))
import fhd_svg as f


@pytest.fixture(scope='module')
def layouts(tmp_path_factory):
    captured = []
    original = f.check_layout
    def capture(layout):
        captured.append(layout)
        return original(layout)
    f.check_layout = capture
    try:
        assert f.author(ROOT, True, tmp_path_factory.mktemp('composition') / 'check.json') == 0
    finally:
        f.check_layout = original
    import json
    catalog = json.loads((ROOT / 'docs/diagram-catalog.json').read_text())['diagrams']
    return {row['include']: layout for row, layout in zip(catalog, captured)}


@pytest.mark.parametrize('include,keys', [
    ('diagrams/static/ci-cd/ci-cd-study/ci-cd-workflow.html', ('root.0.1.0', 'root.0.1.2')),
    ('diagrams/static/ci-cd/jenkins/jenkins-pipeline-layers.html', ('root.0.1.0', 'root.0.1.2')),
    ('diagrams/static/sap-c02/sts-assume-role-cross-account.html', ('root.0.1.0', 'root.0.1.2')),
    ('diagrams/static/spring/spring-24-authn-authz.html', ('root.0.1.0', 'root.0.1.2')),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-pipeline.html', ('root.0.3', 'root.0.5')),
])
def test_confirmed_serial_boundaries_share_top_bottom(layouts, include, keys):
    groups = {g['source']: g for g in layouts[include].groups}
    a, b = (groups[key] for key in keys)
    assert abs(a['y'] - b['y']) <= 1
    assert abs(a['y'] + a['height'] - b['y'] - b['height']) <= 1


@pytest.mark.parametrize('tier', ['Professional', 'Associate', 'Foundational', 'Specialty', 'Business'])
def test_certification_tier_title_separates_adjacent_inline_labels(layouts, tier):
    assert any(t['text'].startswith(tier + ' ') for t in layouts['diagrams/aws-certification-map.html'].texts)


def test_packer_builder_caption_has_a_real_card_corridor(layouts):
    drawing = layouts['diagrams/packer-golden-image.html']
    boxes = {b['source']: b for b in drawing.boxes}
    a, b = boxes['root.0.1.1.0'], boxes['root.0.1.1.2']
    captions = [t for t in drawing.texts if t['source'] == 'root.0.1.1.1']
    assert captions
    for text in captions:
        assert text['x'] >= a['x'] + a['width'] + 12
        assert text['x'] + text['width'] <= b['x'] - 12


@pytest.mark.parametrize('kind', ['card', 'group'])
def test_declared_inner_clearance_rejects_touching_strokes(kind):
    drawing = f.Layout(None, 32, 26, profile={'group_insets': {'root.0.1': 24}})
    drawing.groups.append({'source': 'root.0.1', 'x': 200, 'y': 200, 'width': 400, 'height': 400, 'classes': []})
    child = {'source': 'root.0.1.0', 'x': 200, 'y': 200, 'width': 120, 'height': 100, 'classes': [], 'label': 'child'}
    (drawing.boxes if kind == 'card' else drawing.groups).append(child)
    assert any(i['code'] == 'declared-inner-stroke-clearance' for i in f.check_layout(drawing))
    child.update(x=224, y=224)
    assert not any(i['code'] == 'declared-inner-stroke-clearance' for i in f.check_layout(drawing))
    drawing.profile = {}
    child.update(x=200, y=200)
    assert not any(i['code'] == 'declared-inner-stroke-clearance' for i in f.check_layout(drawing))


def test_numbered_section_titles_keep_name_and_number_together(layouts):
    drawing = layouts['diagrams/static/ai/rag-02-chunking-strategies.html']
    for number in range(1, 4):
        key = 'root.0.1.1.1.' + str(number - 1)
        labels = [t['text'] for t in drawing.texts if t['source'] == key and t['label']]
        assert labels == ['Section ' + str(number)]


@pytest.mark.parametrize('include,key', [
    ('diagrams/static/kubernetes/karpenter-provisioning-flow.html', 'root.0.1.1'),
    ('diagrams/static/kubernetes/mysql-kubernetes-deployment.html', 'root.0.4.1'),
    ('diagrams/static/observability/log_monitoring.html', 'root.0.2.1'),
])
def test_refuted_candidate_true_caption_contacts_have_stroke_clearance(layouts, include, key):
    drawing = layouts[include]
    edge = next(e for e in drawing.connectors if e['source'] == key)
    boxes = {b['source']: b for b in drawing.boxes}
    target = boxes[edge['to'][0]]
    labels = [t for t in drawing.texts if t['source'] == key]
    assert labels
    assert all(t['x'] + t['width'] <= target['x'] - 12 for t in labels)


def test_kinesis_alternative_models_are_centered_without_serializing_them(layouts):
    drawing = layouts['diagrams/static/sap-c02/kinesis-efo-vs-shared-consumers.html']
    boundary = next(g for g in drawing.groups if g['source'] == 'root.0.2.4')
    assert abs(boundary['x'] + boundary['width'] / 2 - f.WIDTH / 2) <= 1
    assert len(drawing.connectors) == 2


def test_litellm_adjunct_label_tracks_proxy_database_relation(layouts):
    drawing = layouts['diagrams/static/ai/litellm-architecture.html']
    edge = next(e for e in drawing.connectors if e['source'] == 'root.0.2.0')
    assert edge['from'] == ['root.0.1.2'] and edge['to'] == ['root.0.2.1']
    assert edge['undirected'] is True
    labels = [t for t in drawing.texts if t['source'] == edge['source']]
    assert labels
    assert all(12 <= t['x'] - edge['points'][0][0] <= 48 for t in labels)


def test_spring_batch_result_is_centered_in_balanced_comparison(layouts):
    drawing = layouts['diagrams/static/spring/spring-20-n-plus-1-fix.html']
    groups = {g['source']: g for g in drawing.groups}
    left, right = groups['root.0.1.0'], groups['root.0.1.1']
    assert abs(left['y'] - right['y']) <= 1
    assert abs(left['height'] - right['height']) <= 1
    result = next(b for b in drawing.boxes if b['source'] == 'root.0.1.1.1.4')
    assert abs(result['x'] + result['width'] / 2 - right['x'] - right['width'] / 2) <= 1
    assert len(drawing.connectors) == 3


@pytest.mark.parametrize('include,target', [
    ('diagrams/static/ai/agentic-development-workspace.html', 'Workspace'),
    ('diagrams/static/ai/graph-system-intelligence.html', 'Shared state'),
])
def test_non_temporal_blank_relations_do_not_invent_next_stage(layouts, include, target):
    drawing = layouts[include]
    edge = next(e for e in drawing.connectors if e['source'] == 'root.0.4')
    assert edge['from'] == ['root.0.3'] and edge['to'] == ['root.0.5']
    assert edge['label'] == ''
    assert edge['meaning'] == target
    assert edge['meaning_at_target'] is True
    assert not any(t['source'] == 'root.0.4.meaning' for t in drawing.texts)


def test_graph_loop_ontology_peers_do_not_wrap_into_left_only_lower_row(layouts):
    drawing = layouts['diagrams/static/ai/graph-system-intelligence.html']
    groups = {g['source']: g for g in drawing.groups}
    peers = [groups['root.0.1.' + str(i)] for i in range(3)]
    assert max(g['y'] for g in peers) - min(g['y'] for g in peers) < 1
    assert peers[0]['x'] < peers[1]['x'] < peers[2]['x']
