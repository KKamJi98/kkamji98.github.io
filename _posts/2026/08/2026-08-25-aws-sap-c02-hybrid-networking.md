---
title: "SAP-C02 박살내기 3 - 하이브리드 네트워크"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, vpc, transit-gateway, direct-connect, vpn, privatelink, networking]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-25 10:00:00 +0900
---

온프레미스 배치 서버가 Direct Connect private VIF로 VPC에 들어와서 S3에 업로드를 시작했는데 전부 타임아웃이 났습니다. 그 VPC에는 S3 gateway endpoint가 이미 있었고, VPC 안 EC2 인스턴스는 같은 버킷에 잘 쓰고 있었습니다. 온프레미스 라우터의 BGP 세션은 up이고 VPC route table에는 gateway endpoint가 만든 prefix list 라우트가 그대로 들어 있습니다.

같은 날 다른 팀에서는 virtual private gateway 기반 Site-to-Site VPN으로 들어온 온프레미스 서버를 VPC의 public NAT gateway로 내보내려다 같은 증상을 만났습니다. 라우트를 넣었고, NACL을 열었고, 터널 상태도 정상인데 패킷이 한 개도 나가지 않습니다.

두 경우 모두 라우트 항목은 존재합니다. 문제는 그 라우트가 참조하는 대상이 VPC 밖에서 들어온 트래픽에는 적용되지 않는다는 데 있습니다. gateway endpoint는 route table 항목으로만 존재하고, virtual private gateway를 종단으로 삼은 트래픽은 NAT gateway로 향하는 라우트를 따르지 못합니다. 둘 다 설정 실수가 아니라 지원되지 않는 조합입니다.

SAP-C02 Domain 1이 네트워크에서 내는 문항이 정확히 이 층에 있습니다. 서비스 이름을 아는 것으로는 선지가 좁혀지지 않고, 어떤 조합이 아예 성립하지 않는지를 알아야 답이 하나로 남습니다.

> **TL;DR**  
> - VPC의 기존 CIDR은 크기를 바꿀 수 없고 서로 다른 RFC 1918 대역을 섞을 수도 없다. 설계 시점에 결정된다.  
> - VPC route table 평가는 local 라우트 우선, 그다음 longest prefix match, 같은 목적지면 static이 propagated를 이긴다.  
> - VPC peering은 전이되지 않고 peer의 IGW, NAT, VPN, Direct Connect, gateway endpoint도 쓸 수 없다.  
> - virtual private gateway 기반 VPN과 Direct Connect에서는 NAT gateway로 라우팅할 수 없다. transit gateway면 가능하다.  
> - Transit Gateway는 association으로 어느 route table을 볼지, propagation으로 그 table에 무엇이 실릴지를 나눈다.  
> - TGW peering attachment는 static route만 지원해 BGP 자동 전환과 ECMP가 성립하지 않고 두 TGW 사이에 하나만 만든다.  
> - stateful appliance가 있는 VPC attachment에 appliance mode를 켜지 않으면 응답이 다른 AZ로 돌아가 드롭된다.  
> - Direct Connect는 기본적으로 암호화하지 않는다. MACsec은 dedicated connection과 LAG와 partner interconnect의 10, 100, 400 Gbps 선택된 PoP에서 지원하고 hosted connection은 지원하지 않는다.  
> - private VIF의 수신 prefix 기본 상한은 100개이고 넘겨 광고하면 BGP 세션이 idle로 떨어져 회선이 끊긴다.  
> - accelerated VPN은 transit gateway attach 전용이고 기존 연결에서 켤 수 없으며 public VIF와 병용할 수 없다.  
> - gateway endpoint는 S3와 DynamoDB만, route table 안에서만, 같은 리전에서만 동작한다. 온프레미스에서는 interface endpoint를 쓴다.  
> - VPC Flow Logs는 Amazon DNS 질의와 169.254.169.254 metadata 트래픽을 수집하지 않는다.  
{: .prompt-info}

---

## 1. VPC CIDR은 만든 뒤에 크기를 바꿀 수 없다

VPC IPv4 CIDR은 /16에서 /28 사이에서 고릅니다. /16이면 65,536개, /28이면 16개이고 0.0.0.0/8, 127.0.0.0/8, 169.254.0.0/16, 224.0.0.0/4는 지정할 수 없습니다. 여기까지는 흔한 지식인데 시험에서 답을 가르는 것은 그다음 규칙들입니다.

**기존 CIDR 블록의 크기는 늘릴 수도 줄일 수도 없습니다.** primary CIDR은 disassociate조차 되지 않습니다. 주소가 모자라면 secondary CIDR을 추가하는 길밖에 없고, 그 추가에도 두 겹의 제약이 붙습니다.

첫째는 라우트 제약입니다. secondary CIDR은 어떤 route table의 목적지 CIDR과 같거나 그보다 더 큰 범위로 추가할 수 없습니다. primary가 10.2.0.0/16인 VPC에 10.0.0.0/24가 virtual private gateway로 향하는 라우트가 있다면 10.0.0.0/24 이상은 추가할 수 없고 10.0.0.0/25 이하만 가능합니다.

둘째는 RFC 1918 대역 제약입니다. 서로 다른 사설 대역은 섞을 수 없습니다.

| 기존 VPC CIDR | 추가할 수 없는 CIDR |
| :--- | :--- |
| 10.0.0.0/8 범위 | 172.16.0.0/12 범위, 192.168.0.0/16 범위, 198.19.0.0/16 |
| 172.16.0.0/12 범위 | 10.0.0.0/8 범위, 192.168.0.0/16 범위, 198.19.0.0/16, 172.31.0.0/16 |
| 192.168.0.0/16 범위 | 10.0.0.0/8 범위, 172.16.0.0/12 범위, 198.19.0.0/16 |

"10.0.0.0/16으로 시작했다가 부족해지면 192.168.0.0/16을 붙인다"는 계획은 이 표에서 막힙니다.

셋째는 연결 제약입니다. **하나의 Direct Connect gateway에 연결된 VPC들은 CIDR이 겹치면 안 됩니다.** secondary CIDR을 추가할 때도 같은 조건이 적용되므로, 나중에 하이브리드 연결을 붙일 계획이 있으면 주소 계획을 조직 단위로 잡아 두어야 합니다. VPC peering은 더 엄격해서 CIDR이 하나라도 겹치면 연결 자체를 만들 수 없습니다.

이 세 제약을 조직 규모에서 관리하는 도구가 VPC IPAM입니다. IPAM은 scope와 pool로 IP 공간을 라우팅 도메인과 보안 도메인 단위로 나누고, 비즈니스 규칙에 따라 VPC에 CIDR을 자동 할당하며, 조직 전체의 할당 이력을 남깁니다. BYOIP 주소를 여러 리전과 계정에 걸쳐 공유하고, Amazon이 제공하는 연속된 IPv6 CIDR을 pool에 프로비저닝하는 것도 IPAM의 일입니다. 지문에 "여러 계정에 걸쳐 중복 없는 주소 할당"이나 "할당 이력 추적"이 들어 있으면 IPAM이 답입니다.

---

## 2. 서브넷은 IP 다섯 개를 가져간다

서브넷 IPv4 CIDR은 /28에서 /16 사이입니다. 각 서브넷에서 다섯 개 주소가 예약되어 인스턴스에 할당되지 않습니다.

| 주소 | 용도 |
| :--- | :--- |
| base + 0 | 네트워크 주소 |
| base + 1 | VPC router |
| base + 2 | Amazon DNS server |
| base + 3 | 향후 사용 예약 |
| 마지막 주소 | 브로드캐스트 예약 |

/28 서브넷의 가용 주소가 11개인 이유가 여기 있습니다. VPC에 CIDR이 여러 개 있으면 **DNS 서버 IP는 primary CIDR 기준으로 계산된 base + 2 하나뿐입니다.** secondary CIDR 서브넷마다 별도의 DNS IP가 생기지 않습니다.

IPv6는 규칙이 다릅니다. Amazon 제공 IPv6 CIDR은 기본 /56이고, /44에서 /60까지 /4 단위로 최대 5개를 VPC에 연결할 수 있습니다. 서브넷 IPv6는 /44에서 /64까지 /4 단위입니다. **IPv6 범위는 직접 고를 수 없습니다.** Amazon의 IPv6 주소 pool에서 받고, disassociate한 뒤 다시 요청하면 같은 범위를 받는다는 보장이 없습니다. IPv4처럼 "이 대역으로 주세요"가 성립하지 않는 점이 IPv4와 갈리는 지점입니다.

주요 VPC quota는 다음과 같습니다.

| 항목 | 기본값 | 조정 |
| :--- | :--- | :--- |
| VPCs per Region | 5 | 가능 |
| subnets per VPC | 200 | 가능 |
| IPv4 CIDR per VPC | 5 | 최대 50 |
| route tables per VPC | 200 | 가능 |
| routes per route table | 500 | 최대 1,000 |
| propagated routes per route table | 100 | **조정 불가** |
| rules per network ACL | 20 | inbound 40 + outbound 40까지 |
| rules per security group | 60 | 가능 |
| security groups per ENI | 5 | 최대 16 |

security group 개수와 규칙 수에는 곱셈 상한이 하나 더 붙습니다. **ENI당 SG 수 곱하기 SG당 규칙 수가 1,000을 넘을 수 없습니다.** SG를 16개까지 늘리면 SG당 규칙은 62개가 상한입니다.

customer-managed prefix list는 리전당 100개이고 항목은 최대 1,000개입니다. security group 규칙에서 prefix list를 참조하면 항목 수가 아니라 **prefix list의 `maximum entries` 값이 그대로 SG 규칙 수로 계산됩니다.** 항목을 20개로 잡아 둔 prefix list를 한 줄 참조하면 SG 규칙 20개를 쓴 것과 같습니다. 규칙 수가 왜 갑자기 늘었는지 묻는 문항의 답이 여기 있습니다.

Network Address Usage(NAU)라는 별도의 지표도 있습니다. VPC당 64,000이 기본이고 최대 256,000까지, intra-Region으로 peering된 VPC들의 합산은 128,000이 기본이고 최대 512,000까지입니다. **리전 간 peering은 peered NAU 합산에 포함되지 않습니다.**

---

## 3. route table은 local, longest prefix match, static 순으로 갈린다

VPC route table의 평가 순서는 세 단계입니다.

1. **local 라우트가 언제나 우선합니다.** VPC CIDR 안의 목적지는 다른 어떤 라우트보다 local이 이깁니다.
2. 그다음 **longest prefix match**입니다. 10.0.0.0/16과 10.0.1.0/24가 모두 있으면 10.0.1.5로 가는 패킷은 /24 라우트를 따릅니다.
3. 목적지가 완전히 같으면 **static 라우트가 propagated 라우트를 이깁니다.**

이 순서가 실무 함정을 하나 만듭니다. gateway endpoint를 만들면 route table에 목적지가 AWS 관리형 prefix list인 라우트가 자동으로 들어오는데, 그보다 더 구체적인 CIDR로 S3 IP 범위를 지정한 static 라우트가 이미 있으면 그 라우트가 이깁니다. endpoint를 만들었는데 트래픽이 endpoint를 타지 않는 경우의 원인 중 하나입니다.

---

## 4. NAT gateway의 55,000은 동시 연결 총수가 아니다

NAT gateway는 5 Gbps에서 시작해 100 Gbps까지 자동으로 확장하고, 초당 1,000,000 패킷에서 10,000,000 패킷까지 처리한 뒤 그 이상은 드롭합니다. 더 필요하면 서브넷을 나눠 NAT gateway를 여러 개 두는 것이 공식 권고입니다.

시험에서 자주 오해되는 숫자가 55,000입니다. **이 값은 IPv4 주소 하나당 unique destination마다의 동시 연결 수입니다.** unique destination은 목적지 IP와 목적지 포트와 프로토콜의 조합입니다. 목적지가 다르면 각각 55,000이 따로 계산되므로, 같은 대상에 5.5만 개 이상 동시 연결을 만드는 특수한 워크로드가 아니면 이 값이 먼저 걸리지 않습니다. 걸리더라도 주소를 늘리는 길이 있습니다. NAT gateway에는 primary 1개와 secondary 7개까지 총 8개의 IPv4 주소를 붙일 수 있고, public NAT gateway의 Elastic IP는 기본 2개에서 요청으로 8개까지 늘어납니다.

제어 방식도 문항 재료입니다. **NAT gateway에는 security group을 붙일 수 없습니다.** 제어는 그 서브넷의 network ACL로만 하고, NAT gateway는 포트 1024부터 65535까지를 사용하므로 NACL 규칙을 이 범위에 맞춰야 합니다. 지원 프로토콜은 TCP, UDP, ICMP 세 가지입니다.

MTU는 8500입니다. 초과하는 패킷은 드롭되거나 fragment되며, 인터넷과 통신하는 인스턴스는 MTU를 1500 이하로 두는 것이 권고입니다. Path MTU Discovery와 MSS clamping은 지원합니다.

---

## 5. NAT gateway에 도달할 수 없는 출발지가 정해져 있다

도입에서 본 두 번째 증상의 원인이 여기 있습니다. NAT gateway로 라우팅할 수 없는 조합이 문서에 명시되어 있습니다.

| 출발지 | NAT gateway 경유 |
| :--- | :--- |
| 같은 VPC의 private subnet 인스턴스 | 가능 |
| VPC peering 상대 VPC | **불가** |
| virtual private gateway 기반 Site-to-Site VPN | **불가** |
| Direct Connect (virtual private gateway 종단) | **불가** |
| transit gateway attachment | 가능 |

