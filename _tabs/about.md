---
# the default layout is 'page'
icon: fas fa-info-circle
order: 4
---

<!-- > Add Markdown syntax content to file `_tabs/about.md`{: .filepath } and it will show up on this page.
{: .prompt-tip } -->

> ## <span style="color:#BF8C79">About Me</span>

<div style="display: flex; align-items: center;">
  <div style="flex: 1.2;">
    <img src="/assets/img/kkam-img/kcd_2025.jpg" alt="Profile Photo" style="max-width: 90%; border-radius: 8px;">
  </div>
  <div style="flex: 2; margin-left: 10px;">
    <!-- <h3 style="color: #D49A7B;">Introduce</h3> -->
    <h4> "DevOps & Cloud" </h4>
    <p>
      - 새로운 기술을 습득하는 것을 좋아합니다. <br>
      - 사소한 문제라도 지나치지 않고 해결하는 것을 좋아합니다. <br>
      - 겪은 시행 착오나 공부한 기술을 공유하는 것을 좋아합니다. <br>
      - 주어진 기간 내 최고의 결과물을 만들어내기 위해 최선을 다합니다.
    </p>
  </div>
</div>

> ## <span style="color:#BF8C79">Skill-Set</span>

| 구분           | 기술                                                          |
| -------------- | ------------------------------------------------------------- |
| AWS            | EC2, EKS, ECS, ECR, RDS, VPC, Route53, CloudFront, CloudWatch |
| CI/CD          | Jenkins, GitHub Actions, ArgoCD                               |
| Monitoring     | ELK, Prometheus, Grafana                                      |
| Container      | Docker, Kubernetes                                            |
| IaC            | Terraform, Ansible                                            |
| Programming    | Go, Python                                                    |
| OS             | Windows, Ubuntu, CentOS, Amazon Linux                         |
| Virtualization | Hyper-V, VMware                                               |

> ## <span style="color:#BF8C79">Certificate</span>

- HashiCorp Certified: Terraform Associate (003) [2025.07]
- AWS Certified DevOps Engineer - Professional [2024.12]
- Certified Kubernetes Administrator [2024.07.23]
- AWS Certified Solutions Architect - Associate [2024.02.02]
- 정보처리기사 [2023.09.30]
- AWS Certified Cloud Practitioner [2023.05.31]

