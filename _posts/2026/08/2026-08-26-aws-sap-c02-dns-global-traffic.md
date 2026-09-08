---
title: "SAP-C02 박살내기 4 - DNS와 글로벌 트래픽"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, route53, dns, global-accelerator, cloudfront, failover, latency-routing]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-26 10:00:00 +0900
---

split-view DNS를 구성한 VPC 안에서 `www.example.com`을 조회했는데 private hosted zone에 넣어 둔 내부 IP 대신 온프레미스 DNS가 준 공인 IP가 돌아오는 상황이 있습니다. private hosted zone은 VPC에 정상적으로 연결되어 있고 레코드도 있습니다. 콘솔에서 zone을 열어 보면 아무 문제가 없습니다.

원인은 zone이 아니라 그 옆에 걸려 있던 Resolver forwarding rule입니다. 온프레미스가 권한을 갖는 `legacy.example.com` 하나를 넘기려고 만든 규칙의 도메인을 `example.com`으로 넓게 잡아 두면, 같은 이름을 다루는 private hosted zone과 Resolver rule 중에서 Resolver rule이 이깁니다. 하위 이름 질의가 통째로 온프레미스로 나가고 zone은 한 번도 조회되지 않습니다.

여기에 조금 더 나쁜 변형이 있습니다. 같은 구성에서 규칙을 지우고 zone만 남겼는데 레코드를 빠뜨리면, VPC Resolver는 public resolver로 넘기지 않고 NXDOMAIN을 반환합니다. 매칭되는 private hosted zone이 존재한다는 사실 자체가 public 경로를 끊습니다.

SAP-C02 Domain 1의 DNS 문항은 이 층에서 답이 갈립니다. 사용자의 요청이 어느 리전의 어느 오리진에 도달할지는 DNS 응답, 애니캐스트 IP, 엣지 캐시 세 계층 중 어디에서든 결정될 수 있고, 각 계층이 볼 수 있는 값과 통제하지 **못하는** 값이 따로 있습니다. 서비스 이름을 아는 것으로는 선지가 좁혀지지 않습니다.

> **TL;DR**  
> - alias는 zone apex에 만들 수 있고 AWS 리소스를 가리키면 TTL을 지정할 수 없다. EC2 instance는 alias 대상이 아니다.  
> - 라우팅 정책은 8종이고 private hosted zone에서 쓸 수 없는 것은 IP-based 하나다.  
> - 같은 이름과 타입 레코드 수는 대부분 100개인데 geoproximity만 30개다.  
> - health check는 전 세계 checker 중 18퍼센트 초과가 healthy로 보고할 때 healthy다. HTTPS health check는 인증서를 검증하지 않는다.  
> - health check를 붙이지 않은 레코드는 항상 healthy로 취급하고, 전부 unhealthy면 Route 53은 전부 healthy로 간주한다. failover에서는 primary를 반환한다.  
> - Route 53 health checker는 VPC 밖에 있다. 사설 IP만 있는 엔드포인트는 CloudWatch alarm data stream 기반 health check로 감시한다.  
> - 매칭되는 private hosted zone이 있으면 레코드가 없어도 NXDOMAIN이고 public으로 넘어가지 않는다.  
> - 같은 도메인에서 Resolver rule이 private hosted zone을 이긴다.  
> - inbound endpoint는 Direct Connect나 VPN이 필요하고, outbound endpoint는 NAT gateway도 경로가 된다.  
> - Global Accelerator는 기본 고정 anycast IP로 TCP와 UDP를 처리하며 캐시하지 않는다. CloudFront는 HTTP와 HTTPS를 캐시하고 기본 distribution 진입점은 공유 IP를 사용한다. allowlist에는 승인된 Anycast static IP list를 별도로 연결한다.  
> - traffic dial은 그 endpoint group으로 이미 향한 트래픽에만 적용되고, 이미 맺힌 연결은 TCP idle timeout 340초까지 endpoint를 바꾸지 않는다.  
> - CloudFront origin failover는 `GET`, `HEAD`, `OPTIONS`에만 동작하고 origin group은 origin 2개다.  
> - viewer 쪽 ACM 인증서는 us-east-1에서 발급하거나 import해야 한다.  
{: .prompt-info}

---

## 1. 이름 하나가 세 계층에서 각각 결정된다

글로벌 트래픽 설계 문항이 어려운 이유는 "어디로 보낼지"를 정하는 지점이 하나가 아니기 때문입니다. 클라이언트가 이름을 주소로 바꾸는 순간, 애니캐스트 IP가 가장 가까운 엣지를 고르는 순간, 엣지가 캐시를 줄지 오리진에 물어볼지 정하는 순간이 각각 다른 결정입니다.