peering이 막히는 것은 edge-to-edge routing 제약이고, VGW 기반 VPN과 Direct Connect가 막히는 것은 별도로 명시된 미지원 조합입니다. 문서는 같은 문장에서 **transit gateway를 쓰면 가능하다**고 함께 적습니다. 온프레미스 트래픽을 AWS 쪽 고정 IP로 인터넷에 내보내야 하는 요구가 나오면 종단점을 virtual private gateway에서 transit gateway로 바꾸는 것이 답입니다. NACL을 열거나 NAT gateway에 security group을 붙이는 선지는 전부 오답입니다.

private NAT gateway도 함께 정리해 둡니다. private NAT gateway에는 Elastic IP를 붙일 수 없고 인터넷으로 나가지 않습니다. 겹치는 온프레미스 주소 공간과 통신할 때 출발지 주소를 바꾸는 용도입니다. private NAT gateway가 있는 VPC에 internet gateway를 attach하는 것 자체는 가능하지만, 그쪽으로 라우팅하면 internet gateway가 트래픽을 드롭합니다.

![온프레미스에서 시작한 트래픽이 VPC peering에서 끊기고 Transit Gateway를 거치면 이어지는 두 경로](/assets/img/sap-c02/transitive-routing-boundaries.webp)

전이 라우팅이 성립하는 경계와 성립하지 않는 경계를 한 장에 놓은 그림입니다. 위쪽 레인은 온프레미스가 VPC A에 도달한 뒤 peering 상대인 VPC B의 게이트웨이를 쓰려는 경로이고, 아래쪽 레인은 같은 요구를 Direct Connect gateway와 Transit Gateway로 처리하는 경로입니다. 중앙 NAT gateway가 아래쪽 레인에만 있는 이유가 이 절의 표입니다.

---

## 6. IPv6 아웃바운드는 egress-only internet gateway와 NAT64로 갈린다

IPv6에는 NAT라는 개념이 필요 없어 보이지만 AWS에는 두 가지 장치가 있고 용도가 다릅니다.

**egress-only internet gateway**는 IPv6 전용이고 아웃바운드만 허용하는 stateful 장치입니다. 인스턴스가 인터넷으로 나가는 것은 되고 인터넷이 인스턴스로 들어오는 것은 막힙니다. security group을 붙일 수 없고, 리전당 5개이며 VPC당 하나만 attach합니다. 데이터 전송 요금 외에 별도 요금이 없습니다.

**NAT gateway의 NAT64**는 방향이 다른 문제를 풉니다. IPv6 워크로드가 IPv4로만 서비스되는 대상에 도달해야 할 때, Route 53 Resolver의 DNS64와 조합해 IPv6 주소를 IPv4 대상으로 변환합니다. IPv6에서 IPv4로 건너가는 경우이지 IPv6 아웃바운드 인터넷 접근이 아닙니다.

| 축 | NAT gateway | egress-only internet gateway |
| :--- | :--- | :--- |
| 대상 프로토콜 | IPv4, 그리고 IPv6에 대해 NAT64 | IPv6만 |
| 요금 | 시간 요금 + 데이터 처리 요금 | 없음 |
| security group | 부착 불가 | 부착 불가 |
| 개수 | AZ당 5개 | 리전당 5개, VPC당 1개 |
| 확장 | 5에서 100 Gbps, 1M에서 10M pps | 관리형 수평 확장 |

"IPv6 인스턴스의 인터넷 아웃바운드를 열되 인바운드는 막고 비용을 최소화한다"는 요구에는 egress-only internet gateway가 답입니다. NAT gateway는 요금이 붙고 그 자리에서 필요하지도 않습니다.

---

## 7. VPC peering은 전이되지 않고 peer의 게이트웨이도 빌려주지 않는다

VPC peering은 두 VPC 사이의 1대1 연결입니다. 시험에서 다루는 제약은 다섯 갈래입니다.

**전이되지 않습니다.** A와 B, A와 C가 peering되어 있어도 B와 C는 통신하지 못합니다. 라우트를 추가해도 소용이 없고 B와 C 사이에 직접 peering을 맺어야 합니다. VPC N개를 완전 연결하려면 N(N-1)/2개의 연결이 필요하고, 이 곱셈이 Transit Gateway가 존재하는 이유입니다.

**edge-to-edge routing이 금지됩니다.** peer VPC의 다음 자원을 쓸 수 없습니다.

- internet gateway
- NAT device
- Site-to-Site VPN 연결
- Direct Connect 연결
- gateway endpoint

이 목록이 도입의 첫 번째 증상과 이어집니다. VPC B에 S3 gateway endpoint가 있어도 peering으로 연결된 VPC A의 인스턴스는 그 endpoint를 쓰지 못합니다. VPC 밖에서 들어온 Direct Connect 트래픽도 마찬가지입니다.

**CIDR이 겹치면 연결 자체가 만들어지지 않습니다.** IPv4든 IPv6든, CIDR이 여러 개일 때 하나만 겹쳐도 불가합니다. 두 VPC 사이의 peering 연결은 하나만 존재할 수 있습니다.

**MTU가 위치에 따라 다릅니다.** 같은 리전 peering은 9001, 리전 간 peering은 8500입니다.

**DNS에 별도 조건이 붙습니다.** peer VPC의 Amazon DNS server에 직접 질의할 수 없습니다. 리전 간 peering에서는 CIDR이 RFC 1918 범위에 있더라도 DNS resolution 옵션을 켜야 private hostname이 private IP로 해석됩니다.

운영에서 걸리는 시간 값도 있습니다. peering 요청은 pending-acceptance 상태에서 7일이 지나면 만료됩니다. 실패한 연결은 요청자에게 2시간, 거절된 연결은 2일 동안 보입니다.

계정 경계도 한 줄 있습니다. shared VPC의 participant 계정은 peering 연결을 describe, create, accept, reject, modify, delete 중 어느 것도 할 수 없습니다. VPC owner만 가능합니다.

---

## 8. Transit Gateway는 association과 propagation 두 층으로 격리를 만든다

Transit Gateway는 attachment를 붙이고 route table로 그 attachment들 사이의 도달 범위를 정하는 라우터입니다. 시험에서 답을 가르는 것은 route table을 다루는 두 동작의 구분입니다.

- **association**은 attachment가 어느 route table을 보고 다음 홉을 정할지 지정한다. attachment 하나는 route table 하나에만 association된다.
- **propagation**은 attachment가 알고 있는 라우트를 어느 route table에 실을지 지정한다. 하나의 attachment를 여러 route table에 propagate할 수 있다.

이 둘을 분리하면 spoke VPC끼리는 서로 보지 못하고 shared services VPC만 볼 수 있는 구조가 route table 두 개로 만들어집니다. spoke attachment들은 spoke route table에 association되고 그 table에는 shared services VPC 라우트만 실립니다. shared services attachment는 별도 route table에 association되고 그 table에는 모든 spoke 라우트가 propagate됩니다.

![spoke attachment의 association과 shared services route table의 propagation이 만드는 격리 구조](/assets/img/sap-c02/tgw-route-table-isolation.webp)

route table 두 개로 spoke 사이 격리와 shared services 공유를 동시에 만드는 구성을 그린 그림입니다. blackhole route가 별도로 붙어 있는 것은 격리를 라우트 부재가 아니라 명시적 드롭으로 강제하는 경우를 나타냅니다. TGW route table에 blackhole route를 넣으면 해당 CIDR로 향하는 트래픽이 드롭됩니다.

attachment에는 AZ 조건이 하나 있고 이것이 자주 나오는 함정입니다. **VPC attachment는 AZ마다 정확히 서브넷 하나를 지정합니다.** 지정하면 그 AZ의 모든 서브넷이 라우팅 대상이 되지만, attachment 서브넷을 지정하지 않은 AZ의 리소스는 VPC route table에 TGW 라우트가 있어도 transit gateway에 도달하지 못합니다. 세 AZ 중 두 AZ만 attachment에 넣고 배포한 뒤 한 AZ의 인스턴스만 온프레미스에 닿지 않는 증상이 여기서 나옵니다.

주요 quota는 다음과 같습니다.

| 항목 | 값 | 조정 |
| :--- | :--- | :--- |
| 계정당 transit gateway | 5 | 가능 |
| TGW당 attachment | 5,000 | 가능 |
| VPC당 transit gateway | 5 | **불가** |
| 같은 VPC에 대한 VPC attachment | 1 | 불가 |
| TGW당 peering attachment | 50 | 가능 |
| 두 TGW 사이 peering attachment | **1** | 불가 |
| TGW당 route table | 20 | 가능 |
| route table 전체 합산 라우트 | 10,000 | 가능 |
| 하나의 prefix에 대한 static route | attachment 1개 | 불가 |
| Connect attachment당 Connect peer | 4 | 불가 |
| TGW당 Direct Connect gateway | 20 | **불가** |
| Direct Connect gateway당 TGW | 6 | **불가** |

---

## 9. TGW route 평가 순서와 ECMP가 성립하는 조건

TGW route table의 평가는 most specific 우선입니다. 목적지 CIDR이 완전히 같을 때 순위가 갈리는 기준이 따로 있습니다.

1. static route
2. prefix list 참조 route
3. VPC로부터 propagate된 route
4. Direct Connect gateway로부터 propagate된 route
5. Transit Gateway Connect로부터 propagate된 route
6. private Direct Connect 위의 VPN으로부터 propagate된 route
7. Site-to-Site VPN으로부터 propagate된 route
8. VPN Concentrator
9. Client VPN
10. peering

같은 유형끼리 남으면 BGP 속성으로 갈립니다. AS Path 길이가 짧은 쪽, 그다음 MED 값이 낮은 쪽, 그다음 eBGP가 iBGP보다 우선입니다. MED를 지정하지 않으면 Direct Connect는 0, VPN과 Connect는 100이 적용됩니다. 이 기본값 때문에 **Direct Connect와 VPN이 같은 prefix를 광고하면 Direct Connect가 선택됩니다.** VPN을 Direct Connect의 백업으로 두는 구성이 별도 설정 없이 의도대로 동작하는 이유입니다.

ECMP는 조건이 까다롭습니다. 네 가지 중 하나라도 어긋나면 성립하지 않습니다.

| 조건 | 내용 |
| :--- | :--- |
| dynamic routing | VPN은 BGP를 쓸 때만 ECMP가 동작한다. static routing VPN은 불가 |
| CIDR 중복 불가 대상 | VPC attachment는 CIDR이 겹칠 수 없으므로 애초에 ECMP 대상이 아니다 |
| 같은 attachment 유형 | 유형이 다르면 ECMP가 성립하지 않는다 |
| 같은 ASN | BGP Multipath AS-Path Relax를 지원하지 않아 ASN이 다르면 불가 |

Direct Connect 쪽에는 반대 방향의 권고가 하나 붙습니다. **하나의 Direct Connect gateway는 여러 transit VIF에 걸쳐 ECMP를 지원하므로 gateway를 나누지 말라**는 것입니다. 대역폭을 늘리려고 Direct Connect gateway를 여러 개 만드는 선지는 이 권고와 충돌합니다.

---

## 10. stateful appliance를 붙이면 appliance mode가 필수다

중앙 inspection VPC에 방화벽 어플라이언스를 두고 TGW로 east-west 트래픽을 검사하는 구성은 흔합니다. 여기에 조건이 하나 붙습니다.

**stateful appliance가 있는 VPC attachment에는 appliance mode를 켜야 합니다.** 켜지 않으면 요청 방향과 응답 방향이 서로 다른 AZ의 어플라이언스에 도착합니다. 응답을 받은 어플라이언스는 그 세션을 모르므로 패킷을 드롭합니다. 같은 출발지와 목적지 조합인데도 성공과 실패가 섞이고, 어플라이언스 로그에는 세션 테이블에 없는 패킷이라는 기록이 남습니다.

![appliance mode를 껐을 때 응답이 다른 AZ로 돌아가는 경로와 켰을 때 같은 AZ로 고정되는 경로](/assets/img/sap-c02/tgw-appliance-mode-symmetry.webp)

같은 트래픽이 appliance mode 설정에 따라 어디로 가는지를 두 레인으로 나눠 놓은 그림입니다. 위 레인의 마지막 상자가 드롭인 것이 이 절의 증상이고, 아래 레인의 양방향 연결이 appliance mode가 만드는 상태입니다.

여기서 파생되는 오답이 두 개 있습니다. 첫째, **transit gateway를 여러 개 붙여 방향별로 나누면 오히려 나빠집니다.** TGW끼리는 flow state를 공유하지 않아 stickiness가 보장되지 않습니다. 둘째, AWS Network Firewall attachment로 바꾸면 appliance mode가 자동으로 켜지고 static routing만 지원하지만 **서드파티 방화벽은 지원하지 않습니다.** 기존 어플라이언스를 유지해야 하는 지문에서는 답이 되지 못합니다.

---

## 11. TGW 대역폭과 MTU, 그리고 peering attachment가 static route만 지원한다

대역폭은 attachment 유형과 AZ 단위로 정해집니다.

| attachment | 대역폭 |
| :--- | :--- |
| VPC attachment | AZ당 각 방향 최대 100 Gbps |
| Direct Connect gateway attachment | AZ당 각 방향 최대 100 Gbps |
| peering attachment | AZ당 각 방향 최대 100 Gbps |
| 공통 패킷 한도 | attachment당 AZ당 최대 7,500,000 pps |
| Connect peer (GRE 터널) | 터널당 최대 5 Gbps, 4개 합산 20 Gbps |

