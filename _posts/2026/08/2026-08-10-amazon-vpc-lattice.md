---
title: "Amazon VPC Lattice: Service-to-Service 통신을 단순화하는 Application Networking"
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

---

## 1. ALB, NLB, API Gateway와 무엇이 다른가

기존 AWS 로드밸런서와 API Gateway는 각각 외부 트래픽 진입이나 단일 VPC 내부 로드밸런싱에 최적화되어 있습니다. VPC Lattice는 service-to-service 통신, 즉 내부 서비스 간 연결에 초점을 맞춥니다.

| 구분 | VPC Lattice | ALB | NLB | API Gateway |
| :--- | :--- | :--- | :--- | :--- |
| 목적 | service-to-service connectivity | 외부 트래픽 로드밸런싱 | L4 로드밸런싱 | 외부 API 관리 |
| cross-VPC/cross-account | 자동 (RAM 공유) | 수동 (Peering/TGW) | 수동 | 제한적 |
| sidecar proxy | 불필요 | 해당 없음 | 해당 없음 | 해당 없음 |
| 프로토콜 | HTTP, HTTPS, gRPC, TCP | HTTP, HTTPS, gRPC | TCP, UDP, TLS | HTTP, HTTPS, WebSocket |
| overlapping CIDR | 자동 NAT 처리 | 미지원 | 미지원 | 해당 없음 |
| 관리 주체 | AWS (fully managed) | AWS | AWS | AWS |

VPC Lattice가 ALB나 API Gateway를 완전히 대체하는 것은 아닙니다. 외부 트래픽 진입점으로는 ALB, API Gateway, CloudFront가 여전히 필요하며, VPC Lattice는 그 뒷단의 서비스 간 통신을 담당합니다. ALB 자체를 VPC Lattice의 target으로 등록할 수도 있습니다.

---

## 2. 핵심 구성 요소

VPC Lattice를 이해하려면 다섯 가지 개념이 필요합니다.

**Service Network**는 서비스와 리소스 설정의 논리적 경계입니다. 같은 service network에 속한 클라이언트와 서비스는 권한이 있으면 서로 통신할 수 있습니다. VPC를 service network에 association하면 해당 VPC 내의 리소스가 service network의 서비스에 접근할 수 있습니다. 하나의 VPC는 하나의 service network에만 직접 association할 수 있으며, 추가 연결이 필요하면 VPC endpoint(type: service network)를 사용합니다.

**Service**는 독립적으로 배포 가능한 소프트웨어 단위입니다. EC2 인스턴스, ECS/EKS/Fargate 컨테이너, Lambda 함수에서 실행되며, listener, rule, target group으로 구성됩니다. 구조 자체는 ALB와 유사합니다.

**Target Group**은 서비스를 실행하는 대상의 모음입니다. EC2 인스턴스, IP 주소, Lambda 함수, ALB, ECS 태스크, Kubernetes Pod을 target으로 등록할 수 있습니다. ELB target group과 유사하지만 호환되지는 않습니다.

**Listener**는 연결 요청을 확인하고 target group으로 라우팅합니다. protocol(HTTP, HTTPS, TLS)과 port로 설정하며, listener 아래에 여러 rule을 둘 수 있습니다.

**Rule**은 listener의 기본 구성 요소로, priority, actions, conditions로 구성됩니다. 요청을 특정 target으로 전달하는 방법을 결정합니다.

---

## 3. cross-VPC, cross-account 연결

VPC Lattice의 핵심 가치는 cross-VPC, cross-account 연결을 자동화하는 데 있습니다. AWS RAM(Resource Access Manager)으로 service network를 계정 간에 공유하면, 공유받은 계정의 VPC를 해당 service network에 association할 수 있습니다. VPC Peering이나 Transit Gateway를 개별적으로 설정할 필요가 없습니다.

VPC 간 IP 대역이 겹치는 overlapping CIDR 문제도 VPC Lattice가 자동으로 처리합니다. IPv4, IPv6, overlapping IP 주소 사이의 NAT를 자동 관리하므로, 서로 다른 VPC에서 같은 IP 대역을 사용 중이어도 서비스 간 통신이 가능합니다.

cross-Region 연결은 제한적입니다. Service, resource, service network는 모두 Regional component이므로, 리전 간 통신이 필요한 경우 cross-Region VPC Peering, Transit Gateway, Direct Connect, Cloud WAN을 조합해야 합니다.

온프레미스 환경에서의 접근은 VPC endpoint(type: service network, AWS PrivateLink 기반)를 통해 Direct Connect나 VPN으로 연결할 수 있습니다.

---

## 4. 보안: 4계층 방어와 TLS

VPC Lattice의 보안 모델은 4개 계층으로 구성됩니다.

첫째, VPC와 service network의 association 자체가 첫 번째 접근 제어입니다. 둘째, VPC-service network association에 security group을 적용해 트래픽을 제어합니다. 셋째, service network 수준의 auth policy로 접근을 제한합니다. 넷째, 개별 service 수준의 auth policy로 세밀한 인가를 수행합니다.

