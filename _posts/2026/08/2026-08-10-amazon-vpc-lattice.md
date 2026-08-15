---
title: "Amazon VPC Lattice 알아보기 - Service Network와 서비스 간 통신"
date: 2026-08-10 20:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, vpc, lattice, networking, microservices, service-mesh, security]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

마이크로서비스가 여러 VPC와 AWS 계정에 흩어져 있으면 서비스 간 연결이 복잡해집니다. 팀 A의 서비스는 계정 X에, 팀 B의 서비스는 계정 Y에 배포되고, 두 서비스가 통신하려면 VPC Peering이나 Transit Gateway를 설정하고 보안 그룹을 조정하고 DNS를 구성해야 합니다. 서비스가 늘어날수록 이 연결망은 거미줄처럼 얽히고, 한쪽 IP 대역이 바뀌면 연쇄적으로 수정해야 합니다.

Amazon VPC Lattice는 이 문제를 application networking 계층에서 해결합니다. 서비스를 논리적으로 등록하고, 정책으로 접근을 제어하고, cross-VPC/cross-account 연결을 자동 관리하는 fully managed 서비스입니다. Sidecar proxy 없이 service mesh 수준의 기능을 제공하며, 2023년 3월 31일에 일반 available(GA)되었습니다. 서울(ap-northeast-2) 리전을 포함한 30개 리전에서 사용할 수 있습니다.

![VPC Lattice cross-VPC connectivity](/assets/img/aws/vpc-lattice-cross-vpc-flow.webp)
_세 개의 서로 다른 AWS 계정에 있는 VPC가 하나의 Service Network를 통해 연결됩니다. VPC Peering이나 Transit Gateway 없이 VPC Association만으로 cross-VPC 통신이 가능합니다._

---

## 1. 서비스 간 통신 복잡성: VPC Lattice가 해결하는 문제

마이크로서비스 아키텍처에서는 서비스가 여러 팀에 걸쳐 배포됩니다. 개발자가 애플리케이션을 빠르게 배포하려면 인프라와 네트워킹 설정을 매번 처리해야 하고, 관리자는 연결이 늘어날수록 일관된 보안 통제를 유지해야 합니다.

AWS는 VPC Lattice FAQ에서 이 문제를 다음과 같이 정의합니다: "bridge the gap between developers and cloud administrators by providing role-specific features and capabilities." 개발자는 네트워크가 아닌 애플리케이션에 집중해야 하고, 관리자는 혼합된 컴퓨팅 환경(instance, container, serverless)과 여러 VPC/계정에 걸쳐 인증, 인가, 암호화를 일관되게 적용해야 합니다.

VPC Lattice의 접근은 기존 인프라 패턴과 함께 동작하는 non-invasive 방식입니다. Sidecar proxy를 각 워크로드 옆에 배포하거나 frontend load balancer를 직접 관리할 필요가 없습니다. overlapping CIDR 문제, cross-account 권한 설정, DNS 해결을 VPC Lattice가 자동 처리합니다.

---

## 2. 핵심 구성 요소: Service Network, Service, Target Group

VPC Lattice는 5가지 핵심 객체로 구성됩니다.

**Service Network**는 서비스와 리소스의 논리적 경계입니다. 같은 service network에 속한 client와 service는 권한이 있으면 서로 통신할 수 있습니다. AWS RAM(Resource Access Manager)으로 다른 계정과 service network를 공유할 수 있습니다.

**Service**는 listener, rule, target group으로 구성됩니다. 구조가 ALB와 유사하지만, 서비스 자체가 DNS 이름을 가지며 cross-VPC 연결을 자동 처리합니다.

**Target Group**은 실제 컴퓨팅 리소스의 모음입니다. EC2 instances, IP addresses, Lambda functions, ALB, ECS tasks, Kubernetes Pods를 target으로 등록할 수 있습니다.

**Listener**는 클라이언트의 연결 요청을 확인하는 진입점입니다. HTTP, HTTPS, TLS 프로토콜과 port를 지정합니다.

**Rule**은 listener가 받은 요청을 target group으로 라우팅하는 방법을 정의합니다. path-based routing, weighted target으로 blue/green 및 canary 배포가 가능합니다.

---

## 3. 요청이 흐르는 경로: DNS에서 target까지

클라이언트가 VPC Lattice service에 요청을 보내는 과정은 다음과 같습니다.

클라이언트가 service의 FQDN(예: `service-a-xxx.vpc-lattice-aws.com`)으로 DNS 쿼리를 보내면, Route 53 Resolver가 VPC Lattice link-local endpoint IP를 반환합니다. 클라이언트의 요청이 VPC Lattice 데이터플레인에 도달하면, listener가 프로토콜과 port를 평가하고 rule이 요청을 target group으로 라우팅합니다.