MTU는 attachment 유형에 따라 갈립니다. VPC, Direct Connect, Connect, peering attachment 사이는 8500이고 **VPN 트래픽만 1500**입니다. TGW는 모든 패킷에 MSS clamping을 적용합니다. Path MTU Discovery는 VPC attachment와 Connect attachment의 ingress에서만 지원하고 Site-to-Site VPN, Direct Connect, peering attachment에서는 지원하지 않습니다.

MTU 값 차이가 마이그레이션 함정을 하나 만듭니다. 같은 리전 VPC peering의 MTU는 9001인데 TGW 경유는 8500입니다. peering에서 TGW로 옮길 때 양쪽 VPC를 동시에 전환하지 않으면 비대칭 경로가 생기고 jumbo 패킷이 드롭될 수 있습니다.

peering attachment에는 결정적인 제약이 하나 더 있습니다. **peering attachment는 static route만 지원합니다.** dynamic routing이 없으므로 BGP 기반 자동 전환이 불가능하고, ECMP도 성립하지 않으며, 같은 static route를 두 target에 걸 수도 없습니다. 게다가 두 transit gateway 사이의 peering attachment는 하나뿐입니다. "리전 간 TGW peering을 이중화하고 BGP로 전환하며 대역폭을 두 배로 만든다"는 계획은 이 세 문장에서 전부 막힙니다.

---

## 12. Direct Connect의 물리 계층: dedicated, hosted, LAG

Direct Connect 연결에는 두 종류가 있고 계약 경로와 속도 선택지가 다릅니다.

**dedicated connection**은 고객 하나에 배정되는 물리 이더넷 연결이고 콘솔, CLI, API로 직접 요청합니다. 포트 속도는 single-mode fiber 기준으로 정해져 있습니다.

| 속도 | 광 인터페이스 |
| :--- | :--- |
| 1 Gbps | 1000BASE-LX |
| 10 Gbps | 10GBASE-LR |
| 100 Gbps | 100GBASE-LR4 |
| 400 Gbps | 400GBASE-LR4 |

**hosted connection**은 AWS Direct Connect Partner가 고객을 대신해 프로비저닝합니다. 콘솔로 요청할 수 없고 파트너를 통해야 하며, 만들어진 연결을 고객이 accept해야 사용할 수 있습니다. 속도는 50 Mbps, 100 Mbps, 200 Mbps, 300 Mbps, 400 Mbps, 500 Mbps, 1 Gbps, 2 Gbps, 5 Gbps, 10 Gbps, 25 Gbps 중에서 고릅니다. 1 Gbps 이상은 특정 요건을 충족한 파트너만 제공할 수 있고, 25 Gbps는 100 Gbps 포트가 제공되는 location에서만 가능합니다. AWS는 hosted connection에 traffic policing을 적용하므로 설정 최대 속도에 도달하면 초과 트래픽이 드롭되고, 버스트가 많은 트래픽은 실효 처리량이 더 낮게 나옵니다.

VIF를 만들 수 있는 개수가 두 종류에서 크게 다릅니다.

| 항목 | dedicated connection | hosted connection |
| :--- | :--- | :--- |
| private 또는 public VIF | 50개 | 종류 무관 **1개** |
| transit VIF | 4개 | 종류 무관 1개 |
| 합계 | 51개 | 1개 |
| 조정 | 불가 | 불가 |

hosted connection이 VIF 하나만 지원한다는 사실이 문항의 축이 되는 경우가 있습니다. 하나의 회선으로 VPC 접근과 S3 public endpoint 접근을 동시에 하려면 VIF 두 개가 필요하고, hosted connection에서는 성립하지 않습니다.

**LAG**는 여러 dedicated connection을 하나의 논리 연결로 묶습니다. 묶을 수 있는 개수가 포트 속도에 따라 갈립니다.

| 포트 속도 | LAG당 dedicated connection |
| :--- | :--- |
| 100 Gbps 미만 | 4개 |
| 100 Gbps | **2개** |

리전당 LAG는 10개이고 LAG당 VIF는 51개입니다. "100 Gbps 회선 네 개를 LAG로 묶어 400 Gbps를 만든다"는 선지는 두 번째 행에서 막힙니다. LAG는 같은 location의 링크 묶음이므로 **location 장애를 흡수하지 못한다**는 점도 함께 기억해야 합니다.

하나의 Direct Connect location, 하나의 리전, 하나의 계정 기준으로 active connection은 10개입니다.

---

## 13. VIF 세 종류가 도달하는 대상이 다르다

virtual interface는 물리 연결 위에 올라가는 논리 인터페이스이고 종단점에 따라 세 종류입니다.

![private VIF, public VIF, transit VIF가 각각 종단하는 지점과 도달 범위](/assets/img/sap-c02/dx-vif-reach-scope.webp)

같은 물리 회선에서 갈라진 세 VIF가 각각 어디에 종단하고 그 너머로 무엇에 도달하는지를 그린 그림입니다. 종단점이 다르다는 사실 하나에서 MTU 상한과 prefix 상한과 SiteLink 가능 여부가 함께 갈립니다.

| 축 | private VIF | public VIF | transit VIF |
| :--- | :--- | :--- | :--- |
| 종단 | virtual private gateway 또는 Direct Connect gateway | AWS public prefix 전체 | Direct Connect gateway에 연결된 transit gateway |
| 도달 대상 | VPC의 private IP | S3, EC2 public IP, 서비스 API endpoint | TGW에 붙은 모든 attachment |
| MTU | 1500 또는 9001 | jumbo 미지원 | 1500 또는 8500 |
| dedicated당 개수 | private과 public 합산 50 | 합산 50 | 4 |
| 수신 prefix 상한 | 기본 100, 최대 1,000 | 1,000 고정 | 기본 100, 최대 1,000 |
| SiteLink | Direct Connect gateway 연결 시만 지원 | 미지원 | 지원 |

public VIF의 성격을 정확히 잡아 둘 필요가 있습니다. public VIF는 AWS의 public prefix 전체를 광고받아 EC2 public IP, S3, 서비스 API endpoint에 도달합니다. Amazon 소유가 아닌 prefix는 받지 못하므로 인터넷 회선을 대체하지 못합니다. 반대 방향으로는, AWS가 public VIF로 받은 고객 prefix를 AWS 외부로 재광고하지는 않지만 **그 prefix는 모든 AWS 고객에게 보입니다.** 광고할 수 있는 prefix는 최소 1개에서 최대 1,000개이고 길이는 IPv4가 /1에서 /32, IPv6가 /1에서 /64입니다.

MTU 변경에는 부작용이 붙습니다. jumbo로 바꾸면 그 물리 연결의 **모든 VIF가 최대 30초 끊깁니다.** 같은 라우트를 서로 다른 MTU의 private VIF 두 개가 광고하거나 Site-to-Site VPN이 같은 라우트를 광고하면 1500이 적용됩니다. hosted connection은 부모 연결에 jumbo가 켜져 있어야 켤 수 있습니다.

BGP 설정에도 고정 규칙이 있습니다.

- **VIF의 customer gateway ASN과 virtual private gateway 또는 Direct Connect gateway ASN을 같은 값으로 쓸 수 없다.**
- 16-bit private ASN 범위는 64512부터 65534다.
- public VIF에 private ASN을 쓰면 AS prepending이 동작하지 않는다.
- BGP MD5 인증은 기본 활성이고 끌 수 없다.
- IPv6 peering 주소는 Amazon이 /125로 자동 할당하며 직접 지정할 수 없다.

---

## 14. Direct Connect gateway와 SiteLink가 여는 경로

Direct Connect gateway는 VIF와 gateway 사이에 놓여 연결 범위를 넓히는 전역 리소스입니다. 계정당 200개까지 만들 수 있고, gateway 하나에 virtual private gateway 20개 또는 transit gateway 6개를 붙입니다. gateway당 private 또는 transit VIF는 30개입니다.

앞서 본 대로 **하나의 Direct Connect gateway에 연결된 VPC들은 CIDR이 겹치면 안 됩니다.** 이 조건이 주소 설계와 하이브리드 연결 설계를 묶습니다.

**SiteLink**는 온프레미스 거점 사이의 트래픽을 AWS 백본으로 보내는 기능입니다. 지원 범위가 좁아서 그 자체가 문항이 됩니다.

| VIF 구성 | SiteLink |
| :--- | :--- |
| transit VIF | 지원 |
| Direct Connect gateway에 붙은 private VIF | 지원 (virtual private gateway 연결 여부와 무관) |
| virtual private gateway에 직접 붙은 private VIF | **미지원** |
| public VIF | **미지원** |

GovCloud(US)와 중국 리전에서는 SiteLink를 제공하지 않습니다. 온프레미스 라우터가 같은 라우트를 여러 VIF에 광고하면 동작하지 않습니다. prefix 상한은 IPv4와 IPv6 각각 1,000개입니다.

---

## 15. BGP prefix 상한을 넘기면 회선 전체가 끊긴다

private VIF와 transit VIF는 온프레미스에서 AWS 방향으로 IPv4와 IPv6 각각 기본 100개의 prefix를 받습니다. prefix control로 각각 1,000개까지 확장할 수 있습니다. **상한을 넘겨 광고하면 BGP 세션이 idle 상태로 떨어지고 status가 DOWN으로 보고됩니다.**

증상이 특징적입니다. 물리 회선과 라우터 설정과 MD5 인증에 문제가 없고 직전까지 정상이었는데, 온프레미스 쪽에서 경로를 세분화해 광고한 직후 연결이 전부 끊깁니다. 조치는 두 가지입니다. 경로를 요약해 100개 이하로 줄이거나 prefix control로 상한을 올리는 것입니다.

방향별 상한이 다르다는 점도 함께 봅니다.

| 방향과 VIF | 상한 |
| :--- | :--- |
| 온프레미스에서 AWS로, private VIF | IPv4와 IPv6 각각 기본 100, 최대 1,000 |
| 온프레미스에서 AWS로, transit VIF | IPv4와 IPv6 각각 기본 100, 최대 1,000 |
| 온프레미스에서 AWS로, public VIF | 1,000 고정 |
| AWS에서 온프레미스로, transit VIF | IPv4와 IPv6 **합산 200** |

transit VIF의 나가는 방향 합산 200이 조용한 함정입니다. TGW에 붙은 VPC가 많아지면 온프레미스로 광고되는 prefix 수가 이 값에 먼저 걸립니다. 물리 연결을 추가하거나 LAG를 만들어도 prefix 상한은 VIF 단위 제약이라 각각 같은 값이 적용됩니다.

---

## 16. Direct Connect는 기본적으로 암호화하지 않는다

Direct Connect는 전용 회선이지 암호화 서비스가 아닙니다. 전송 중 암호화 요건이 나오면 두 가지 선택지가 있고 각각 조건이 붙습니다.

**MACsec**은 물리 계층 암호화입니다. 지원 범위가 좁습니다.

| 항목 | 조건 |
| :--- | :--- |
| 연결 종류 | dedicated connection, LAG, partner interconnect 지원. hosted connection **미지원** |
| 포트 속도 | 10, 100, 400 Gbps. **1 Gbps 미지원** |
| location | 선택된 PoP만 |
| 키 길이 | 256-bit만 |
| cipher suite | 100/400 Gbps는 XPN 필수(GCM-AES-XPN-256), 10 Gbps는 GCM-AES-256도 가능 |
| 기본 모드 | `should_encrypt`. 협상 실패 시 평문으로 fallback |
| 엄격 모드 | `must_encrypt`. 협상 실패 시 트래픽을 흘리지 않는다 |
| 키 회전 | CKN/CAK를 최대 3쌍 보관해 무중단 회전 |

`should_encrypt`가 기본값이라는 점이 문항이 됩니다. 규제 요건이 "암호화되지 않은 트래픽이 흐르지 않아야 한다"이면 `must_encrypt`로 바꿔야 하고, 그 대가로 협상이 실패하면 통신이 끊깁니다.

**IPsec VPN over Direct Connect**는 MACsec 조건을 만족하지 못할 때의 표준 대안입니다. 같은 dedicated connection에 public VIF를 추가로 만들고 그 위로 Site-to-Site VPN을 올리면 회선 교체 없이 암호화 경로가 생깁니다. dedicated connection은 private과 public VIF를 합쳐 50개까지 만들 수 있으므로 기존 private VIF 경로를 유지한 채 추가할 수 있습니다. 1 Gbps 연결에서 암호화 요건을 만족해야 하는 지문의 답이 이 경로입니다.

---

## 17. 이중화 모델이 SLA를 정하고 리드타임이 일정을 정한다

Direct Connect Resiliency Toolkit은 세 가지 모델을 제시하고 각각 SLA 목표가 다릅니다.

| 모델 | 구성 | SLA 목표 | 흡수하는 장애 |
| :--- | :--- | :--- | :--- |
| Maximum resiliency | 2개 이상 location, 각 location에서 서로 다른 디바이스로 종단 | 99.99% | 디바이스 장애, location 장애 |
| High resiliency | 2개 location에 각각 단일 연결 | 99.9% | location 장애 |
| Development and test | 1개 location의 별도 디바이스 | 없음 | 디바이스 장애만 |

