"""Source contracts for all 38 connectors reconciled by the unresolved review.

No browser audit indexes are used as source selectors. Endpoint names and local
structure bind each contract; visual geometry remains the browser gate's job.
"""
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class Element:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.parts = [], []

    @property
    def text(self):
        return ' '.join(''.join(p.text if isinstance(p, Element) else p
                                for p in self.parts).split())

    @property
    def classes(self):
        return self.attrs.get('class', '').split()

    @property
    def next(self):
        assert self.parent is not None
        siblings = self.parent.children
        index = siblings.index(self) + 1
        return siblings[index] if index < len(siblings) else None

    def descendants(self):
        return [child for node in self.children
                for child in [node, *node.descendants()]]


class Source(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Element('root', [])
        self.stack = [self.root]
        self.feed(text)
        self.nodes = self.root.descendants()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        self.stack[-1].parts.append(node)
        if tag not in {'br', 'img', 'hr', 'input', 'meta', 'link'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        assert self.stack[-1].tag == tag, (tag, self.stack[-1].tag)
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].parts.append(data)


def connector(source, contract):
    if contract['role'] == 'loop':
        found = [n for n in source.nodes if 'sd-loop' in n.classes]
    else:
        found = [n for n in source.nodes if n.tag == 'div'
                 and ('sd-arrow' in n.classes or 'sd-reference' in n.classes)
                 and n.text == contract['label']]
    assert len(found) == 1, (contract['review_id'], len(found))
    return found[0]


class ConnectorSemanticsTests(unittest.TestCase):
    def test_review_reconciliation(self):
        self.assertEqual(len(CONTRACTS), 38)
        self.assertEqual(len({c['include'] for c in CONTRACTS}), 30)
        self.assertEqual(len({c['review_id'] for c in CONTRACTS}), 38)
        self.assertEqual(Counter(c['role'] for c in CONTRACTS),
                         {'continuation': 24, 'reference': 9, 'loop': 3,
                          'reference-note': 2})

    def test_all_reviewed_roles_and_endpoints(self):
        for contract in CONTRACTS:
            with self.subTest(connector=contract['review_id']):
                source = Source((ROOT / '_includes' / contract['include']).read_text())
                edge = connector(source, contract)
                self.assertEqual(edge.attrs.get('data-connector-role'), contract['role'])
                if contract['role'] == 'continuation':
                    self.assertIn('sd-arrow', edge.classes)
                    self.assertIsNone(edge.next)
                    target = edge.parent.next
                    self.assertIsNotNone(target)
                    self.assertTrue(set(target.classes) & {'sd-grid', 'sd-band', 'sd-lane', 'sd-loop'})
                    self.assertEqual(target.text, contract['boundary_text'])
                    self.assertEqual(edge.parent.children[-2].text, contract['source_text'])
                    self.assertNotIn('data-from', edge.attrs)
                    self.assertNotIn('data-to', edge.attrs)
                else:
                    endpoints = []
                    for attr, expected_id, expected_text in (
                        ('data-from', contract['from_id'], contract['source_text']),
                        ('data-to', contract['to_id'], contract['target_text']),
                    ):
                        self.assertEqual(edge.attrs.get(attr), expected_id)
                        found = [n for n in source.nodes if n.attrs.get('id') == expected_id]
                        self.assertEqual(len(found), 1)
                        self.assertEqual(found[0].text, expected_text)
                        self.assertIn('sd-node', found[0].classes)
                        endpoints.append(found[0])
                    if contract['role'] == 'reference':
                        self.assertIn('sd-arrow', edge.classes)
                        self.assertEqual(edge.next.text, contract['boundary_text'])
                        self.assertIn(endpoints[1], [edge.next, *edge.next.descendants()])
                    elif contract['role'] == 'loop':
                        actions = [n for n in edge.descendants() if 'sd-node' in n.classes]
                        self.assertIs(endpoints[0], actions[-1])
                        self.assertIs(endpoints[1], actions[0])
                    else:
                        self.assertEqual(set(edge.classes), {'sd-note', 'sd-reference'})
                        self.assertFalse(any('sd-arrow' in n.classes or 'sd-loop' in n.classes
                                             for n in [edge, *edge.descendants()]))
                        self.assertIn(contract['visible_source'], edge.text)
                        self.assertIn(contract['visible_target'], edge.text)

    def test_preserved_text_structure_and_existing_relations(self):
        all_ids = []
        for include, baseline in BASELINES.items():
            with self.subTest(include=include):
                text = (ROOT / '_includes' / include).read_text()
                source = Source(text)
                self.assertNotIn('data-audit-id', text)
                self.assertEqual(len(source.nodes), baseline['elements'])
                self.assertEqual(sha256(source.root.text.encode()).hexdigest(), baseline['text_sha256'])
                ids = [n.attrs['id'] for n in source.nodes if 'id' in n.attrs]
                self.assertEqual(len(ids), len(set(ids)))
                all_ids.extend(ids)
                for attrs in baseline['relations']:
                    found = [n for n in source.nodes if n.attrs.get('data-relation') == attrs['data-relation']]
                    self.assertEqual(len(found), 1)
                    for key, value in attrs.items():
                        self.assertEqual(found[0].attrs.get(key), value)
        self.assertEqual(len(all_ids), len(set(all_ids)))


# Frozen source contracts, selected by reviewed visible labels, not DOM indexes.
CONTRACTS = [{'review_id': 'openid-connect-authorization-code-flow-simplied:26',
  'include': 'diagrams/static/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.html',
  'role': 'continuation',
  'label': 'Application -> Keycloak: Token Endpoint exchange',
  'source_text': '5. Application exchanges the code ID Token과 Access Token을 발급받음',
  'boundary_text': '6. Application establishes a session Application -> Application: ID Token으로 '
                   '사용자 신원을 확인하고 session 생성'},
 {'review_id': 'openid-connect-authorization-code-flow-simplied:28',
  'include': 'diagrams/static/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.html',
  'role': 'loop',
  'label': '6. Application establishes a session Application -> Application: ID Token으로 사용자 신원을 '
           '확인하고 session 생성',
  'from_id': 'openid-connect-authorization-code-flow-simplied-6-application-establishes-a-session',
  'to_id': 'openid-connect-authorization-code-flow-simplied-6-application-establishes-a-session',
  'source_text': '6. Application establishes a session Application -> Application: ID Token으로 사용자 '
                 '신원을 확인하고 session 생성',
  'target_text': '6. Application establishes a session Application -> Application: ID Token으로 사용자 '
                 '신원을 확인하고 session 생성'},
 {'review_id': 'sap-c02-regional-failover-trigger-layers-title:6',
  'include': 'diagrams/static/sap-c02/regional-failover-trigger-layers.html',
  'role': 'continuation',
  'label': '전환 계층 비교',
  'source_text': '클라이언트 요청 primary 장애와 control plane 조작 불가를 가정해 전환 경로를 비교한다.',
  'boundary_text': '사전 구성된 data plane 기반 전환 Route 53 health check failover data plane 동작. 클라이언트 '
                   'DNS cache TTL만큼 지연될 수 있다. ARC routing control RECOVERY_CONTROL health check를 '
                   'on 또는 off로 바꾸는 data plane API. 같은 대피 요건으로 볼 수 없는 수단 Global Accelerator traffic '
                   'dial 리전 간 traffic 분배와 active-standby가 가능하나 dial 변경은 control plane operation이다. '
                   'CloudFront origin failover 설정된 실패 조건의 GET / HEAD / OPTIONS를 secondary로 재시도한다. '
                   '이후 origin 요청은 primary부터 시도한다.'},
 {'review_id': 'sap-c02-s3-intelligent-tiering-tiers-title:16',
  'include': 'diagrams/static/sap-c02/s3-intelligent-tiering-tiers.html',
  'role': 'continuation',
  'label': '선택 계층을 켠 경우',
  'source_text': 'Archive Instant Access 여기까지가 자동 계층이다.',
  'boundary_text': '선택 계층 Archive Access최소 90일부터 최대 730일까지 설정한다. 둘 다 켜면 더 깊은 계층으로 이동 Deep Archive '
                   'Access최소 180일부터 최대 730일까지 설정한다.'},
 {'review_id': 'sap-c02-outposts-rack-vs-server-title:6',
  'include': 'diagrams/static/sap-c02/outposts-rack-vs-server.html',
  'role': 'continuation',
  'label': '시설 안 연결 방식 선택',
  'source_text': '온프레미스 네트워크 공장 제어망 또는 사내 네트워크. rack과 server 모두 양방향 통신한다.',
  'boundary_text': '고객이 확보하고 관리하는 시설 rack 경로 local gateway (LGW) rack 전용이며 IPv4만 지원한다. VPC 연결 '
                   'Outposts rack EC2, EBS, S3 on Outposts, EKS, ECS, RDS, EMR, ALB를 지원한다. server '
                   '경로 local network interface (LNI) Outpost subnet에서만 동작한다. VPC 연결 Outposts '
                   'server EC2와 ECS, VPC subnet까지 지원한다. EBS 없이 instance store만 사용하며 신규 판매는 중단됐다.'},
 {'review_id': 'eventbridge-fanout-target-limit:16',
  'include': 'diagrams/static/sap-c02/eventbridge-fanout-target-limit.html',
  'role': 'continuation',
  'label': '다섯 target으로 직접 분기',
  'source_text': 'Rule target 5개 한도, 조정 불가',
  'boundary_text': 'Direct target slots 1-4 Direct target 1 slot 1 Direct target 2 slot 2 Direct '
                   'target 3 slot 3 Direct target 4 slot 4 Slot 5 SNS topic 다섯 번째 target. '
                   'subscriber별 fan-out SNS subscriptions Team queue A Team queue B HTTP/S '
                   'subscriber'},
 {'review_id': 'dns-global-traffic-decision-layers:31',
  'include': 'diagrams/static/sap-c02/dns-global-traffic-decision-layers.html',
  'role': 'reference',
  'label': 'CloudFront 캐시 미스일 때',
  'from_id': 'dns-global-traffic-decision-layers-cloudfront',
  'to_id': 'dns-global-traffic-decision-layers-',
  'source_text': 'CloudFront 엣지 캐시 히트면 오리진에 가지 않습니다.',
  'target_text': '리전 오리진 CloudFront가 origin 요청을 전달합니다.',
  'boundary_text': '리전 오리진 CloudFront가 origin 요청을 전달합니다.'},
 {'review_id': 'sap-c02-migration-discovery-tool-ownership-title:6',
  'include': 'diagrams/static/sap-c02/migration-discovery-tool-ownership.html',
  'role': 'continuation',
  'label': '수집 방식과 질문에 따라 도구 선택',
  'source_text': '온프레미스 자산 VMware VM과 물리 서버가 섞여 있는 출발점이다.',
  'boundary_text': 'Migration Evaluator collector Windows Server VM 1대. WMI, SNMP, vSphere, T-SQL을 '
                   '사용하며 게스트 에이전트는 없다. 비용 모델 business case EC2, EBS, OS와 SQL Server 라이선스, BYOL 비용을 '
                   '계산한다. application dependency mapping은 하지 않는다. ADS Agentless Collector '
                   'Agentless Collector vCenter에 OVA 1개를 배포한다. 약 60분 주기이며 VMware VM 전용이다. 추적 전송 '
                   'Migration Hub home Region 추적 데이터는 한 리전에 저장하고 대상 리전은 따로 선택한다. ADS Discovery '
                   'Agent 서버별 agent 약 15초 주기로 물리 서버와 프로세스, 네트워크 의존성을 수집한다. 두 산출물로 분기 Migration Hub '
                   '서버 그룹핑과 의존성 시각화. Athena와 CSV 시계열 사용률과 network data 내보내기.'},
 {'review_id': 'sap-c02-modernization-compute-target-decision-title:6',
  'include': 'diagrams/static/sap-c02/modernization-compute-target-decision.html',
  'role': 'continuation',
  'label': '제약 판정: 15분, 메모리, OS 접근, 상시 실행',
  'source_text': '기존 워크로드 실행 시간, 상태 보유 여부, 런타임 요구를 먼저 기록한다.',
  'boundary_text': '짧은 이벤트와 무상태 15분 이내 함수 호출당 최대 900초, 무상태로 처리한다. 이벤트 실행 AWS Lambda 이벤트 기반 함수. '
                   '메모리는 최대 10,240MB다. 장시간 또는 상태 보유 컨테이너 작업 15분을 넘길 수 있고 실행 중 메모리 상태를 유지한다. 태스크 실행 '
                   'AWS Fargate ECS 컨테이너. 실행 시간 하드 리밋이 없고 최대 244GiB 메모리다. OS 또는 특수 런타임 호스트 수준 제어 '
                   '커널, 드라이버, 패치 레벨, 특수 파일 시스템이 필요하다. 직접 관리 Amazon EC2 운영체제와 런타임을 직접 관리하는 컴퓨트다.'},
 {'review_id': 'sap-c02-modernization-container-hosting-boundaries-title:11',
  'include': 'diagrams/static/sap-c02/modernization-container-hosting-boundaries.html',
  'role': 'continuation',
  'label': '오케스트레이터 선택',
  'source_text': 'Amazon ECR 버전이 있는 공통 이미지 공급 경로다.',
  'boundary_text': 'ECS on Fargate ECS 선택 IP target을 사용하며 Fargate Spot을 선택할 수 있다. 태스크 배치 ECS '
                   'Fargate 태스크 awsvpc ENI와 EBS, Fargate Spot을 사용할 수 있다. EKS on Fargate EKS 선택 '
                   'Fargate profile이 매칭되고 private subnet에서 실행한다. Pod 배치 EKS Fargate Pod DaemonSet, '
                   'EBS, GPU, Fargate Spot을 지원하지 않는다.'},
 {'review_id': 'sap-c02-modernization-database-target-selection-title:6',
  'include': 'diagrams/static/sap-c02/modernization-database-target-selection.html',
  'role': 'continuation',
  'label': '요구사항 판정',
  'source_text': '기존 데이터베이스 엔진, 스키마, 조인, 트랜잭션, 액세스 패턴을 확인한다.',
  'boundary_text': '관계형 호환성이 핵심 조인과 트랜잭션 유지기존 관계형 계약을 보존한다. replatform RDS 또는 Aurora관리형 관계형 '
                   '데이터베이스다. 액세스 패턴이 key-value 대규모 분산 처리스키마를 key-value 모델로 다시 설계한다. purpose-built '
                   'DB Amazon DynamoDBkey-value 액세스 패턴에 맞춘다. 검색과 분석이 핵심 문서와 검색 인덱스검색 질의와 분석 요구를 '
                   '분리한다. 검색 엔진 Amazon OpenSearch검색과 분석을 전담한다. 엔진 옵션과 OS 제어가 필요 관리형 지원 범위 밖커널, '
                   '드라이버, 세부 엔진 옵션을 직접 제어해야 한다. 운영 책임 유지 EC2 self-managedrehost에 가까우며 패치와 백업 부담이 '
                   '남는다.'},
 {'review_id': 'sap-c02-modernization-integration-choice-boundaries-title:6',
  'include': 'diagrams/static/sap-c02/modernization-integration-choice-boundaries.html',
  'role': 'continuation',
  'label': '순서, 버퍼, 라우팅, 승인 요구 확인',
  'source_text': '모놀리스 모듈 기존 동기 호출을 어떤 보장으로 분리할지 정한다.',
  'boundary_text': '순서와 소비자별 버퍼 FIFO 전달소비자마다 보존된 순서와 버퍼가 필요하다. 팬아웃 SNS FIFO필터링과 팬아웃을 담당한다. 소비자별 큐 '
                   'SQS FIFO소비자별 보존과 순서를 보장한다. 콘텐츠 기반 라우팅 이벤트 패턴내용에 따라 서로 다른 대상이 필요하다. rule 매칭 '
                   'Amazon EventBridgerule로 이벤트를 대상에 라우팅한다. 긴 대기와 사람 승인 비멱등 작업긴 실행과 콜백, 승인 단계가 '
                   '필요하다. 상태 있는 실행 Step Functions Standard승인과 callback을 포함한 긴 워크플로다.'},
 {'review_id': 'sd-blockchain-utxo-reference-structure:11',
  'include': 'diagrams/static/blockchain/utxo-reference-structure.html',
  'role': 'continuation',
  'label': '새 output으로 분기',
  'source_text': 'New transaction 319d3776 output 전체를 유일한 input으로 소비',
  'boundary_text': 'vout[0] payment 1.5 BTC to bob new UTXO vout[1] change 48.4999859 BTC alice에게 '
                   '돌아가는 새 UTXO'},
 {'review_id': 'sd-blockchain-rpc-balance-is-local:6',
  'include': 'diagrams/static/blockchain/rpc-balance-is-local.html',
  'role': 'continuation',
  'label': '같은 address 조회',
  'source_text': 'EOA 0xf39Fd6e5 공개 테스트 키 1개',
  'boundary_text': 'Anvil :8545 latest 5 chainId 31337, 9998.9997 ETH Anvil :8547 latest 3 chainId '
                   '31337, 9998.9992 ETH Sepolia RPC balance 0 chainId 11155111'},
 {'review_id': 'kubernetes-cilium-kube-proxy-replacement:8',
  'include': 'diagrams/static/kubernetes/cilium/kube-proxy_replacement.html',
  'role': 'continuation',
  'label': 'Service endpoint 선택',
  'source_text': 'Pod A request curl이 Service ClusterIP로 요청을 보냅니다.',
  'boundary_text': '기존 kube-proxy path Pod A socket와 veth Pod 네트워크에서 host 쪽으로 나옵니다. DNAT 규칙 조회 '
                   'kube-proxy iptables Service와 endpoint를 DNAT rule로 연결합니다. host stack traversal '
                   'Linux routing와 FORWARD PREROUTING, FORWARD, POSTROUTING chain을 통과합니다. endpoint '
                   '전달 Pod B endpoint 반대쪽 veth와 socket으로 도착합니다. Cilium eBPF replacement Pod A '
                   'Service request Service 주소에 대한 요청이며 적용 hook은 구성에 따라 다릅니다. kernel service '
                   'lookup Cilium eBPF service datapath 기본 socket-LB는 socket에서 backend를 선택합니다. Pod '
                   'namespace 우회 구성은 tc/veth에서 Service lookup을 수행합니다. host 작업을 줄여 전달 Pod B '
                   'endpoint kube-proxy의 Service NAT를 대체하지만 모든 host networking을 우회하지는 않습니다. '
                   'socketLB.hostNamespaceOnly=true는 Pod namespace의 socket rewrite 대신 tc/veth '
                   'fallback을 사용합니다. socket과 veth를 필수 연속 LB 단계로 읽으면 안 됩니다.'},
 {'review_id': 'sd-kubernetes-6w-cilium-ingress-identity:7',
  'include': 'diagrams/static/kubernetes/cilium/6w-cilium-ingress-identity.html',
  'role': 'continuation',
  'label': 'world identity로 진입',
  'source_text': 'External client cluster 밖에서 들어오는 요청은 world identity입니다.',
  'boundary_text': 'Kubernetes cluster Load Balancer Kubernetes Service가 외부 요청을 cluster로 받습니다. 첫 '
                   '정책 경계: source world, destination ingress Ingress Envoy를 거쳐 backend로 보내는 트래픽의 '
                   'source identity는 ingress입니다. 두 번째 정책 경계: source ingress, destination '
                   'productpage productpage-app Pod destination identity가 productpage인 backend입니다. '
                   'source는 ingress로 평가합니다.'},
 {'review_id': 'sd-blockchain-solc-pin-two-hashes:6',
  'include': 'diagrams/static/blockchain/solc-pin-two-hashes.html',
  'role': 'continuation',
  'label': 'compiler version 선택',
  'source_text': 'Escrow source 같은 Solidity 파일',
  'boundary_text': 'solc 0.8.35 compile 고정한 compiler deployedBytecode bytecode A 5234 hex, sha256 '
                   'd8f49804... solc 0.8.28 compile 다른 compiler deployedBytecode bytecode B 5234 '
                   'hex, sha256 98a49743..., A와 다름'},
 {'review_id': 'gitops-control-loop:2',
  'include': 'diagrams/static/ci-cd/ci-cd-study/gitops-control-loop.html',
  'role': 'loop',
  'label': 'Observe state 현재 클러스터 상태를 관찰차이 확인Calculate actions 원하는 상태와의 차이를 계산조정 계획Apply actions '
           '필요한 변경을 클러스터에 적용',
  'from_id': 'gitops-control-loop-apply-actions',
  'to_id': 'gitops-control-loop-observe-state',
  'source_text': 'Apply actions 필요한 변경을 클러스터에 적용',
  'target_text': 'Observe state 현재 클러스터 상태를 관찰'},
 {'review_id': 'kubernetes-architecture-overview:10',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference',
  'label': 'API server <-> Database (etcd)',
  'from_id': 'kubernetes-architecture-overview-api-server',
  'to_id': 'kubernetes-architecture-overview-database-etcd',
  'source_text': 'API server 모든 구성요소와 client가 통신하는 REST API',
  'target_text': 'Database (etcd) 클러스터 상태 저장',
  'boundary_text': 'Database (etcd) 클러스터 상태 저장'},
 {'review_id': 'kubernetes-architecture-overview:16',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference',
  'label': 'API server <-> Scheduler',
  'from_id': 'kubernetes-architecture-overview-api-server',
  'to_id': 'kubernetes-architecture-overview-scheduler',
  'source_text': 'API server 모든 구성요소와 client가 통신하는 REST API',
  'target_text': 'Scheduler Pod를 실행할 node 선택',
  'boundary_text': 'Scheduler Pod를 실행할 node 선택'},
 {'review_id': 'kubernetes-architecture-overview:22',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference',
  'label': 'API server <-> Controller Manager',
  'from_id': 'kubernetes-architecture-overview-api-server',
  'to_id': 'kubernetes-architecture-overview-controller-manager',
  'source_text': 'API server 모든 구성요소와 client가 통신하는 REST API',
  'target_text': 'Controller Manager desired state로 지속 조정',
  'boundary_text': 'Controller Manager desired state로 지속 조정'},
 {'review_id': 'kubernetes-architecture-overview:28',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference',
  'label': 'API server <-> Cloud Controller Manager',
  'from_id': 'kubernetes-architecture-overview-api-server',
  'to_id': 'kubernetes-architecture-overview-cloud-controller-manager',
  'source_text': 'API server 모든 구성요소와 client가 통신하는 REST API',
  'target_text': 'Cloud Controller Manager cloud provider 자원과 연동',
  'boundary_text': 'Cloud Controller Manager cloud provider 자원과 연동'},
 {'review_id': 'kubernetes-architecture-overview:55',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference-note',
  'label': 'kubectl <-> API server: HTTPS 요청과 응답',
  'from_id': 'kubernetes-architecture-overview-kubectl-user-machine',
  'to_id': 'kubernetes-architecture-overview-api-server',
  'source_text': 'kubectl (User machine) HTTPS로 API server를 호출',
  'target_text': 'API server 모든 구성요소와 client가 통신하는 REST API',
  'visible_source': 'kubectl',
  'visible_target': 'API server'},
 {'review_id': 'kubernetes-architecture-overview:58',
  'include': 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html',
  'role': 'reference',
  'label': 'Cloud Controller Manager -> Cloud Provider API',
  'from_id': 'kubernetes-architecture-overview-cloud-controller-manager',
  'to_id': 'kubernetes-architecture-overview-cloud-provider-api',
  'source_text': 'Cloud Controller Manager cloud provider 자원과 연동',
  'target_text': 'Cloud Provider API Cloud Controller Manager가 호출하는 외부 API',
  'boundary_text': 'Cloud Provider API Cloud Controller Manager가 호출하는 외부 API'},
 {'review_id': 'sd-hd-mnemonic-three-addresses:6',
  'include': 'diagrams/static/blockchain/hd-mnemonic-three-addresses.html',
  'role': 'continuation',
  'label': 'index로 HD derivation',
  'source_text': 'public mnemonic 12 words, Anvil default',
  'boundary_text': 'index 0 0xf39Fd6e5 Anvil account 0 index 1 0x70997970 Anvil account 1 index 2 '
                   '0x3C44CdDd Anvil account 2'},
 {'review_id': 'sd-blockchain-sign-verify-tamper:11',
  'include': 'diagrams/static/blockchain/sign-verify-tamper.html',
  'role': 'continuation',
  'label': '원문과 변조 입력으로 분기',
  'source_text': 'signature 132 hex chars',
  'boundary_text': '원문 verify succeeded message와 address 일치 변조 입력 verify exit 1 문자 1개 변경'},
 {'review_id': 'gitops-lifecycle:2',
  'include': 'diagrams/static/ci-cd/ci-cd-study/gitops-lifecycle.html',
  'role': 'loop',
  'label': 'Deploy Git에 저장된 manifest를 클러스터에 반영상태 관찰Monitoring Git repository와 클러스터 상태를 모니터링차이 '
           '탐지Drift Detection 원하는 상태와 live state의 차이를 감지조정 실행Take Action Rollback 또는 3-way-diff로 '
           '상태를 수정',
  'from_id': 'gitops-lifecycle-take-action',
  'to_id': 'gitops-lifecycle-deploy',
  'source_text': 'Take Action Rollback 또는 3-way-diff로 상태를 수정',
  'target_text': 'Deploy Git에 저장된 manifest를 클러스터에 반영'},
 {'review_id': 'sd-kubernetes-control-plane-flow:7',
  'include': 'diagrams/static/kubernetes/kubernetes-control-plane-flow.html',
  'role': 'continuation',
  'label': '모든 제어 요청은 API로 진입',
  'source_text': 'Users and automation kubectl, CI, operator가 요청을 보냅니다.',
  'boundary_text': 'Control plane API server and etcd cluster state의 유일한 writer와 일관된 저장소입니다. '
                   'desired state 관찰 Controllers and scheduler desired state와 actual state의 차이를 '
                   'reconcile합니다.'},
 {'review_id': 'node-http-request-lifecycle-flow:43',
  'include': 'diagrams/static/nodejs/node-http-request-lifecycle-flow.html',
  'role': 'reference-note',
  'label': 'Graceful shutdown -> Accepted TCP socket: stop accepting / drain in-flight',
  'from_id': 'node-http-request-lifecycle-flow-graceful-shutdown',
  'to_id': 'node-http-request-lifecycle-flow-accepted-tcp-socket',
  'source_text': 'Graceful shutdown 새 연결 수락 중단, in-flight request drain',
  'target_text': 'Accepted TCP socket libuv가 server에 전달',
  'visible_source': 'Graceful shutdown',
  'visible_target': 'Accepted TCP socket'},
 {'review_id': 'sd-kubernetes-terminating-pod-troubleshooting:7',
  'include': 'diagrams/static/kubernetes/terminating-pod-troubleshooting.html',
  'role': 'continuation',
  'label': '원인별 조건부 진단',
  'source_text': 'Pod deletion requestdeletionTimestamp와 grace period 확인',
  'boundary_text': 'Finalizers: 존재할 때 API metadata 확인finalizer가 있으면 담당 controller의 cleanup과 제거 여부 '
                   '조사. 모든 Pod에 존재하는 필수 gate가 아님 Node / kubelet / runtime 종료 진행 상태 확인node 도달 가능성, '
                   'preStop, TERM, grace 만료 후 KILL 및 runtime 이벤트 조사 Storage: 해당될 때 Unmount / '
                   'detach 확인volume 사용 시 관련 정리 상태 조사. Pod API 삭제와 detach 완료를 동일시하지 않음'},
 {'review_id': 'spring-07-autoconfiguration-flow:16',
  'include': 'diagrams/static/spring/spring-07-autoconfiguration-flow.html',
  'role': 'continuation',
  'label': '조건 결과에 따라 분기',
  'source_text': '조건 충족 여부 OnClass, OnMissingBean, OnProperty',
  'boundary_text': 'Yes: 조건 충족 자동설정 bean 등록 embedded Tomcat, DispatcherServlet, converters No: 조건 '
                   '불충족 건너뜀: back off 클래스 부재, property 불일치 또는 기존 bean 때문에 조건 불충족'},
 {'review_id': 'spring-11-webflux-event-loop:6',
  'include': 'diagrams/static/spring/spring-11-webflux-event-loop.html',
  'role': 'continuation',
  'label': 'non-blocking 할당',
  'source_text': '다수 connection A, B, C, D, E, F, ...',
  'boundary_text': 'Netty event loop pool, CPU core 수 수준 event-loop-1 A, C, E 처리 blocking 없음 '
                   'event-loop-2 B, D, F 처리 blocking 없음'},
 {'review_id': 'vault-secrets-operator:20',
  'include': 'diagrams/static/ci-cd/ci-cd-study/vault-secrets-operator.html',
  'role': 'reference',
  'label': 'Controller가 인증 / secret 요청Vault가 token / data 반환',
  'from_id': 'vso-controller',
  'to_id': 'vso-vault',
  'source_text': 'Vault Secrets Operator ControllerVaultAuth로 인증하고 secret data를 받아 native Secret을 '
                 'create 또는 update',
  'target_text': 'Vault APIOperator 요청에 응답',
  'boundary_text': '클러스터 밖 / HashiCorp Vault Vault APIOperator 요청에 응답 Kubernetes Auth and '
                   'PolicyServiceAccount identity 검증과 secret path 권한 Secret EngineKV, Database, '
                   'PKI의 static 또는 dynamic secret'},
 {'review_id': 'vault-secrets-operator:36',
  'include': 'diagrams/static/ci-cd/ci-cd-study/vault-secrets-operator.html',
  'role': 'reference',
  'label': 'Controller가 Secret A 동기화',
  'from_id': 'vso-controller',
  'to_id': 'vault-secrets-operator-kubernetes-secret-a',
  'source_text': 'Vault Secrets Operator ControllerVaultAuth로 인증하고 secret data를 받아 native Secret을 '
                 'create 또는 update',
  'target_text': 'Kubernetes Secret ADatabase 자격증명',
  'boundary_text': 'Kubernetes cluster / Namespace A Kubernetes Secret ADatabase 자격증명 mount 또는 env '
                   '주입 Application Pod AVault SDK 없이 native Secret 사용'},
 {'review_id': 'vault-secrets-operator:56',
  'include': 'diagrams/static/ci-cd/ci-cd-study/vault-secrets-operator.html',
  'role': 'reference',
  'label': 'Controller가 Secret B 동기화',
  'from_id': 'vso-controller',
  'to_id': 'vault-secrets-operator-kubernetes-secret-b',
  'source_text': 'Vault Secrets Operator ControllerVaultAuth로 인증하고 secret data를 받아 native Secret을 '
                 'create 또는 update',
  'target_text': 'Kubernetes Secret BCloud 자격증명',
  'boundary_text': 'Kubernetes cluster / Namespace B Kubernetes Secret BCloud 자격증명 mount 또는 env 주입 '
                   'Application Pod BVault SDK 없이 native Secret 사용'},
 {'review_id': 'sd-project-weasel-cicd:16',
  'include': 'diagrams/static/project/weasel/cicd.html',
  'role': 'continuation',
  'label': 'artifact path 분기',
  'source_text': 'Jenkins build and publish artifacts',
  'boundary_text': 'Kubernetes backend Jenkins에서 ECR image push와 Manifest Repository update로 독립 '
                   '분기합니다. ECR image ECR Jenkins가 image push Manifest update Manifest Repository '
                   'Jenkins가 manifest update ArgoCD detects manifest ArgoCD desired state watcher '
                   'Apply K8s Deployment cluster workload update Frontend static hosting S3 File '
                   'update Jenkins가 frontend build 결과를 정적 웹 호스팅 bucket에 반영합니다.'},
 {'review_id': 'sd-blockchain-receipt-finality-tags:6',
  'include': 'diagrams/static/blockchain/receipt-finality-tags.html',
  'role': 'continuation',
  'label': '실행 결과와 합의 head로 분기',
  'source_text': 'JSON-RPC HTTP 200만으로 부족',
  'boundary_text': 'receipt 실행 결과 receipt status 0x0 Anvil boom, gasUsed 21492 호출이 revert되었고 gas는 '
                   '소비되었습니다. finalized 합의 head finalized 11544938 Sepolia read-only, latest보다 64 뒤 '
                   '어느 block이 합의상 굳었는지를 읽습니다.'},
 {'review_id': 'sd-blockchain-reentrancy-cei:6',
  'include': 'diagrams/static/blockchain/reentrancy-cei.html',
  'role': 'continuation',
  'label': '호출 순서 분기',
  'source_text': 'withdraw() balance가 아직 1 ETH',
  'boundary_text': '취약 순서 msg.sender.call 먼저 1 ETH 전송 receive 실행 attacker receive withdraw를 다시 호출 '
                   'mapping이 아직 0이 아님 withdraw again balance가 두 번 지급될 수 있음 CEI 순서 CEI withdraw '
                   'storage를 0으로 만든 뒤 send nested call이 0을 읽음 msg.sender.call 바깥 call은 두 번 지급하지 '
                   '않음'}]

BASELINES = {'diagrams/static/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.html': {'elements': 34,
                                                                                            'text_sha256': '1d6d3c9d2cdfc3ce9254cc706a02e3d35a6f075b60369698c549fe99b512a997',
                                                                                            'relations': []},
 'diagrams/static/sap-c02/regional-failover-trigger-layers.html': {'elements': 31,
                                                                   'text_sha256': '182f673987005db7a7762f2b9bcb03ad3fb5e98e9ee219cd24dcef013aaed7e6',
                                                                   'relations': []},
 'diagrams/static/sap-c02/s3-intelligent-tiering-tiers.html': {'elements': 35,
                                                               'text_sha256': '66408f409e2289d6b47bf6776f4fa72e86b56c87a06b00636d1c824768e3f83e',
                                                               'relations': []},
 'diagrams/static/sap-c02/outposts-rack-vs-server.html': {'elements': 42,
                                                          'text_sha256': 'fb41eb88d2faa173dc6e6e1cddac32589d4936042918c5e486fd8d7f99d2d124',
                                                          'relations': []},
 'diagrams/static/sap-c02/eventbridge-fanout-target-limit.html': {'elements': 48,
                                                                  'text_sha256': '5f63782ea0fa157e073e5ce68c69af625670f1cc59d26172df981568b85dc3c2',
                                                                  'relations': []},
 'diagrams/static/sap-c02/dns-global-traffic-decision-layers.html': {'elements': 36,
                                                                     'text_sha256': '8f955e8310a6315e28312723ec6c4cdf506e8b1ab88855efd3877811a4ca2840',
                                                                     'relations': []},
 'diagrams/static/sap-c02/migration-discovery-tool-ownership.html': {'elements': 47,
                                                                     'text_sha256': '1f1785d475ddb25da10550605fb0927f295e02a599310e91a8d9fbbcfa06c223',
                                                                     'relations': []},
 'diagrams/static/sap-c02/modernization-compute-target-decision.html': {'elements': 42,
                                                                        'text_sha256': '6f17b83198fe519d57ecd1a3af127e258a1d40290c59f892b458e0240f1eca16',
                                                                        'relations': []},
 'diagrams/static/sap-c02/modernization-container-hosting-boundaries.html': {'elements': 41,
                                                                             'text_sha256': '5adee3f4e7c2c6efe9ac28a7541036400e698165cf309943fd1dbdb4c48384b1',
                                                                             'relations': []},
 'diagrams/static/sap-c02/modernization-database-target-selection.html': {'elements': 53,
                                                                          'text_sha256': '260a53a6e407dbb0a8bb50864fb49553687ebb5f023fe318435bb221f51c9cf1',
                                                                          'relations': []},
 'diagrams/static/sap-c02/modernization-integration-choice-boundaries.html': {'elements': 47,
                                                                              'text_sha256': '96b090adf41eb297b4cca743772ffbae446e3e8179ae12c132cca005c38402bc',
                                                                              'relations': []},
 'diagrams/static/blockchain/utxo-reference-structure.html': {'elements': 28,
                                                              'text_sha256': 'a3a0a5618f25f5df9c3a02eae5383c6d502a128b5dfefd454ce87dd1870aca93',
                                                              'relations': []},
 'diagrams/static/blockchain/rpc-balance-is-local.html': {'elements': 28,
                                                          'text_sha256': 'eeb94f40a65d683dc67cb6ec9754bdded5fdab672b227f6bc2d94833c1465b57',
                                                          'relations': []},
 'diagrams/static/kubernetes/cilium/kube-proxy_replacement.html': {'elements': 53,
                                                                   'text_sha256': 'd542c8c109ab368b7ff35fa750ea9136016e4e1fea14442a1ccc3e43c2c088ef',
                                                                   'relations': []},
 'diagrams/static/kubernetes/cilium/6w-cilium-ingress-identity.html': {'elements': 32,
                                                                       'text_sha256': '983e83d54d6bca7975499ec2567ee426c28b04d648c20d71cf658877a628436d',
                                                                       'relations': []},
 'diagrams/static/blockchain/solc-pin-two-hashes.html': {'elements': 32,
                                                         'text_sha256': 'afdb86763f552611c423ccfb646f92081a2e66b0ef8e5f608c472c2ff57700fc',
                                                         'relations': []},
 'diagrams/static/ci-cd/ci-cd-study/gitops-control-loop.html': {'elements': 18,
                                                                'text_sha256': 'dd07ab1be1bbf4834ddafa80e2b9aef44e3282baaffa3ecc668a0832ca16b586',
                                                                'relations': []},
 'diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html': {'elements': 64,
                                                                             'text_sha256': '0cff30bbd8d46b9d0e881b34723a20dc161f347841e304181cfe4b4298f64ff4',
                                                                             'relations': []},
 'diagrams/static/blockchain/hd-mnemonic-three-addresses.html': {'elements': 25,
                                                                 'text_sha256': 'c49e53deb826df1164363633e6dd7120e3c3823c0ad9671acb65806b91fbc37b',
                                                                 'relations': []},
 'diagrams/static/blockchain/sign-verify-tamper.html': {'elements': 27,
                                                        'text_sha256': '0e9f30e3372ecdc99b9e60d343d45fff39075f01be708ece4655c7588296b395',
                                                        'relations': []},
 'diagrams/static/ci-cd/ci-cd-study/gitops-lifecycle.html': {'elements': 23,
                                                             'text_sha256': '57eb18021ba9294d2e00cbac184ed6827494828258cfac76ba542090a4145785',
                                                             'relations': []},
 'diagrams/static/kubernetes/kubernetes-control-plane-flow.html': {'elements': 34,
                                                                   'text_sha256': 'd98edeb75d672907e0611e5e863a88971ffb1bad5d66498447e79aafe2a98ead',
                                                                   'relations': []},
 'diagrams/static/nodejs/node-http-request-lifecycle-flow.html': {'elements': 47,
                                                                  'text_sha256': '8b89796a8b5d5142a6389c2e7fa4085c1369be0bcf1465bfd41e8c8a41d0aed0',
                                                                  'relations': []},
 'diagrams/static/kubernetes/terminating-pod-troubleshooting.html': {'elements': 34,
                                                                     'text_sha256': 'bae5e6b976859f812892aac84daddc9b6a39f020694e676445f3ae155a7f824f',
                                                                     'relations': []},
 'diagrams/static/spring/spring-07-autoconfiguration-flow.html': {'elements': 32,
                                                                  'text_sha256': '4794ae987a0ccf0786838f513388a73f1e1d989e2ad357f579c6aea4edf60a48',
                                                                  'relations': []},
 'diagrams/static/spring/spring-11-webflux-event-loop.html': {'elements': 24,
                                                              'text_sha256': '99314820f3d085c017b98c026f03ba0ffdc7080d5f623d2f8a8c3844f8c25fb6',
                                                              'relations': []},
 'diagrams/static/ci-cd/ci-cd-study/vault-secrets-operator.html': {'elements': 76,
                                                                   'text_sha256': '761942b49bc7de8a12c89272a544446c0c05d7a0458658503ac4cbb92f5c3041',
                                                                   'relations': [{'data-relation': 'controller-vault',
                                                                                  'data-from': 'vso-controller',
                                                                                  'data-to': 'vso-vault'},
                                                                                 {'data-relation': 'pod-a-database',
                                                                                  'data-from': 'vso-pod-a',
                                                                                  'data-to': 'vso-database'},
                                                                                 {'data-relation': 'pod-b-cloud',
                                                                                  'data-from': 'vso-pod-b',
                                                                                  'data-to': 'vso-cloud'}]},
 'diagrams/static/project/weasel/cicd.html': {'elements': 54,
                                              'text_sha256': '038b851a75f076a7e7519f6f639cd8e2580b420fee68635370e1066b59bbb404',
                                              'relations': []},
 'diagrams/static/blockchain/receipt-finality-tags.html': {'elements': 23,
                                                           'text_sha256': 'c01c5aeb359d1c386ba8efe5507e866b4eed90606bbbc01b421eda58543084d9',
                                                           'relations': []},
 'diagrams/static/blockchain/reentrancy-cei.html': {'elements': 37,
                                                    'text_sha256': 'f3f72b475a3f1150a88778024d98202d4aa153b9ce6d92ffc2becb67bb4746bc',
                                                    'relations': []}}

if __name__ == "__main__":
    unittest.main()