{% include diagrams/static/sap-c02/dns-global-traffic-decision-layers.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/dns-global-traffic-decision-layers--a47e5a8e7b65f34e.png" %}

세 계층이 각각 무엇을 입력으로 보고 무엇을 바꿀 수 있는지, 그리고 어느 계층이 캐싱과 고정 IP를 담당하는지를 정리한 그림입니다.

| 계층 | 결정 주체 | 결정에 쓰는 입력 | 전환 지연을 만드는 요인 |
| :--- | :--- | :--- | :--- |
| DNS 응답 | Route 53 라우팅 정책과 health check | resolver의 위치, 측정된 지연, 레코드 가중치, health check 상태 | 레코드 TTL과 resolver 캐시 |
| 애니캐스트 IP | Global Accelerator | BGP 애니캐스트 경로, endpoint group health check, traffic dial | 기존 TCP 연결의 idle timeout |
| 엣지 캐시 | CloudFront | 캐시 키, TTL, origin group failover 조건 | 객체 TTL과 무효화 반영 |

이 표가 답을 가르는 방식은 단순합니다. 지문에 "DNS 캐시 때문에 전환이 늦다"가 있으면 첫 번째 계층 문제이고, "고정 IP를 방화벽에 등록해야 한다"가 있으면 기본 고정 IP를 주는 Global Accelerator와 승인된 Anycast static IP list를 연결할 수 있는 CloudFront를 함께 검토합니다. 이때 프로토콜과 L4 endpoint 라우팅 요구를 확인해야 하며, "오리진 부하를 줄여야 한다"가 있으면 세 번째 계층의 CloudFront 캐시를 봅니다. 두 서비스를 동시에 쓰는 경우에도 viewer 경로와 API 또는 비HTTP 경로 요구를 분리해 각 진입점을 정합니다.

---

## 2. alias가 CNAME으로 대체되지 않는 여섯 가지 지점

Route 53의 alias는 DNS 표준 레코드가 아니라 Route 53 확장입니다. 겉으로는 CNAME과 비슷해 보이지만 여섯 곳에서 동작이 다르고, 그 차이가 그대로 문항이 됩니다.

| 축 | alias | CNAME |
| :--- | :--- | :--- |
| zone apex | 만들 수 있다 | 만들 수 없다 |
| 대상 | 정해진 AWS 리소스와 같은 zone의 같은 타입 레코드만 | 임의의 DNS 이름 |
| TTL 지정 | AWS 리소스 대상이면 불가능하고 Route 53이 그 리소스의 기본 TTL을 쓴다 | 지정할 수 있다 |
| 과금 | AWS 리소스 대상 쿼리는 과금하지 않는다 | 과금한다. Route 53 안의 다른 레코드로 향하면 쿼리 2건이다 |
| 쿼리 타입 매칭 | 레코드 이름과 타입이 모두 일치할 때만 응답한다 | 쿼리 타입과 무관하게 리다이렉트한다 |
| dig 응답 | A나 AAAA 같은 지정 타입으로 보인다. alias 속성은 콘솔과 API에서만 보인다 | CNAME으로 보인다 |

alias 대상으로 지정할 수 있는 것은 API Gateway custom regional API와 edge-optimized API, VPC interface endpoint, CloudFront distribution, App Runner service, Elastic Beanstalk environment, ELB(ALB, CLB, NLB), Global Accelerator accelerator, OpenSearch Service custom domain, static website로 설정된 S3 bucket, 같은 hosted zone의 같은 타입 레코드, AppSync domain name입니다. **EC2 instance는 이 목록에 없습니다.** EC2 인스턴스를 이름으로 가리키려면 인스턴스의 public DNS 이름에 CNAME을 걸거나 앞에 로드 밸런서를 두어야 합니다.

apex에서 같은 zone 안의 CNAME 타입 레코드로 라우팅하는 조합만 예외로 성립하지 않습니다. 그 외에는 apex에 alias를 두는 것이 정답 경로입니다.

TTL 규칙이 DR 문항의 함정입니다. **AWS 리소스를 가리키는 alias 레코드에는 TTL을 지정할 수 없습니다.** "전환 전에 TTL을 60초로 낮춰 둔다"는 선지는 그 레코드가 non-alias일 때만 성립합니다. alias가 같은 hosted zone의 다른 레코드를 가리키는 경우에는 대상 레코드의 TTL을 씁니다.

---

## 3. 라우팅 정책 8종이 각각 보는 입력값

Route 53 라우팅 정책은 8종입니다. 각 정책이 무엇을 보고 답을 고르는지, 그리고 private hosted zone에서 쓸 수 있는지가 선지를 좁히는 두 축입니다.

| 정책 | 답을 고르는 기준 | private hosted zone | 대표 용도 |
| :--- | :--- | :--- | :--- |
| simple | 기준 없음. 레코드 하나를 그대로 반환한다 | 지원한다 | 단일 리소스 |
| weighted | 지정한 가중치 비율 | 지원한다 | 카나리 배포, 점진적 트래픽 이동 |
| latency | 측정된 네트워크 지연 | 지원한다 | 리전 간 성능 |
| failover | primary의 health check 상태 | 지원한다 | active-passive |
| geolocation | 쿼리 출발지의 대륙, 국가, 미국 주 | 지원한다 | 규제, 저작권, 언어별 콘텐츠 |
| geoproximity | 사용자와 리소스 사이 물리적 거리와 bias | 지원한다 | 리소스 위치 기반 분산 |
| multivalue answer | health check를 통과한 레코드 중 무작위 | 지원한다 | 여러 IP를 돌려주는 단순 분산 |
| IP-based | 쿼리 출발지 IP가 속한 CIDR block | **지원 문구가 없다** | ISP 단위 최적화 |

**IP-based routing만 private hosted zone 지원 목록에 들어 있지 않습니다.** "지사 IP 대역별로 다른 내부 서버를 주도록 private hosted zone에 IP-based 레코드를 만든다"는 선지가 여기서 탈락합니다.

active-active와 active-passive의 구성 방법도 정책과 묶여 있습니다. **active-active는 failover를 제외한 아무 라우팅 정책으로 만들고, active-passive는 failover 라우팅 정책으로 만듭니다.** 두 리전에 똑같이 트래픽을 흘리는 구성을 failover 정책으로 만들 수는 없습니다.

같은 이름과 타입을 갖는 레코드를 몇 개까지 둘 수 있는지도 쿼터로 걸립니다. geolocation, latency, multivalue answer, weighted, IP-based는 100개인데 **geoproximity만 30개**입니다. 리전 50개에 geoproximity 규칙을 붙이는 설계는 쿼터에서 막힙니다.

---

## 4. latency와 geolocation과 geoproximity가 서로 다른 답을 내는 이유

세 정책은 모두 "가까운 곳"을 고르는 것처럼 보이지만 보는 값이 전부 다릅니다.

| 축 | latency-based | geolocation | geoproximity |
| :--- | :--- | :--- | :--- |
| 판단 기준 | 측정된 네트워크 지연 | 쿼리 출발지의 행정 구역 | 사용자와 리소스 사이 물리적 거리 |
| 리소스 위치 지정 | AWS Region | 지정하지 않는다 | AWS Region, Local Zone Group, 또는 위도와 경도 |
| 트래픽 이동 손잡이 | 없다 | 없다. 매핑 자체를 바꿔야 한다 | bias로 조정한다 |
| 같은 이름과 타입 레코드 수 | 100 | 100 | 30 |
| 고르는 이유 | 성능 | 규제와 콘텐츠 요구 | 리소스 위치 기반 분산과 점진적 이동 |

지연은 거리와 비례하지 않습니다. 물리적으로 가까운 리전이 회선 사정 때문에 더 느릴 수 있고, latency 정책은 그 실측을 보므로 지리적으로 먼 리전을 고를 수 있습니다. 규제 요구는 반대입니다. "독일 사용자 데이터는 반드시 eu-central-1에서 처리한다"는 요구는 지연과 무관하므로 geolocation이 답이고 latency를 고르면 틀립니다.

geoproximity에는 다른 둘에 없는 조정 손잡이가 있습니다. **bias는 확장 방향으로 +1에서 +99, 축소 방향으로 -1에서 -99이고, 계산식은 `Biased distance = actual distance * [1 - (bias/100)]`입니다.** bias를 키우면 그 리소스가 담당하는 지리적 영역이 넓어집니다. 리전을 하나 늘리면서 트래픽을 조금씩 옮기는 요구에는 이 손잡이가 답이 됩니다.

geoproximity의 리소스 위치는 AWS Region, Local Zone Group, 또는 AWS 밖 리소스의 위도와 경도로 지정합니다. 지도 위에서 영역을 눈으로 보는 시각화는 Traffic Flow에서만 제공하지만, geoproximity 자체는 Traffic Flow 전용 기능이 아니고 일반 라우팅 정책으로 쓸 수 있습니다.

---

## 5. multivalue answer가 로드 밸런서를 대체하지 못하는 지점

multivalue answer는 여러 레코드를 한 응답에 담아 반환하는 정책입니다. 겉보기에 부하 분산처럼 보여서 오답 선지로 자주 등장합니다.

| 축 | multivalue answer | simple with multiple values | ELB |
| :--- | :--- | :--- | :--- |
| health check 연결 | 레코드별로 붙일 수 있다 | 붙일 수 없다 | 내장되어 있다 |
| unhealthy 제외 | 제외하고 반환한다 | 제외하지 않는다 | 제외한다 |
| 반환 개수 | healthy 레코드 최대 8개 | 지정한 값 전부 | 해당 없음 |
| 전부 unhealthy | unhealthy 레코드를 최대 8개 반환한다 | 해당 없음 | 5xx 또는 무응답 |
| 분산 정확도 | resolver 캐시에 좌우된다 | 없다 | 연결 단위 |

문서가 직접 "로드 밸런서를 대체하지 않는다"고 적습니다. 이유는 두 가지입니다. 반환 개수가 최대 8개로 잘리고, resolver가 응답을 캐시하는 동안 같은 답이 재사용되어 실제 분산이 균등해지지 않습니다.

**health check를 붙이지 않은 multivalue answer 레코드는 Route 53이 항상 healthy로 간주합니다.** 레코드 8개 중 3개에만 health check를 걸어 두면 나머지 5개는 죽어 있어도 계속 응답에 들어갑니다.

---

## 6. health check 3종과 18퍼센트 집계 규칙

Route 53 health check는 세 종류이고, 감시 대상에 도달하는 방식이 각각 다릅니다.

| 종류 | 감시 대상 | 쓰는 상황 |
| :--- | :--- | :--- |
| endpoint health check | 지정한 IP 또는 도메인 이름의 엔드포인트 | 공개 엔드포인트를 직접 검사한다 |
| calculated health check | 다른 health check들의 결과 | 여러 조건을 조합해 하나의 판정을 만든다 |
| CloudWatch alarm health check | CloudWatch alarm의 data stream | 직접 도달할 수 없는 대상을 metric으로 판정한다 |

endpoint health check의 동작 수치가 문항에 그대로 나옵니다.

- 요청 간격은 **10초 또는 30초** 둘 중 하나다.
- 전 세계 health checker 중 **18퍼센트를 초과**하는 비율이 healthy로 보고하면 healthy이고, 18퍼센트 이하면 unhealthy다.
- HTTP와 HTTPS health check는 **4초 안에 TCP 연결**이 되어야 하고 연결 후 **2초 안에 2xx나 3xx**를 받아야 한다. TCP health check는 10초 안에 연결되어야 한다.
- string matching health check는 응답 본문의 **첫 5,120바이트** 안에 지정 문자열이 전부 나타나야 한다.
- 데이터가 충분히 쌓이기 전의 새 health check는 healthy로 취급한다. invert 옵션을 켜 두었다면 unhealthy로 취급한다.

**HTTPS health check는 SSL/TLS 인증서를 검증하지 않습니다.** 만료되었거나 이름이 맞지 않는 인증서로도 health check는 통과합니다. "HTTPS health check가 통과했으니 인증서가 유효하다"는 판단은 성립하지 않고, 인증서 만료 감지에는 ACM 이벤트나 별도 모니터링이 필요합니다.

CloudWatch alarm 기반 health check에도 두 가지 제약이 붙습니다. 이 health check는 alarm의 상태가 아니라 **alarm이 보는 data stream**을 봅니다. 그래서 `SetAlarmState` API로 alarm 상태를 강제해도 health check 상태는 바뀌지 않습니다. 그리고 **cross-account CloudWatch alarm은 지원하지 않습니다.** 여러 계정의 상태를 중앙 계정에서 하나의 health check로 묶는 구성은 이 지점에서 막힙니다.

calculated health check 하나가 감시할 수 있는 child health check는 255개이고, health check는 계정당 active 200개까지입니다.

---

## 7. health check가 없는 레코드와 전부 unhealthy일 때의 동작

시험에서 가장 자주 틀리는 지점입니다. 상식과 반대되는 규칙이 세 개 있습니다.

**첫째, 같은 이름과 타입 그룹에서 어느 레코드도 healthy하지 않으면 Route 53은 전부 healthy로 간주하고 정책대로 하나를 고릅니다.** NXDOMAIN을 반환하거나 응답을 거부하지 않습니다. "모든 엔드포인트가 죽으면 DNS가 실패해 클라이언트가 즉시 다른 경로로 간다"는 설계는 성립하지 않습니다.

**둘째, failover 정책에서 primary와 secondary가 모두 unhealthy면 Route 53은 primary를 반환합니다.** 두 리전을 모두 내렸을 때 primary 주소가 돌아오는 관측이 여기서 나옵니다.

**셋째, health check를 붙이지 않은 레코드는 항상 healthy입니다.** secondary에 health check를 걸지 않으면 primary가 unhealthy인 동안 secondary가 5xx를 뿜고 있어도 계속 secondary가 반환됩니다.

weighted 정책에는 별도 규칙이 하나 더 있습니다. weight 0인 레코드와 nonzero 레코드가 섞여 있으면 Route 53은 nonzero 레코드만 먼저 고려하고, 그것들이 전부 unhealthy할 때만 weight 0 레코드를 고려합니다. weight 0은 완전한 배제가 아니라 최후 수단입니다.

alias 레코드에는 health check를 붙이는 대신 **`Evaluate Target Health`를 Yes로** 둡니다. AWS는 health check를 non-alias 레코드에만 붙이라고 권장합니다.

private hosted zone에서 health check를 연결할 수 있는 레코드는 failover, multivalue answer, weighted, latency, geolocation, geoproximity입니다.

---

## 8. VPC 밖에 있는 health checker가 사설 IP에 닿지 못한다

private hosted zone으로 내부 API를 노출하고 멀티 리전 failover를 구성하는 설계에서 반드시 걸리는 제약입니다.

{% include diagrams/static/sap-c02/route53-health-check-private-endpoint.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/route53-health-check-private-endpoint--0e699c2eaf7916f2.png" %}

health checker가 어느 경계 밖에 있는지, 직접 검사가 끊기는 지점이 어디인지, 그리고 CloudWatch metric과 alarm을 거치는 경로가 그 자리를 어떻게 대신하는지를 보여주는 그림입니다.

**Route 53 health checker는 VPC 밖에 있습니다.** 그래서 사설 IP로만 존재하는 인스턴스를 IP로 지정해 검사할 수 없고, security group을 아무리 열어도 결과가 달라지지 않습니다. 선택지는 두 가지입니다.

- 인스턴스에 public IP를 붙이고 그 주소를 health check 대상으로 지정한다.
- 애플리케이션 상태를 CloudWatch metric으로 내보내고, 그 metric에 alarm을 걸고, 그 alarm의 data stream을 보는 health check를 만들어 레코드에 연결한다.

보안 정책상 public IP를 붙일 수 없다는 조건이 지문에 있으면 두 번째가 유일한 답입니다. calculated health check로 묶는 선지는 child health check가 여전히 도달하지 못하므로 결과를 바꾸지 못합니다.

VPC 안에서 커스텀 DNS 서버를 운영하는 경우의 규칙도 함께 나옵니다. 커스텀 DNS 서버는 질의를 **VPC CIDR의 시작 주소에 2를 더한 주소**로 넘겨야 VPC Resolver가 받습니다. `10.0.0.0/16`이면 `10.0.0.2`입니다.

---

## 9. private hosted zone이 NXDOMAIN을 반환하는 조건

private hosted zone은 VPC 안에서만 보이는 이름 공간입니다. 사용 조건과 실패 방식이 문항 재료입니다.

사용 조건부터 봅니다. **VPC의 `enableDnsHostnames`와 `enableDnsSupport`가 둘 다 `true`여야 합니다.** 둘 중 하나라도 꺼져 있으면 private hosted zone이 동작하지 않습니다.

실패 방식이 split-view DNS 설계에서 사고를 만듭니다. **매칭되는 private hosted zone이 있는데 그 안에 해당 레코드가 없으면 VPC Resolver는 public resolver로 넘기지 않고 NXDOMAIN을 반환합니다.** `example.com` private hosted zone을 만들어 두고 `api.example.com`만 등록했다면, VPC 안에서 `www.example.com`을 조회할 때 인터넷의 공개 레코드로 넘어가지 않고 이름이 없다는 응답을 받습니다. public과 private에 같은 도메인을 두는 split-view 설계에서는 private 쪽에도 필요한 이름을 전부 넣어야 합니다.

서브도메인 위임도 가능합니다. private hosted zone 안에 NS 레코드를 만들어 하위 이름의 권한을 다른 서버로 넘길 수 있습니다.

쿼터도 설계를 바꿉니다. **private hosted zone 하나에 연결할 수 있는 VPC는 300개**이고, 그 이상이 필요하면 Route 53 Profiles를 쓰라고 문서가 안내합니다. 교차 계정 연결 authorization은 1,000개입니다. hosted zone 자체는 계정당 500개, 레코드는 hosted zone당 10,000개이며 10,000개를 넘기면 추가 과금이 붙습니다.

---

## 10. Resolver inbound와 outbound가 방향으로 갈린다

하이브리드 DNS 문항의 첫 관문은 방향을 맞추는 것입니다. 두 endpoint는 이름이 비슷하지만 서로를 대체하지 못합니다.

{% include diagrams/static/sap-c02/route53-hybrid-dns-endpoints.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/route53-hybrid-dns-endpoints--22b75362b17065aa.png" %}

질의가 어느 쪽에서 출발하는지에 따라 어떤 endpoint가 그 질의를 받는지, 각 방향에 필요한 연결 수단과 규칙이 무엇인지를 보여주는 그림입니다.

| 축 | inbound endpoint | outbound endpoint |
| :--- | :--- | :--- |
| 질의 방향 | 온프레미스에서 VPC로 | VPC에서 온프레미스로 |
| 해석 대상 | private hosted zone과 VPC 내부 이름 | 온프레미스가 권한을 갖는 도메인 |
| 필요한 연결 | Direct Connect 또는 VPN | Direct Connect, VPN, 또는 **NAT gateway** |
| 규칙 필요 여부 | 규칙 없이 endpoint IP를 온프레미스 DNS에 지정한다 | forwarding rule이 필요하고 VPC에 연결해야 동작한다 |
| 온프레미스 설정 | 조건부 포워딩 또는 위임 시 NS glue record | 없다 |
| RAM 공유 | endpoint 자체는 공유 대상이 아니다 | rule을 공유해 여러 계정에서 재사용한다 |

두 endpoint의 IP는 모두 VPC 내부 주소이고 public IP가 아닙니다. 그래서 온프레미스와의 경로가 반드시 있어야 합니다. **inbound는 Direct Connect나 VPN만 선택지인데, outbound는 NAT gateway도 경로가 됩니다.** 두 방향이 여기서 갈립니다.

forwarding rule의 target IP 처리 방식도 알아 둘 값입니다. VPC Resolver는 rule에 적힌 target IP 중 하나를 **무작위로** 고르고 우선순위를 두지 않습니다. 응답이 없으면 남은 target IP 중 다시 무작위로 골라 재시도합니다. "첫 번째 IP를 주 서버로 두고 두 번째를 백업으로 둔다"는 설계는 성립하지 않습니다.

endpoint 구성에도 최소 요건이 있습니다. API 문서는 IP 주소 배열의 최소 항목 수를 2로 규정하고, 최소가 1로 보이더라도 Route 53이 두 개 이상을 요구한다고 명시합니다. 고가용성을 위해 서로 다른 AZ의 서브넷을 쓰는 이유가 여기 있습니다.

용량 계산도 문항이 됩니다. endpoint IP 하나당 UDP DNS 쿼리 처리량은 **초당 10,000건**인데, **NLB를 거치거나 제한적인 security group 때문에 connection tracking이 강제되면 inbound endpoint의 IP당 최대 QPS가 1,500까지 떨어질 수 있습니다.** 문서는 네트워크 인터페이스 용량의 50퍼센트를 넘으면 인터페이스를 추가하라고 권합니다.

---

## 11. forwarding rule이 private hosted zone과 autodefined rule을 이기는 순서

같은 이름을 여러 곳에서 다룰 때 무엇이 이기는지가 도입부 사고의 원인입니다.

**private hosted zone과 Resolver rule이 같은 도메인 이름을 다루면 Resolver rule이 우선합니다.** 순서를 바꾸거나 zone 연결을 다시 만들어도 이 규칙은 변하지 않습니다. 해결책은 규칙의 도메인을 실제 위임 대상까지만 좁히는 것입니다. `example.com` 전체가 아니라 `legacy.example.com`으로 좁히면 나머지 이름은 private hosted zone이 답합니다.

Resolver rule 타입은 Forward, System, Recursive 세 가지입니다. 기본 "Internet Resolver" 규칙은 Recursive 타입이고 **삭제할 수 없습니다.**

여기에 자동 생성 규칙이 얹힙니다. **`enableDnsHostnames`를 켜면 VPC Resolver가 autodefined system rule을 자동으로 만듭니다.** 대상은 `{Region}.compute.internal`, `{Region}.compute.amazonaws.com`, us-east-1 전용 `ec2.internal`과 `compute-1.internal`과 `compute-1.amazonaws.com`, `10.in-addr.arpa`, `16.172.in-addr.arpa`부터 `31.172.in-addr.arpa`, `168.192.in-addr.arpa`, `localhost`, `localdomain`, `127.in-addr.arpa`, 그리고 VPC CIDR별 역방향 zone입니다.

이 규칙들 때문에 "`.` 하나에 forwarding rule을 걸어 모든 질의를 온프레미스로 넘긴다"는 구성이 기대대로 동작하지 않습니다. autodefined rule이 위 이름들을 로컬에서 처리하기 때문입니다. 다만 같은 도메인 이름으로 conditional forwarding rule을 만들면 autodefined rule을 override할 수 있으므로, `.`이나 `com`을 포워딩할 때는 `amazonaws.com`용 System rule을 함께 만들라고 문서가 권합니다. 그렇게 하면 AWS API 엔드포인트 조회가 온프레미스를 왕복하지 않아 성능이 좋아지고 Resolver 과금도 줄어듭니다.

TGW나 VPC peering으로 다른 VPC와 연결하고 DNS support를 켜면 상대 VPC의 IP 범위 역방향 zone이 자동으로 추가되고, 상대가 다른 리전이면 그 리전의 compute 도메인 규칙도 함께 추가됩니다.

---

## 12. Resolver rule을 RAM으로 공유할 때 쿼터가 어느 계정에 붙는가

멀티 계정 환경에서는 하이브리드 DNS 규칙을 계정마다 만들지 않고 한 계정에서 만들어 공유합니다. 이때 소유권과 쿼터 계산이 갈립니다.

- Resolver rule은 **AWS RAM**으로 공유한다.
- 공유받은 계정은 규칙을 **수정하거나 삭제할 수 없다.**
- rule 개수 쿼터는 **만든 계정**에 계산되고, rule과 VPC 연결 쿼터는 **공유받은 계정**에 계산된다.

조직 구조를 바꿀 때 나오는 함정이 하나 있습니다. 규칙이 OU 단위로 공유되어 있는 상태에서 계정이 다른 OU로 이동하면 그 계정 VPC의 rule 연결이 전부 삭제됩니다. 다만 이동한 대상 OU에도 같은 규칙이 이미 공유되어 있었다면 연결이 유지됩니다. 계정 이동 후 이름 해석이 갑자기 실패하는 시나리오의 원인이 여기입니다.

Resolver 쪽 쿼터는 다음과 같습니다. 계정당 리전별 endpoint 4개, endpoint당 IP 6개, rule당 target IP 6개, 리전당 rule 1,000개, rule과 VPC 연결 2,000개입니다. Resolver API 자체는 계정당 리전별 초당 5요청으로 throttling됩니다.

Resolver query log 쿼터는 리전당 configuration 20개, VPC 연결 100개입니다. **이 100개는 리전 전체에 걸린 상한이라 configuration을 더 만들어도 늘지 않습니다.** 대규모 조직에서 모든 VPC의 DNS 질의를 로깅하려는 설계가 여기서 막힙니다.

---

## 13. Route 53 Profiles는 VPC 하나에 하나만 붙는다

Profiles는 DNS 관련 설정을 묶어 여러 VPC와 계정에 한 번에 배포하는 상위 단위입니다. private hosted zone 하나에 VPC 300개라는 상한을 넘어야 할 때 문서가 안내하는 경로이기도 합니다.

Profile에 담을 수 있는 것은 다음과 같습니다.

- private hosted zone
- Resolver rule(forwarding과 system)
- DNS Firewall rule group
- interface VPC endpoint
- VPC Resolver query logging configuration

동작 제약이 두 가지입니다. **VPC 하나에는 Profile을 하나만 연결할 수 있습니다.** 그리고 평가 순서는 도메인 특정도가 같으면 VPC 로컬 설정이 우선하고, 특정도가 다르면 더 구체적인 쪽이 이깁니다.

Profile 쿼터는 계정당 리전별 Profile 5개, Profile당 VPC 1,000개, DNS Firewall rule group 5개, Resolver rule 1,000개, private hosted zone 5,000개, query logging configuration 2개입니다.

세 가지 배포 수단의 차이를 정리하면 다음과 같습니다.

| 축 | private hosted zone | Resolver forwarding rule | Route 53 Profile |
| :--- | :--- | :--- | :--- |
| 권한 소재 | Route 53이 권한 서버다 | 온프레미스 DNS가 권한 서버다 | 자체 해석을 하지 않는 배포 단위다 |
| 같은 도메인 충돌 | Resolver rule에 밀린다 | private hosted zone을 이긴다 | 특정도가 같으면 VPC 로컬 설정에 밀린다 |
| VPC 연결 상한 | zone당 300 | rule과 VPC 연결 리전당 2,000 | VPC당 Profile 1개, Profile당 VPC 1,000 |
| 멀티 계정 배포 | 계정 간 연결 authorization이 필요하다 | RAM으로 공유한다 | RAM으로 공유하고 여러 자원을 한 묶음으로 넘긴다 |

---

## 14. DNS Firewall의 action 3종과 평가 순서와 실패 모드

Resolver DNS Firewall은 VPC에서 나가는 DNS 질의를 도메인 목록 기준으로 통제합니다. 데이터 유출 경로로 DNS를 쓰는 공격을 막는 용도입니다.

rule action은 세 가지입니다.

| action | 동작 |
| :--- | :--- |
| Allow | 질의를 통과시킨다 |
| Alert | 통과시키되 로그를 남긴다 |
| Block | 차단하고 지정한 응답을 준다 |

Block 응답은 NODATA, NXDOMAIN, OVERRIDE 중에 고릅니다. **OVERRIDE의 record type은 CNAME이어야 하고 TTL 기본값은 0이라 캐시되지 않습니다.**

평가 순서는 **priority 숫자가 낮은 rule부터**입니다. 넓은 Block 규칙에 낮은 숫자를 주면 그보다 큰 숫자를 가진 예외 Allow 규칙이 도달하지 못합니다.

실패 모드의 기본값이 문항이 됩니다. **DNS Firewall이 응답하지 않을 때 VPC Resolver의 기본 동작은 fail closed이고, 질의를 차단하며 `SERVFAIL`을 반환합니다.** 가용성을 보안보다 앞에 두려면 fail open을 켜야 하고, API로는 `UpdateFirewallConfig`의 `FirewallFailOpen`을 바꿉니다. "DNS Firewall 장애 때문에 애플리케이션 이름 해석이 전부 실패했다"는 지문은 이 기본값에서 나옵니다.

DNS Firewall 쿼터는 VPC에 연결 가능한 rule group 5개, 리전당 rule group 1,000개, rule group당 rule 100개, domain list 1,000개, 전체 도메인 100,000개, S3 파일 하나당 도메인 250,000개입니다. rule group은 계정 간 공유가 되고 Firewall Manager 정책으로 조직 전체에 적용할 수 있습니다.

---

## 15. Global Accelerator가 고정 IP로 바꾸는 것

Global Accelerator는 DNS 이름 대신 애니캐스트 IP를 진입점으로 만듭니다. 진입점이 IP로 고정되면 DNS 캐시가 전환 지연을 만들지 않습니다.

- 기본 제공 static IP는 anycast IPv4 **2개**다. dual-stack이면 IPv4 2개와 IPv6 2개로 총 4개다. IPv6는 같은 `/64` prefix 2개에서 할당한다.
- static IP는 **network zone당 하나씩** 배정한다. 한쪽 network zone의 IP가 막혀도 다른 쪽으로 재시도할 수 있다.
- **accelerator를 삭제하면 static IP를 잃는다.** disable만 하면 유지된다.
- listener 프로토콜은 TCP, UDP, 또는 둘 다다.
- Route 53 alias 레코드로 accelerator를 직접 가리킬 수 있다.

accelerator 종류가 둘이고 지원 범위가 다릅니다.

| 축 | standard accelerator | custom routing accelerator |
| :--- | :--- | :--- |
| endpoint | NLB, ALB(internet-facing과 internal 모두), EC2 instance, Elastic IP | EC2 인스턴스가 들어 있는 VPC subnet |
| IP 버전 | IPv4와 dual-stack | **IPv4만** |
| health check | 있다 | **없다** |
| failover | 있다 | **없다** |
| client IP 보존 | 일부 endpoint 타입에서 선택 사항 | 항상 적용된다 |

**custom routing accelerator는 health check를 쓰지 않고 failover도 제공하지 않습니다.** 게임 세션처럼 특정 인스턴스와 포트로 결정론적으로 매핑해야 하는 워크로드용이고, 리전 장애 자동 전환을 요구하는 지문에 고르면 틀립니다.

endpoint group의 health check 설정은 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| interval | 10초 또는 30초, 기본 30초 |
| protocol | TCP, HTTP, HTTPS 중 선택, 기본 TCP |
| port | 기본값은 그 endpoint group이 붙은 listener의 포트다. 포트가 목록이면 첫 번째를 쓴다 |
| path | HTTP와 HTTPS일 때만 쓰고 기본값은 `/`다 |
| threshold count | 상태를 뒤집는 데 필요한 연속 검사 횟수, 기본 3, 범위 1에서 10 |

**healthy endpoint가 하나도 없으면 Global Accelerator는 모든 endpoint로 트래픽을 보냅니다.** Route 53이 전부 unhealthy일 때 전부 healthy로 간주하는 것과 같은 성격의 규칙입니다.

---

## 16. traffic dial과 endpoint weight와 idle timeout이 각각 다른 층에서 작동한다

Global Accelerator에서 트래픽을 옮기는 손잡이가 두 개이고, 옮겨도 즉시 반영되지 않는 이유가 하나 더 있습니다. 셋을 섞으면 문항이 됩니다.

**endpoint weight는 같은 endpoint group 안에서 endpoint 사이 비율을 정합니다.** 값은 0에서 255이고 **기본값이 128**입니다. 트래픽 비율은 각 weight를 그룹 weight 합으로 나눈 값이고, weight를 0으로 두면 그 endpoint로 보내지 않습니다.

**traffic dial은 endpoint group 단위 퍼센트이고, 이미 그 그룹으로 향한 트래픽에만 적용됩니다.** listener 전체 트래픽에 대한 비율이 아닙니다. 최적 경로 계산 결과 그 그룹으로 갈 요청이 100건일 때 dial을 50으로 두면 50건만 받고 나머지는 다른 리전 그룹으로 갑니다. "dial을 30으로 두면 전체의 30퍼센트가 그 리전으로 간다"는 해석은 틀립니다. 기본값은 100입니다.

세 번째가 연결 수명입니다. Global Accelerator는 edge에서 클라이언트 TCP 연결을 종료하고 거의 동시에 endpoint와 새 TCP 연결을 엽니다. 그리고 다음 규칙이 전환 속도를 결정합니다.

- idle timeout은 **TCP 340초, UDP 30초**이고 변경할 수 없다.
- TCP keep-alive 패킷만으로는 연결이 유지되지 않고 최소 1바이트의 데이터가 오가야 한다.
- **이미 맺힌 연결은 endpoint가 unhealthy로 표시되거나 제거되어도 idle timeout까지 그 endpoint로 계속 간다.** 새 연결 시점이나 idle timeout 이후에만 endpoint를 다시 고른다.

장애 훈련에서 endpoint를 제거했는데 기존 연결이 한동안 유지되는 관측은 health check 반영 속도가 아니라 이 규칙 때문입니다.

패킷 처리에도 알아 둘 차이가 있습니다. **UDP fragment는 endpoint로 전달하지만 TCP fragment는 edge에서 버립니다.** 그리고 Global Accelerator는 edge에서 ICMP echo에 직접 응답하므로 ping이 endpoint까지 가지 않습니다. ping 왕복 시간으로 백엔드 성능을 재면 안 되고, PMTUD가 동작하려면 endpoint의 security group이 ICMP를 허용해야 합니다.

security group과 AWS WAF 규칙은 accelerator를 앞에 붙여도 그대로 동작합니다.

---

## 17. Global Accelerator와 CloudFront가 갈리는 축

두 서비스는 모두 "AWS 엣지 네트워크를 써서 빠르게 한다"고 설명되지만, 하는 일이 다릅니다.

{% include diagrams/static/sap-c02/global-accelerator-cloudfront-paths.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/global-accelerator-cloudfront-paths--dc1f0d45cf887c0b.png" %}

같은 클라이언트 요청이 두 서비스에서 각각 어떤 단계를 거쳐 백엔드에 도달하는지, 어느 쪽에 캐시 판정 단계가 있고 어느 쪽에 고정 IP 진입점이 있는지를 나란히 놓은 그림입니다.

| 축 | Global Accelerator | CloudFront |
| :--- | :--- | :--- |
| 결정 계층 | 애니캐스트 IP, edge에서 TCP를 종료하고 AWS 백본으로 endpoint에 전달한다 | 엣지 캐시, 객체를 edge에 저장한다 |
| 진입점 | 고정 static IP 2개, dual-stack이면 4개 | 기본 distribution 도메인과 공유 IP. 승인된 Anycast static IP list를 연결하면 계정 전용 IP를 쓴다 |
| 프로토콜 | TCP, UDP | HTTP와 HTTPS |
| 캐싱 | 없다. 모든 요청이 endpoint로 간다 | 캐시 히트면 origin에 가지 않는다 |
| endpoint | NLB, ALB, EC2, EIP, custom routing은 VPC subnet | S3, ALB, EC2, Lambda function URL, 임의의 HTTP origin |
| 리전 장애 전환 | health check로 새 연결을 다른 리전 endpoint로 보낸다 | origin group 2개, `GET`과 `HEAD`와 `OPTIONS` 한정 |
| 고정 IP 요구 | 기본 static IP로 충족한다 | 기본 IP는 공유 목록이다. allowlist에는 승인된 Anycast static IP list가 필요하다 |
| idle timeout | TCP 340초, UDP 30초 고정 | 해당 없음 |

판단 기준은 세 문장으로 압축됩니다. 캐시 가능한 정적 또는 반정적 HTTP 콘텐츠면 CloudFront입니다. 비HTTP 프로토콜, L4 endpoint 라우팅, 또는 기본 설정에서 빠른 리전 failover와 고정 IP가 함께 필요하면 Global Accelerator입니다. CloudFront도 allowlist용 Anycast static IP list를 별도 승인받아 연결할 수 있으므로 고정 IP 하나만으로 서비스를 고르는 것은 부족합니다. 두 서비스의 기능을 함께 써야 하면 viewer 경로와 API 또는 비HTTP 경로를 분리하고 각 진입점에 맞는 서비스를 선택합니다.

여기서 나오는 오답이 두 가지입니다. "Global Accelerator를 붙이면 정적 콘텐츠가 엣지에 캐시되어 오리진 부하가 준다"는 서술은 Global Accelerator가 캐싱을 하지 않으므로 틀립니다. "CloudFront distribution의 기본 공유 IP를 방화벽 allowlist에 등록한다"는 서술은 계정 전용 고정 목록이 필요하다는 요구와 맞지 않습니다. CloudFront allowlist는 지원 승인된 Anycast static IP list를 연결하고 `PriceClass_All`을 선택해야 합니다.

---

## 18. CloudFront origin 보호는 OAC로 한다

S3 오리진을 CloudFront 뒤에 두면서 버킷 직접 접근을 막는 수단은 두 가지가 있었고, 현재 권장은 origin access control(OAC)입니다.

origin access identity(OAI)가 지원하지 않는 것이 네 가지입니다.

- 모든 리전의 S3 bucket. opt-in 리전과 **2023년 1월 이후 출시된 신규 리전**이 여기 해당한다.
- SSE-KMS로 암호화한 객체
- `PUT`, `POST`, `DELETE` 같은 동적 요청
- 위 요구가 있는 신규 설계 전반

OAC로 옮길 때 함께 맞춰야 하는 설정이 세 가지입니다.

- S3 bucket origin에 OAC를 쓰려면 S3 Object Ownership을 **`Bucket owner enforced`**로 둔다.
- SSE-KMS 객체를 서빙하려면 KMS key policy에 `cloudfront.amazonaws.com` 서비스 주체를 **`AWS:SourceArn` 조건과 함께** 추가한다.
- CloudFront와 S3 사이를 항상 HTTPS로 두려면 OAC의 `SigningBehavior`를 **`always`**로 둔다. `never`나 `no-override`면 viewer protocol policy와 origin protocol policy를 따른다.

**static website endpoint로 설정된 S3 bucket은 custom origin으로만 붙일 수 있고 OAC도 OAI도 쓸 수 없습니다.** 정적 웹사이트 호스팅을 켠 버킷을 CloudFront 뒤에 두고 직접 접근을 막으려는 요구는 이 지점에서 막히고, 버킷 정책과 커스텀 헤더 같은 다른 수단이 필요합니다.

viewer 인증과 오리진 보호는 층이 다릅니다.

| 축 | signed URL | signed cookie | OAC |
| :--- | :--- | :--- | :--- |
| 막는 대상 | 인가 없는 viewer의 개별 파일 접근 | 인가 없는 viewer의 다수 파일 접근 | CloudFront를 우회한 S3 직접 접근 |
| URL 변경 | 필요하다 | 필요 없다 | 무관하다 |
| 쿠키 미지원 클라이언트 | 쓸 수 있다 | 쓸 수 없다 | 무관하다 |
| 충돌 시 | signed cookie보다 우선한다 | signed URL에 밀린다 | 별개 계층이다 |

"OAC를 붙였으니 회원 인증까지 해결된다"는 서술은 두 층을 섞은 것입니다.

---

## 19. origin group failover가 GET과 HEAD와 OPTIONS에만 동작한다

CloudFront origin group은 오리진 두 개를 primary와 secondary로 묶어 오리진 장애 시 자동 전환합니다. 제약이 촘촘합니다.

{% include diagrams/static/sap-c02/cloudfront-origin-failover-path.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/cloudfront-origin-failover-path--48260729773245c3.png" %}

캐시 판정 이후 요청이 primary origin으로 가는 경로와 failover 조건을 만났을 때 secondary로 넘어가는 경로, 그리고 이 전환 경로를 타지 못하는 요청 종류를 보여주는 그림입니다.

- origin group은 primary와 secondary **origin 2개**로 구성한다. 세 번째 오리진을 넣을 수 없다.
- failover 트리거로 고를 수 있는 상태 코드는 **400, 403, 404, 416, 429, 500, 502, 503, 504**다.
- 연결 실패를 트리거하려면 **503**을, 타임아웃을 트리거하려면 **504**를 failover 상태 코드에 포함해야 한다.
- **origin failover는 viewer 요청이 `GET`, `HEAD`, `OPTIONS`일 때만 동작한다.** `POST`와 `PUT`은 failover하지 않는다. `OPTIONS`는 cache behavior의 cached HTTP methods에 포함되어 있어야 한다.
- CloudFront는 항상 primary로 먼저 보낸다. 직전 요청이 failover했더라도 다음 요청은 다시 primary로 간다.

전환에 걸리는 시간은 타임아웃 설정으로 정해집니다. origin 연결 타임아웃은 기본 10초이고 1초에서 10초로 지정하며, 연결 시도는 기본 3회이고 1회에서 3회로 지정하고, 응답 타임아웃은 기본 30초이며 1초에서 120초로 지정합니다. **기본 조합이면 오리진이 연결을 받지 못할 때 secondary로 넘어가기까지 최대 30초가 걸립니다.**

여기서 나오는 설계 결론이 두 가지입니다. 쓰기 API 가용성은 origin group으로 해결되지 않으므로 다른 이중화 수단이 필요합니다. 그리고 전환을 빠르게 하려면 연결 타임아웃과 시도 횟수를 낮추고 503과 504를 failover 상태 코드에 넣어야 합니다.

Lambda@Edge를 origin group과 함께 쓸 때 주의할 점도 있습니다. origin request 트리거가 primary와 secondary에 대해 **요청 하나에 두 번 실행될 수 있습니다.** 이 트리거에 부수 효과가 있는 로직을 넣으면 중복 실행됩니다.

---

## 20. 엣지 캐시의 TTL을 실제로 결정하는 값

캐시 동작 문항은 오리진이 보낸 헤더와 CloudFront 설정 중 무엇이 이기는지를 묻습니다.

- cache policy를 쓰지 않을 때 기본 TTL은 **24시간**이다.
- `Cache-Control: max-age`가 지원하는 값의 범위는 최소 0초에서 최대 100년이다.
- `max-age`와 `s-maxage`가 함께 오면 **CloudFront는 `s-maxage`를, 브라우저는 `max-age`를** 쓴다.
- `max-age`와 `Expires`가 함께 오면 CloudFront는 `max-age`만 쓴다.
- `stale-while-revalidate`와 `stale-if-error`는 지정값과 maximum TTL 중 **작은 쪽**까지만 적용된다.

가장 자주 틀리는 규칙은 minimum TTL입니다. **minimum TTL이 0보다 크면 CloudFront는 오리진이 보낸 `no-cache`, `no-store`, `private`를 무시하고 minimum TTL 동안 캐시합니다.** "오리진이 `no-store`를 보내니 캐시되지 않는다"는 판단은 minimum TTL 설정을 확인하기 전에는 성립하지 않습니다. 이 동작을 피하려면 오리진이 `Cache-Control: stale-if-error=0`을 함께 보내야 합니다.

price class는 캐시 성능과 비용을 함께 움직이는 설정입니다. 값은 `PriceClass_100`, `PriceClass_200`, `PriceClass_All` 중 하나이고, `PriceClass_All`이면 모든 CloudFront 엣지 로케이션에서 요청에 응답합니다. 그 외 값을 고르면 CloudFront는 **선택한 price class에 포함된 엣지 로케이션 중 지연이 가장 낮은 곳**에서 서빙하고, 제외된 지역에 있거나 가까이 있는 viewer는 더 느린 응답을 받습니다. 어느 지리 그룹이 어느 price class에 들어가는지는 CloudFront 요금 페이지가 정본입니다.

---

## 21. geo restriction과 signed URL과 signed cookie가 각각 막는 것

접근 제한 수단 세 가지는 적용 단위와 판단 근거가 전부 다릅니다.

**geo restriction은 distribution 전체에 국가 단위로만 적용됩니다.** 경로별로 다르게 적용할 수 없으므로, 일부 경로만 특정 국가에 막으려면 distribution을 분리하거나 서드파티 geolocation 서비스를 씁니다.

- 차단된 viewer에게는 **HTTP 403**을 반환한다.
- IP와 국가 매핑 정확도는 전체 기준 99.8퍼센트이고, **위치를 판정하지 못하면 콘텐츠를 그대로 서빙한다.**
- 오류 응답 캐시 기본값은 10초다.
- CloudFront managed certificate 검증 경로 `/.well-known/pki-validation/`은 geo restriction 대상에서 제외된다. WAF 규칙이 이 경로를 막으면 인증서 발급과 갱신이 실패한다.

signed URL과 signed cookie는 회원 여부를 판정하는 수단입니다. 개별 파일 단위 제한이 필요하거나 쿠키를 지원하지 않는 클라이언트가 있으면 signed URL을 쓰고, 다수 파일을 다루면서 URL을 바꾸고 싶지 않으면 signed cookie를 씁니다. **둘 다 적용되면 signed URL이 우선합니다.**

여기에 결정적인 제약이 하나 있습니다. **기존 URL의 query string에 `Expires`, `Policy`, `Signature`, `Key-Pair-Id`, `Hash-Algorithm` 중 하나라도 들어 있으면 signed URL도 signed cookie도 쓸 수 없습니다.** CloudFront가 그 URL을 이미 서명된 것으로 간주하고 쿠키를 보지 않기 때문입니다. 기존 배포에서 일부 자산 URL에 서명 파라미터가 남아 있는 상태로 signed cookie를 도입하면 그 자산들만 실패하고, 해결책은 해당 URL을 서명 파라미터 없는 형태로 재발급하는 것입니다.

---

## 22. CloudFront Functions와 Lambda@Edge의 경계

엣지에서 코드를 실행하는 수단이 둘이고 능력 차이가 뚜렷합니다.

| 축 | CloudFront Functions | Lambda@Edge |
| :--- | :--- | :--- |
| 런타임 | JavaScript ECMAScript 5.1 | Node.js, Python |
| 트리거 | viewer request, viewer response | viewer와 origin의 request와 response 4종 |
| 실행 시간 | submillisecond | 최대 30초 |
| 메모리 | 2 MB | viewer 트리거 128 MB, origin 트리거 10,240 MB |
| 코드 크기 | 코드와 라이브러리 합계 10 KB | 패키지 50 MB |
| network, file system, request body | 접근할 수 없다 | 접근할 수 있다 |
| geolocation과 device 데이터 | 접근할 수 있다 | **origin 트리거에서만** 접근할 수 있다 |
| KeyValueStore | 지원한다. JavaScript runtime 2.0이 필요하다 | 지원하지 않는다 |
| 처리량 | 초당 수백만 요청 | 리전당 초당 10,000 요청 |

배치가 뒤집히는 오답이 두 가지 나옵니다.

**"CloudFront Functions로 요청 본문을 검사한다"는 성립하지 않습니다.** request body에 접근할 수 없기 때문이고, 본문 검사나 외부 API 호출이 필요하면 Lambda@Edge나 WAF입니다.

**"Lambda@Edge viewer request 트리거에서 국가 코드로 리다이렉트한다"도 성립하지 않습니다.** Lambda@Edge의 geolocation과 device 데이터는 origin 트리거에서만 접근할 수 있습니다. viewer 단계에서 국가 코드를 보고 경로를 바꾸는 처리는 CloudFront Functions의 자리입니다.

처리량도 배치를 가릅니다. 모든 viewer request에 걸리는 초당 수십만 규모의 경량 처리는 CloudFront Functions이고, Lambda@Edge는 리전당 초당 10,000 요청 수준이라 그 자리에 맞지 않습니다.

---

## 23. viewer 인증서가 us-east-1이어야 하는 이유와 키 길이 상한

alternate domain name에 HTTPS를 붙이는 문항은 인증서의 리전과 키 길이에서 갈립니다.

- **viewer와 CloudFront 사이 HTTPS용 ACM 인증서는 us-east-1에서 발급하거나 import해야 한다.** 다른 리전 인증서는 alternate domain name에 붙일 수 없다.
- CloudFront와 오리진 사이에 ELB를 두는 경우 그 ELB의 인증서는 아무 리전이나 된다.
- CloudFront는 RSA **1024, 2048, 3072, 4096비트**를 지원한다. **ACM은 최대 2048비트까지 발급하므로 3072와 4096은 외부에서 받아 import해야 한다.**
- ECDSA는 prime256v1과 secp384r1을 지원한다.
- 인증서 갱신이나 재import는 현재 인증서 `NotAfter` **최소 24시간 전**에 해야 하고, 반영은 비동기라 최대 24시간이 걸린다.

"워크로드가 ap-northeast-2에 있으니 인증서도 ap-northeast-2에서 발급한다"는 선지는 여기서 탈락합니다. 그리고 "보안 강화를 위해 ACM에서 4096비트 인증서를 발급한다"는 선지는 ACM의 발급 상한 때문에 탈락합니다.

---

## 24. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**Route 53 레코드와 쿼터**

| 항목 | 값 |
| :--- | :--- |
| hosted zone | 계정당 500 |
| hosted zone당 레코드 | 10,000. 초과 시 추가 과금 |
| 같은 이름과 타입 레코드 수 | geolocation, latency, multivalue, weighted, IP-based는 100. geoproximity는 30 |
| private hosted zone당 VPC | 300. 초과 요구는 Profiles |
| 교차 계정 연결 authorization | 1,000 |
| health check | 계정당 active 200 |
| calculated health check의 child | 255 |
| health check 응답 헤더 총 길이 | 16,384바이트 |
| traffic policy | 계정당 50, 버전은 policy당 1,000, **traffic policy record는 계정당 5** |
| reusable delegation set | 계정당 100, 하나를 쓸 수 있는 hosted zone 100 |
| CIDR collection | 계정당 5, collection당 CIDR block 1,000 |
| `ChangeResourceRecordSets` 한 요청 | `ResourceRecord` 1,000개, `Value` 문자 합계 32,000자. `UPSERT`는 2회로 계산 |

**health check 동작**

| 항목 | 값 |
| :--- | :--- |
| 요청 간격 | 10초 또는 30초 |
| healthy 판정 임계 | health checker의 18퍼센트 초과 |
| HTTP와 HTTPS 타임아웃 | 연결 4초, 응답 2초, 2xx 또는 3xx |
| TCP 타임아웃 | 연결 10초 |
| string matching 검사 범위 | 응답 본문 첫 5,120바이트 |
| 인증서 검증 | 하지 않는다 |
| cross-account CloudWatch alarm | 지원하지 않는다 |
| 데이터 부족 시 | healthy. invert면 unhealthy |

**Route 53 Resolver와 Profiles와 DNS Firewall**

| 항목 | 값 |
| :--- | :--- |
| Resolver endpoint | 계정당 리전별 4 |
| endpoint의 IP 주소 | 최소 2, 쿼터 6 |
| rule당 target IP | 6 |
| Resolver rule | 리전당 1,000 |
| rule과 VPC 연결 | 2,000 |
| endpoint IP당 UDP 쿼리 | 초당 10,000. connection tracking이 걸리면 inbound는 1,500까지 하락 |
| Resolver API throttling | 계정당 리전별 초당 5요청 |
| query log configuration | 리전당 20, VPC 연결 리전 전체 100 |
| Profile | 계정당 리전별 5, VPC당 1개, Profile당 VPC 1,000 |
| Profile 수용량 | rule 1,000, private hosted zone 5,000, DNS Firewall rule group 5, query logging configuration 2 |
| DNS Firewall | VPC당 rule group 5, 리전당 rule group 1,000, rule group당 rule 100, domain list 1,000, 도메인 100,000, S3 파일당 250,000 |
| DNS Firewall 실패 모드 | 기본 fail closed, `SERVFAIL` 반환 |

**Global Accelerator**

| 항목 | 값 |
| :--- | :--- |
| static IP | anycast IPv4 2개, dual-stack이면 IPv4 2개와 IPv6 2개 |
| endpoint weight | 0에서 255, 기본 128 |
| traffic dial | 0에서 100, 기본 100. 그 그룹으로 향한 트래픽에만 적용 |
| health check interval | 10초 또는 30초, 기본 30초 |
| health check protocol | TCP, HTTP, HTTPS 중 선택, 기본 TCP |
| health check path | HTTP와 HTTPS일 때 기본 `/` |
| health check port | 기본은 listener 포트 |
| threshold count | 기본 3, 범위 1에서 10 |
| idle timeout | TCP 340초, UDP 30초, 변경 불가 |
| fragment 처리 | UDP는 전달, TCP는 edge에서 폐기 |
| healthy endpoint 없음 | 모든 endpoint로 전송 |

**CloudFront**

| 항목 | 값 |
| :--- | :--- |
| Anycast static IP | 지원 승인, allowlist use case 21개 또는 apex routing use case 3개. `PriceClass_All` 필요 |
| origin group | primary와 secondary 2개 |
| failover 상태 코드 | 400, 403, 404, 416, 429, 500, 502, 503, 504 |
| failover 대상 메서드 | `GET`, `HEAD`, `OPTIONS` |
| origin 연결 타임아웃 | 기본 10초, 1에서 10 |
| origin 연결 시도 | 기본 3회, 1에서 3 |
| origin 응답 타임아웃 | 기본 30초, 1에서 120 |
| 기본 TTL | cache policy 미사용 시 24시간 |
| `Cache-Control: max-age` 범위 | 0초에서 100년 |
| geo restriction 단위 | distribution 전체, 국가 단위, 차단 시 403 |
| geo 매핑 정확도 | 99.8퍼센트, 판정 실패 시 서빙 |
| viewer 인증서 리전 | us-east-1 |
| RSA 키 | CloudFront는 1024, 2048, 3072, 4096. ACM 발급은 2048까지 |
| 인증서 갱신 기한 | `NotAfter` 최소 24시간 전, 반영 최대 24시간 |
| CloudFront Functions | 실행 submillisecond, 메모리 2 MB, 코드 10 KB |
| Lambda@Edge | 최대 30초, viewer 128 MB, origin 10,240 MB, 패키지 50 MB, 리전당 초당 10,000 |

---

## 25. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| alias 대 CNAME | alias는 zone apex에 만들 수 있고 AWS 리소스 대상 쿼리가 무료이며 TTL을 지정할 수 없다. CNAME은 임의 이름을 가리키고 TTL을 지정하지만 apex에 둘 수 없다. EC2 instance는 alias 대상이 아니다 |
| latency 대 geolocation | latency는 실측 지연을 보고 geolocation은 쿼리 출발지의 행정 구역을 본다. 규제와 콘텐츠 요구는 geolocation이고 성능 요구는 latency다 |
| geolocation 대 geoproximity | geolocation은 행정 구역 매핑이고 손잡이가 없다. geoproximity는 물리적 거리와 bias이고 같은 이름과 타입 레코드가 30개로 제한된다 |
| weighted 대 geoproximity bias | weighted는 레코드 비율을 직접 정한다. bias는 리소스가 담당하는 지리적 영역을 넓히거나 좁힌다 |
| multivalue answer 대 ELB | multivalue는 최대 8개를 반환하고 resolver 캐시에 좌우된다. 문서가 로드 밸런서 대체가 아니라고 명시한다 |
| multivalue answer 대 simple 다중값 | multivalue는 레코드별 health check로 unhealthy를 제외한다. simple 다중값은 health check를 붙일 수 없다 |
| active-active 대 active-passive | active-active는 failover를 제외한 정책으로 만들고 active-passive는 failover 정책으로 만든다 |
| endpoint health check 대 CloudWatch alarm health check | 전자는 공개 엔드포인트에 직접 도달해야 한다. 후자는 alarm의 data stream을 보므로 사설 IP 대상에 쓴다. `SetAlarmState`로 강제할 수 없고 cross-account alarm을 지원하지 않는다 |
| health check 부착 대 미부착 | 붙이지 않은 레코드는 항상 healthy로 취급된다. failover secondary에 붙이지 않으면 죽은 secondary가 계속 반환된다 |
| public hosted zone 대 private hosted zone | private는 `enableDnsHostnames`와 `enableDnsSupport`가 둘 다 true여야 하고, 매칭되면 레코드가 없어도 NXDOMAIN을 반환하며 public으로 넘기지 않는다 |
| private hosted zone 대 Resolver rule | 같은 도메인이면 Resolver rule이 이긴다. zone은 Route 53이 권한 서버이고 rule은 온프레미스가 권한 서버다 |
| inbound endpoint 대 outbound endpoint | inbound는 온프레미스에서 VPC로 오는 질의를 받고 Direct Connect나 VPN이 필요하다. outbound는 VPC에서 나가는 질의를 넘기고 NAT gateway도 경로가 되며 forwarding rule이 필요하다 |
| Resolver rule 대 Route 53 Profile | rule은 이름 해석 규칙 하나를 공유한다. Profile은 zone과 rule과 firewall group과 로깅 설정을 묶어 배포하고 VPC 하나에 하나만 붙는다 |
| autodefined system rule 대 forwarding rule | autodefined는 `compute.internal`과 역방향 zone 등을 로컬에서 처리한다. 같은 이름의 forwarding rule을 만들면 override된다 |
| DNS Firewall fail open 대 fail closed | 기본은 fail closed이고 응답이 없으면 `SERVFAIL`로 차단한다. fail open은 가용성을 보안보다 앞에 둔다 |
| Global Accelerator 대 CloudFront | 전자는 기본 고정 anycast IP로 TCP와 UDP를 처리하고 캐시하지 않는다. 후자는 HTTP와 HTTPS를 캐시하고 기본 진입점은 공유 IP이며, allowlist에는 승인된 Anycast static IP list를 연결한다 |
| standard accelerator 대 custom routing accelerator | standard는 NLB, ALB, EC2, EIP를 endpoint로 받고 health check와 failover가 있다. custom routing은 VPC subnet을 받고 IPv4만 지원하며 health check와 failover가 없다 |
| endpoint weight 대 traffic dial | weight는 같은 endpoint group 안 endpoint 사이 비율이다. dial은 group 단위이고 그 group으로 향한 트래픽에만 적용된다 |
| OAC 대 OAI | OAI는 opt-in 리전, 2023년 1월 이후 신규 리전, SSE-KMS, 동적 요청을 지원하지 않는다. 현재 권장은 OAC다 |
| OAC 대 signed URL | OAC는 CloudFront를 우회한 S3 직접 접근을 막는다. signed URL은 viewer의 접근 권한을 판정한다 |
| signed URL 대 signed cookie | signed URL은 개별 파일과 쿠키 미지원 클라이언트에 쓴다. signed cookie는 다수 파일에 쓰고 URL을 바꾸지 않는다. 둘 다면 signed URL이 이긴다 |
| geo restriction 대 WAF geo match | geo restriction은 distribution 전체에 국가 단위로만 적용된다. 경로별 통제가 필요하면 distribution 분리나 다른 수단이 필요하다 |
| CloudFront Functions 대 Lambda@Edge | Functions는 viewer 트리거 전용이고 body와 network에 접근할 수 없지만 geolocation 데이터를 볼 수 있고 초당 수백만을 처리한다. Lambda@Edge는 4종 트리거와 body와 network를 쓰지만 geolocation은 origin 트리거에서만 볼 수 있다 |
| origin group failover 대 Route 53 failover | origin group은 `GET`과 `HEAD`와 `OPTIONS` 한정이고 CloudFront 안에서 즉시 전환한다. Route 53 failover는 DNS 응답 계층이라 TTL과 resolver 캐시에 좌우된다 |
| minimum TTL 대 오리진 `Cache-Control` | minimum TTL이 0보다 크면 `no-cache`와 `no-store`와 `private`를 무시한다. `stale-if-error=0`을 함께 보내야 회피된다 |
| viewer 인증서 대 오리진 측 인증서 | viewer 쪽은 us-east-1 ACM이어야 한다. CloudFront와 오리진 사이 ELB 인증서는 아무 리전이나 된다 |

---

## 26. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| apex 도메인 `example.com`을 ALB DNS 이름으로 CNAME 처리한다 | zone apex에는 CNAME을 만들 수 없다. alias A 레코드를 쓴다 |
| alias 레코드 TTL을 60초로 낮춰 DR 전환을 빠르게 한다 | AWS 리소스를 가리키는 alias에는 TTL을 지정할 수 없다. TTL 사전 인하는 non-alias 레코드에만 해당한다 |
| EC2 인스턴스를 alias 대상으로 지정한다 | EC2 instance는 alias 대상 목록에 없다. 로드 밸런서를 두거나 인스턴스 public DNS 이름에 CNAME을 건다 |
| private hosted zone에 IP-based routing 레코드를 만들어 지사 대역별로 다른 서버를 준다 | private hosted zone 지원 정책 목록에 IP-based가 없다 |
| geoproximity 규칙을 리전 50개에 붙인다 | 같은 이름과 타입의 geoproximity 레코드는 30개가 상한이다 |
| multivalue answer routing이 ALB를 대체해 부하를 균등 분산한다 | 최대 8개만 반환하고 resolver 캐시가 분산을 왜곡한다. 문서가 로드 밸런서 대체가 아니라고 명시한다 |
| multivalue 레코드에 health check를 걸지 않아도 죽은 대상은 빠진다 | health check가 없는 레코드는 항상 healthy로 취급된다 |
| 모든 엔드포인트가 unhealthy면 Route 53이 NXDOMAIN을 반환해 클라이언트가 즉시 실패한다 | 전부 unhealthy면 전부 healthy로 간주하고 하나를 반환한다. failover에서는 primary를 반환한다 |
| failover secondary에는 health check가 필요 없다 | 붙이지 않으면 secondary가 5xx를 뿜어도 계속 반환된다 |
| weight 0으로 두면 그 레코드는 절대 반환되지 않는다 | nonzero 레코드가 전부 unhealthy하면 weight 0 레코드가 고려된다 |
| HTTPS health check가 통과했으니 인증서가 유효하다 | Route 53 HTTPS health check는 인증서를 검증하지 않는다 |
| 다른 계정의 CloudWatch alarm으로 health check를 만들어 중앙에서 관리한다 | cross-account CloudWatch alarm은 지원하지 않는다 |
| `SetAlarmState`로 alarm을 강제해 health check failover를 훈련한다 | health check는 alarm 상태가 아니라 alarm의 data stream을 본다 |
| Route 53 health check로 사설 서브넷 EC2를 감시해 private hosted zone failover를 만든다 | health checker는 VPC 밖에 있어 사설 IP에 도달하지 못한다. public IP를 붙이거나 CloudWatch alarm 기반 health check를 쓴다 |
| 사설 IP health check 두 개를 calculated health check로 묶으면 판정이 안정된다 | child가 여전히 도달하지 못하므로 결과가 달라지지 않는다 |
| private hosted zone에 레코드가 없으면 public DNS로 넘어가 인터넷 응답을 받는다 | 매칭되는 private hosted zone이 있으면 NXDOMAIN을 반환하고 public으로 넘기지 않는다 |
| private hosted zone 연결을 다시 만들면 Resolver rule보다 우선하게 된다 | 우선순위는 설정 순서가 아니라 정책이다. 규칙 도메인을 좁혀야 한다 |
| 온프레미스가 VPC의 private hosted zone을 해석하도록 outbound endpoint를 만든다 | 방향이 반대다. 온프레미스에서 오는 질의는 inbound endpoint가 받는다 |
| outbound endpoint를 만들었으니 별도 경로 없이 온프레미스로 나간다 | endpoint IP는 public이 아니다. Direct Connect, VPN, NAT gateway 중 하나가 필요하다 |
| inbound endpoint를 NAT gateway로 노출한다 | inbound의 선택지는 Direct Connect와 VPN이다 |
| forwarding rule의 첫 번째 target IP가 주 서버로 쓰인다 | target IP는 무작위로 선택되고 우선순위가 없다 |
| `.` 포워딩 규칙 하나로 모든 질의를 온프레미스 DNS로 넘긴다 | autodefined system rule이 `compute.internal`과 `amazonaws.com` 계열과 역방향 zone을 로컬에서 처리한다. `amazonaws.com`용 System rule을 함께 만들라고 문서가 권한다 |
| 공유받은 Resolver rule을 사용 계정에서 수정한다 | 공유받은 계정은 규칙을 수정하거나 삭제할 수 없다 |
| VPC 하나에 Profile 두 개를 붙여 설정을 합친다 | VPC당 Profile은 하나다 |
| query logging configuration을 늘리면 VPC 연결 상한도 늘어난다 | VPC 연결 100개는 리전 전체에 걸린 상한이다 |
| DNS Firewall rule에 priority 큰 번호를 주면 먼저 평가된다 | priority 숫자가 낮은 것부터 평가한다 |
| DNS Firewall이 장애면 질의가 그대로 통과한다 | 기본값은 fail closed이고 `SERVFAIL`을 반환한다. 통과시키려면 fail open을 켜야 한다 |
| Global Accelerator를 붙이면 정적 콘텐츠가 엣지에 캐시되어 오리진 부하가 준다 | Global Accelerator는 캐싱하지 않는다 |
| CloudFront distribution의 기본 공유 IP를 방화벽 allowlist에 등록한다 | 기본 진입점은 계정 전용 목록이 아니다. CloudFront allowlist에는 승인된 Anycast static IP list를 연결하고 `PriceClass_All`을 선택한다 |
| custom routing accelerator로 리전 장애 자동 전환을 구성한다 | custom routing은 health check와 failover를 제공하지 않고 IPv4만 지원한다 |
| traffic dial을 30으로 두면 전체 트래픽의 30퍼센트만 그 리전으로 간다 | dial은 이미 그 endpoint group으로 향한 트래픽에만 적용된다 |
| endpoint를 제거하면 기존 세션이 즉시 다른 리전으로 넘어간다 | 이미 맺힌 연결은 idle timeout까지 유지된다. TCP는 340초다 |
| accelerator를 삭제했다가 다시 만들면 같은 static IP를 되찾는다 | 삭제하면 static IP를 잃는다. 유지하려면 disable만 한다 |
| ping 왕복 시간으로 accelerator 뒤 백엔드 성능을 측정한다 | Global Accelerator가 edge에서 ICMP echo에 직접 응답한다 |
| S3 static website endpoint origin에 OAC를 붙여 직접 접근을 막는다 | website endpoint는 custom origin이라 OAC도 OAI도 쓸 수 없다 |
| OAI로 SSE-KMS 암호화 객체를 서빙한다 | OAI는 SSE-KMS를 지원하지 않는다. OAC로 옮기고 KMS key policy에 CloudFront 서비스 주체를 넣는다 |
| OAC를 붙였으니 회원 인증까지 해결된다 | OAC는 오리진 우회를 막는 계층이고 viewer 인증과 무관하다 |
| origin group에 tertiary origin을 추가해 전환 경로를 늘린다 | origin group은 primary와 secondary 2개로만 구성한다 |
| origin group을 만들었으니 API `POST` 요청도 secondary로 failover된다 | failover는 `GET`, `HEAD`, `OPTIONS`에만 동작한다 |
| `POST`를 cached HTTP methods에 추가하면 failover 대상이 된다 | 그 설정은 `OPTIONS` 캐싱과 관련된 항목이고 `POST`를 failover 대상으로 만들지 못한다 |
| CloudFront가 오리진 연결에 실패하면 즉시 secondary로 넘어간다 | 기본값이면 10초 연결 시도 3회로 최대 30초가 걸리고, 503을 failover 상태 코드로 지정해 두어야 트리거된다 |
| 직전 요청이 failover했으니 다음 요청도 secondary로 간다 | CloudFront는 항상 primary로 먼저 보낸다 |
| 오리진이 `Cache-Control: no-store`를 보내니 CloudFront가 캐시하지 않는다 | minimum TTL이 0보다 크면 그 지시를 무시하고 minimum TTL 동안 캐시한다 |
| geo restriction으로 `/premium/*` 경로만 특정 국가에 막는다 | geo restriction은 distribution 전체에 국가 단위로만 적용된다 |
| geo restriction을 켜면 위치를 모르는 요청도 차단된다 | 위치를 판정하지 못하면 콘텐츠를 그대로 서빙한다 |
| 기존 서명 query string이 붙은 URL에 signed cookie를 얹어 접근을 통제한다 | `Expires`, `Policy`, `Signature`, `Key-Pair-Id`, `Hash-Algorithm` 중 하나라도 있으면 CloudFront가 signed URL로 판단하고 쿠키를 보지 않는다 |
| CloudFront Functions로 요청 본문을 검사해 봇을 차단한다 | Functions는 request body에 접근할 수 없다. Lambda@Edge나 WAF가 필요하다 |
| Lambda@Edge viewer request 트리거에서 국가 코드로 리다이렉트한다 | geolocation 데이터는 Lambda@Edge의 origin 트리거에서만 접근할 수 있다 |
| Lambda@Edge에서 KeyValueStore로 설정값을 조회한다 | KeyValueStore는 CloudFront Functions 전용이다 |
| ap-northeast-2의 ACM 인증서를 CloudFront alternate domain name에 붙인다 | viewer 쪽 인증서는 us-east-1이어야 한다 |
| ACM에서 4096비트 RSA 인증서를 발급해 CloudFront에 붙인다 | ACM은 최대 2048비트까지 발급한다. 그 이상은 외부 발급 후 import한다 |
| WAF로 모든 경로를 차단해도 CloudFront managed certificate는 갱신된다 | `/.well-known/pki-validation/` 경로를 막으면 발급과 갱신이 실패한다 |

---

## 27. 예상 문제 10문항

**Q1.** 두 리전에 배포한 내부 API가 private hosted zone의 이름으로 노출됩니다. 인스턴스에는 사설 IP만 있고 보안 정책상 public IP를 붙일 수 없습니다. 팀이 인스턴스 사설 IP를 대상으로 Route 53 health check를 만들어 failover 레코드를 구성했는데 health check가 계속 unhealthy로 표시됩니다. security group은 필요한 포트를 열어 두었습니다. MOST appropriate 구성은 무엇입니까?

- A. 인스턴스에 Elastic IP를 붙이고 health check 대상 IP를 그것으로 바꾼다
- B. 애플리케이션 상태를 CloudWatch metric으로 내보내고 그 metric에 건 alarm의 data stream 기반 health check를 failover 레코드에 연결한다
- C. 사설 IP health check 두 개를 calculated health check로 묶어 판정을 안정화한다
- D. health check 프로토콜을 HTTPS로 바꾸고 string matching을 활성화한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Route 53 health checker는 VPC 밖에 있어 사설 IP에 도달하지 못합니다. 공식 문서는 사설 IP만 있는 엔드포인트를 감시하려면 CloudWatch metric에 alarm을 걸고 그 alarm의 data stream을 보는 health check를 만들라고 안내합니다. 이 health check를 private hosted zone의 failover 레코드에 연결하면 요구를 만족합니다.

- A가 틀린 이유: public IP를 붙일 수 없다는 보안 정책과 정면으로 충돌한다.
- C가 틀린 이유: calculated health check는 child health check 결과를 조합할 뿐이다. child가 여전히 도달하지 못하므로 결과가 달라지지 않는다.
- D가 틀린 이유: 프로토콜 변경은 도달 자체를 해결하지 못한다. 게다가 HTTPS health check는 인증서를 검증하지 않아 기대와 다른 판정을 준다.

</details>

**Q2.** 멀티 리전 active-passive 구성에서 primary는 ap-northeast-2, secondary는 us-west-2이고 failover 라우팅 정책을 씁니다. 운영팀은 primary 레코드에만 health check를 붙였습니다. 훈련에서 primary를 내리자 트래픽이 secondary로 넘어갔는데, 그때 secondary는 배포 실수로 5xx를 반환하는 상태였음에도 Route 53이 계속 secondary를 반환했습니다. 이후 두 리전을 모두 내리자 primary가 반환되었습니다. MOST accurate 원인 설명은 무엇입니까?

- A. secondary에 health check가 없으면 항상 healthy로 간주되고, primary와 secondary가 모두 unhealthy이면 Route 53은 primary를 반환한다
- B. resolver가 이전 응답을 TTL 동안 캐시해 secondary 응답이 유지되었다
- C. alias 레코드의 Evaluate Target Health가 No로 설정되어 있었다
- D. health checker의 18퍼센트 임계 때문에 secondary가 healthy로 집계되었다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

health check를 붙이지 않은 레코드를 Route 53은 항상 healthy로 취급합니다. 그래서 primary가 unhealthy인 동안 secondary의 실제 상태와 무관하게 secondary가 반환됩니다. 그리고 failover에서 primary와 secondary가 모두 unhealthy이면 Route 53은 primary를 반환합니다. 관측된 두 동작이 모두 문서화된 규칙입니다.

- B가 틀린 이유: 캐시는 응답이 바뀌는 시점을 늦출 뿐이다. 두 리전이 모두 죽었을 때 primary로 돌아온 관측을 설명하지 못한다.
- C가 틀린 이유: Evaluate Target Health는 alias 레코드가 대상 리소스 상태를 반영하게 하는 옵션이다. secondary가 계속 반환된 이유는 health check 부재다.
- D가 틀린 이유: 18퍼센트 임계는 health checker 집계 규칙이다. 애초에 secondary에 health check가 없어 집계 자체가 일어나지 않았다.

</details>

**Q3.** 회사가 온프레미스 DNS와 AWS를 통합합니다. 온프레미스 서버가 VPC의 private hosted zone 이름을 해석해야 하고, VPC의 인스턴스는 온프레미스가 권한을 갖는 `corp.example.local` 도메인을 질의해야 합니다. VPC와 온프레미스는 Direct Connect로 연결되어 있고, 이름 데이터를 양쪽에 중복 관리하지 않는 것이 조건입니다. 필요한 구성 두 가지는 무엇입니까? (Select TWO.)

- A. Route 53 Resolver inbound endpoint를 만들고 온프레미스 DNS가 그 endpoint IP로 조건부 포워딩하게 한다
- B. private hosted zone의 레코드를 온프레미스 DNS로 zone transfer 한다
- C. Route 53 Resolver outbound endpoint를 만들고 `corp.example.local` 대상 forwarding rule을 VPC에 연결한다
- D. 온프레미스 zone을 Route 53 public hosted zone으로 복제하고 VPC에서 그것을 조회하게 한다
- E. `corp.example.local`용 private hosted zone을 만들고 온프레미스 레코드를 수동으로 등록한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, C**

온프레미스에서 VPC로 들어오는 질의는 inbound endpoint가 받고, 온프레미스 DNS는 그 endpoint의 VPC 내부 IP로 조건부 포워딩합니다. 반대 방향은 outbound endpoint와 forwarding rule이 담당하며 rule을 VPC에 연결해야 동작합니다. 두 endpoint 모두 public IP가 아니므로 Direct Connect 연결이 전제입니다.

- B가 틀린 이유: private hosted zone은 zone transfer를 제공하지 않고, 복제 자체가 이름 데이터 중복 관리 금지 조건에 어긋난다.
- D가 틀린 이유: 내부 도메인을 public hosted zone에 올리면 정보가 인터넷에 노출되고, 역시 중복 관리가 발생한다.
- E가 틀린 이유: 온프레미스가 권한을 갖는 도메인을 private hosted zone으로 다시 만들면 레코드를 양쪽에서 관리해야 한다. 게다가 매칭되는 private hosted zone이 있으면 레코드가 없을 때 NXDOMAIN이 반환되어 온프레미스로 넘어가지 않는다.

</details>

**Q4.** 회사는 `example.com`을 인터넷에 공개하면서 VPC 안에서는 같은 이름을 내부 IP로 해석하는 split-view DNS를 씁니다. 동시에 온프레미스 DNS가 권한을 갖는 `legacy.example.com`이 있어 Resolver forwarding rule을 `example.com`에 걸어 두었습니다. 배포 후 VPC 안에서 `www.example.com` 조회가 내부 IP 대신 온프레미스 응답을 받습니다. private hosted zone에는 정상적으로 레코드가 있습니다. MOST appropriate 조치는 무엇입니까?

- A. private hosted zone과 VPC 연결을 재생성해 우선순위를 회복한다
- B. VPC의 `enableDnsHostnames`를 끄고 커스텀 DNS 서버로 질의를 넘긴다
- C. private hosted zone에 `www.example.com` NS 레코드를 만들어 권한을 위임한다
- D. forwarding rule의 도메인을 `legacy.example.com`으로 좁힌다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

private hosted zone과 Resolver rule이 같은 도메인 이름을 다루면 Resolver rule이 우선합니다. `example.com` 전체에 forwarding rule을 걸면 하위 이름 질의가 통째로 온프레미스로 나갑니다. 규칙 도메인을 실제 위임 대상인 `legacy.example.com`으로 좁히면 나머지는 private hosted zone이 응답합니다.

- A가 틀린 이유: 연결을 다시 만들어도 Resolver rule 우선 규칙은 그대로다. 우선순위는 설정 순서가 아니라 정책이다.
- B가 틀린 이유: `enableDnsHostnames`를 끄면 private hosted zone 사용 조건 자체가 깨진다. 두 속성이 모두 true여야 한다.
- C가 틀린 이유: NS 레코드는 서브도메인 권한을 다른 서버로 위임하는 수단이다. 이미 온프레미스로 나가는 질의를 되돌리지 못한다.

</details>

**Q5.** 글로벌 게임 백엔드가 UDP 기반 프로토콜을 사용하고, 기업 고객은 방화벽 allowlist에 등록할 고정 IP를 요구합니다. 트래픽은 세 리전의 Network Load Balancer로 분산되고, 리전 장애가 발생하면 새 연결이 자동으로 다른 리전으로 가야 합니다. 클라이언트는 IPv4와 IPv6를 모두 사용합니다. MOST appropriate 구성은 무엇입니까?

- A. Route 53 latency 기반 라우팅으로 세 리전 NLB를 등록하고 각 NLB에 Elastic IP를 붙인다
- B. dual-stack standard accelerator를 만들고 UDP listener에 세 리전 NLB를 endpoint로 등록한다
- C. CloudFront distribution을 앞에 두고 origin group으로 리전 장애를 처리한다
- D. custom routing accelerator를 만들고 각 리전의 VPC subnet을 endpoint로 등록한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Global Accelerator standard accelerator는 anycast static IP를 제공하고 TCP와 UDP listener를 지원하며 NLB를 endpoint로 받습니다. dual-stack이면 IPv4 2개와 IPv6 2개를 제공하므로 allowlist 요구와 IPv6 요구를 함께 만족하고, health check로 새 연결을 healthy endpoint로 보냅니다.

- A가 틀린 이유: 고객이 등록할 IP가 리전 수만큼 늘어나고 리전을 추가할 때마다 allowlist를 갱신해야 한다. 전환도 DNS TTL에 좌우된다.
- C가 틀린 이유: CloudFront는 HTTP와 HTTPS를 처리하는 서비스라 UDP 프로토콜 요구를 만족하지 못한다. allowlist용 Anycast static IP list를 연결해도 UDP endpoint가 되지 않는다.
- D가 틀린 이유: custom routing accelerator는 IPv4만 지원하고 health check와 failover를 제공하지 않는다.

</details>

**Q6.** 운영팀이 AWS Global Accelerator로 트래픽을 세 리전에 분배합니다. 한 endpoint group의 traffic dial을 50으로 낮춰 전체 트래픽의 절반을 다른 리전으로 옮기려 했는데 실제 이동량이 기대와 달랐습니다. 또 장애 훈련에서 그 그룹의 endpoint를 제거했는데 기존 TCP 연결이 즉시 옮겨가지 않고 한동안 유지되었습니다. MOST accurate 설명은 무엇입니까?

- A. endpoint weight가 기본값 128이라 traffic dial보다 우선 적용되었다
- B. health check 간격이 길어 endpoint 제거가 반영되지 않았다
- C. traffic dial은 이미 그 endpoint group으로 향한 트래픽에만 적용되고, 이미 맺힌 연결은 TCP idle timeout 340초까지 기존 endpoint로 계속 간다
- D. 클라이언트 resolver가 accelerator 도메인을 캐시해 전환이 지연되었다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

traffic dial은 endpoint group 단위 퍼센트이고 listener 전체 트래픽이 아니라 그 그룹으로 이미 향한 트래픽에만 적용됩니다. 그리고 이미 맺힌 연결은 endpoint가 unhealthy로 표시되거나 제거되어도 idle timeout까지 그 endpoint로 계속 가며, TCP idle timeout은 340초 고정입니다.

- A가 틀린 이유: endpoint weight는 같은 endpoint group 안에서 endpoint 사이 비율을 정한다. group 단위 dial과 적용 층이 다르다.
- B가 틀린 이유: 기존 연결 유지는 health check 반영 속도가 아니라 idle timeout 규칙 때문이다.
- D가 틀린 이유: Global Accelerator는 anycast static IP로 진입하므로 DNS 캐시가 전환 지연의 원인이 아니다.

</details>

**Q7.** 이커머스가 CloudFront origin group으로 두 리전 ALB를 primary와 secondary로 묶었습니다. 장애 훈련에서 상품 조회 `GET` 요청은 secondary로 넘어갔지만 결제 `POST` 요청은 계속 실패했고, origin이 연결을 받지 못하는 상황에서 전환까지 약 30초가 걸렸습니다. origin group의 타임아웃과 failover 상태 코드는 기본값 그대로입니다. MOST appropriate 개선 방향은 무엇입니까?

- A. `POST`는 origin failover 대상이 아니므로 쓰기 경로는 다른 수단으로 이중화하고, origin 연결 타임아웃과 시도 횟수를 낮추고 503과 504를 failover 상태 코드에 포함한다
- B. `POST`를 cache behavior의 cached HTTP methods에 추가하면 failover 대상이 된다
- C. origin group에 tertiary origin을 추가해 전환 경로를 늘린다
- D. Lambda@Edge origin request 트리거에서 실패를 감지해 secondary origin으로 재요청한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

origin failover는 viewer 요청이 `GET`, `HEAD`, `OPTIONS`일 때만 동작하므로 결제 `POST` 경로는 origin group으로 해결되지 않습니다. 전환 지연은 기본값이 연결 타임아웃 10초에 시도 3회라 최대 30초가 걸리기 때문이고, 연결 실패를 트리거하려면 503을, 타임아웃을 트리거하려면 504를 failover 상태 코드로 지정해야 합니다.

- B가 틀린 이유: cached HTTP methods 설정은 `OPTIONS` 캐싱과 관련된 항목이고 `POST`를 failover 대상으로 만들지 못한다.
- C가 틀린 이유: origin group은 primary와 secondary 두 origin으로만 구성한다.
- D가 틀린 이유: origin group과 Lambda@Edge를 함께 쓰면 origin request 트리거가 요청 하나에 두 번 실행될 수 있고, `POST` failover 제약 자체를 바꾸지 못한다.

</details>

**Q8.** 미디어 회사가 S3에 SSE-KMS로 암호화한 자산을 두고 CloudFront로 서빙합니다. 현재는 origin access identity를 쓰고 있는데, 신규 리전에 만든 버킷 추가, 업로드용 `PUT` 요청 지원, 사용자 정의 도메인 HTTPS가 새 요구로 들어왔습니다. 인증서는 ACM에서 발급할 예정입니다. MOST appropriate 구성은 무엇입니까?

- A. origin access identity를 유지하고 버킷 정책에 신규 리전 버킷을 추가한다
- B. 버킷을 static website endpoint로 전환하고 origin access control을 적용한다
- C. origin access control로 전환하되 인증서는 워크로드 리전인 ap-northeast-2 ACM에서 발급한다
- D. origin access control로 전환하고 KMS key policy에 `cloudfront.amazonaws.com` 서비스 주체를 `AWS:SourceArn` 조건과 함께 추가하며, alternate domain name 인증서는 us-east-1 ACM에서 발급한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

origin access identity는 SSE-KMS, `PUT`과 `POST` 같은 동적 요청, 2023년 1월 이후 출시된 신규 리전을 지원하지 않습니다. 세 요구 모두 origin access control로 전환해야 풀립니다. SSE-KMS 객체를 OAC로 서빙하려면 KMS key policy에 CloudFront 서비스 주체를 `AWS:SourceArn` 조건과 함께 넣어야 하고, viewer와 CloudFront 사이 HTTPS용 ACM 인증서는 us-east-1에서 발급하거나 import해야 합니다.

- A가 틀린 이유: OAI는 SSE-KMS와 `PUT` 요청을 지원하지 않으므로 버킷 정책만 고쳐서는 요구를 만족하지 못한다.
- B가 틀린 이유: static website endpoint로 설정한 S3 버킷은 custom origin이라 OAC도 OAI도 쓸 수 없다.
- C가 틀린 이유: viewer 쪽 인증서는 us-east-1에서 발급하거나 import해야 한다. 다른 리전 인증서는 alternate domain name에 붙일 수 없다.

</details>

**Q9.** 엣지에서 두 가지 처리를 넣으려 합니다. 하나는 모든 viewer request에서 요청 국가 코드를 보고 경로를 재작성하는 처리로, 초당 수십만 요청을 감당하면서 지연을 최소화해야 합니다. 다른 하나는 origin request 단계에서 요청 본문을 검사하고 외부 API를 호출해 서명을 검증하는 처리입니다. MOST appropriate 조합은 무엇입니까?

- A. 두 처리 모두 Lambda@Edge로 구현한다
- B. 두 처리 모두 CloudFront Functions로 구현한다
- C. 국가 코드 기반 경로 재작성은 CloudFront Functions로, 본문 검사와 외부 API 호출은 Lambda@Edge origin request 트리거로 구현한다
- D. 국가 코드 기반 경로 재작성은 Lambda@Edge viewer request 트리거로, 본문 검사는 CloudFront Functions로 구현한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

CloudFront Functions는 viewer request와 viewer response 트리거에서 submillisecond로 실행되고 초당 수백만 요청을 처리하며 geolocation 데이터에 접근할 수 있습니다. 반면 request body와 network 접근이 필요한 처리는 Lambda@Edge의 몫이고, origin 트리거는 최대 10,240 MB 메모리와 30초 실행 시간을 씁니다.

- A가 틀린 이유: Lambda@Edge는 리전당 초당 10,000 요청 수준이라 초당 수십만 요청의 viewer request 처리에 맞지 않고 지연도 더 크다.
- B가 틀린 이유: CloudFront Functions는 request body와 network에 접근할 수 없어 서명 검증 API 호출을 할 수 없다.
- D가 틀린 이유: 두 배치가 모두 뒤집혔다. CloudFront Functions는 origin 트리거를 지원하지 않고, Lambda@Edge의 geolocation 데이터는 origin 트리거에서만 접근할 수 있다.

</details>

**Q10.** 구독 서비스가 회원에게만 동영상 세그먼트 수천 개를 제공하려 합니다. 플레이어는 자산 URL을 변경하지 않는 전제로 구현되어 있고 쿠키는 지원합니다. 기존 배포에서 일부 자산 URL에는 이미 `Expires`와 `Signature` query string이 붙어 있고, 운영팀은 세그먼트마다 서명을 발급하는 부담을 피하려 합니다. MOST appropriate 판단은 무엇입니까?

- A. signed cookie를 도입하고, 서명 query string이 붙어 있는 URL은 그 파라미터가 없는 형태로 재발급한다
- B. 세그먼트마다 signed URL을 발급하고 플레이어가 URL을 갱신하도록 수정한다
- C. geo restriction으로 회원이 거주하는 국가만 허용한다
- D. origin access control을 적용하면 회원 인증까지 함께 해결된다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

다수 파일을 다루면서 URL을 바꾸고 싶지 않을 때는 signed cookie를 씁니다. 다만 URL의 query string에 `Expires`, `Policy`, `Signature`, `Key-Pair-Id`, `Hash-Algorithm` 중 하나라도 있으면 CloudFront가 그 URL을 signed URL로 간주하고 쿠키를 보지 않으므로, 해당 URL을 서명 파라미터가 없는 형태로 재발급해야 합니다.

- B가 틀린 이유: 플레이어가 URL을 바꾸지 않는다는 전제와 충돌하고, 세그먼트 수천 개마다 서명하는 운영 부담을 피하려는 요구와도 어긋난다.
- C가 틀린 이유: geo restriction은 distribution 전체에 국가 단위로만 적용되어 회원과 비회원을 구분하지 못한다.
- D가 틀린 이유: origin access control은 CloudFront를 우회한 S3 직접 접근을 막는 계층이고 viewer 인증과 무관하다.

</details>

---

## 28. Reference

- [Amazon Route 53 - Choosing a routing policy](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy.html)
- [Amazon Route 53 - Multivalue answer routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-multivalue.html)
- [Amazon Route 53 - Geoproximity routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-geoproximity.html)
- [Amazon Route 53 - Choosing between alias and non-alias records](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-choosing-alias-non-alias.html)
- [Amazon Route 53 - Quotas](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/DNSLimitations.html)
- [Amazon Route 53 - How Route 53 determines whether a health check is healthy](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-determining-health-of-endpoints.html)
- [Amazon Route 53 - How health checks work in complex configurations](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-how-route-53-chooses-records.html)
- [Amazon Route 53 - Active-active and active-passive failover](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-types.html)
- [Amazon Route 53 - Configuring failover in a private hosted zone](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-private-hosted-zones.html)
- [Amazon Route 53 - Considerations when working with a private hosted zone](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zone-private-considerations.html)
- [Amazon Route 53 - Forwarding inbound DNS queries to your VPCs](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-forwarding-inbound-queries.html)
- [Amazon Route 53 - Forwarding outbound DNS queries to your network](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-forwarding-outbound-queries.html)
- [Amazon Route 53 - Managing forwarding rules](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-rules-managing.html)
- [Amazon Route 53 - Autodefined system rules](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-overview-forward-vpc-to-network-autodefined-rules.html)
- [Amazon Route 53 - Route 53 Profiles](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/profiles.html)
- [Amazon Route 53 - DNS Firewall rule actions](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall-rule-actions.html)
- [Amazon Route 53 - DNS Firewall rule settings](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall-rule-settings.html)
- [Amazon Route 53 - DNS Firewall rule groups](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall-rule-groups.html)
- [Amazon Route 53 - DNS Firewall VPC configuration](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-dns-firewall-vpc-configuration.html)
- [Amazon Route 53 API - CreateResolverEndpoint](https://docs.aws.amazon.com/Route53/latest/APIReference/API_route53resolver_CreateResolverEndpoint.html)
- [AWS Global Accelerator - Components of Global Accelerator](https://docs.aws.amazon.com/global-accelerator/latest/dg/introduction-components.html)
- [AWS Global Accelerator - How Global Accelerator works](https://docs.aws.amazon.com/global-accelerator/latest/dg/introduction-how-it-works.html)
- [AWS Global Accelerator - Endpoints in Global Accelerator](https://docs.aws.amazon.com/global-accelerator/latest/dg/about-endpoints.html)
- [AWS Global Accelerator - Endpoint weights](https://docs.aws.amazon.com/global-accelerator/latest/dg/about-endpoints-endpoint-weights.html)
- [AWS Global Accelerator API - EndpointGroup](https://docs.aws.amazon.com/global-accelerator/latest/api/API_EndpointGroup.html)
- [Amazon CloudFront - Restricting access to an Amazon S3 origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [Amazon CloudFront - Request Anycast static IPs for allowlisting](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/request-static-ips.html)
- [Amazon CloudFront - Optimizing high availability with origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)
- [Amazon CloudFront - Customize at the edge with functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/edge-functions.html)
- [Amazon CloudFront - Choosing between CloudFront Functions and Lambda@Edge](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/edge-functions-choosing.html)
- [Amazon CloudFront - Requirements for using alternate domain names](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html)
- [Amazon CloudFront - Restricting the geographic distribution of your content](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/georestrictions.html)
- [Amazon CloudFront - Managing how long content stays in the cache](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html)
- [Amazon CloudFront - Choosing between signed URLs and signed cookies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-choosing-signed-urls-cookies.html)
- [Amazon CloudFront API - DistributionConfig](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_DistributionConfig.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