99.99퍼센트를 요구하는 지문에는 Maximum resiliency만 답이 됩니다. 같은 location에서 LAG로 묶거나 디바이스만 나누는 구성은 location 장애를 흡수하지 못합니다.

일정 축도 문항 재료입니다.

- 연결 요청 검토와 포트 할당에 최대 **72 business hours**가 걸린다.
- LOA 관련 추가 정보 요청에 7일 안에 응답하지 않으면 연결이 삭제된다.
- public VIF 생성도 검토에 최대 72 business hours가 걸린다.
- 여기에 물리 회선 조달 기간이 따로 붙는다.

"2주 안에 온프레미스와 AWS 사이 연결을 열어야 한다"는 요구에 Direct Connect 신규 계약이 답이 되지 않는 이유가 이 목록입니다. 즉시 필요한 연결은 Site-to-Site VPN이고, Direct Connect가 준비되면 VPN을 백업으로 남깁니다.

---

## 18. Site-to-Site VPN은 터널 2개이고 라우트 상한은 gateway 종류로 갈린다

Site-to-Site VPN 연결 하나는 터널 두 개로 구성됩니다. 터널 종류에 따라 처리량이 다릅니다.

| 터널 종류 | 처리량 | 패킷 |
| :--- | :--- | :--- |
| 표준 터널 | 최대 1.25 Gbps | 140,000 pps |
| large bandwidth 터널 | 최대 5 Gbps | 400,000 pps |
| VPN Concentrator 터널 | 최대 100 Mbps | 10,000 pps |

MTU는 1446이고 MSS는 1406입니다. **jumbo frame을 지원하지 않고 Path MTU Discovery도 지원하지 않습니다.** IPv6 VPN은 IPv4와 동일한 처리량, MTU, 라우트 상한을 가집니다.

라우트 상한은 AWS 쪽 종단점이 무엇이냐에 따라 크게 갈립니다.

| 항목 | virtual private gateway 기반 | transit gateway 기반 |
| :--- | :--- | :--- |
| customer gateway에서 AWS로, dynamic | 100 | 1,000 |
| AWS에서 customer gateway로 | 1,000 | 5,000 |
| static route | 100 | - |

리전당 quota도 함께 봅니다. Site-to-Site VPN connection 50개, virtual private gateway 5개, customer gateway 50개, virtual private gateway당 VPN connection 10개, accelerated VPN 10개입니다. **VPC에 attach할 수 있는 virtual private gateway는 하나뿐입니다.**

**VPN CloudHub**는 여러 지사가 하나의 virtual private gateway를 허브로 삼아 서로 통신하는 hub-and-spoke 구성입니다. 구성 조건이 명확합니다.

- virtual private gateway 하나를 만든다.
- customer gateway를 지사마다 만들고 **각각 서로 다른 BGP ASN을 쓴다.**
- 각 customer gateway에서 그 공통 virtual private gateway로 **dynamic routing** VPN 연결을 만든다.
- 각 지사 라우터가 자기 prefix를 광고하면 virtual private gateway가 받아 다른 BGP peer에게 재광고한다.
- **지사들의 IP 범위가 겹치면 안 된다.**

VPC 없이도 쓸 수 있고, Direct Connect로 virtual private gateway에 연결된 거점도 CloudHub의 구성원이 될 수 있습니다. 과금은 VPN 연결마다의 시간 요금과, virtual private gateway에서 나가는 방향의 데이터 전송 요금입니다.

---

## 19. accelerated VPN은 새로 만들어야 하고 조합 제약이 있다

accelerated Site-to-Site VPN은 AWS Global Accelerator의 애니캐스트 IP로 터널 종단점을 노출해 지연과 지터를 줄입니다. 제약이 네 개이고 전부 문항 재료입니다.

| 제약 | 내용 |
| :--- | :--- |
| 종단점 | **transit gateway attach VPN만 지원.** virtual private gateway 미지원 |
| 전환 방식 | 기존 연결에서 켜거나 끌 수 **없다.** 새 연결을 만들어야 한다 |
| 병용 | Direct Connect **public VIF와 함께 쓸 수 없다** |
| NAT-T | 필수이며 기본 활성 |
| IKE 개시 | customer gateway 쪽에서 개시해야 한다 |
| 인증서 인증 | Global Accelerator의 fragmentation 제약 때문에 IKE fragmentation을 지원하는 장비가 필요하다 |

"기존 VPN에 acceleration을 켜서 지연을 줄인다"는 선지는 두 번째 행에서 막히고, "virtual private gateway를 유지한 채 켠다"는 선지는 첫 번째 행에서 막힙니다. 지문에 public VIF가 함께 등장하면 세 번째 행까지 봐야 합니다.

---

## 20. Client VPN이 SNAT하는 것과 하지 않는 것

AWS Client VPN은 OpenVPN 기반 TLS 연결입니다. 포트는 TCP와 UDP의 443과 1194를 지원하고 기본은 443입니다.

주소 처리가 프로토콜에 따라 갈립니다. **IPv4 트래픽은 client CIDR 주소를 Client VPN ENI의 주소로 SNAT하고, IPv6는 SNAT하지 않습니다.** 대상 리소스의 로그에 클라이언트 주소가 어떻게 남는지가 여기서 결정됩니다.

접근 제어에는 명시적 단계가 하나 더 있습니다. **기본 authorization rule이 없습니다.** endpoint를 만들고 target network를 연결해도 authorization rule을 추가하지 않으면 어떤 대상에도 접근이 열리지 않습니다. target network는 VPC subnet association이거나 transit gateway 직접 attach입니다.

---

## 21. gateway endpoint는 VPC route table 안에서만 산다

VPC endpoint는 다섯 유형입니다. Interface, Gateway Load Balancer, Resource, Service network, Gateway입니다. 이 중 **gateway endpoint의 대상 서비스는 Amazon S3와 DynamoDB 둘뿐이고 AWS PrivateLink를 쓰지 않습니다.** 추가 요금이 없다는 점이 큰 장점이고, 두 서비스는 interface endpoint도 함께 지원합니다.

gateway endpoint를 만들면 선택한 route table에 목적지가 AWS 관리형 prefix list인 라우트가 자동으로 들어옵니다. 이 라우트는 **수정하거나 삭제할 수 없습니다.** 한 route table에 같은 서비스의 endpoint 라우트를 둘 이상 둘 수도 없습니다.

route table 기반이라는 구현이 세 가지 제약을 만듭니다.

1. **VPC 밖에서 쓸 수 없다.** peering 상대 VPC, Direct Connect, Site-to-Site VPN에서 들어온 트래픽은 gateway endpoint를 경유하지 못한다. edge-to-edge routing 금지 목록에 gateway endpoint가 명시되어 있다.
2. **다른 리전의 버킷에는 적용되지 않는다.** prefix list가 리전 한정이라 다른 리전 S3로 향하는 트래픽은 gateway endpoint를 타지 않는다. 별도 interface endpoint나 TGW 경로가 없으면 VPC route table의 default route target(예: internet gateway)에 따라 전송된다.
3. **더 구체적인 static 라우트가 이긴다.** 서비스 IP 범위를 정확히 지정한 라우트가 있으면 그 라우트가 endpoint 라우트보다 우선한다.

security group 설정에도 특징이 있습니다. gateway endpoint로 접근할 때 인스턴스는 여전히 **서비스의 public endpoint를 호출합니다.** 따라서 security group outbound에 그 서비스의 prefix list를 허용해야 하고, network ACL은 prefix list를 참조할 수 없으므로 CIDR을 직접 나열해야 합니다.

![VPC 안 인스턴스와 온프레미스 서버가 S3에 도달하는 세 경로와 각 경로가 성립하는 조건](/assets/img/sap-c02/s3-private-access-paths.webp)

같은 S3 버킷에 도달하는 세 경로를 출발지 기준으로 나눠 놓은 그림입니다. 온프레미스 쪽에서 gateway endpoint로 향하는 경로가 점선과 붉은 상자로 처리된 것이 도입의 첫 번째 증상이고, 그 자리를 interface endpoint가 대신합니다.

---

## 22. interface endpoint와 PrivateLink endpoint service

interface endpoint는 서브넷에 ENI를 만들고 private IP를 부여합니다. 이 구현이 gateway endpoint와의 모든 차이를 만듭니다.

| 축 | gateway endpoint | interface endpoint |
| :--- | :--- | :--- |
| 대상 서비스 | S3와 DynamoDB만 | 대부분의 AWS 서비스와 사용자 endpoint service |
| 구현 | route table의 prefix list 라우트 | 서브넷의 ENI와 private IP |
| 온프레미스 접근 | **불가** | 가능. private IP로 도달 |
| peering, TGW 경유 | **불가** | 가능 |
| 요금 | 없음 | 시간 요금 + 데이터 처리 요금 |
| 대역폭 | 별도 상한 없음 | AZ당 10 Gbps에서 100 Gbps 자동 확장 |
| endpoint policy | 지원 | 지원 |

온프레미스에서 S3에 private IP로 접근하면서 endpoint policy로 대상 버킷을 제한해야 하는 요구에는 interface endpoint 하나만 답이 됩니다. gateway endpoint는 경로 자체가 만들어지지 않고, public VIF 경로는 VPC 안 private IP를 종단으로 거치지 않아 endpoint policy가 적용되지 않습니다.

interface endpoint의 대역폭과 MTU는 다음과 같습니다. AZ당 기본 10 Gbps에서 100 Gbps까지 자동 확장하므로 모든 AZ에 분산하면 최대치는 AZ 수 곱하기 100 Gbps입니다. MTU는 8500이고 초과 패킷은 드롭됩니다. Path MTU Discovery를 지원하지 않고 MSS clamping을 항상 적용합니다.

quota는 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| interface와 Gateway Load Balancer endpoint 합산 | VPC당 50 |
| gateway endpoint | 리전당 20, VPC당 최대 255 |
| resource endpoint | VPC당 200 |
| service network endpoint | VPC당 50 |
| VPC endpoint policy 길이 | 공백 포함 20,480자 |

**endpoint service**를 직접 만들어 다른 계정에 서비스를 노출하는 것이 PrivateLink의 provider 쪽 기능입니다. 조건이 둘 있습니다. Network Load Balancer 또는 Gateway Load Balancer가 필요하고, 만들어진 endpoint service는 **기본적으로 비공개**입니다. 특정 AWS principal을 허용해야 consumer가 연결을 요청할 수 있고, provider가 그 요청을 accept하거나 reject합니다.

**resource endpoint**는 로드 밸런서 없이 데이터베이스, EC2 인스턴스, 도메인 타깃, IP 주소에 직접 연결하는 유형이고 RAM으로 공유합니다. 로드 밸런서를 세우기 위한 구성이 부담인 경우의 대안입니다.

endpoint policy의 기본값도 기억해야 합니다. **기본 VPC endpoint policy는 모든 principal의 모든 action을 모든 resource에 허용합니다.** 제한하려면 명시적으로 정책을 붙여야 하고, 붙이지 않은 endpoint는 통제 지점이 아니라 통과 지점입니다.

---

## 23. 전이 라우팅이 되는 조합과 되지 않는 조합

앞의 절들에 흩어진 규칙을 한 표로 모읍니다. SAP 문항의 상당수가 이 표의 한 행입니다.

| 경로 | 성립 여부 | 근거 |
| :--- | :--- | :--- |
| VPC A - peering - VPC B - peering - VPC C | 불가 | transitive peering 미지원 |
| VPC A - peering - VPC B의 internet gateway | 불가 | edge-to-edge routing |
| VPC A - peering - VPC B의 NAT gateway | 불가 | edge-to-edge routing |
| VPC A - peering - VPC B의 gateway endpoint | 불가 | edge-to-edge routing |
| 온프레미스 - Direct Connect - VPC A - peering - VPC B | 불가 | edge-to-edge routing |
| 온프레미스 - VGW VPN - VPC의 NAT gateway | 불가 | 문서에 미지원으로 명시 |
| 온프레미스 - Direct Connect(VGW) - VPC의 NAT gateway | 불가 | 문서에 미지원으로 명시 |
| 온프레미스 - TGW VPN - 다른 VPC의 NAT gateway | 가능 | transit gateway 경유는 지원 |
| 온프레미스 - transit VIF - TGW - 여러 VPC | 가능 | TGW route table이 허용하는 범위 |
| VPC A - TGW - VPC B | 가능 | route table이 허용하면 |
| VPC A - TGW - TGW peering - 다른 리전 VPC | 가능 | static route만 |
| 온프레미스 - Direct Connect - VPC의 interface endpoint | 가능 | private IP로 도달 |
| 온프레미스 - Direct Connect - VPC의 gateway endpoint | 불가 | route table 기반 |

표의 첫 절반이 "peering으로 묶었으니 통한다"는 오해를 무너뜨리고, 뒷절반이 Transit Gateway를 쓰는 이유를 설명합니다.

AWS Cloud WAN이라는 상위 서비스도 존재하지만 SAP-C02 Exam Guide v1.2의 in-scope 서비스 목록에 없습니다. 여러 리전의 Transit Gateway와 VPN을 정책 문서 하나로 관리하는 계층이라는 정도만 알아 두면 충분합니다.

---

## 24. shared VPC와 Transit Gateway 중 무엇을 고를 것인가

여러 계정이 같은 네트워크를 쓰는 방법이 둘입니다. RAM으로 서브넷을 공유하는 shared VPC와 계정마다 VPC를 두고 TGW로 잇는 방식입니다.

