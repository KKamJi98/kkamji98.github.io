"""Source-declared relationship identities must override visual neighbor order."""
from test_corpus_composition import layouts
import pytest

@pytest.mark.parametrize('include,key,target', [
 ('diagrams/static/sap-c02/directory-service-selection.html','root.0.1.0.3.0.1.1','root.0.1.0.3.0.1.2'),
 ('diagrams/static/sap-c02/dms-schema-object-ownership.html','root.0.1.2.0.1.1','root.0.1.2.0.1.2'),
 ('diagrams/static/sap-c02/dms-schema-object-ownership.html','root.0.1.2.1.1.1','root.0.1.2.1.1.2'),
 ('diagrams/static/sap-c02/aurora-global-switchover-failover.html','root.0.1.1','root.0.1.2'),
])
def test_blank_support_output_replication_arrows_do_not_invent_stages(layouts,include,key,target):
 drawing=layouts[include];edge=next(e for e in drawing.connectors if e['source']==key)
 labels=' '.join(t['text'] for t in drawing.texts if t['source']==target and t['label'])
 assert edge['label']=='' and edge['to']==[target]
 assert ''.join(edge['meaning'].split())==''.join(labels.split())
 assert edge['meaning_at_target'] is True
 assert not any(t['source']==key+'.meaning' for t in drawing.texts)


def test_jenkins_registry_is_actual_image_pull_source(layouts):
 drawing=layouts['diagrams/static/ci-cd/ci-cd-study/jenkins-ci-overview.html']
 edge=next(e for e in drawing.connectors if e['source']=='root.0.2.1.2.3')
 assert edge['from']==['root.0.2.0.2.2']
 assert edge['to']==['root.0.2.1.2.4']
 assert edge['label']=='Registry -> node runtime: image pull'


def test_gitops_image_pull_and_manifest_application_have_independent_sources(layouts):
 drawing=layouts['diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html']
 incoming=[e for e in drawing.connectors if e.get('to')==['root.0.2.1.2.4']]
 assert len(incoming)==2
 assert {(tuple(e['from']),e['label']) for e in incoming}=={
  (('root.0.2.1.2.2',),'CD -> Kubernetes clusters: desired state 적용'),
  (('root.0.2.0.2.0',),'Image Registry -> Kubernetes clusters: Pull')}


def test_oidc_self_call_is_not_invented_retry_and_stays_inside_its_frame(layouts):
 drawing=layouts['diagrams/static/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.html']
 edge=next(e for e in drawing.connectors if e['source']=='root.0.2.loop')
 frame=next(g for g in drawing.groups if g['source']=='root.0.2')
 assert '반복' not in edge['label']
 assert 'session' in edge['label']
 assert edge['from']==edge['to']==['root.0.2.0.0']
 assert all(frame['x']<x<frame['x']+frame['width'] and frame['y']<y<frame['y']+frame['height'] for x,y in edge['points'])


def test_config_change_recording_reaches_recorder_not_gap(layouts):
 drawing=layouts['diagrams/static/sap-c02/config-evaluation-remediation.html']
 edge=next(e for e in drawing.connectors if e['source']=='root.0.1.0.0.2')
 assert edge['to']==['root.0.1.0.0.3.0']
 box=next(b for b in drawing.boxes if b['source']==edge['to'][0])
 assert abs(edge['points'][-1][0]-(box['x']+box['width']/2))<1
 assert abs(edge['points'][-1][1]-(box['y']-12))<1


def test_vso_controller_vault_reference_avoids_unrelated_namespace_frame(layouts):
 drawing=layouts['diagrams/static/ci-cd/ci-cd-study/vault-secrets-operator.html']
 edge=next(e for e in drawing.connectors if e['source']=='root.0.4.0.0')
 namespace=next(g for g in drawing.groups if g['source']=='root.0.4.1.1')
 assert edge['from']==['root.0.3.1.2'] and edge['to']==['root.0.4.0.1.1']
 for a,b in zip(edge['points'],edge['points'][1:]):
  if a[0]==b[0] and namespace['x']<a[0]<namespace['x']+namespace['width']:
   assert max(min(a[1],b[1]),namespace['y'])>=min(max(a[1],b[1]),namespace['y']+namespace['height'])
 vault=next(b for b in drawing.boxes if b['source']=='root.0.4.0.1.1')
 assert edge['points'][-1]==[vault['x']+vault['width']/2,vault['y']-12]