Auth policy는 IAM 기반(`AWS_IAM` auth type)으로 동작합니다. 주의할 점은 auth policy가 IAM identity-based policy와 별개라는 것입니다. 인가가 성공하려면 identity-based policy와 auth policy 모두에 explicit allow가 있어야 합니다. Resource configuration에는 auth policy를 적용할 수 없습니다.

TLS는 세 가지 방식을 지원합니다. HTTPS listener에서 VPC Lattice가 관리하는 TLS 인증서를 자동 프로비저닝하는 방식, ACM 인증서로 custom domain에 BYOC(Bring Your Own Certificate)를 사용하는 방식, 그리고 2024년 5월에 추가된 TLS passthrough로 애플리케이션이 직접 TLS를 종료하는 방식입니다. native mTLS 종료는 공식적으로 제공하지 않으며, TLS passthrough를 통해 애플리케이션 단에서 end-to-end 인증을 수행하는 방식으로 mTLS 시나리오를 처리합니다.

---

## 5. 관측과 요금

모든 request/response에 대해 metrics와 logs가 생성됩니다. 로그는 CloudWatch Logs, Kinesis Firehose, Amazon S3로 전송할 수 있으며, service owner, resource owner, service network owner 각각이 로깅을 활성화할 수 있습니다. CloudTrail로 VPC Lattice API 호출을 추적할 수 있습니다.

요금은 세 가지 차원으로 부과됩니다. Service 시간당 요금, 처리한 데이터 GB당 요금, HTTP request 또는 TCP connection 건당 요금입니다. US East(N. Virginia) 기준 예시로 service 시간당 $0.025, 데이터 처리 GB당 $0.025, request 100만 건당 $0.10입니다. 리전별로 단가가 다르므로 정확한 금액은 AWS 요금 페이지에서 확인해야 합니다.

Always Free Tier가 있습니다. 서비스당 시간당 300,000건의 request/connection이 무료로 공제됩니다. VPC association과 Service Network Endpoint는 추가 비용 없이 사용할 수 있습니다. Inter-AZ 데이터 전송 요금도 별도로 부과되지 않으며, 모든 inter-AZ 데이터가 데이터 처리 요금에 포함됩니다.

---

## 6. EKS 통합: AWS Gateway API Controller

VPC Lattice는 Kubernetes Gateway API의 AWS 구현체인 AWS Gateway API Controller를 통해 EKS와 통합됩니다. Kubernetes 클러스터에 `HTTPRoute` 리소스를 생성하면 VPC Lattice service와 target group이 자동으로 프로비저닝됩니다. Sidecar 없이 EKS Pod을 VPC Lattice target으로 등록할 수 있으므로, 별도의 service mesh 데이터플레인 없이 service-to-service 연결을 구성할 수 있습니다.

ECS/Fargate 태스크와 Lambda 함수도 target type으로 지원됩니다. EC2 인스턴스, IP 주소(IPv4, IPv6), ALB도 target으로 등록할 수 있어 기존 인프라와 점진적으로 통합할 수 있습니다.

---

## 7. 언제 VPC Lattice를 써야 하는가

다음 상황에서 VPC Lattice가 효과를 발휘합니다. 여러 VPC나 AWS 계정에 마이크로서비스가 분산되어 있고, 서비스 간 연결을 관리하는 데 드는 운영 부담이 큰 경우. Sidecar proxy를 운영할 인프라 여력이 없거나 service mesh 데이터플레인 운영을 피하고 싶은 경우. Cross-account service sharing을 자동화하고 싶은 경우. Overlapping CIDR로 인해 VPC 간 직접 연결이 어려운 경우.

반대로 단일 VPC 내에서 단순 로드밸런싱만 필요하다면 ALB로 충분합니다. Cross-Region 글로벌 라우팅이 필요하다면 Route 53이나 Global Accelerator를 검토해야 합니다. App Mesh 수준의 fine-grained traffic control(circuit breaker, 카나리 배포 비율 조정 등)이 필요하다면 App Mesh나 VPC Lattice를 조합하는 것이 적합합니다.

---

## 8. Reference

- [Amazon VPC Lattice 공식 페이지](https://aws.amazon.com/vpc/lattice/)
- [Amazon VPC Lattice Features](https://aws.amazon.com/vpc/lattice/features/)
- [Amazon VPC Lattice Pricing](https://aws.amazon.com/vpc/lattice/pricing/)
- [Amazon VPC Lattice FAQ](https://aws.amazon.com/vpc-lattice/faqs/)
- [Amazon VPC Lattice User Guide](https://docs.aws.amazon.com/vpc-lattice/latest/ug/what-is-vpc-lattice.html)
- [VPC Lattice Auth Policies](https://docs.aws.amazon.com/vpc-lattice/latest/ug/auth-policies.html)
- [VPC Lattice Service Networks](https://docs.aws.amazon.com/vpc-lattice/latest/ug/service-networks.html)
- [VPC Lattice Quotas](https://docs.aws.amazon.com/vpc-lattice/latest/ug/quotas.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