**shared VPC**는 같은 AWS Organizations 조직 안의 계정에만 가능합니다. participant 계정은 공유받은 서브넷에 자기 리소스를 만들고 수정하고 삭제할 수 있지만 다른 participant나 owner의 리소스는 보거나 수정할 수 없습니다. 반대로 owner는 participant 리소스에 붙은 ENI와 security group을 볼 수 있습니다. VPC당 participant 계정은 100개, 계정당 공유받을 수 있는 서브넷은 100개입니다.

| 축 | shared VPC | Transit Gateway |
| :--- | :--- | :--- |
| 계정 경계 | 같은 조직 안에서만 | RAM 공유로 조직 밖 계정과도 가능 |
| 통신 방식 | VPC 내부 라우팅이라 홉이 없다 | attachment 사이 L3 라우팅 |
| 라우팅 제어 | owner가 route table을 독점 관리 | route table 분리로 attachment 격리 |
| IP 공간 | 하나의 VPC CIDR을 나눠 소비 | VPC마다 별도 CIDR, 중복 불가 |
| 규모 상한 | VPC당 participant 100개 | attachment 5,000개 |
| 비용 특성 | 별도 시간 요금 없음 | attachment당 시간 요금 + 데이터 처리 요금 |

"팀마다 계정은 나누되 네트워크는 하나로 유지하고 라우팅 관리를 중앙에 남긴다"는 요구에는 shared VPC가 맞고, "계정마다 독립된 주소 공간을 갖되 필요한 곳만 연결한다"는 요구에는 Transit Gateway가 맞습니다.

VPC peering과 Transit Gateway를 고르는 기준도 함께 정리합니다.

| 축 | VPC peering | Transit Gateway |
| :--- | :--- | :--- |
| 전이 라우팅 | 불가 | route table이 허용하는 범위에서 가능 |
| CIDR 중복 | 절대 불가 | VPC attachment끼리 중복 불가, route table로 격리는 가능 |
| MTU | 같은 리전 9001, 리전 간 8500 | 8500, VPN 트래픽만 1500 |
| peer의 게이트웨이 사용 | 불가 | 중앙 NAT와 중앙 DX gateway 공유가 표준 패턴 |
| 확장 | VPC 쌍마다 연결 1개, N개 완전 연결에 N(N-1)/2개 | attachment 5,000개 |
| 비용 | 연결 자체에 시간 요금 없음 | attachment 시간 요금 + 데이터 처리 요금 |
| 답이 갈리는 지점 | VPC 두 개만 붙이고 MTU와 비용을 최적화할 때 | 3개 이상, 온프레미스 공유, 라우트 격리가 필요할 때 |

---

## 25. security group과 NACL과 Network Firewall이 각각 막는 것

세 계층은 적용 지점과 상태 처리 방식이 다릅니다.

| 축 | security group | network ACL | AWS Network Firewall |
| :--- | :--- | :--- | :--- |
| 적용 지점 | ENI | 서브넷 | firewall endpoint로 향하는 라우트 |
| 상태 | stateful | stateless | stateful IPS |
| 규칙 표현력 | 포트, 프로토콜, 출발지(SG 참조와 prefix list 포함) | 포트, 프로토콜, CIDR, 순서가 있는 allow와 deny | Suricata 호환 규칙, 도메인 목록, 포트와 무관한 프로토콜 탐지 |
| 상한 | 규칙 60개, ENI당 SG 5개(최대 16) | 규칙 20개, 최대 inbound 40 + outbound 40 | 별도 quota |
| 조직 단위 관리 | 없음 | 없음 | Firewall Manager |

AWS Network Firewall에는 배치 규칙이 두 개 있고 둘 다 문항이 됩니다.

1. **firewall subnet은 Network Firewall 전용이어야 한다.** 다른 워크로드를 같은 서브넷에 두지 않는다.
2. **firewall endpoint는 자기가 있는 서브넷의 인바운드와 아웃바운드 트래픽을 필터할 수 없다.** 검사 대상 워크로드를 같은 서브넷에 두면 검사되지 않는다.

트래픽을 방화벽으로 유도하는 것은 VPC route table의 일입니다. 방화벽이 알아서 가로채지 않으므로 라우트 설계가 통제의 실체입니다.

---

## 26. 트래픽이 어디서 막혔는지 알아내는 네 가지 도구

**VPC Flow Logs**는 ENI 단위의 흐름 기록입니다. 성능 걱정으로 끄는 선택은 근거가 없습니다. **flow log 데이터는 네트워크 트래픽 경로 밖에서 수집되어 처리량과 지연에 영향을 주지 않습니다.** 대상은 CloudWatch Logs, S3, Amazon Data Firehose입니다.

기억해야 할 것은 무엇이 기록되지 않는가입니다.

| 수집되지 않는 트래픽 | 비고 |
| :--- | :--- |
| Amazon DNS server로 가는 질의 | 자체 DNS 서버를 쓰면 기록된다 |
| Windows 라이선스 활성화 | |
| 169.254.169.254 instance metadata | |
| 169.254.169.123 Time Sync Service | |
| DHCP | |
| traffic mirror source 트래픽 | target 쪽 트래픽만 보인다 |
| 기본 VPC router 예약 IP로 가는 트래픽 | |
| endpoint ENI와 Network Load Balancer ENI 사이 트래픽 | |
| ARP | |

"인스턴스가 어떤 도메인을 조회하는지 Flow Logs로 감사한다"는 선지가 여기서 막힙니다. DNS 가시성은 Route 53 Resolver query logging의 영역이고, 메타데이터 호출은 Flow Logs 밖의 수단이 필요합니다.

운영 제약도 함께 봅니다. **flow log는 생성 후 설정과 record format을 바꿀 수 없어 삭제하고 다시 만들어야 합니다.** peered VPC는 같은 계정일 때만 flow log를 켤 수 있습니다. Nitro 인스턴스의 ENI는 지정한 max aggregation interval과 무관하게 항상 1분 이하로 집계됩니다. 리소스당 계정당 subscription은 250개입니다.

**Reachability Analyzer**는 패킷을 보내지 않는 configuration analysis 도구입니다. 도달 가능하면 hop-by-hop 가상 경로를 내고, 불가능하면 차단하는 컴포넌트를 지목합니다. security group, network ACL, route table, 로드 밸런서가 지목 대상입니다. 분석 실행 단위로 과금합니다. 구성 오류를 찾는 데는 빠르지만 **실제 트래픽 동작을 증명하지 못한다**는 점이 오답 선지의 재료입니다.

**Network Access Analyzer**는 의도한 네트워크 접근 경로와 실제 구성이 어긋나는 지점을 찾는 도구입니다.

**Traffic Mirroring**은 실제 패킷 사본을 분석 대상에 보냅니다. 캡슐화 방식이 제약을 만듭니다.

- VXLAN(UDP 4789)으로 캡슐화한다.
- **target의 security group이 source로부터 UDP 4789를 허용해야 한다.**
- Network Load Balancer를 target으로 쓸 때 UDP 4789 listener가 없으면 **에러 표시 없이 미러링이 실패한다.**
- Gateway Load Balancer MTU 8500 기준으로 IPv4는 헤더 54바이트, IPv6는 74바이트가 붙어 각각 8446, 8426을 넘으면 잘린다.
- mirror source에서 inbound security group이나 network ACL로 드롭된 트래픽은 미러링되지 않는다.
- outbound mirror 트래픽에는 source의 outbound security group 규칙이 적용되지 않는다.
- mirror target은 다른 계정 소유일 수 있다. 고가용성을 위해 NLB나 Gateway Load Balancer endpoint를 target으로 쓰면 패킷 순서가 어긋날 수 있다.

---

## 27. 리전과 AZ 선택을 네트워크 제약이 좁히는 지점

리전과 AZ 선택은 지연과 데이터 주권으로 논의되는 경우가 많지만, 시험에서 답을 가르는 것은 앞 절들에 흩어진 구조적 제약입니다.

| 제약 | 선택에 미치는 영향 |
| :--- | :--- |
| TGW attachment 서브넷이 없는 AZ는 TGW에 도달하지 못한다 | 워크로드를 배치할 AZ와 attachment 서브넷 집합이 같아야 한다 |
| attachment 대역폭이 AZ당 계산된다 | AZ를 늘리는 것이 대역폭 상한을 늘리는 수단이 된다 |
| interface endpoint 대역폭도 AZ당 계산된다 | 모든 AZ에 endpoint를 두면 최대치가 AZ 수만큼 곱해진다 |
| 리전 간 peering MTU는 8500이고 같은 리전은 9001 | jumbo frame에 의존하는 워크로드는 리전을 넘지 않는 편이 안전하다 |
| 리전 간 peering은 peered NAU 합산에 포함되지 않는다 | NAU 상한 계산에서 같은 리전과 다른 리전이 다르게 취급된다 |
| Direct Connect location 다중화가 SLA를 가른다 | 99.99퍼센트를 요구하면 location을 2개 이상 확보할 수 있는 지역이어야 한다 |

---

## 28. 암기해야 하는 하드 리밋과 동작 제약

**VPC와 서브넷**

| 항목 | 값 |
| :--- | :--- |
| VPC IPv4 CIDR | /16에서 /28 |
| 서브넷 IPv4 CIDR | /28에서 /16 |
| 서브넷 예약 주소 | 앞 4개와 마지막 1개, 총 5개 |
| VPC IPv6 CIDR | Amazon 제공 기본 /56, /44에서 /60까지 /4 단위, 최대 5개 |
| 서브넷 IPv6 CIDR | /44에서 /64까지 /4 단위 |
| 기존 CIDR 크기 변경 | 불가. primary CIDR은 disassociate도 불가 |
| VPCs per Region | 5 (조정 가능) |
| subnets per VPC | 200 |
| IPv4 CIDR per VPC | 5 (최대 50) |
| route tables per VPC | 200 |
| routes per route table | 500 (최대 1,000) |
| propagated routes per route table | 100 (조정 불가) |
| rules per network ACL | 20 (최대 inbound 40 + outbound 40) |
| rules per security group | 60 |
| security groups per ENI | 5 (최대 16), SG 수 곱하기 규칙 수는 1,000 이하 |
| customer-managed prefix list | 리전당 100개, 항목 최대 1,000개 |
| internet gateway | 리전당 5개, VPC당 1개 |
| egress-only internet gateway | 리전당 5개, VPC당 1개 |
| NAT gateway | AZ당 5개 |
| Elastic IP | 리전당 5개, public NAT gateway당 2개(최대 8개) |
| Network Address Usage | VPC당 64,000(최대 256,000), intra-Region peered 합산 128,000(최대 512,000) |

**NAT gateway**

| 항목 | 값 |
| :--- | :--- |
| 처리량 | 5 Gbps에서 100 Gbps 자동 확장 |
| 패킷 | 1,000,000 pps에서 10,000,000 pps, 초과분 드롭 |
| 동시 연결 | IPv4 주소 하나당 unique destination마다 55,000 |
| IPv4 주소 | primary 1개 + secondary 7개 |
| security group | 부착 불가. NACL로만 제어 |
| 사용 포트 | 1024에서 65535 |
| 프로토콜 | TCP, UDP, ICMP |
| MTU | 8500 |

**VPC peering**

| 항목 | 값 |
| :--- | :--- |
| 전이 라우팅 | 불가 |
| 두 VPC 사이 연결 수 | 1 |
| CIDR 중복 | 불가. 하나만 겹쳐도 불가 |
| MTU | 같은 리전 9001, 리전 간 8500 |
| 요청 만료 | pending-acceptance 7일 |
| 실패한 연결 표시 | 요청자에게 2시간 |
| 거절된 연결 표시 | 요청자에게 2일 |

**Transit Gateway**

| 항목 | 값 |
| :--- | :--- |
| 계정당 TGW | 5 (조정 가능) |
| TGW당 attachment | 5,000 |
| VPC당 TGW | 5 (조정 불가) |
| TGW당 peering attachment | 50 |
| 두 TGW 사이 peering attachment | 1 |
| TGW당 route table | 20 |
| 전체 합산 라우트 | 10,000 |
| Connect attachment당 Connect peer | 4 |
| VPC/DX gateway/peering attachment 대역폭 | AZ당 각 방향 100 Gbps |
| attachment 패킷 | AZ당 7,500,000 pps |
| Connect peer 대역폭 | GRE 터널당 5 Gbps, 합산 20 Gbps |
| MTU | 8500, VPN 트래픽만 1500 |
| PMTUD | VPC와 Connect attachment ingress만 지원 |
| TGW당 Direct Connect gateway | 20 (조정 불가) |
| Direct Connect gateway당 TGW | 6 (조정 불가) |
| peering attachment 라우팅 | static만 |

**Direct Connect**