- Email - <xowl5460@naver.com>
- Github - [https://github.com/kkamji98](https://github.com/kkamji98)
- Blog - [https://kkamji.net](https://kkamji.net)
- LinkedIn - [https://linkedin.com/in/taejikim](https://linkedin.com/in/taejikim)

> ## <span style="color:#BF8C79">Careers</span>

### Warepoint / Technical Architect - [ 2024.12 ~ 현재 ]

- Samsung Galaxy Chatting Plus (RCS) 서비스 운영
- AWS Infra 구축 및 운영 (Terraform IaC)
- EKS Cluster 운영 및 업그레이드
- 서비스 장애 대응 및 근본 원인 분석(RCA) 가이드 작성
- GitHub Actions Matrix Strategy 도입 (Multi-Architecture Container Image Build 시간 50% 이상 단축)
- Apache Superset 구축, PoC, 운영
- Keycloak SSO + RBAC 적용 (Grafana, Argo CD, Apache Superset)
- InfluxDB(TSDB) 마이그레이션 AL2 -> Ubuntu (EoS 대응)
- Open-source Software 버전 업그레이드 (Grafana, Prometheus, Thanos, External Secrets)

> ## <span style="color:#BF8C79">Open-source Contribution</span>

- [Amazon Observability Helm Charts PR #190](https://github.com/aws-observability/helm-charts/pull/190) - 불필요한 리소스 생성을 제어할 수 있도록 `dcgmExporter.enabled`, `neuronMonitor.enabled` Flag 추가
- [Strands Agents SDK PR #1906](https://github.com/strands-agents/sdk-python/pull/1906) - README 내 깨진 Documentation Link 19개 수정, [v1.35.0 Release](https://github.com/strands-agents/sdk-python/discussions/2095)의 New Contributors 항목에 포함

> ## <span style="color:#BF8C79">Projects</span>

### Home Sweet Home - [ 2025.04 ~ 2025.04 ]

> 청년 주택청약 알리미 Web App (Students @ AI - Seoul Hackathon)
> Infra / Frontend / Backend 역할로 참여
{: .prompt-tip}

#### 주요 역할 및 담당

- Streamlit 기반 사용자 Frontend UI 개발
- Bedrock Knowledge Base 기반 특정 청약 정보에 대한 대화형 조회 구현
- 로그 모니터링을 통한 트러블슈팅

### Remember Me - [ 2024.11 ~ 2024.12 ]

> 서버리스(AWS Lambda) 기반 영단어 암기 Web App
> Infra / DevOps Lead 역할로 참여
{: .prompt-tip}

[Remember Me Github Organizations - https://github.com/vocaAppServerless](https://github.com/vocaAppServerless)

#### 주요 역할 및 담당

- Terraform(HCP Terraform) 기반 Cloud Infra IaC
- Lambda CI/CD Pipeline 구축
- CloudWatch Logs Subscription Filters + ELK Stack을 사용해 Lambda Logs 중앙화
- AWS Budgets, WAF Rule Event Slack Alarm 연동
- Secrets Manager, Parameter Store 기반 시크릿 및 환경변수 관리

### Weasel - [ 2024.07 ~ 2024.08 ]

> Bedrock 기반 문제풀이 서비스
> Antrophic Claude Sonnet 3.5 Model 활용해 문제의 답과 해설 제공
{: .prompt-tip}

![banner](/assets/img/project/weasel/banner.webp)

[Weasel Github Organizations - https://github.com/Team-S5T1](https://github.com/Team-S5T1)

#### 주요 역할 및 담당

- Team Lead
- Cloud Infra 설계, 구축
- EKS Cluster 운영
- WEB, WAS, DB 배포
- Secret 관리
- IAM User, Group 관리
- CI/CD 파이프라인 구축 (Jenkins, ArgoCD)

#### 프로젝트 기술 스택

| 구분     | 기술                                                            |
| -------- | --------------------------------------------------------------- |
| Develop  | Spring Boot, React                                              |
| Deploy   | EKS, S3, Route53, CloudFront                                    |
| Database | RDS(MySQL)                                                      |
| IaC      | Terraform                                                       |
| CI/CD    | Jenkins, ArgoCD                                                 |
| 모니터링 | Prometheus, Grafana                                             |
| AI       | Bedrock (Claude Sonnet 3.5)                                     |
| ETC      | Notion, Slack, Postman, GitHub, Secrets Manager, Karpenter, HPA |

#### 주요 성과

- Terraform Remote State 적용
- Terraform을 활용한 AWS Infra 구축
- EKS Node Auto Scaling 및 HPA 적용
- Spot Instance와 NAT Instance를 활용한 비용 절감
- Jenkins CI Pipeline 최적화

#### Architecture

![Architecture](/assets/img/project/weasel/about/architecture.png)

#### CI/CD Pipeline

![ci-cd](/assets/img/project/weasel/about/ci-cd.png)

#### CI - Jenkins

![ci-jenkins](/assets/img/project/weasel/about/ci-jenkins.png)

#### CD - ArgoCD

![cd-argocd](/assets/img/project/weasel/about/cd-argocd.png)

#### Workflow

![workflow](/assets/img/project/weasel/about/workflow.png)

#### Project Management

![project-management](/assets/img/project/weasel/about/project-management.png)

### Amazon Photo Query - [ 2024.01 ~ 2024.03 ]

> 기존 앨범 서비스에 AI 모델을 도입. 자연어 검색, 얼굴 검색, 자동 태깅 등 이미지 검색 편의성 제공
> AWS 클라우드 상에서 MSA, 3-Tier-Architecture로 구축 및 배포
{: .prompt-tip}

[백엔드 개발 저장소 - https://github.com/KKamJi98/Photo-Query](https://github.com/KKamJi98/Photo-Query)
[EKS 배포 저장소 - https://github.com/kkamji98/aws-app-eks-manifests](https://github.com/kkamji98/aws-app-eks-manifests)

#### 데모 영상

<table>
  <tr>
    <td align="center">
      <iframe width="350" height="220" src="https://www.youtube.com/embed/373Xvy3tddM" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
      <p><strong>얼굴 기반 사진 검색</strong></p>
    </td>
    <td align="center">
      <iframe width="350" height="220" src="https://www.youtube.com/embed/jOgX3f43c1Q?si=LOGMPSblNM_v2WwA" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
      <p><strong>자연어로 사진 검색</strong></p>
    </td>
  </tr>
  <tr>
    <td align="center">
      <iframe width="350" height="220" src="https://www.youtube.com/embed/GlHXMVzgk-s?si=9l69N_pEyp1g-SAa" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
      <p><strong>태그 자동 생성 기능</strong></p>
    </td>
    <td align="center">
      <iframe width="350" height="220" src="https://www.youtube.com/embed/7bvTYE_tMAg?si=rn0vQ8f-jJ5RynsL" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
      <p><strong>기본 앨범 기능</strong></p>
    </td>
  </tr>
</table>

<!-- [![유사한 사진 검색](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/31dc7819-2d79-481d-8b50-0d1acd783788)](https://www.youtube.com/watch?v=373Xvy3tddM) -->

#### 주요역할 및 담당

- Cloud Architecture 설계
- AWS 인프라 구축 & 운영
- CI/CD 파이프라인 구축
- ERD 구축 & 운영
- EKS 모니터링 및 비용 추적
- 이미지 CRD, 북마크, 태그 기능 개발 & 배포

#### 프로젝트 기술 스택

| 구분        | 기술                                                                                  |
| ----------- | ------------------------------------------------------------------------------------- |
| Programming | Go, Python, Node.js, Flutter                                                          |
| CI/CD       | Jenkins, ArgoCD, CodeSeries                                                           |
| Container   | Docker, EKS, ECR                                                                      |
| Database    | RDS(MySQL), DynamoDB, DocumentDB                                                      |
| Monitoring  | Prometheus, Grafana, Container Insight, KubeCost                                      |
| ETC         | S3, Cognito, Rekognition, Secrets Manager, Terraform, SNS, SQS, Karpenter, Fluent-bit |
| Tools       | Notion, Slack, Postman, GitHub                                                        |

#### 주요 기능

- 회원 가입, 로그인
- 자연어를 통한 사진 검색
- 얼굴 인식을 사용한 사진 조회
- 태그 자동 생성
- 사진 업로드, 삭제, 조회
- 선정적인 사진 필터링

#### Architecture

![Architecture](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/85603917-67cc-4df3-a02b-ec2265ea235c)

#### CI/CD Pipeline

![CI/CD](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/054c8b31-2309-42ba-9d34-d99e743210d5)

#### EKS 모니터링

![EKS 모니터링](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/3534ef17-b8b9-4698-941d-c8c4e7bda81f)

![EKS 모니터링(Container Insight)](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/05163450-9b6d-4c9f-927e-9e229fb6a567)

#### 비용 추적(Kubecost)

![EKS 비용추적](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/f6e3bd64-3681-4ebf-a44a-ee366ec9b160)

#### 업로드 로직

![이미지 업로드 로직](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/c3410c5e-e326-4164-8a2c-803b00a6d641)

#### 프로젝트 일정 관리

![프로젝트 일정 관리](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/dfc08e2b-e621-419a-b520-52d9d87ab71d)

#### 의견 공유 및 공지

![Slack](https://github.com/kkamji98/kkamji98.github.io/assets/72260110/90306aad-c2bb-47b5-8461-2257b180300f)

#### 트러블 슈팅

> **S3, DynamoDB 등의 리소스에 대한 Public 접근 차단 후** S3, DynamoDB에서 Access Deny 문제 직면
> **AWS IRSA** 개념을 공식문서를 통해 습득 후, 팀원들에게 공유
{: .prompt-danger}
---

> 성능 테스트 도중 다수(500MB 700장)의 이미지 업로드 시 **5분 이상의 시간과 상당한 리소스를 사용**한다는 문제를 발생
{: .prompt-danger}

1. 기존 로직에서 이미지 리사이징 기능을 Lambda함수로 분리
2. 버지니아 리전을 사용으로 생긴 네트워크 지연 해소를 위해 **Global Accelerator** 도입
3. 동시성 구현을 위해 **Goroutine**을 프로젝트에 도입
4. **이미지 업로드 API 응답시간을 5분에서 1분 미만으로 단축** (문제 해결)

---

> ## <span style="color:#BF8C79">Personal Projects</span>

수동/반복 작업에 대한 편의성을 향상시키기 위해 아래와 같은 도구 및 서비스를 개발했습니다.

| 프로젝트                                                                                  | 설명                                                       |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [ssh-connector](https://github.com/KKamJi98/ssh-connector)                                 | SSH Config 파일의 설정을 기반으로 동작하는 서버 접근 관리 Tool |
| [aws-pick](https://github.com/KKamJi98/aws-pick)                                           | AWS CLI 사용에 적용되는 Default Profile 전환 Tool          |
| [kubernetes-monitoring-python](https://github.com/KKamJi98/kubernetes-monitoring-python)   | Kubernetes Cluster Monitoring CLI Tool                     |
| [listup-aws-resources](https://github.com/KKamJi98/listup-aws-resources)                   | AWS 리소스를 수집 및 정리해 Excel / JSON으로 내보내는 Tool |
| [log-filter](https://github.com/KKamJi98/log-filter)                                       | 정규식 패턴으로 기존 로그를 제외하고 신규 패턴 로그만 추출하는 Tool |
| [image-converter](https://github.com/KKamJi98/image-converter)                             | 이미지 확장자 변환, 리사이즈, 압축을 제공하는 Web App      |

---

> ## <span style="color:#BF8C79">Educational Background</span>

> **중원대학교 컴퓨터공학과 [2018.03 - 2023.08]**
> - 융합과학대학 수석 졸업
> - 학생 대표로 교내 J-Smart, 교수역량진단시스템 사업 참여
> - 데이터베이스 강의 보조 활동
> - GPA (Overall): 4.40 / 4.5
> - GPA (Major): 4.42 / 4.5
{: .prompt-tip}

---

> ## <span style="color:#BF8C79">Education</span>

> **Cilium 공식 문서 핸즈온 스터디 1기 / CloudNet@ [2025.07 - 2025.08]**
>
> - Cloud Native 네트워킹 심화 스터디
> - eBPF, Cilium 기반 Kubernetes DataPath 이해 및 L3 / L4 / L7 Network Policy 설계
> - Routing 모드: Encapsulation(VXLAN / GENEVE) vs Native Routing 구조 및 Trade-off 비교
> - Cluster Mesh: 멀티클러스터 서비스 디스커버리 / 통신, Identity 학습
> - Service Mesh 연계: Ingress / Gateway API + Envoy로 TLS, L7 트래픽 처리
> - Hubble 활용: Flow / Service Map, DNS / HTTP 가시성으로 정책 미스 및 차단 트래픽 트러블슈팅
{: .prompt-tip}

---

> **AWS Cloud School 1기 [2023.08 - 2024.03]**
>
> - Cloud(AWS) & DevOps 교육
> - Network, Linux, Docker, Kubernetes, Jenkins, ArgoCD, AWS 학습
> - 교육과정 내 공지 게시판 개발
> - AI & Cloud 기반 앨범 서비스 "Photo Query" 팀 프로젝트 참여 (5인)
{: .prompt-tip}

---

> **Rising Camp Plus 1기 [2023.07 - 2023.09]**
> - Java Backend 교육
> - Java, Spring Boot3, JPA, MySQL, Git 학습
> - Spring Boot 기반 채용사이트 개발 팀 프로젝트 참여 (3인)
{: .prompt-tip}

---

> ## <span style="color:#BF8C79">Awards</span>

- Fastfive x AWS Frugality Fest GameDay - Winner [2025.04]
- Students @ AI - Seoul Hackathon - Winner [2025.04]
- AWS PS GameDay(GenAI) - 5th Place [2024.08]
- AWS x RAPA DevOps Jam - Runner-up (2nd Place) [2023.12]

---

> ## <span style="color:#BF8C79">Activities</span>

- Cloud Native Korea Community Day 2025 세션 진행 (ArgoCD와 함께하는 Multi-Cluster 운영) [2025.09]
- Dive 2025 Global Data Hackathon (부산항만공사) 참여 [2025.08]
- AWS Cloud School 8기 - Amazon Working Backwards 참여(Mentor/Staff) [2025.06]
- 2025 경기창고 개회식 참여(Staff) [2025.05]
- 충남대학교 커스텀 GPT 프롬프톤 참여(Staff) [2024.08]
- AWS 클라우드 부트캠프 & 멘토링 프로그램 참여(보조강사) [2024.07 ~ 2024.08]
  - 부산일과학고등학교, 서울디지텍고등학교
- AWS PS GenAI GameDay 참가 [2024.07]
- AWS 온라인 세미나 세션 진행 (MicroK8s를 사용해 EC2기반 경량 클러스터 구축하기) [2024.06]
- AWS Summit Seoul 2024 참여 [2024.05]
- AWS Student Community Day 2024 참여 [2024.04]
- Wanted Backend Challenge - AWS를 활용한 시스템 아키텍처 참여 [2024.03]
- Advanced Architecting on AWS 수료 [2023.12]
- AWS DevOps Jam 차석 [2023.12]
- DevOps Engineering on AWS 수료 [2023.12]
- Developing on AWS 수료 [2023.12]
- AWS Well-Architected Best Practices 수료 [2023.11]
- AWS Community Day 2023 참여 [2023.10]
- AWS Security Essentials 수료 [2023.10]
- AWS Cloud Practitioner Essentials 수료 [2023.10]
