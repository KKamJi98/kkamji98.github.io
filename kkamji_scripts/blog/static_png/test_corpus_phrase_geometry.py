"""Protected native phrases fit at their existing source font sizes."""
from pathlib import Path
import sys,json,hashlib
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'kkamji_scripts/blog'))
import fhd_svg as f

@pytest.fixture(scope='module')
def drawings():
    lookup={hashlib.sha256(f.source_fragment((ROOT/'_includes'/r['include']).read_text()).encode()).hexdigest():r['include'] for r in json.loads((ROOT/'docs/diagram-catalog.json').read_text())['diagrams']}
    found={};original=f.svg_document
    def capture(layout,figure,source_hash):
        found[lookup[source_hash]]=layout
        return original(layout,figure,source_hash)
    f.svg_document=capture
    try:f.author(ROOT,True,None)
    finally:f.svg_document=original
    return found

@pytest.mark.parametrize('include,key', [
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.1'),
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.3'),
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.5'),
 ('diagrams/static/observability/kibana-query-flow.html','root.0.1.1'),
 ('diagrams/static/observability/log_monitoring.html','root.0.2.3'),
])
def test_adjacent_caption_real_ink_keeps_two_stroke_margins(drawings,include,key):
    from PIL import ImageFont
    layout=drawings[include]
    edge=next(e for e in layout.connectors if e['source']==key)
    boxes={b['source']:b for b in layout.boxes}
    source,target=boxes[edge['from'][0]],boxes[edge['to'][0]]
    runs=[t for t in layout.texts if t['source']==key]
    assert runs
    font=ImageFont.truetype(str(ROOT/f.FONT),2000,layout_engine=ImageFont.Layout.RAQM)
    font.set_variation_by_axes([400])
    for t in runs:
        left,_,right,_=font.getbbox(t['text'],anchor='ls');scale=t['size']/2000
        assert t['x']+left*scale-source['x']-source['width']>=12-.001
        assert target['x']-t['x']-right*scale>=12-.001


@pytest.mark.parametrize('include,key,font,phrase',[
 ('diagrams/static/kubernetes/endpoint_vs_endpointslice.html','root.0.2.1.2',(24,20),'node metadata도'),
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.1',(28,22),'x + 1을 확인하고'),
 ('diagrams/static/sap-c02/data-transfer-charge-points.html','root.0.1.2.3.1.2',(18,16),'전송 요금'),
])
def test_uncached_native_remaining_phrases(drawings,include,key,font,phrase):
    layout=drawings[include]
    assert (layout.label_size,layout.detail_size)==font
    assert any(phrase in t['text']for t in layout.texts if t['source']==key)


def test_endpoint_slice_note_keeps_real_ink_in_its_parent(drawings):
    from PIL import ImageFont
    layout=drawings['diagrams/static/kubernetes/endpoint_vs_endpointslice.html']
    frame=next(g for g in layout.groups if g['source']=='root.0.2.1')
    font=ImageFont.truetype(str(ROOT/f.FONT),2000,layout_engine=ImageFont.Layout.RAQM)
    font.set_variation_by_axes([400])
    for t in (t for t in layout.texts if t['source']=='root.0.2.1.2'):
        _,_,right,_=font.getbbox(t['text'],anchor='ls')
        assert frame['x']+frame['width']-1-t['x']-right*t['size']/2000>=12


def test_two_registry_inputs_have_separate_target_ports(drawings):
    for include in ['diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html',
                    'diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html']:
        layout=drawings[include]
        pull=next(e for e in layout.connectors if e['source'].endswith('.image-pull'))
        others=[e for e in layout.connectors if e is not pull and e['to']==pull['to']]
        assert others
        assert all(abs(e['points'][-1][1]-pull['points'][-1][1])>=24 for e in others)


def test_tcp_text_inset_keeps_native_ink_off_both_strokes(drawings):
    from PIL import ImageFont
    layout=drawings['diagrams/static/network/tcp-3-way-handshake.html']
    for t in layout.texts:
        matches=[b for b in layout.boxes if b['source']==t['source']]
        if not matches:
            continue
        node=matches[0]
        font=ImageFont.truetype(str(ROOT/f.FONT),2000,layout_engine=ImageFont.Layout.RAQM)
        font.set_variation_by_axes([700 if t['label'] else 400])
        left,_,right,_=font.getbbox(t['text'],anchor='ls');scale=t['size']/2000
        assert t['x']+left*scale-node['x']-1>=12, (node['source'],t['text'])
        assert node['x']+node['width']-1-t['x']-right*scale>=12, (node['source'],t['text'])


def test_four_eks_alternatives_use_two_by_two_peer_tracks(drawings):
    layout=drawings['diagrams/static/sap-c02/eks-compute-option-split.html']
    frames=[g for g in layout.groups if g['source'] in [f'root.0.2.2.{n}'for n in range(4)]]
    assert len(frames)==4
    assert len({round(g['x'],3)for g in frames})==2
    assert len({round(g['y'],3)for g in frames})==2


@pytest.mark.parametrize('include,source,font,phrase',[
 ('diagrams/packer-golden-image.html','root.0.1.1.2',(28,22),'설정 저장'),
 ('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html','root.0.2.0.2.2',(24,20),'이미지 저장소'),
 ('diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html','root.0.2.1.2.2',(20,18),'live state와 비교'),
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.4',(28,22),'ESTABLISHED로 이동'),
 ('diagrams/static/observability/kibana-query-flow.html','root.0.1.6',(28,22),'검색 대상'),
 ('diagrams/packer-golden-image.html','root.0.1.1.1',(28,22),'임시 EC2 생성'),
 ('diagrams/static/network/tcp-3-way-handshake.html','root.0.2.1',(28,22),'자신의 sequence를 보냄'),
 ('diagrams/static/jvm/jvm-02-stack-vs-heap.html','root.0.1.3',(28,22),'new Order()가'),
 ('diagrams/static/observability/kibana-query-flow.html','root.0.1.3',(28,22),'Elasticsearch에'),
 ('diagrams/static/kubernetes/cilium/cilium_l7_layer_policy.html','root.0.1.2.1.1.0.1.1',(24,20),'/v1/exhaust-port'),
 ('diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html','root.0.1.6.1.1.2.2',(22,18),'INSUFFICIENT_DATA'),
])
def test_original_font_and_whole_protected_phrase(drawings,include,source,font,phrase):
    layout=drawings[include]
    assert (layout.label_size,layout.detail_size)==font
    assert any(phrase in t['text'] for t in layout.texts if t['source']==source)