| 항목 | 값 |
| :--- | :--- |
| dedicated 포트 속도 | 1, 10, 100, 400 Gbps |
| hosted 포트 속도 | 50 Mbps에서 25 Gbps (50/100/200/300/400/500 Mbps, 1/2/5/10/25 Gbps) |
| dedicated당 VIF | private과 public 합산 50, transit 4, 총 51 |
| hosted당 VIF | 1 |
| LAG | 100 Gbps 미만 4개, 100 Gbps 2개 |
| 리전당 LAG | 10, LAG당 VIF 51 |
| 계정당 Direct Connect gateway | 200 |
| gateway당 VGW | 20 |
| gateway당 TGW | 6 |
| gateway당 private 또는 transit VIF | 30 |
| location과 리전과 계정당 active connection | 10 |
| private/transit VIF 수신 prefix | IPv4와 IPv6 각각 기본 100, 최대 1,000 |
| public VIF prefix | 1,000 고정 |
| transit VIF 송신 prefix | IPv4와 IPv6 합산 200 |
| private VIF MTU | 1500 또는 9001 |
| transit VIF MTU | 1500 또는 8500 |
| jumbo 전환 영향 | 해당 물리 연결의 모든 VIF가 최대 30초 중단 |
| MACsec 지원 | dedicated connection, LAG, partner interconnect의 10/100/400 Gbps 선택 PoP만, 256-bit key. hosted connection은 미지원 |
| 프로비저닝 리드타임 | 연결 요청 검토 최대 72 business hours, public VIF 검토도 최대 72 business hours |
| LOA 응답 기한 | 7일. 미응답 시 연결 삭제 |
| 16-bit private ASN | 64512에서 65534 |
| SLA 목표 | Maximum resiliency 99.99%, High resiliency 99.9% |

**Site-to-Site VPN과 Client VPN**

| 항목 | 값 |
| :--- | :--- |
| 연결당 터널 | 2 |
| 표준 터널 | 1.25 Gbps, 140,000 pps |
| large bandwidth 터널 | 5 Gbps, 400,000 pps |
| VPN Concentrator 터널 | 100 Mbps, 10,000 pps |
| MTU | 1446, MSS 1406 |
| jumbo frame과 PMTUD | 미지원 |
| VGW 기반 라우트 | CGW에서 AWS로 dynamic 100, static 100, AWS에서 CGW로 1,000 |
| TGW 기반 라우트 | CGW에서 AWS로 1,000, AWS에서 CGW로 5,000 |
| 리전당 VPN connection | 50 |
| 리전당 virtual private gateway | 5 |
| 리전당 customer gateway | 50 |
| VGW당 VPN connection | 10 |
| VPC당 virtual private gateway | 1 |
| 리전당 accelerated VPN | 10 |
| Client VPN 포트 | TCP와 UDP의 443, 1194. 기본 443 |
| Client VPN SNAT | IPv4는 SNAT, IPv6는 SNAT하지 않음 |

**VPC endpoint**

| 항목 | 값 |
| :--- | :--- |
| gateway endpoint 대상 | S3와 DynamoDB만 |
| gateway endpoint 요금 | 없음 |
| interface + Gateway Load Balancer endpoint | VPC당 50 |
| gateway endpoint | 리전당 20, VPC당 최대 255 |
| resource endpoint | VPC당 200 |
| service network endpoint | VPC당 50 |
| endpoint policy 길이 | 공백 포함 20,480자 |
| interface endpoint 대역폭 | AZ당 10 Gbps에서 100 Gbps |
| interface endpoint MTU | 8500, PMTUD 미지원, MSS clamping 항상 적용 |
| 기본 endpoint policy | 모든 principal의 모든 action 허용 |

**모니터링**

| 항목 | 값 |
| :--- | :--- |
| flow log 대상 | CloudWatch Logs, S3, Amazon Data Firehose |
| flow log 설정 변경 | 불가. 삭제 후 재생성 |
| flow log subscription | 리소스당 계정당 250 |
| Nitro ENI 집계 간격 | 설정과 무관하게 1분 이하 |
| Traffic Mirroring 캡슐화 | VXLAN, UDP 4789 |
| Traffic Mirroring 패킷 상한 | IPv4 8446, IPv6 8426 (GWLB MTU 8500 기준) |
| shared VPC | VPC당 participant 100개, 계정당 공유 subnet 100개 |

---

## 29. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| VPC peering 대 Transit Gateway | peering은 전이되지 않고 peer의 게이트웨이도 쓸 수 없다. TGW는 route table이 허용하는 범위에서 전이되고 중앙 NAT와 중앙 DX gateway 공유가 표준 패턴이다 |
| gateway endpoint 대 interface endpoint | gateway는 S3와 DynamoDB만, route table 기반이라 VPC 밖에서 쓸 수 없고 요금이 없다. interface는 ENI 기반이라 온프레미스와 peering과 TGW 경유가 되고 시간 요금과 데이터 처리 요금이 붙는다 |
| private VIF 대 transit VIF | private은 VGW 또는 DX gateway에 종단해 VPC 하나 또는 gateway에 붙은 VPC들에 닿고 MTU 9001까지다. transit은 DX gateway를 거쳐 TGW에 닿고 MTU 8500이며 dedicated당 4개다 |
| public VIF 대 인터넷 회선 | public VIF는 AWS public prefix만 광고받아 AWS 서비스에만 닿는다. non-Amazon prefix는 받지 못해 인터넷 회선을 대체하지 못한다 |
| dedicated connection 대 hosted connection | dedicated는 콘솔로 요청하고 VIF 51개에 MACsec과 LAG가 가능하다. hosted는 파트너가 프로비저닝하고 VIF 1개에 MACsec이 불가하며 traffic policing이 적용된다 |
| Direct Connect 대 Site-to-Site VPN | DX는 대역폭이 일정하고 지터가 낮지만 리드타임이 72 business hours 이상에 물리 회선 조달이 더해진다. VPN은 API 호출로 수분 안에 열리고 IPsec 암호화가 기본이며 MTU 1446이다 |
| MACsec 대 IPsec over Direct Connect | MACsec은 dedicated connection과 LAG와 partner interconnect의 10/100/400 Gbps 선택 PoP에서 물리 계층으로 처리한다. IPsec은 public VIF 위에 올려 회선 조건과 무관하게 암호화한다 |
| virtual private gateway 대 Transit Gateway | VGW는 VPC 하나에만 붙고 NAT gateway 경유와 accelerated VPN을 지원하지 않으며 VPN 라우트 상한이 낮다. TGW는 attachment 5,000개에 그 셋을 모두 지원한다 |
| Maximum resiliency 대 High resiliency | 전자는 2개 이상 location에서 각각 별도 디바이스로 종단해 SLA 99.99% 목표다. 후자는 2개 location에 단일 연결씩으로 99.9% 목표다 |
| LAG 대 다중 location 이중화 | LAG는 같은 location의 링크 묶음이라 대역폭은 늘리지만 location 장애를 막지 못한다. SLA는 location 수가 정한다 |
| NAT gateway 대 egress-only internet gateway | NAT gateway는 IPv4용이고 IPv6에는 NAT64를 수행하며 시간 요금과 데이터 처리 요금이 붙는다. egress-only는 IPv6 아웃바운드 전용이고 별도 요금이 없다 |
| public NAT gateway 대 private NAT gateway | public은 EIP를 붙여 인터넷으로 나간다. private은 EIP를 붙일 수 없고 인터넷으로 나가지 않으며 겹치는 주소 공간과의 통신에서 출발지를 바꾼다 |
| security group 대 network ACL | SG는 ENI에 붙는 stateful allow 목록이고 SG 참조와 prefix list 참조가 된다. NACL은 서브넷에 붙는 stateless 목록이고 순서가 있는 deny를 쓸 수 있으며 prefix list를 참조하지 못한다 |
| network ACL 대 Network Firewall | NACL은 포트와 CIDR 수준이고 규칙 수가 작다. Network Firewall은 Suricata 규칙과 도메인 목록과 포트 무관 프로토콜 탐지를 하고 Firewall Manager로 조직 단위 관리가 된다 |
| Flow Logs 대 Traffic Mirroring | Flow Logs는 흐름 메타데이터이고 경로 밖에서 수집되어 성능 영향이 없다. Traffic Mirroring은 패킷 사본이고 VXLAN 캡슐화와 target security group 조건이 붙는다 |
| Reachability Analyzer 대 실제 연결 테스트 | Analyzer는 패킷을 보내지 않는 configuration analysis라 구성 오류는 지목하지만 실제 트래픽 동작을 증명하지 못한다 |
| shared VPC 대 Transit Gateway | shared VPC는 같은 조직 안에서 하나의 CIDR을 나눠 쓰고 라우팅을 owner가 독점한다. TGW는 계정마다 별도 CIDR을 두고 route table로 격리한다 |
| association 대 propagation | association은 attachment가 어느 route table을 볼지 정하고 하나만 가능하다. propagation은 attachment의 라우트가 어느 table에 실릴지 정하고 여러 table에 가능하다 |
| appliance mode 대 Network Firewall attachment | appliance mode는 VPC attachment의 옵션으로 서드파티 어플라이언스에 쓴다. Network Firewall attachment는 appliance mode가 자동이지만 static routing만 지원하고 서드파티를 지원하지 않는다 |
| VPN CloudHub 대 Transit Gateway | CloudHub는 virtual private gateway 하나를 허브로 삼는 BGP 재광고 구조이고 지사마다 고유 ASN이 필요하다. TGW는 attachment와 route table로 같은 일을 하며 VPC 연결과 라우트 격리가 함께 된다 |

---