Target group에서는 round robin 알고리즘으로 healthy target을 선택합니다. 이때 AZ 친화성 라우팅을 적용해 클라이언트와 같은 AZ의 target을 우선 선택합니다. 해당 AZ를 사용할 수 없으면 다른 AZ의 target으로 라우팅합니다. 모든 target이 health check에 실패하면, VPC Lattice는 fail-open으로 동작해 모든 target에 요청을 분산시킵니다.

---

## 4. Cross-VPC, Cross-Account: 연결 자동화가 VPC Lattice의 본질

VPC Lattice의 핵심 가치는 cross-VPC, cross-account 연결을 자동화하는 것입니다.

Service network를 생성하고 각 VPC를 association하면, VPC Peering이나 Transit Gateway 없이도 서로 다른 VPC의 서비스가 통신할 수 있습니다. Cross-account 시나리오에서는 AWS RAM으로 service network를 다른 계정에 공유한 뒤, 각 계정에서 자기 VPC를 해당 service network에 associate합니다.

Overlapping CIDR 문제도 VPC Lattice가 자동으로 처리합니다. VPC 간 IP 대역이 겹치더라도 network address translation을 통해 통신이 가능합니다.

하나의 VPC는 하나의 service network에만 직접 association할 수 있습니다. 여러 service network에 연결하려면 VPC endpoint(type: service network)를 사용합니다. 온프레미스 환경에서 접근하려면 VPC endpoint(AWS PrivateLink 기반)를 Direct Connect나 VPN과 조합해 사용합니다.

Cross-Region 연결은 지원하지 않습니다. Service, resource, service network는 모두 Regional component이므로, cross-Region 통신은 VPC Peering이나 Transit Gateway, Direct Connect, Cloud WAN을 조합해야 합니다.

---

## 5. 보안: 4계층 접근 제어와 TLS

VPC Lattice는 4계층 접근 제어 모델을 사용합니다.

첫째, VPC와 service network의 association 자체가 첫 번째 접근 제어입니다. 둘째, VPC-service network association에 security group을 적용해 트래픽을 제어합니다. 셋째, service network 수준에 auth policy를 부착해 coarse-grained 인가를 적용합니다. 넷째, 개별 service 수준에 auth policy를 부착해 fine-grained 인가를 적용합니다.

Auth policy는 IAM resource policy입니다. Identity-based policy(사용자/역할에 부착)와 별개로 동작하며, 인가가 성공하려면 양쪽 모두에 explicit allow가 있어야 합니다. Resource configuration에는 auth policy를 적용할 수 없습니다.

TLS는 세 가지 방식을 지원합니다. HTTPS listener에서 VPC Lattice가 관리하는 TLS 인증서를 자동 프로비저닝합니다. ACM 인증서로 custom domain name에 BYOC(Bring Your Own Certificate)를 사용할 수 있습니다. 2024년 5월에 추가된 TLS passthrough로 애플리케이션에서 end-to-end 인증을 수행할 수 있습니다. Native mTLS 종료는 공식적으로 제공하지 않으며, TLS passthrough를 통해 애플리케이션 단에서 mTLS 시나리오를 처리합니다.

---

## 6. ALB, NLB, API Gateway, App Mesh와의 비교

VPC Lattice는 기존 로드밸런서나 API Gateway를 대체하지 않습니다. 외부 트래픽의 진입점으로는 ALB, API Gateway, CloudFront가 여전히 필요하며, VPC Lattice는 그 뒷단의 service-to-service 통신을 담당합니다.

| 구분 | VPC Lattice | ALB | NLB | API Gateway | App Mesh |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 목적 | Service-to-service 연결 | 외부 트래픽 로드밸런싱 | L4 로드밸런싱 | API 관리 | Service mesh |
| 데이터플레인 | AWS 관리 전용 | AWS 관리 | AWS 관리 | AWS 관리 | Envoy sidecar |
| Cross-VPC/Account | 자동 (RAM + association) | 미지원 | 미지원 | 미지원 | 별도 구성 필요 |
| Sidecar | 불필요 | 불필요 | 불필요 | 불필요 | 필요 (Envoy) |
| TCP 리소스 (RDS 등) | Resource Configuration으로 등록 | 미지원 | 미지원 | 미지원 | 부적합 |
| mTLS | TLS passthrough로 간접 | 미지원 | 미지원 | 미지원 | Envoy 기반 native 지원 |
| Fine-grained 트래픽 제어 | Path/weighted routing | Path/host routing | 미지원 | API 단위 라우팅 | Circuit breaker, retry, timeout |

