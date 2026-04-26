---
# the default layout is 'page'
icon: fas fa-info-circle
order: 4
---

<style>
  .cv-hero {
    display: grid;
    grid-template-columns: minmax(150px, 210px) 1fr;
    gap: 1.25rem;
    align-items: center;
    margin-bottom: 2rem;
  }

  .cv-hero img {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    border-radius: 8px;
    border: 1px solid var(--main-border-color, #d8dee4);
  }

  .cv-hero h1 {
    margin: 0;
    font-size: 2rem;
    line-height: 1.15;
  }

  .cv-role {
    margin: 0.35rem 0 0.9rem;
    color: var(--text-muted-color, #6a737d);
    font-size: 1.05rem;
  }

  .cv-contact {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.75rem;
  }

  .cv-contact a,
  .cv-contact span {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--main-border-color, #d8dee4);
    border-radius: 6px;
    padding: 0.22rem 0.55rem;
    font-size: 0.9rem;
    line-height: 1.35;
    text-decoration: none;
  }

  .cv-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.75rem;
    margin: 1rem 0 1.6rem;
  }

  .cv-summary-card {
    border: 1px solid var(--main-border-color, #d8dee4);
    border-radius: 8px;
    padding: 0.9rem;
  }

  .cv-summary-card strong {
    display: block;
    margin-bottom: 0.3rem;
  }

  .cv-muted {
    color: var(--text-muted-color, #6a737d);
  }

  @media (max-width: 720px) {
    .cv-hero {
      grid-template-columns: 1fr;
    }

    .cv-hero img {
      max-width: 280px;
    }
  }
</style>

<section class="cv-hero">
  <img src="/assets/img/kkam-img/kcd_2025.jpg" alt="Taeji Kim profile photo">
  <div>
    <h1>Taeji Kim</h1>
    <p class="cv-role">SRE / DevSecOps Engineer</p>
    <p>
      AWS, Kubernetes, IaC, CI/CD, Observability, Security 영역을 함께 다루며
      운영 가능한 플랫폼과 반복 가능한 인프라를 만드는 데 집중합니다.
      장애 대응과 RCA, 자동화, 비용 최적화, 인증/인가 체계 개선 경험을 기반으로
      서비스 신뢰성과 운영 효율을 높이는 일을 지향합니다.
    </p>
    <div class="cv-contact">
      <a href="mailto:xowl5460@naver.com">xowl5460@naver.com</a>
      <a href="https://kkamji.net">Blog</a>
      <a href="https://github.com/KKamJi98">GitHub</a>
      <a href="https://linkedin.com/in/taejikim">LinkedIn</a>
      <span>Target: SRE / DevSecOps Engineer</span>
    </div>
  </div>
</section>

## Profile

Cloud Native 환경에서 운영, 배포, 보안, 관측 가능성을 연결해 서비스 신뢰성을 개선하는 엔지니어입니다. 현재는 Samsung Galaxy Chatting Plus (RCS) 서비스 운영과 AWS / EKS 기반 인프라 운영을 담당하며, Terraform IaC, GitHub Actions, Argo CD, Keycloak, Grafana, Prometheus, Thanos, InfluxDB 등 운영 도구의 구축과 개선을 함께 수행하고 있습니다.

<div class="cv-summary-grid">
  <div class="cv-summary-card">
    <strong>Platform Operations</strong>
    <span class="cv-muted">AWS Infra, EKS, Terraform IaC, Cluster Upgrade, Open-source Upgrade</span>
  </div>
  <div class="cv-summary-card">
    <strong>Reliability</strong>
    <span class="cv-muted">Incident Response, RCA Guide, Observability, Log Centralization</span>
  </div>
  <div class="cv-summary-card">
    <strong>Security & Automation</strong>
    <span class="cv-muted">Keycloak SSO, RBAC, Secrets, CI/CD, Cost Optimization</span>
  </div>
</div>

## Skill Set

| Area | Stack |
| :--- | :--- |
| **Cloud / Infra** | AWS, EC2, EKS, ECS, ECR, RDS, VPC, Route 53, CloudFront, CloudWatch, Lambda, API Gateway, WAF |
| **Kubernetes / Platform** | Kubernetes, EKS, Helm, Karpenter, HPA, IRSA, Cilium, Hubble, Gateway API, Envoy |
| **IaC / CI/CD** | Terraform, HCP Terraform, Jenkins, GitHub Actions, Argo CD |
| **Observability / Data** | Prometheus, Grafana, Thanos, ELK, CloudWatch Logs, InfluxDB, Apache Superset |
| **Security / Identity** | Keycloak, SSO, RBAC, AWS IAM, Secrets Manager, Parameter Store, External Secrets |
| **Programming / App** | Python, Go, Java, Spring Boot, Streamlit, React |
| **OS / Runtime** | Ubuntu, Amazon Linux, CentOS, Docker |

## Careers

### Warepoint / Technical Architect

`2024.12 ~ 현재`

- Samsung Galaxy Chatting Plus (RCS) 서비스 운영
- AWS Infra 구축 및 운영, Terraform 기반 IaC 적용
- EKS Cluster 운영 및 업그레이드
- 서비스 장애 대응 및 근본 원인 분석(RCA) 가이드 작성
- GitHub Actions Matrix Strategy 도입으로 Multi-Architecture Container Image Build 시간 50% 이상 단축
- Apache Superset 구축, PoC, 운영
- Keycloak SSO + RBAC 적용: Grafana, Argo CD, Apache Superset
- InfluxDB(TSDB) 마이그레이션: Amazon Linux 2 -> Ubuntu, EoS 대응
- Open-source Software 버전 업그레이드: Grafana, Prometheus, Thanos, External Secrets

## Open-source Contributions

| Project | Contribution |
| :--- | :--- |
| [Amazon Observability Helm Charts PR #190](https://github.com/aws-observability/helm-charts/pull/190) | 불필요한 리소스 생성을 제어할 수 있도록 `dcgmExporter.enabled`, `neuronMonitor.enabled` Flag 추가 |
| [Strands Agents SDK PR #1906](https://github.com/strands-agents/sdk-python/pull/1906) | README 내 깨진 Documentation Link 19개 수정, [v1.35.0 Release](https://github.com/strands-agents/sdk-python/discussions/2095)의 New Contributors 항목에 포함 |

## Projects

### Home Sweet Home

`2025.04 ~ 2025.04`

청년 주택청약 알리미 Web App, Students @ AI - Seoul Hackathon / Infra, Frontend, Backend

- Streamlit 기반 사용자 Frontend UI 개발
- Bedrock Knowledge Base 기반 특정 청약 정보의 대화형 조회 구현
- 로그 모니터링 기반 트러블슈팅
- Students @ AI - Seoul Hackathon Winner

### Remember Me / [GitHub](https://github.com/vocaAppServerless)

`2024.11 ~ 2024.12`

서버리스(AWS Lambda) 기반 영단어 암기 Web App / Infra, DevOps Lead

- Terraform(HCP Terraform) 기반 Cloud Infra IaC
- Lambda CI/CD Pipeline 구축
- CloudWatch Logs Subscription Filters + ELK Stack 기반 Lambda Logs 중앙화
- AWS Budgets, WAF Rule Event Slack Alarm 연동
- Secrets Manager, Parameter Store 기반 시크릿 및 환경변수 관리

### Weasel / [GitHub](https://github.com/Team-S5T1)

`2024.07 ~ 2024.08`

EKS / Bedrock 기반 문제 풀이 Web App / Project, Infra Lead

- Team Lead 및 Cloud Infra 설계, 구축, 운영
- Terraform(HCP Terraform) 기반 Cloud Infra IaC
- Jenkins / Argo CD 기반 Spring Boot Application CI/CD Pipeline 구축
- EKS Autoscaling: Karpenter, HPA 적용
- IRSA 기반 Pod 단위 IAM 권한 제어
- Spot Instance, NAT Instance, VPC CNI maxPods 튜닝을 통한 비용 최적화
- Prometheus, Grafana 기반 EKS 모니터링 구성

| Area | Stack |
| :--- | :--- |
| Develop | Spring Boot, React |
| Deploy | EKS, S3, Route 53, CloudFront |
| Database | RDS(MySQL) |
| IaC / CI/CD | Terraform, Jenkins, Argo CD |
| Monitoring / AI | Prometheus, Grafana, Bedrock (Claude Sonnet 3.5) |

### Amazon Photo Query / [Backend](https://github.com/KKamJi98/Photo-Query) / [EKS Manifests](https://github.com/KKamJi98/aws-app-eks-manifests)

`2024.01 ~ 2024.03`

AI 기반 사진 앨범 서비스 / Cloud Architecture, Infra, Backend

- AWS 클라우드 상에서 MSA, 3-Tier Architecture 기반 구축 및 배포
- Cloud Architecture 설계, AWS 인프라 구축 및 운영
- CI/CD Pipeline 구축, ERD 구축 및 운영
- EKS 모니터링 및 비용 추적
- 이미지 CRUD, 북마크, 태그 기능 개발 및 배포
- S3, DynamoDB Public Access 차단 이후 Access Deny 문제를 IRSA 적용으로 해결
- 이미지 리사이징 Lambda 분리, Global Accelerator 도입, Goroutine 병렬 처리로 이미지 업로드 API 응답 시간을 5분 이상에서 1분 미만으로 단축

| Area | Stack |
| :--- | :--- |
| Programming | Go, Python, Node.js, Flutter |
| CI/CD | Jenkins, Argo CD, CodeSeries |
| Container | Docker, EKS, ECR |
| Database | RDS(MySQL), DynamoDB, DocumentDB |
| Monitoring | Prometheus, Grafana, Container Insights, Kubecost |
| AWS / ETC | S3, Cognito, Rekognition, Secrets Manager, Terraform, SNS, SQS, Karpenter, Fluent Bit |

## Personal Projects

수동/반복 작업의 편의성을 높이기 위해 CLI Tool과 Web App을 직접 개발하고 운영하고 있습니다.

| Project | Description |
| :--- | :--- |
| [ssh-connector](https://github.com/KKamJi98/ssh-connector) | SSH Config 파일의 설정을 기반으로 동작하는 서버 접근 관리 Tool |
| [aws-pick](https://github.com/KKamJi98/aws-pick) | AWS CLI 사용에 적용되는 Default Profile 전환 Tool |
| [kubernetes-monitoring-python](https://github.com/KKamJi98/kubernetes-monitoring-python) | Kubernetes Cluster Monitoring CLI Tool |
| [listup-aws-resources](https://github.com/KKamJi98/listup-aws-resources) | AWS 리소스를 수집 및 정리해 Excel / JSON으로 내보내는 Tool |
| [log-filter](https://github.com/KKamJi98/log-filter) | 정규식 패턴으로 기존 로그를 제외하고 신규 패턴 로그만 추출하는 Tool |
| [image-converter](https://github.com/KKamJi98/image-converter) | 이미지 확장자 변환, 리사이즈, 압축을 제공하는 Web App |

## Certifications

| Date | Certification |
| :--- | :--- |
| 2025.07 | HashiCorp Certified: Terraform Associate (003) |
| 2024.12 | AWS Certified DevOps Engineer - Professional |
| 2024.07 | CKA: Certified Kubernetes Administrator |
| 2024.02 | AWS Certified Solutions Architect - Associate |
| 2023.09 | 정보처리기사 |
| 2023.05 | AWS Certified Cloud Practitioner |

## Education

### 중원대학교 / 컴퓨터공학과 학사

`2018.02 ~ 2023.08`

- Sorting Algorithm 성능 측정 및 비교분석, 지도교수: 백승훈
- J-Smart, 교수역량진단시스템 사업 참여, 학생대표
- 데이터베이스 강의 보조 활동
- GPA: 4.40 / 4.5, 수석 졸업

## Training & Study

### Cilium 공식 문서 핸즈온 스터디 1기 / CloudNet@

`2025.07 ~ 2025.08`

Cloud Native 네트워킹 심화 스터디

- eBPF, Cilium 기반 Kubernetes DataPath 이해 및 L3 / L4 / L7 Network Policy 설계
- Routing Mode: Encapsulation(VXLAN / GENEVE) vs Native Routing 구조 및 Trade-off 비교
- Cluster Mesh: Multi-Cluster Service Discovery, 통신, Identity 이해
- Service Mesh 연계: Ingress / Gateway API + Envoy 기반 TLS, L7 Traffic 처리
- Hubble 활용: Flow, Service Map, DNS / HTTP 가시성 기반 Policy Miss 및 차단 Traffic Troubleshooting

### AWS Cloud School 1기 / 한국전파진흥협회

`2023.08 ~ 2024.03`

Cloud & DevOps 교육과정

- Network, Linux, Docker, Kubernetes, Jenkins, Argo CD, AWS 학습
- 교육과정 내 공지 게시판 개발
- AI & Cloud 기반 앨범 서비스 Photo Query 팀 프로젝트 참여: Kubernetes 운영, Go Backend 개발

### Rising Camp Plus 백엔드과정 1기 / 소프트스퀘어드

`2023.07 ~ 2023.09`

Java Backend 교육과정

- Java, Spring Boot, JPA, MySQL, Git 학습
- Spring Boot 기반 채용사이트 개발 팀 프로젝트 참여

## Awards

- Fastfive x AWS Frugality Fest GameDay - Winner (2025.04)
- Students @ AI - Seoul Hackathon - Winner (2025.04)
- AWS PS GameDay(GenAI) - 5th Place (2024.08)
- AWS x RAPA DevOps Jam - Runner-up, 2nd Place (2023.12)

## Activities

- Cloud Native Korea Community Day 2025 - Speaker, ArgoCD와 함께하는 Multi-Cluster 운영 (2025.09)
- Dive 2025 Global Data Hackathon, 부산항만공사 (2025.08)
- AWS Cloud School 8기 - Amazon Working Backwards, Mentor / Staff (2025.06)
- 2025 경기창고 개회식, Staff (2025.05)
- 2024 충남대학교 커스텀 GPT 프롬프톤, Staff (2024.08)
- 부산일과학고 AWS Cloud 실습 및 활용, Mentor / Staff (2024.07)
- 서울디지텍고등학교 - Amazon Working Backwards, Mentor / Staff (2024.08)
- AWS PS GameDay(GenAI) 참가 (2024.07)
- 제2회 AWS 강의실 온라인 세미나 - Speaker, MicroK8s Cluster 구축하기 (2024.06)
- AWS Summit Seoul 2024 참여 (2024.05)
- AWS Student Community Day 2024 참여 (2024.04)
- Wanted Backend Challenge - AWS를 활용한 시스템 아키텍처 참여 (2024.03)
- Advanced Architecting on AWS 수료 (2023.12)
- DevOps Engineering on AWS 수료 (2023.12)
- Developing on AWS 수료 (2023.12)
- AWS Well-Architected Best Practices 수료 (2023.11)
- AWS Community Day 2023 참여 (2023.10)
- AWS Security Essentials 수료 (2023.10)
- AWS Cloud Practitioner Essentials 수료 (2023.10)