## 30. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| VPC A와 B, A와 C가 peering되어 있으니 B에서 C로 라우트만 추가하면 통신된다 | transitive peering을 지원하지 않는다. B와 C 사이에 직접 peering이 필요하다 |
| 온프레미스에서 Direct Connect로 들어와 peer VPC의 gateway endpoint로 S3에 접근한다 | edge-to-edge routing 금지 목록에 gateway endpoint가 있고, gateway endpoint는 route table 기반이라 VPC 밖에서 쓸 수 없다. interface endpoint를 쓴다 |
| 온프레미스 서버가 VGW 기반 VPN을 타고 VPC의 NAT gateway로 인터넷에 나간다 | VGW 기반 VPN과 Direct Connect에서는 NAT gateway로 라우팅할 수 없다. transit gateway로 바꾸면 가능하다 |
| NAT gateway에 security group을 붙여 아웃바운드 목적지를 제한한다 | NAT gateway에는 security group을 붙일 수 없다. NACL이나 Network Firewall을 쓴다 |
| NAT gateway 하나로는 55,000개 넘는 동시 연결을 낼 수 없다 | 55,000은 IP 하나당 unique destination 기준이다. 목적지가 다르면 별개로 계산되고 주소를 8개까지 붙일 수도 있다 |
| private NAT gateway가 있는 VPC에 internet gateway를 붙여 인터넷으로 내보낸다 | attach 자체는 되지만 그쪽으로 라우팅하면 internet gateway가 트래픽을 드롭한다 |
| 여러 VPN 터널을 static routing으로 묶어 ECMP로 대역폭을 늘린다 | ECMP는 dynamic routing(BGP)에서만 동작한다 |
| 기존 VPN 연결에 acceleration을 켜서 지연을 줄인다 | 기존 연결에서 켜거나 끌 수 없고 새 연결을 만들어야 한다. VGW attach VPN은 accelerated VPN을 지원하지도 않는다 |
| accelerated VPN을 Direct Connect public VIF와 함께 구성해 백본을 최적화한다 | 두 기능은 함께 사용할 수 없다 |
| 두 TGW를 peering하고 BGP로 라우트를 광고해 이중 경로를 만든다 | peering attachment는 static route만 지원해 dynamic routing과 ECMP가 불가능하고, 두 TGW 사이 peering attachment는 하나뿐이다 |
| 중앙 inspection VPC에 방화벽을 두고 TGW로 보내면 대칭 라우팅이 보장된다 | appliance mode를 켜지 않으면 응답이 발신 AZ로 돌아가 세션을 모르는 어플라이언스에서 드롭된다 |
| 방향별로 TGW를 두 개 두면 flow가 고정된다 | TGW끼리는 flow state를 공유하지 않아 stickiness가 오히려 깨진다 |
| 서드파티 방화벽을 Network Firewall attachment로 붙여 appliance mode를 자동으로 켠다 | network function attachment는 서드파티 방화벽을 지원하지 않는다 |
| TGW에 VPC를 attach했으니 그 VPC의 모든 AZ 리소스가 온프레미스에 도달한다 | attachment 서브넷이 없는 AZ의 리소스는 route table에 TGW 라우트가 있어도 도달하지 못한다 |
| hosted connection에 MACsec을 켜서 Direct Connect 구간을 암호화한다 | MACsec은 hosted connection을 지원하지 않는다. 대안은 public VIF 위의 IPsec VPN이다 |
| 1 Gbps dedicated connection에 MACsec을 켠다 | 1 Gbps는 MACsec 지원 속도가 아니다 |
| MACsec을 켜면 협상이 실패해도 트래픽이 흐르지 않는다 | 기본 모드는 `should_encrypt`라 협상 실패 시 평문으로 fallback한다. `must_encrypt`로 바꿔야 한다 |
| LAG로 100 Gbps 회선 4개를 묶어 400 Gbps를 만든다 | 100 Gbps 포트는 LAG당 2개까지다. 4개는 100 Gbps 미만 속도에서만 가능하다 |
| LAG로 이중화하면 Direct Connect SLA 99.99퍼센트를 만족한다 | LAG는 같은 location의 링크 묶음이라 location 장애를 흡수하지 못한다 |
| virtual private gateway에 직접 붙은 private VIF에 SiteLink를 켠다 | SiteLink는 VGW에 직접 붙은 private VIF와 public VIF를 지원하지 않는다. Direct Connect gateway를 거쳐야 한다 |
| 온프레미스 라우터가 private VIF로 500개 prefix를 광고해 세분화된 라우팅을 만든다 | 기본 상한이 IPv4와 IPv6 각 100개이고 초과하면 BGP 세션이 idle로 떨어져 회선이 끊긴다. prefix control로 1,000까지 올려야 한다 |
| 물리 연결을 추가해 prefix 상한을 늘린다 | prefix 상한은 VIF 단위 제약이라 연결을 늘려도 각각 같은 상한이 적용된다 |
| private VIF의 customer gateway ASN과 Direct Connect gateway ASN을 같은 값으로 맞춘다 | 같은 ASN은 허용되지 않는다 |
| 대역폭을 늘리려고 Direct Connect gateway를 여러 개 만들어 transit VIF를 나눈다 | 하나의 Direct Connect gateway가 여러 transit VIF에 걸쳐 ECMP를 지원하므로 문서는 gateway를 나누지 말라고 권고한다 |
| VPC를 /24로 만들고 나중에 부족하면 /16으로 넓힌다 | 기존 CIDR 블록의 크기는 변경할 수 없다. secondary CIDR을 추가해야 하고 그마저 대역 교차 제한과 기존 라우트 제약에 걸린다 |
| 10.0.0.0/16 VPC에 192.168.0.0/16 secondary CIDR을 추가해 주소를 늘린다 | 서로 다른 RFC 1918 대역은 섞을 수 없다 |
| VPC에 CIDR을 추가했으니 그 대역 서브넷에도 별도 DNS 서버 IP가 생긴다 | DNS 서버 IP는 primary CIDR 기준 base + 2 하나뿐이다 |
| IPv6 CIDR을 원하는 대역으로 지정해 온프레미스 주소 계획과 맞춘다 | Amazon 제공 IPv6 범위는 직접 고를 수 없고 재요청해도 같은 범위를 받는다는 보장이 없다 |
| security group 규칙에 prefix list를 한 줄 넣었으니 규칙을 하나만 쓴 것이다 | prefix list의 `maximum entries` 값이 그대로 규칙 수로 계산된다 |
| 다른 리전의 S3 버킷도 gateway endpoint로 private하게 접근한다 | prefix list는 리전 한정이라 다른 리전 S3 트래픽은 gateway endpoint를 타지 않는다. 별도 interface endpoint나 TGW 경로가 없으면 route table의 default route target(예: internet gateway)에 따라 전송된다 |
| gateway endpoint를 만들었으니 security group outbound를 좁혀도 된다 | 인스턴스는 여전히 서비스의 public endpoint를 호출하므로 outbound에 서비스 prefix list를 허용해야 한다 |
| endpoint를 만들었으니 endpoint policy 없이도 접근이 제한된다 | 기본 endpoint policy는 모든 principal의 모든 action을 허용한다 |
| endpoint service를 만들면 다른 계정이 바로 연결할 수 있다 | 기본은 비공개다. 특정 principal을 허용하고 연결 요청을 accept해야 한다 |
| PrivateLink로 서비스를 노출하려면 Application Load Balancer를 쓴다 | endpoint service는 Network Load Balancer 또는 Gateway Load Balancer가 필요하다 |
| Flow Logs로 인스턴스의 DNS 질의와 메타데이터 호출을 감사한다 | Amazon DNS server 트래픽, 169.254.169.254, 169.254.169.123, DHCP는 기록되지 않는다 |
| Flow Logs의 record format을 바꿔 누락된 필드를 추가한다 | 생성 후 설정과 record format을 바꿀 수 없다. 삭제하고 다시 만들어야 한다 |
| Flow Logs가 트래픽 경로에 끼어 지연을 유발하므로 성능 민감 워크로드에서는 끈다 | flow log는 트래픽 경로 밖에서 수집되어 처리량과 지연에 영향이 없다 |
| Reachability Analyzer로 실제 애플리케이션 연결을 테스트해 정책을 검증한다 | 패킷을 보내지 않는 configuration analysis라 구성 오류는 잡지만 실 트래픽 동작을 증명하지 못한다 |
| Traffic Mirroring target을 NLB로 두면 별도 설정 없이 동작한다 | UDP 4789 listener가 없으면 에러 표시 없이 미러링이 실패한다 |
| security group으로 드롭된 인바운드 트래픽도 미러링해 공격을 분석한다 | source에서 inbound security group이나 NACL로 드롭된 트래픽은 미러링되지 않는다 |
| Network Firewall endpoint가 있는 서브넷의 인스턴스 트래픽도 함께 검사된다 | firewall endpoint는 자기가 있는 서브넷의 트래픽을 필터할 수 없다. firewall subnet은 전용으로 둔다 |
| shared VPC participant 계정이 peering 연결을 만들어 자기 트래픽 경로를 연다 | participant는 peering 연결을 describe, create, accept, reject, modify, delete할 수 없다 |
| CloudHub 지사들이 같은 ASN을 써도 hub-and-spoke가 동작한다 | customer gateway마다 고유한 BGP ASN이 필요하고 지사 IP 범위도 겹치면 안 된다 |
| hosted connection 하나로 VPC 접근과 S3 public endpoint 접근을 동시에 연다 | hosted connection은 종류 무관 VIF 하나만 지원한다 |

---

## 31. 예상 문제 10문항

**Q1.** 온프레미스 데이터센터가 virtual private gateway 기반 Site-to-Site VPN으로 VPC에 연결되어 있습니다. 보안 요건상 온프레미스 서버의 인터넷 아웃바운드를 AWS 쪽 고정 IP로 내보내야 해서 VPC의 public NAT gateway를 경유하도록 라우팅을 구성했지만 트래픽이 전혀 흐르지 않습니다. VPN 터널 상태와 온프레미스 라우터 설정은 정상이고 NACL도 열려 있습니다. MOST appropriate 해결책은 무엇입니까?

- A. NAT gateway를 private NAT gateway로 교체하고 온프레미스 CIDR을 라우팅 대상에 추가한다
- B. NAT gateway가 있는 서브넷의 NACL에 온프레미스 CIDR을 명시적으로 허용한다
- C. virtual private gateway 대신 transit gateway에 VPN을 attach하고 TGW route table로 NAT gateway 서브넷을 경유시킨다
- D. NAT gateway에 security group을 붙여 온프레미스 CIDR의 아웃바운드를 허용한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

virtual private gateway 기반 Site-to-Site VPN이나 Direct Connect에서 들어온 트래픽은 NAT gateway로 라우팅할 수 없습니다. 공식 문서가 이 조합을 미지원으로 명시하고, transit gateway를 쓰면 가능하다고 함께 적습니다. 따라서 종단점을 TGW로 바꾸는 것이 해결책입니다.

- A가 틀린 이유: private NAT gateway는 인터넷으로 나가지 못한다. 게다가 VGW 기반 VPN에서 NAT gateway로 라우팅할 수 없다는 제약은 그대로다.
- B가 틀린 이유: NACL은 원인이 아니다. 문제는 지원되지 않는 라우팅 조합이다.
- D가 틀린 이유: NAT gateway에는 security group을 붙일 수 없다. 제어는 서브넷 NACL로만 한다.

</details>

**Q2.** 온프레미스 배치 서버가 Direct Connect private VIF로 VPC에 접근합니다. 이 서버가 S3에 대량 데이터를 업로드해야 하는데, 보안팀은 트래픽이 VPC 안의 private IP를 종단으로 거치고 endpoint policy로 대상 버킷을 제한할 것을 요구합니다. VPC에는 이미 S3 gateway endpoint가 있지만 온프레미스에서는 사용되지 않습니다. MOST appropriate 구성은 무엇입니까?

- A. VPC에 S3 interface endpoint를 만들고 온프레미스 DNS가 그 endpoint의 private IP로 S3 이름을 해석하게 한 뒤 endpoint policy로 버킷을 제한한다
- B. gateway endpoint가 쓰는 AWS 관리 prefix list를 온프레미스 라우터에 BGP로 광고한다
- C. public VIF를 추가로 만들어 온프레미스에서 S3 public endpoint로 직접 접근한다
- D. S3 버킷 정책에 `aws:SourceVpce` 조건을 추가해 기존 gateway endpoint를 통한 접근만 허용한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

gateway endpoint는 VPC route table의 prefix list 라우트로 구현되므로 VPC 밖에서 사용할 수 없고, edge-to-edge routing 제약으로 Direct Connect나 VPN에서 접근할 수 없습니다. 온프레미스에서 private IP를 종단으로 삼으려면 interface endpoint가 필요하고, 그 endpoint에 endpoint policy를 붙여 대상 버킷을 제한합니다.

- B가 틀린 이유: prefix list 라우트는 VPC route table 안에서만 의미가 있다. 광고해도 온프레미스에서 gateway endpoint를 쓸 수 없다.
- C가 틀린 이유: public VIF는 S3의 public endpoint에 도달하는 경로다. 트래픽이 VPC 안 private IP를 종단으로 거치지 않고 endpoint policy도 적용되지 않는다.
- D가 틀린 이유: 조건을 추가해도 온프레미스에서 gateway endpoint를 경유하는 경로 자체가 생기지 않아 접근이 아예 성립하지 않는다.

</details>

**Q3.** 중앙 inspection VPC에 stateful 방화벽 어플라이언스를 배치하고 transit gateway로 VPC 사이 east-west 트래픽을 검사합니다. 어플라이언스는 세 AZ에 배포했고 TGW route table 구성은 단순합니다. 배포 후 일부 세션이 무작위로 끊기는데, 같은 출발지와 목적지 조합에서도 성공과 실패가 섞입니다. 어플라이언스 로그에는 세션 테이블에 없는 패킷이라는 기록이 남습니다. MOST likely 원인과 조치는 무엇입니까?

- A. VPC route table의 longest prefix match가 어긋난 것이므로 더 구체적인 라우트를 추가한다
- B. TGW를 두 개로 나눠 방향별로 분리하면 flow가 고정된다
- C. AWS Network Firewall attachment로 교체하면 static routing이라 대칭 경로가 보장된다
- D. inspection VPC attachment에 appliance mode를 켜서 flow가 같은 AZ로 대칭 라우팅되게 한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

appliance mode를 stateful appliance가 있는 VPC attachment에 켜지 않으면 응답 트래픽이 발신 AZ로 돌아가 세션을 모르는 어플라이언스에 도착하고 드롭됩니다. 세션 테이블에 없는 패킷이라는 로그는 비대칭 라우팅의 전형적인 증상입니다.

- A가 틀린 이유: 문제는 목적지 선택이 아니라 AZ 사이 경로 비대칭이다. 더 구체적인 라우트를 넣어도 응답 방향의 AZ 선택은 바뀌지 않는다.
- B가 틀린 이유: transit gateway를 여러 개 붙이면 TGW끼리 flow state를 공유하지 않아 stickiness가 오히려 보장되지 않는다.
- C가 틀린 이유: network function attachment는 appliance mode가 자동으로 켜지지만 서드파티 방화벽을 지원하지 않는다. 기존 어플라이언스를 그대로 둘 수 없다.

</details>

**Q4.** 서로 다른 두 리전의 transit gateway를 peering attachment로 연결했습니다. 네트워크팀은 리전 간 경로를 이중화해 BGP로 장애 시 자동 전환하고, 두 경로에 트래픽을 분산해 유효 대역폭을 두 배로 늘리는 계획을 세웠습니다. 두 TGW의 ASN은 서로 다르고, 리전 간 트래픽은 이미 두 리전 사이 최대 100 Gbps를 쓰고 있습니다. 이 계획의 MOST significant 문제는 무엇입니까?

- A. 두 TGW 사이에 peering attachment를 두 개 만들면 되지만 ASN이 달라 ECMP가 동작하지 않는다
- B. peering attachment는 static route만 지원해 BGP 자동 전환과 ECMP가 성립하지 않고, 두 TGW 사이 peering attachment도 하나만 만들 수 있다
- C. peering attachment의 MTU가 1500이라 대역폭 증설 효과가 상쇄된다
- D. peering attachment에 appliance mode를 켜지 않으면 경로가 비대칭이 되어 분산이 무의미하다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

transit gateway peering attachment는 static route만 지원합니다. dynamic routing이 없어 BGP 기반 자동 전환과 ECMP가 모두 불가능하고, 같은 static route를 두 target에 걸 수도 없습니다. 게다가 두 transit gateway 사이의 peering attachment는 하나로 제한됩니다.

- A가 틀린 이유: attachment를 두 개 만드는 것 자체가 불가능하다. ASN 차이는 dynamic routing이 있을 때의 ECMP 제약이고 여기서는 그 단계에 도달하지 않는다.
- C가 틀린 이유: peering attachment의 MTU는 8500이다. 1500은 VPN 트래픽의 값이다.
- D가 틀린 이유: appliance mode는 stateful appliance가 있는 VPC attachment에 켜는 옵션이다. peering 이중화 계획의 실패 원인이 아니다.

</details>

**Q5.** 규제 요건으로 온프레미스와 AWS 사이 모든 트래픽을 전송 중 암호화해야 합니다. 현재 연결은 1 Gbps dedicated connection 하나이고 private VIF가 virtual private gateway에 붙어 있습니다. 회선을 상위 속도로 교체하거나 신규 회선을 계약하지 않고 요건을 만족해야 하며 기존 private VIF 경로도 유지해야 합니다. MOST appropriate 방법은 무엇입니까?