App Mesh와의 핵심 차이는 데이터플레인입니다. VPC Lattice는 AWS 관리 전용 데이터플레인을 사용해 sidecar가 필요 없지만, App Mesh는 각 컨테이너 옆에 Envoy proxy를 배포해야 합니다. App Mesh는 Envoy의 full 기능(circuit breaker, retry policy, fault injection)이 필요하고 Prometheus, Jaeger 같은 서드파티 관측성 도구를 이미 사용 중인 경우에 적합합니다. VPC Lattice는 sidecar 운영 부담 없이 cross-VPC/계정 연결을 자동화하고 IAM 기반 인증을 선호하는 경우에 적합합니다. 두 서비스는 배타적이지 않아서, VPC Lattice로 cross-VPC 연결을 관리하고 App Mesh로 단일 클러스터 내 정밀 제어를 수행하는 하이브리드 접근도 가능합니다.

---

## 7. 요금: 3가지 차원과 Always Free Tier

VPC Lattice 요금은 세 가지 차원으로 산정됩니다. US East(N. Virginia) 기준으로 service 시간당 $0.025, 데이터 처리 GB당 $0.025, HTTP request 또는 TCP connection 1M건당 $0.10입니다. 리전별로 단가가 상이하며, 정확한 단가는 AWS 요금 페이지에서 확인해야 합니다.

Always Free Tier로 서비스당 시간당 300,000 request/connection이 무료로 공제됩니다. VPC association과 Service Network Endpoints는 추가 비용 없이 사용할 수 있으며, inter-AZ 데이터 전송 요금도 별도로 부과되지 않습니다. 모든 inter-AZ 데이터는 데이터 처리 요금에 포함됩니다.

---

## 8. EKS 통합: AWS Gateway API Controller

VPC Lattice는 Kubernetes Gateway API의 AWS 구현체인 AWS Gateway API Controller를 통해 EKS와 자체 관리 Kubernetes 워크로드를 native로 통합합니다. HTTPRoute 리소스를 생성하면 VPC Lattice service와 target group이 자동으로 프로비저닝되며, sidecar 없이 EKS Pod을 target으로 등록할 수 있습니다.

Target group이 지원하는 target type은 EC2 instances, IP addresses, Lambda functions, ALB, ECS tasks, Kubernetes Pods 6가지입니다. 점진적 온보딩이 가능하므로 기존 인프라와 혼합해 도입할 수 있습니다.

---

## 9. 언제 VPC Lattice를 쓰고, 언제 다른 것을 쓸까

VPC Lattice가 적합한 경우는 multi-VPC 또는 multi-account 마이크로서비스 환경, sidecar proxy 운영 부담을 피하고 싶은 경우, cross-account service sharing이 필요한 경우, overlapping CIDR 문제가 있는 경우입니다.

부적합한 경우는 단일 VPC 내의 단순 로드밸런싱(ALB로 충분), cross-Region 글로벌 라우팅(Route 53, Global Accelerator 필요), Envoy 수준의 fine-grained traffic control(circuit breaker, retry, outlier detection)이 필요한 경우입니다.

re:Invent 2022와 GA 발표에서 공개된 고객 사례 중 Adways Inc.는 multi-account 환경에서 네트워크 추상화로 개발자가 인프라 걱정 없이 플랫폼 개발에 집중한 사례이고, seek.com.au는 여러 팀의 서비스를 중앙 analytics engine에 분 단위로 연결한 사례입니다. AltusGroup은 M&A로 인수한 여러 비즈니스의 애플리케이션과 데이터 소스를 cross-account로 안전하게 연결했고, Unique Vision Company는 overlapping CIDR 환경에서 Lambda 기반 신규 캠페인 기능을 기존 서비스와 통합했습니다.

---

## 10. Reference

- [Amazon VPC Lattice 공식 페이지](https://aws.amazon.com/vpc/lattice/)
- [Amazon VPC Lattice Features](https://aws.amazon.com/vpc/lattice/features/)
- [Amazon VPC Lattice Pricing](https://aws.amazon.com/vpc/lattice/pricing/)
- [Amazon VPC Lattice FAQ](https://aws.amazon.com/vpc/lattice/faqs/)
- [VPC Lattice User Guide - What is VPC Lattice](https://docs.aws.amazon.com/vpc-lattice/latest/ug/what-is-vpc-lattice.html)
- [VPC Lattice User Guide - How VPC Lattice Works](https://docs.aws.amazon.com/vpc-lattice/latest/ug/how-it-works.html)
- [VPC Lattice User Guide - Auth Policies](https://docs.aws.amazon.com/vpc-lattice/latest/ug/auth-policies.html)
- [VPC Lattice User Guide - Service Networks](https://docs.aws.amazon.com/vpc-lattice/latest/ug/service-networks.html)
- [VPC Lattice User Guide - Target Groups](https://docs.aws.amazon.com/vpc-lattice/latest/ug/target-groups.html)
- [VPC Lattice User Guide - Quotas](https://docs.aws.amazon.com/vpc-lattice/latest/ug/quotas.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