- A. 이 연결에 MACsec을 활성화해 물리 계층에서 암호화한다
- B. private VIF를 transit VIF로 교체하면 transit gateway 구간이 암호화된다
- C. 같은 dedicated connection에 public VIF를 추가로 만들고 그 위로 IPsec Site-to-Site VPN을 구성한다
- D. Global Accelerator를 사용하는 accelerated Site-to-Site VPN을 Direct Connect public VIF와 함께 구성한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Direct Connect는 기본적으로 암호화를 제공하지 않습니다. MACsec은 10, 100, 400 Gbps dedicated connection의 선택된 PoP에서만 지원하므로 1 Gbps 연결에서는 쓸 수 없습니다. dedicated connection은 private과 public VIF를 합쳐 50개까지 만들 수 있으므로 public VIF를 추가하고 그 위로 IPsec VPN을 올려 암호화 경로를 만들 수 있습니다.

- A가 틀린 이유: MACsec은 1 Gbps 연결과 hosted connection을 지원하지 않는다.
- B가 틀린 이유: transit VIF도 암호화를 제공하지 않는다. VIF 종류는 도달 대상이 다를 뿐 암호화와 무관하다.
- D가 틀린 이유: accelerated Site-to-Site VPN은 Direct Connect public VIF와 함께 사용할 수 없고 transit gateway attachment에서만 지원된다.

</details>

**Q6.** 온프레미스 라우터가 private VIF로 온프레미스 경로 320개를 광고하기 시작한 직후 Direct Connect의 BGP 세션이 DOWN으로 표시되고 VPC 연결이 전부 끊겼습니다. 물리 회선 상태, 라우터 설정, MD5 인증에는 이상이 없고 광고 이전에는 정상 동작했습니다. 세분화된 라우팅은 유지하고 싶습니다. MOST appropriate 조치는 무엇입니까?

- A. 광고 prefix를 기본 상한인 100개 이하로 요약하거나 prefix control로 상한을 1,000개까지 올린다
- B. LAG를 만들어 dedicated connection을 추가하고 광고를 분산한다
- C. private VIF의 MTU를 9001로 올려 라우팅 업데이트 패킷이 잘리지 않게 한다
- D. private VIF를 transit VIF로 교체해 광고 가능한 prefix 수를 늘린다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

private VIF는 온프레미스에서 AWS 방향으로 IPv4와 IPv6 각각 기본 100개의 prefix를 받습니다. 상한을 넘겨 광고하면 BGP 세션이 idle 상태로 떨어지고 status가 DOWN으로 보고됩니다. 경로를 요약해 100개 이하로 줄이거나 prefix control로 상한을 최대 1,000개까지 확장하면 해결됩니다.

- B가 틀린 이유: prefix 상한은 VIF 단위 제약이라 물리 연결을 늘려도 같은 상한이 각각 적용된다.
- C가 틀린 이유: MTU는 데이터 평면 패킷 크기 문제이고 BGP prefix 상한 초과와 무관하다. jumbo 전환은 오히려 해당 연결의 모든 VIF를 최대 30초 끊는다.
- D가 틀린 이유: transit VIF도 온프레미스에서 AWS 방향 기본 상한이 같고, AWS에서 온프레미스로 나가는 방향은 IPv4와 IPv6 합산 200개로 더 좁다.

</details>

**Q7.** 결제 시스템이 온프레미스와 AWS를 오가며 Direct Connect SLA 99.99퍼센트를 요구합니다. 예산은 확보되어 있고 구축 기간은 6개월이며, 특정 Direct Connect location 전체가 내려가는 상황에서도 연결이 유지되어야 합니다. AWS Direct Connect Resiliency Toolkit 기준으로 이 목표에 대응하는 MOST appropriate 구성은 무엇입니까?

- A. 하나의 location에서 LAG로 dedicated connection 두 개를 묶는다
- B. 하나의 location에서 서로 다른 디바이스에 연결 두 개를 종단한다
- C. 두 location에 각각 연결 하나씩을 둔다
- D. 두 개 이상의 location에서 각 location마다 서로 다른 디바이스로 종단하는 연결을 둔다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

Resiliency Toolkit의 Maximum resiliency 모델이 SLA 99.99퍼센트를 목표로 합니다. 두 개 이상의 location에서 각각 별도 디바이스에 종단하는 구성이라 디바이스 장애와 location 장애를 모두 흡수합니다.

- A가 틀린 이유: LAG는 같은 location의 링크 묶음이라 location 장애를 흡수하지 못한다.
- B가 틀린 이유: 이는 Development and test 모델에 해당하며 디바이스 장애만 막고 location 장애를 막지 못한다.
- C가 틀린 이유: 이는 High resiliency 모델로 SLA 목표가 99.9퍼센트다. 요구한 99.99퍼센트에 미치지 못한다.

</details>

**Q8.** 세 AZ에 워크로드가 분산된 VPC를 transit gateway에 attach했습니다. attachment 서브넷은 두 AZ에만 지정했고, VPC route table에는 온프레미스 CIDR이 TGW로 향하는 라우트가 들어 있습니다. 배포 후 attachment 서브넷을 지정하지 않은 AZ의 인스턴스만 온프레미스에 도달하지 못합니다. security group과 network ACL은 세 AZ가 동일하고 TGW route table에도 해당 CIDR이 있습니다. MOST likely 원인은 무엇입니까?

- A. TGW route table의 propagation이 그 AZ의 서브넷에만 적용되지 않았다
- B. attachment 서브넷이 없는 AZ의 리소스는 route table에 TGW 라우트가 있어도 transit gateway에 도달하지 못한다
- C. 세 번째 AZ의 서브넷이 TGW의 appliance mode 대상에서 빠져 있다
- D. VPC당 attach할 수 있는 transit gateway가 하나라서 세 번째 AZ가 다른 TGW를 쓰고 있다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

transit gateway VPC attachment는 AZ마다 정확히 서브넷 하나를 지정하고, 지정하면 그 AZ의 모든 서브넷으로 라우팅됩니다. 반대로 attachment가 없는 AZ의 리소스는 VPC route table에 TGW 라우트가 있어도 transit gateway에 도달하지 못합니다. 세 번째 AZ의 서브넷을 attachment에 추가하면 해결됩니다.

- A가 틀린 이유: TGW route propagation은 attachment 단위로 동작하고 AZ 단위로 나뉘지 않는다.
- C가 틀린 이유: appliance mode는 stateful appliance가 있는 attachment의 flow 대칭 옵션이고 AZ 도달성과 무관하다.
- D가 틀린 이유: VPC당 transit gateway는 5개까지 attach할 수 있고, 문제의 원인도 attachment 수가 아니라 AZ별 서브넷 지정이다.

</details>

**Q9.** 해외 지사가 기존 Site-to-Site VPN으로 본사 AWS 리전에 접속하는데 지연과 지터가 큽니다. 이 VPN은 virtual private gateway에 attach되어 있고 Direct Connect public VIF도 함께 사용 중입니다. 네트워크팀이 AWS Global Accelerator를 활용하는 accelerated Site-to-Site VPN으로 개선하려 합니다. 전환에 MOST appropriate 작업은 무엇입니까?

- A. transit gateway를 만들어 VPN을 attach하고 acceleration을 켠 VPN 연결을 새로 생성한 뒤, 함께 쓰던 Direct Connect public VIF 구성을 정리한다
- B. 기존 VPN 연결의 설정에서 acceleration 옵션을 활성화한다
- C. virtual private gateway를 유지한 채 acceleration을 켜고 customer gateway에서 IKE를 개시하도록 바꾼다
- D. Direct Connect public VIF 위에 accelerated VPN을 구성해 백본 구간을 최적화한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

accelerated VPN은 transit gateway에 attach된 VPN에서만 지원하고 virtual private gateway는 지원하지 않습니다. 기존 연결에서 옵션을 켜거나 끌 수 없어 새 연결을 만들어야 하고, Direct Connect public VIF와 함께 사용할 수 없습니다. 세 제약을 모두 반영한 전환 절차가 필요합니다.

- B가 틀린 이유: 기존 VPN 연결에서 acceleration을 켜거나 끌 수 없다. 새로 만들어야 한다.
- C가 틀린 이유: virtual private gateway attach VPN은 accelerated VPN을 지원하지 않는다. IKE 개시 주체 설정은 별개의 요구사항이다.
- D가 틀린 이유: accelerated VPN은 Direct Connect public VIF와 함께 사용할 수 없다.

</details>

**Q10.** 보안팀이 EC2 인스턴스가 어떤 도메인을 조회하는지, 그리고 인스턴스 메타데이터 호출 패턴이 어떤지 감사하려 합니다. 현재 VPC Flow Logs를 S3로 보내고 있지만 두 종류의 레코드가 전혀 보이지 않습니다. Flow Logs 설정 자체는 정상이고 같은 ENI의 다른 트래픽 레코드는 정상 수집되며, 인스턴스는 VPC의 Amazon DNS server를 그대로 사용합니다. MOST appropriate 조치는 무엇입니까?

- A. Flow Logs의 record format에 필드를 추가해 DNS와 metadata 트래픽을 포함시킨다
- B. Flow Logs 대상을 CloudWatch Logs로 바꾸고 Logs Insights로 조회한다
- C. DNS 감사는 Route 53 Resolver query logging으로 수집하고, metadata 호출은 Flow Logs로 볼 수 없으므로 인스턴스 내부 로깅 같은 별도 수단을 쓴다
- D. Reachability Analyzer로 인스턴스에서 메타데이터 서비스까지의 경로를 분석한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

VPC Flow Logs는 Amazon DNS server로 향하는 질의와 169.254.169.254 instance metadata 트래픽을 수집하지 않습니다. 169.254.169.123 Time Sync, DHCP, ARP도 같은 제외 목록에 있습니다. DNS 가시성은 Route 53 Resolver query logging이 담당하고, 메타데이터 호출은 Flow Logs 밖의 수단이 필요합니다.

- A가 틀린 이유: 제외 대상 트래픽은 필드 구성과 무관하게 수집되지 않는다. record format은 생성 후 변경할 수도 없어 삭제하고 다시 만들어야 한다.
- B가 틀린 이유: 대상 변경은 저장 위치만 바꾼다. 수집 제외 목록은 그대로다.
- D가 틀린 이유: Reachability Analyzer는 패킷을 보내지 않는 configuration analysis 도구라 실제 호출 이력을 남기지 않는다.

</details>

---

## 32. Reference

- [Amazon VPC - What is Amazon VPC?](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html)
- [Amazon VPC - VPC CIDR blocks](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-cidr-blocks.html)
- [Amazon VPC - Subnet CIDR blocks](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-sizing.html)
- [Amazon VPC - Amazon VPC quotas](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html)
- [Amazon VPC - NAT gateways](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html)
- [Amazon VPC - Egress-only internet gateways](https://docs.aws.amazon.com/vpc/latest/userguide/egress-only-internet-gateway.html)
- [Amazon VPC - VPC peering routing](https://docs.aws.amazon.com/vpc/latest/peering/vpc-peering-routing.html)
- [Amazon VPC - How AWS Transit Gateway works](https://docs.aws.amazon.com/vpc/latest/tgw/how-transit-gateways-work.html)
- [Amazon VPC - Transit gateway quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html)
- [Amazon VPC - Transit gateway network function attachments](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-nf-fw.html)
- [Amazon VPC - Gateway endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html)
- [Amazon VPC - Gateway endpoints for Amazon S3](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [Amazon VPC - Cross-region enabled AWS services](https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-cross-region-privatelink-support.html)
- [Amazon VPC - Configure an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/interface-endpoints.html)
- [Amazon VPC - PrivateLink quotas](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-limits-endpoints.html)
- [Amazon VPC - AWS PrivateLink concepts](https://docs.aws.amazon.com/vpc/latest/privatelink/concepts.html)
- [Amazon VPC - VPC Flow Logs limitations](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-limitations.html)
- [Amazon VPC - Reachability Analyzer](https://docs.aws.amazon.com/vpc/latest/reachability/what-is-reachability-analyzer.html)
- [Amazon VPC - How Network Access Analyzer works](https://docs.aws.amazon.com/vpc/latest/network-access-analyzer/how-network-access-analyzer-works.html)
- [Amazon VPC - Traffic mirror target concepts](https://docs.aws.amazon.com/vpc/latest/mirroring/traffic-mirroring-targets.html)
- [AWS Direct Connect - Dedicated connections](https://docs.aws.amazon.com/directconnect/latest/UserGuide/dedicated_connection.html)
- [AWS Direct Connect - Hosted connections](https://docs.aws.amazon.com/directconnect/latest/UserGuide/hosted_connection.html)
- [AWS Direct Connect - Virtual interfaces](https://docs.aws.amazon.com/directconnect/latest/UserGuide/WorkingWithVirtualInterfaces.html)
- [AWS Direct Connect - Direct Connect quotas](https://docs.aws.amazon.com/directconnect/latest/UserGuide/limits.html)
- [AWS Direct Connect - MACsec](https://docs.aws.amazon.com/directconnect/latest/UserGuide/MACsec.html)
- [AWS Direct Connect - Direct Connect Resiliency Toolkit](https://docs.aws.amazon.com/directconnect/latest/UserGuide/resiliency_toolkit.html)
- [AWS Site-to-Site VPN - VPN quotas](https://docs.aws.amazon.com/vpn/latest/s2svpn/vpn-limits.html)
- [AWS Site-to-Site VPN - Accelerated VPN](https://docs.aws.amazon.com/vpn/latest/s2svpn/accelerated-vpn.html)
- [AWS Client VPN - What is AWS Client VPN?](https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/what-is.html)
- [Amazon Route 53 - Forwarding DNS queries inbound](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-forwarding-inbound-queries.html)
- [Amazon Route 53 - Resolver query logging](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-query-logs.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
