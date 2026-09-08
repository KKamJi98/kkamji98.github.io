---
title: "SAP-C02 박살내기 15 - 모더나이제이션 패턴"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, modernization, strangler-fig, containerization, serverless, refactoring, microservices]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-06 10:00:00 +0900
---

온프레미스 야간 배치가 70분 동안 24GiB 메모리를 사용한다면 Lambda로 옮기는 것이 모더나이제이션처럼 보이지 않을 수 있습니다. 반대로 하루에 몇 번만 실행되는 짧은 작업을 EC2에 계속 올려 두면 운영 부담이 그대로 남습니다. 모더나이제이션의 첫 질문은 어떤 AWS 서비스가 유행하는지가 아니라, 기존 워크로드가 가진 제약이 무엇인지입니다.

또 다른 실패는 모놀리스 앞에 라우터 하나를 놓고 모든 트래픽을 새 서비스로 보내는 순간 발생합니다. 데이터와 호출 경계가 준비되지 않은 상태에서 라우트를 한 번에 바꾸면 장애 원인을 되돌리기 어렵습니다. 새 서비스와 기존 기능이 함께 동작하는 기간, 관측할 신호, 되돌릴 위치를 먼저 설계해야 합니다.

SAP-C02 Domain 4의 Task 4.3과 4.4는 이 판단을 묻습니다. 서비스 이름을 나열하는 대신 실행 시간, 상태 보유, 네트워크와 OS 제어, 데이터 모델, 메시지 보장, 팀의 운영 역량을 요구사항으로 바꿔 타깃을 고르는 문제입니다.

> **TL;DR**  
> - 모더나이제이션은 서비스 선택보다 기존 워크로드의 실행 시간, 상태, 런타임, 데이터 모델, 운영 제약을 먼저 기록하는 작업이다.  
> - strangler fig은 transform, coexist, eliminate 세 단계로 진행하고 coexist 동안 모놀리스를 빠른 롤백 대상으로 남긴다.  
> - 외부 HTTP 요청을 모놀리스 경계에서 가로챌 수 없고 내부 호출을 바꿀 수 있다면 branch by abstraction이 더 적합하다.  
> - Lambda는 호출당 최대 900초와 10,240MB 메모리이며, Fargate는 실행 시간 하드 리밋이 없고 태스크당 최대 244GiB 메모리와 32 vCPU를 제공한다.  
> - Fargate 태스크의 로드 밸런서 target type은 `ip`이고, EKS Fargate는 DaemonSet, EBS, GPU, Fargate Spot을 지원하지 않는다.  
> - ECR은 이미지 공급 경로이고 ECS와 EKS는 오케스트레이션 선택이다. ECS는 네트워크와 보안을 제어하면서 운영 부담을 낮추고, EKS는 Kubernetes 유연성과 그에 따른 운영 역량을 요구한다.  
> - 관계형 조인과 트랜잭션을 유지하면 RDS 또는 Aurora, 액세스 패턴을 key-value로 다시 설계할 수 있으면 DynamoDB, OS 수준 제어가 필요하면 EC2 self-managed가 후보가 된다.  
> - Aurora Serverless v2는 ACU 단위로 스케일하지만 Database Activity Streams와 Aurora Auto Scaling을 지원하지 않는다.  
> - 소비자별 버퍼와 순서가 필요하면 SNS FIFO와 SQS FIFO, 콘텐츠 라우팅이면 EventBridge, 긴 사람 승인과 비멱등 작업이면 Step Functions Standard를 검토한다.  
> - 단계 전환에는 route, feature toggle, abstraction, 데이터 동기화 각각의 롤백 조건을 둔다. 검증이 끝나기 전에 eliminate하지 않는다.  
{: .prompt-info}

---

## 1. 기존 워크로드를 제약으로 읽는 순서

모더나이제이션 대상은 이미 운영 중인 시스템입니다. 새 시스템 설계처럼 빈 화면에서 고를 수 없으므로 먼저 현재 동작을 보존해야 할 항목과 바꿀 수 있는 항목을 나눕니다. 다음 정보를 애플리케이션 단위로 수집하면 타깃 선택이 서비스 이름 맞히기로 변하지 않습니다.

| 확인 축 | 질문 | 실패를 만드는 조건 |
| :--- | :--- | :--- |
| 실행 | 한 번의 작업이 얼마나 오래 실행되는가 | Lambda 15분 상한, 배치 중단 |
| 상태 | 실행 중 메모리와 로컬 파일을 다음 요청이 기대하는가 | 무상태 함수로 옮긴 뒤 상태 유실 |
| 런타임 | 특정 OS, 커널, 드라이버, 라이선스, 패치 레벨이 필요한가 | 관리형 플랫폼의 지원 범위 밖 |
| 네트워크 | 고정 IP, 사설 연결, 특정 포트 또는 파일 프로토콜이 필요한가 | public endpoint 또는 IP target 제약 |
| 데이터 | 조인과 트랜잭션, 파일 잠금, 검색, key-value 중 무엇이 핵심인가 | 데이터 모델을 바꾸지 않고 다른 DB를 선택 |
| 전달 | 순서, 재시도, 보존, 팬아웃, 사람 승인이 필요한가 | 메시지 유실, 중복, 순서 역전 |
| 운영 | 팀이 Kubernetes와 OS 패치와 클러스터 업그레이드를 감당하는가 | 관리형 서비스 선택이 운영 부담으로 바뀜 |

이 기록은 7R을 고르는 입력값이기도 합니다. 사용하지 않는 시스템은 retire, 등가 플랫폼이 없는 시스템은 retain, 코드를 바꾸지 않고 그대로 옮기면 rehost, 플랫폼만 바꾸면 replatform, 코드를 분해하거나 데이터 모델을 바꾸면 refactor입니다. 7R의 분류 절차와 마이그레이션 도구는 [마이그레이션 전략 편](/posts/aws-sap-c02-migration-strategy/)의 주제이므로 여기서는 타깃 아키텍처가 분류 결과를 어떻게 구체화하는지만 다룹니다.

서비스를 고르는 순서는 다음과 같습니다.

1. 보존해야 할 사용자 계약과 데이터 일관성을 적습니다.
2. 한 요청 또는 한 작업의 최장 실행 시간과 필요한 메모리를 측정합니다.
3. OS 수준 접근, 특정 네트워크, 파일 프로토콜, 특수 하드웨어가 필요한지 확인합니다.
4. 데이터 모델과 읽기 및 쓰기 패턴을 분리해 적습니다.
5. 비동기화했을 때 필요한 순서, 보존, 재시도, 팬아웃을 정합니다.
6. 팀의 운영 능력과 배포 및 롤백 속도를 타깃의 비용으로 계산합니다.

이 과정을 거치면 같은 애플리케이션 안에서도 컴퓨트와 스토리지와 데이터베이스의 타깃이 달라질 수 있습니다. 예를 들어 Windows 애플리케이션은 EC2에서 계속 실행하면서 SMB 파일 계층만 FSx for Windows File Server로 옮기고, 읽기 중심 세션 데이터는 DynamoDB나 ElastiCache로 별도 분리할 수 있습니다. 하나의 서비스로 모두 옮겨야 한다는 가정이 오히려 변경 범위를 키웁니다.

{% include diagrams/static/sap-c02/modernization-compute-target-decision.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/modernization-compute-target-decision--a61792e5a659de27.png" %}

그림은 기존 워크로드의 실행 시간과 상태와 OS 제어 요구가 Lambda, Fargate, EC2로 갈라지는 지점을 보여줍니다. 짧은 무상태 이벤트와 장시간 컨테이너와 호스트 수준 제어가 필요한 작업을 같은 방식으로 옮길 수 없는 이유가 드러납니다.

### 1.1. 변경 범위를 먼저 고정하는 이유

마이그레이션과 모더나이제이션을 하나의 배포에 몰아 넣으면 장애가 발생했을 때 원인을 나눌 수 없습니다. 네트워크 경로를 바꾸면서 데이터 모델까지 바꾸고, 동시에 런타임을 함수로 바꾸면 어떤 변경이 지연과 오류를 만들었는지 확인하기 어렵습니다.

따라서 첫 단계는 동작을 보존하는 타깃을 만들고, 이후 한 경계씩 개선하는 방식이 안전합니다. rehost 또는 replatform으로 동일한 API와 데이터 계약을 유지한 뒤, 트래픽 분할과 관측을 확보하고, 그 다음에 purpose-built 데이터베이스와 이벤트 기반 호출로 바꿉니다. refactor가 목표여도 첫 릴리스에서 모든 모듈을 분리하지 않는 이유입니다.

---

## 2. strangler fig은 라우트와 롤백을 함께 설계한다

strangler fig은 모놀리스를 한 번에 제거하는 패턴이 아닙니다. 외부 호출이 들어오는 경계에 HTTP proxy 또는 facade를 놓고, 특정 기능만 새 서비스로 점진적으로 옮긴 다음 기존 기능을 제거합니다. AWS Prescriptive Guidance는 이 흐름을 transform, coexist, eliminate 세 단계로 설명합니다.

{% include diagrams/static/sap-c02/modernization-strangler-route-switch.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/modernization-strangler-route-switch--17dda1332051d164.png" %}

그림은 하나의 외부 HTTPS endpoint가 proxy와 라우팅 결정을 거쳐 기존 모놀리스 또는 현대화 서비스로 향하는 모습을 보여줍니다. 새 서비스의 데이터 저장소가 별도 경계를 가질 때도 기존 모놀리스 경로를 남겨 두어 검증 중 되돌릴 수 있다는 것이 핵심입니다.

### 2.1. transform 단계

transform에서는 어떤 기능을 옮길지 선택하고 새 구현을 병렬로 만듭니다. 이 시점의 완료 조건은 새 서비스가 운영 트래픽을 받는 것이 아니라, 기존 계약을 기준으로 독립적인 테스트가 가능하고 필요한 데이터와 권한과 관측이 준비된 것입니다.

기능을 고를 때는 기술적인 크기보다 경계의 명확성을 먼저 봅니다. 고객 알림처럼 입력과 출력이 분명하고 재처리가 가능한 기능은 경계 후보가 되기 쉽습니다. 반대로 여러 테이블을 하나의 트랜잭션으로 갱신하며 모놀리스 내부 객체를 직접 참조하는 기능은 먼저 데이터와 호출 경계를 정해야 합니다.

새 구현은 기존 저장소를 그대로 공유할 수도 있지만, 공유 기간과 읽기 및 쓰기 책임을 문서로 고정해야 합니다. 양쪽이 같은 테이블을 자유롭게 갱신하면 route를 되돌려도 데이터 상태가 이전과 같지 않을 수 있습니다. 롤백은 코드 라우팅만 되돌리는 일이 아니라 데이터 계약을 포함한 복구라는 점을 이 단계에서 확인합니다.

### 2.2. coexist 단계

coexist에서는 기존 모놀리스를 롤백 수단으로 유지하고 proxy에서 외부 요청을 새 서비스로 보냅니다. 초기에는 모든 요청을 기존 경로로 보내고, 검증 대상 기능만 새 경로로 전환합니다. 새 경로에서 오류율과 지연과 데이터 정합성을 확인한 뒤 범위를 넓힙니다.

라우팅은 기능 단위로 관찰할 수 있어야 합니다. 사용자나 테넌트 일부, 특정 API path, 요청 헤더 또는 버전별 route를 기준으로 나눌 수 있습니다. 다만 분할 기준이 재현 가능해야 하며, 장애가 난 동일 요청을 어느 경로가 처리했는지 로그와 trace에서 확인할 수 있어야 합니다.

AWS 문서가 경고하는 proxy의 단일 장애점과 성능 병목도 이 단계에서 측정합니다. proxy 자체의 오류율, latency, 연결 수, upstream별 응답을 별도 지표로 수집하고, proxy 장애 시 기존 경로로 우회할 수 있는지 확인합니다. 라우터를 하나 더 추가한 뒤 그 라우터의 상태를 보지 않는다면 모놀리스의 문제를 새로운 공통 장애점으로 옮긴 것에 불과합니다.

### 2.3. eliminate 단계

새 서비스가 필요한 기능을 모두 제공하고 검증 기간이 끝나면 기존 모듈을 제거합니다. 제거는 가장 마지막 변경입니다. route를 0으로 만든 것과 코드를 삭제한 것은 다른 상태이며, 데이터 보존 기간과 감사 로그와 롤백 가능 기간을 먼저 확인해야 합니다.

각 기능마다 다음 rollback 조건을 수치로 정합니다.

| 신호 | 예시 조건 | 조치 |
| :--- | :--- | :--- |
| 오류 | 새 경로 5분 p95 오류율이 기존 대비 1%포인트 초과 | route를 이전 weight로 되돌림 |
| 지연 | p99가 SLO를 연속 3분 초과 | 신규 트래픽 중단, 원인 확인 |
| 데이터 | dual-read 비교에서 필드 불일치 발생 | 쓰기 경로를 기존 구현으로 복귀 |
| 비용 | 호출량이 아닌 공통 계층 비용이 예산 초과 | 용량과 캐시와 경로를 재평가 |

수치는 조직의 SLO에 맞게 정해야 하며 표의 값 자체를 AWS 하드 리밋으로 해석하면 안 됩니다. 중요한 것은 관측 전에 eliminate하지 않는다는 순서입니다.

### 2.4. Refactor Spaces의 현재 위치

AWS Migration Hub Refactor Spaces는 strangler fig을 구현할 때 environment, application, service, route를 만들고 API Gateway, Network Load Balancer, Transit Gateway, Resource Access Manager, security group을 조합해 계정 간 경로를 구성하던 서비스입니다. 환경 소유 계정, 기존 애플리케이션 계정, 첫 신규 마이크로서비스 계정으로 나누는 구성이 문서에 제시되어 있습니다. service endpoint는 VPC 안의 HTTP 또는 HTTPS URL이나 Lambda function으로 등록합니다. 기존 애플리케이션 service에 연결한 default route는 생성 시 active가 기본이며 필요할 때 inactive로 전환해 신규 route를 검증할 수 있습니다.

현재 AWS 공식 availability 안내에 따르면 Migration Hub는 2025년 11월 7일부터 신규 고객을 받지 않습니다. 기존 프로젝트는 계속 운영할 수 있지만 새 프로젝트의 권장 대안은 AWS Transform입니다. 따라서 시험에서는 Refactor Spaces의 리소스 모델과 strangler fig 원리를 알아야 하지만, 신규 환경을 설계할 때 이 서비스를 현재 선택지로 단정하면 안 됩니다.

### 2.5. strangler fig을 쓰지 않는 조건

AWS 문서가 명시한 부적합 조건은 두 가지입니다. 시스템의 규모와 복잡도가 작아 점진적 라우팅 계층의 비용이 더 큰 경우, 그리고 백엔드 요청을 가로채 라우팅할 수 없는 경우입니다. 모놀리스 내부에서 직접 호출되는 컴포넌트는 외부 proxy가 볼 수 없으므로 다음 절의 branch by abstraction을 검토합니다.

---

## 3. 컴퓨트 타깃은 실행 시간과 운영 책임으로 나눈다

컨테이너화했다고 해서 곧바로 Fargate가 정답이 되는 것은 아닙니다. 기존 프로세스가 장시간 실행되는지, 실행 중 메모리 상태를 보유하는지, OS를 직접 만져야 하는지, 이벤트가 있을 때만 실행되는지를 먼저 봅니다.

### 3.1. EC2와 Elastic Beanstalk

EC2는 OS와 런타임과 네트워크를 직접 제어해야 하는 대신 지원 범위가 가장 넓습니다. 특정 커널 모듈, 상용 에이전트, 벤더가 인증한 패치 레벨, GPU 또는 특별한 파일 시스템이 필요하면 self-managed EC2가 남습니다. 이 선택은 rehost 또는 제한된 replatform에 가깝고 패치와 백업과 용량 계획과 장애 복구를 팀이 계속 책임집니다.

Elastic Beanstalk는 애플리케이션 서버와 배포와 오토 스케일링을 관리형으로 제공해 VM보다 운영 부담을 낮춥니다. 다만 플랫폼 브랜치의 OS와 런타임 수명 주기를 따라가야 합니다. AWS 공식 일정에서 Amazon Linux 2 기반 브랜치는 2026년에 retirement 대상이며, 본문과 개별 행의 날짜가 다르게 보일 수 있으므로 현재 표를 배포 전에 확인합니다. 새 모더나이제이션 타깃으로 고를 때 AL2023 기반 브랜치와 지원 런타임을 확인하고, AL2를 그대로 새 표준으로 복제하지 않습니다.

### 3.2. App Runner와 ECS Express Mode

App Runner는 소스 또는 컨테이너 이미지에서 웹 애플리케이션을 빠르게 배포하고 인프라를 거의 관리하지 않는 높은 수준의 경로였습니다. 현재 AWS 공식 문서는 App Runner를 신규 고객에게 닫았고, 기존 고객에게는 보안과 가용성 유지 범위에서 서비스를 계속 제공합니다. 신규 설계에서 App Runner를 선택하기보다 ECS Express Mode를 검토해야 하며, 기존 App Runner를 옮길 때는 같은 컨테이너 이미지를 사용해 ECS 서비스와 Application Load Balancer를 만들고 Route 53 weighted routing으로 점진 전환하는 절차가 문서에 있습니다.

App Runner의 단순함이 필요한 팀이라도 VPC 서브넷과 security group 수준의 제어가 요구되면 ECS on Fargate가 더 직접적인 선택입니다. App Runner가 제공하던 운영 편의와 네트워크 제어 요구를 동시에 적은 선지는 서비스의 추상화 경계를 확인해야 합니다.

### 3.3. Lambda의 하드 리밋

Lambda는 짧은 이벤트 기반 작업에 적합합니다. 현재 공식 quotas 문서에서 함수 호출 한 번의 최대 실행 시간은 900초이고, 메모리는 128MB에서 10,240MB까지 1MB 단위입니다. 메모리 1,769MB에서 vCPU 1개에 해당하며 CPU는 메모리에 비례합니다.

| 항목 | Lambda 값 | 타깃 판단 |
| :--- | :--- | :--- |
| 호출당 실행 시간 | 900초 | 15분을 넘는 배치는 그대로 옮길 수 없음 |
| 메모리 | 128MB에서 10,240MB | 24GiB 작업은 함수 하나로 수용할 수 없음 |
| 동시성 | 기본 1,000, 증액 가능 | 예약 동시성과 계정 쿼터를 함께 확인 |
| 함수별 확장 | 10초마다 실행 환경 1,000개 | 급격한 burst는 throttle 가능 |
| 동기 payload | 요청과 응답 각각 6MB | 큰 데이터는 S3 같은 저장소로 분리 |
| 비동기 payload | 1MB | 이벤트 본문 대신 포인터를 전달 |
| zip 배포 | 50MB 업로드, 250MB unzipped | 큰 런타임은 컨테이너 이미지 또는 Fargate 검토 |
| 컨테이너 이미지 | 최대 10GB | 이미지가 크면 시작 시간과 저장 공간을 평가 |
| `/tmp` | 512MB에서 10,240MB | 임시 공간이지 영구 상태 저장소가 아님 |

Lambda는 기본적으로 무상태 함수입니다. 함수 실행 환경이 재사용될 수 있어 메모리 캐시가 보이는 경우에도 이를 영속 상태로 가정하지 않습니다. 상태는 DynamoDB, S3, EFS 또는 데이터베이스로 옮기고 함수는 이벤트를 받아 처리한 뒤 결과를 기록합니다. VPC에 연결된 함수가 관계형 DB에 직접 연결되면 동시 실행마다 연결이 늘어날 수 있으므로 RDS Proxy 같은 연결 풀링을 별도 검토합니다.

### 3.4. Fargate의 하드 리밋과 운영 경계

Fargate는 컨테이너를 실행하는 서버리스 컴퓨트 엔진입니다. AWS 결정 가이드는 실행 시간 하드 리밋이 없고 태스크당 최대 244GiB 메모리와 32 vCPU를 제공한다고 설명합니다. 컨테이너는 실행 중 메모리 상태를 유지할 수 있지만 중요한 상태는 외부 저장소에 둬야 태스크 교체와 확장에 안전합니다.

Fargate 태스크는 CPU와 메모리 조합표 안에서만 등록됩니다. 예를 들어 4 vCPU는 8GB에서 30GB 범위의 메모리 조합을 사용하고, 더 큰 메모리가 필요하면 상위 CPU 조합을 선택해야 합니다. platform version 1.4.0 이상의 Linux 태스크는 ephemeral storage를 기본 20GiB에서 `ephemeralStorage` 설정으로 최대 200GiB까지 늘릴 수 있습니다. 압축 이미지와 압축 해제 이미지가 같은 공간을 사용하므로 이미지가 클수록 애플리케이션이 쓸 수 있는 용량이 줄어듭니다.

Fargate는 `awsvpc` 네트워크 모드를 사용하고 태스크마다 ENI와 IP를 가집니다. Application Load Balancer, Network Load Balancer 또는 Gateway Load Balancer를 연결할 때 target type은 `ip`여야 합니다. `instance` target은 EC2 인스턴스에 등록하는 방식이라 Fargate 태스크와 맞지 않습니다.

Fargate의 capacity provider는 Fargate와 Fargate Spot입니다. Fargate Spot은 용량 회수 전에 2분 경고를 주므로 중단을 허용하는 비동기 작업에만 적용합니다. 서비스에서 온디맨드와 Spot을 섞을 때 `capacityProviderStrategy`를 사용하고 `launchType`과 동시에 지정하지 않습니다.

### 3.5. Lambda와 Fargate를 비교하는 기준

| 축 | Lambda | Fargate |
| :--- | :--- | :--- |
| 실행 모델 | 이벤트가 호출하는 함수 | ECS 태스크와 서비스 또는 배치 컨테이너 |
| 실행 시간 | 호출당 15분 | 하드 리밋 없음 |
| 상태 | 외부 저장소에 둔다 | 실행 중 메모리 상태 가능, 중요 상태는 외부화 |
| 런타임 | AWS 런타임과 custom runtime | 컨테이너로 패키징 가능한 런타임 |
| 네트워크 | 기본 AWS 관리 네트워크, VPC 연결 선택 | 태스크마다 VPC ENI |
| 확장 | 요청과 동시성 중심 | desired task 수와 서비스 용량 중심 |
| 배포 | weighted alias | blue/green, canary, linear 지원 |
| 콜드 스타트 | provisioned concurrency, SnapStart | SOCI lazy loading과 이미지 최적화 |
| 운영 판단 | 짧고 불규칙한 이벤트 | 장시간, 지속 연결, 특정 자원 컨테이너 |

한 번에 수십 분 이상 실행되는 데이터 처리, 지속 연결을 유지하는 워커, 컨테이너 안에서 in-memory 상태가 필요한 작업은 Fargate 쪽이 자연스럽습니다. 이벤트마다 짧게 실행되고 입력과 출력이 저장소로 분리되는 작업은 Lambda가 단순합니다. 단순히 서버를 없애고 싶다는 이유만으로 장시간 배치를 Lambda 여러 개로 쪼개면 실행 경계와 재시도와 상태 저장이 새 복잡도가 됩니다.

---

## 4. 컨테이너화 뒤 ECS와 EKS를 고르는 기준

컨테이너 이미지는 실행 플랫폼과 분리해 관리합니다. 소스에서 Docker 이미지를 만들고 Amazon ECR에 버전을 저장한 뒤 오케스트레이터가 해당 digest를 배포하는 흐름을 고정하면, ECS와 EKS 사이의 선택이 이미지 재작성 작업으로 번지지 않습니다.

{% include diagrams/static/sap-c02/modernization-container-hosting-boundaries.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/modernization-container-hosting-boundaries--5d0d822779b499a7.png" %}

그림은 같은 ECR 이미지가 ECS on Fargate와 EKS on Fargate로 갈라지고, 각 플랫폼의 제약을 거쳐 IP target 서비스에 연결되는 경계를 보여줍니다. ECS는 capacity provider와 태스크 단위 운영을 사용하고, EKS는 Fargate profile과 Kubernetes Pod 스케줄링을 사용합니다.

### 4.1. ECS on Fargate

ECS는 AWS가 제공하는 오케스트레이션 모델로 태스크 정의, 서비스 desired count, service discovery, 배포와 롤링 업데이트를 AWS 개념으로 관리합니다. AWS 컨테이너 결정 가이드는 네트워크와 보안 설정을 더 제어하면서 규모와 기능을 유지하려는 조직에 ECS를 권장합니다.

Fargate를 사용하면 EC2 클러스터를 프로비저닝하거나 노드 AMI를 패치할 필요가 없습니다. 태스크 정의에서 CPU, memory, task role, execution role, 서브넷과 security group을 지정합니다. private subnet에서 ECR 이미지를 pull하려면 NAT gateway 또는 필요한 ECR interface VPC endpoint와 S3 gateway endpoint 경로를 준비합니다.

서비스 배포에서 blue/green 또는 canary를 사용하려면 ALB 또는 적합한 service discovery와 health check를 함께 설계합니다. target group은 `ip` 유형으로 만들고, 새 task set의 health signal이 통과한 뒤 트래픽을 이동합니다. 실패 시 이전 task set을 남겨 두고 target weight 또는 배포 상태를 되돌립니다.

### 4.2. EKS on Fargate

EKS는 Kubernetes API와 객체 모델을 유지해야 하거나, Kubernetes 생태계와 배포 도구를 조직 표준으로 사용해야 할 때 선택합니다. AWS가 관리하는 control plane이 있어도 클러스터 버전과 애드온과 Kubernetes 운영은 조직의 책임으로 남습니다. AWS 결정 가이드는 Kubernetes가 연 3회 major release를 내고 구버전을 deprecate하므로 잦은 업그레이드를 감당할 SRE 역량이 필요하다고 설명합니다.

EKS Fargate는 Pod가 Fargate profile에 매칭될 때만 스케줄됩니다. profile에 매칭되지 않는 Pod는 `Pending`에 남을 수 있습니다. ALB와 NLB는 IP target만 사용하고 Pod는 private subnet에만 배치됩니다.

다음 제약은 타깃 선택을 자르는 핵심입니다.

- DaemonSet을 지원하지 않으므로 노드마다 실행할 로그 수집기나 보안 데몬은 sidecar 또는 EC2 노드용 워크로드로 재구성합니다.
- EBS 볼륨을 Fargate Pod에 마운트할 수 없습니다. EFS는 자동 마운트할 수 있지만 dynamic provisioning은 지원하지 않고 static provisioning을 사용합니다.
- Fargate Spot을 지원하지 않습니다. 중단을 허용하는 비용 절감은 ECS Fargate Spot 또는 EC2 Spot 노드에서 검토합니다.
- privileged container, GPU, `HostPort`, `HostNetwork`, custom CNI, 노드 SSH를 지원하지 않습니다.
- IMDS에 접근할 수 없으므로 Pod 권한은 IAM roles for service accounts 같은 방식으로 부여합니다.
- Outposts, Wavelength, Local Zones에 Fargate Pod를 배치할 수 없습니다.

현재 Kubernetes 구성이 DaemonSet, EBS PVC, node IP target, IMDS, GPU 중 하나에 의존한다면 EKS Fargate로 단순히 옮길 수 없습니다. 해당 부분을 sidecar와 EFS와 IRSA로 바꾸거나, 제약을 감당할 수 있는 EC2 노드 그룹에 남겨 두는 혼합 구성이 필요합니다.

### 4.3. ECS와 EKS를 가르는 운영 질문

| 질문 | ECS on Fargate | EKS on Fargate |
| :--- | :--- | :--- |
| 팀의 주 운영 모델 | AWS ECS 태스크와 서비스 | Kubernetes Pod와 클러스터 |
| Spot | Fargate Spot 가능 | 지원하지 않음 |
| EBS | ECS 태스크의 지원 범위에서 사용 | Pod에서 마운트 불가 |
| DaemonSet | Kubernetes DaemonSet 개념 없음 | 지원하지 않음 |
| 공개 서브넷 | public IP 조건에서 가능 | private subnet만 |
| 로드 밸런서 | `ip` target | `ip` target |
| 특수 제어 | task definition과 IAM task role | Kubernetes API와 IRSA |
| 조직 요구 | AWS 제어면과 낮은 운영 부담 | Kubernetes 이식성과 높은 제어 |

컨테이너 운영 경험이 적고 Kubernetes API 호환성이 요구사항이 아니라면 ECS on Fargate가 운영 경계를 더 작게 만듭니다. 반대로 이미 Kubernetes 도구와 조직 표준을 갖고 있고 클러스터 업그레이드와 Pod 제약을 운영할 수 있다면 EKS가 이식성과 제어를 제공합니다. 팀의 인력 조건을 무시한 EKS 선택은 관리형 서비스를 사용해도 운영 부담을 줄이지 못합니다.

---

## 5. 스토리지 타깃은 파일 이름이 아니라 접근 의미로 고른다

스토리지 이전에서 먼저 확인할 것은 기존 경로를 그대로 유지해야 하는지, 애플리케이션이 블록 장치를 직접 다루는지, 여러 호스트가 같은 파일을 동시에 읽고 쓰는지입니다. 파일을 저장한다는 한 문장만으로 EBS, EFS, FSx, S3를 서로 바꿀 수 없습니다. 프로토콜과 일관성 모델과 잠금 의미가 달라 애플리케이션 변경 범위가 달라지기 때문입니다.

| 기존 요구 | 타깃 후보 | 유지되는 의미 | 먼저 확인할 것 |
| :--- | :--- | :--- | :--- |
| 한 EC2의 블록 장치, 낮은 지연 | EBS | 블록 I/O와 스냅샷 | 볼륨과 인스턴스의 AZ, 장애 시 attach 절차 |
| Linux 여러 인스턴스의 공유 파일 | EFS | NFS와 POSIX 권한 | throughput, 성능 모드, mount target과 네트워크 |
| Windows SMB, NTFS ACL, AD | FSx for Windows File Server | SMB 파일 공유와 Windows 인증 | 디렉터리 서비스, 파일 잠금, DNS와 보안 그룹 |
| 대용량 객체, 비동기 처리 | S3 | 객체 키와 내구성 | prefix, 버전, lifecycle, API 기반 접근으로의 변경 |
| 온프레미스 iSCSI 블록과 AWS 백업 | Volume Gateway | iSCSI 디바이스와 기존 블록 접근 | cached와 stored 중 지연 및 캐시 요구 |

### 5.1. EBS, EFS, FSx, S3의 경계

EBS는 EC2에 연결하는 블록 스토리지입니다. 일반적인 볼륨은 한 AZ 안에서 사용하고, Multi-Attach가 가능한 일부 볼륨 유형도 여러 인스턴스가 파일 시스템을 안전하게 공유한다는 뜻은 아닙니다. 여러 호스트가 동시에 쓰려면 cluster-aware 파일 시스템과 잠금 조정이 필요합니다. 따라서 기존 애플리케이션이 SMB 공유를 기대한다면 EBS 여러 개를 연결하는 방식으로 대체하지 않습니다. 스냅샷은 백업과 복구용 기준점을 만들지만, 스냅샷 생성 시점과 애플리케이션 쓰기 일관성도 함께 확인합니다.

EFS는 NFS 기반의 리전 파일 시스템으로 여러 AZ의 Linux 클라이언트가 같은 파일 계층을 사용할 때 후보입니다. POSIX 사용자와 그룹 권한, 파일 경로, 파일 잠금이 필요한 애플리케이션의 변경 폭을 줄일 수 있습니다. Windows SMB 클라이언트나 NTFS ACL을 전제로 하는 애플리케이션은 EFS의 프로토콜과 권한 모델에 맞지 않습니다. Fargate와 EKS Fargate에서 사용할 때는 태스크 또는 Pod의 서브넷, security group, mount target과 IAM 권한을 함께 설계합니다.

FSx는 특정 파일 시스템의 의미를 관리형으로 제공하는 제품군입니다. FSx for Windows File Server는 SMB, NTFS ACL, Active Directory와 Windows 파일 잠금을 유지해야 할 때 선택합니다. FSx for Lustre는 고성능 병렬 파일 시스템을 필요로 하는 Linux 계산 작업의 후보입니다. 따라서 문제에 Windows 공유와 AD가 함께 나오면 일반적인 FSx라는 이름보다 FSx for Windows File Server를 지목해야 합니다.

S3는 객체 저장소입니다. 애플리케이션이 객체 키로 읽고 쓰며 파일 시스템의 rename, POSIX 권한, SMB 잠금 또는 임의 바이트 블록 업데이트를 기대하지 않을 때 적합합니다. 대용량 파일을 데이터베이스나 메시지 본문에 넣는 대신 S3 객체를 만들고 포인터와 메타데이터만 전달하는 방식은 데이터와 처리 계층을 분리합니다. 다만 로컬 파일 경로를 S3 mount 도구로 감싸는 것만으로 파일 시스템의 모든 의미가 보존된다고 가정하지 않습니다.

### 5.2. Volume Gateway로 기존 블록 접근을 유지하는 경우

Volume Gateway는 온프레미스 애플리케이션 서버에 iSCSI 디바이스로 노출되는 클라우드 백업형 볼륨입니다. cached volumes는 주 데이터를 S3에 두고 자주 읽는 부분을 게이트웨이 로컬 캐시에 남깁니다. stored volumes는 전체 데이터를 게이트웨이 로컬에 두고 point-in-time 스냅샷을 S3로 비동기 백업합니다. 기존 서버가 iSCSI 블록을 사용하고 클라우드로 단계적으로 데이터를 옮겨야 한다면 파일 시스템이나 애플리케이션 API를 먼저 바꾸지 않고 중간 계층으로 사용할 수 있습니다.

cached 모드는 로컬 캐시보다 큰 데이터 집합을 운영할 수 있지만 전체 볼륨을 반복해서 읽는 작업은 S3에서 다시 내려받아 대역폭을 크게 사용할 수 있습니다. stored 모드는 전체 데이터의 낮은 지연 읽기가 중요할 때 유리하지만 로컬 게이트웨이와 디스크 용량을 계속 운영해야 합니다. 두 모드 모두 기존 호스트의 파일 시스템 잠금과 다중 호스트 쓰기 조건을 별도 검증해야 합니다. 하나의 블록 볼륨을 여러 호스트에 연결하는 것만으로 비클러스터 파일 시스템 공유가 안전해지지 않습니다.

스토리지 전환의 rollback은 경로를 예전 볼륨으로 바꾸는 데서 끝나지 않습니다. 새 계층에 쓰인 데이터가 기존 계층으로 역복제되는지, 복제 지연 동안 어느 계층이 권위 있는지, 파일 잠금과 객체 버전이 어떻게 보존되는지를 정합니다. 읽기 전환부터 시작하고 쓰기 권한은 한 계층에만 두면 중복 쓰기와 되돌리기 어려운 충돌을 줄일 수 있습니다.

---

## 6. 데이터베이스 타깃은 엔진 이름보다 데이터 모델과 관리 책임으로 결정한다

관계형 데이터베이스를 다른 이름의 데이터베이스로 복사하는 것과 데이터 모델을 다시 설계하는 것은 다른 작업입니다. SQL 조인과 다중 테이블 트랜잭션을 유지해야 하는지, 키로 한 항목을 읽는지, 검색어와 집계를 처리하는지, 운영체제와 엔진을 직접 패치해야 하는지를 분리해 적습니다.

{% include diagrams/static/sap-c02/modernization-database-target-selection.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/modernization-database-target-selection--f7b545e2451756b5.png" %}

그림에서 RDS와 Aurora는 관계형 계약을 유지하면서 데이터베이스 운영을 위임하는 경로이고, DynamoDB와 OpenSearch는 목적에 맞는 액세스 패턴을 다시 설계하는 경로입니다. EC2 self-managed는 관리형 서비스가 제공하지 않는 OS와 엔진 제어를 남기는 대신 패치와 백업 책임도 남깁니다.

| 요구 | 후보 | 변경과 남는 책임 |
| :--- | :--- | :--- |
| SQL, 조인, 트랜잭션, 관리형 패치 | RDS 또는 Aurora | 엔진과 스키마는 유지할 수 있지만 쿼리와 파라미터를 검증 |
| 엔진 옵션, OS 스크립트, 특정 벤더 패치 | EC2 self-managed | OS, DB 패치, 백업, 용량과 가용성을 직접 운영 |
| 키 기반 고속 접근, 유연한 스키마 | DynamoDB | 파티션 키와 정렬 키 중심으로 액세스 패턴을 재설계 |
| 텍스트 검색, 분석 인덱스 | OpenSearch Service | 검색 인덱스와 원본 데이터의 권위 및 재색인을 설계 |
| 메모리 캐시 또는 내구성 있는 메모리 DB | ElastiCache 또는 MemoryDB | 캐시인지 primary 데이터인지에 따라 내구성 선택 |

### 6.1. RDS와 Aurora를 선택하는 범위

RDS와 Aurora는 관계형 엔진을 관리형으로 운영하는 replatform의 중심입니다. 기존 SQL과 트랜잭션을 보존하면서 OS 설치, 기본 패치, 다중 AZ 구성 같은 운영 책임을 AWS 쪽으로 넘길 수 있습니다. 그렇다고 스키마와 쿼리 설계가 사라지는 것은 아닙니다. 엔진 호환성, 확장 방식, 커넥션 수, 백업 복구 시간과 애플리케이션의 failover 처리를 검증해야 합니다.

EC2 self-managed는 관리형 RDS에서 지원하지 않는 엔진 버전이나 옵션, OS 수준의 스크립트, 벤더 인증 패치 레벨이 요구될 때 남습니다. 이 경우 rehost가 빠를 수 있지만 관리형 경계를 포기한 비용이 있습니다. 패치, 취약점 대응, 백업 검증, 스토리지 확장, 장애 조치와 성능 및 가용성 목표를 기존 팀이 계속 책임집니다. 일정이 짧다는 이유로 RDS로 옮긴 뒤 지원되지 않는 기능을 나중에 복구하려 하면 데이터베이스 전환을 다시 해야 합니다.

DynamoDB는 모든 관계형 테이블을 그대로 담는 저장소가 아닙니다. 읽기와 쓰기의 access pattern을 먼저 정하고 파티션 키와 정렬 키 및 필요한 보조 인덱스를 설계합니다. 현재 DynamoDB 개별 아이템 최대 크기는 400KB이므로 문서나 큰 payload를 아이템 하나에 넣는 대신 S3 객체와 포인터를 조합할 수 있습니다. Streams는 변경 이벤트를 전달하지만 보존 기간이 24시간이므로 장기 감사 보관소로 직접 사용하지 않습니다.

OpenSearch Service는 원본 트랜잭션의 대체품이라기보다 텍스트 검색과 분석 인덱스 타깃입니다. 주문 원장을 OpenSearch만으로 옮기기 전에 원본 쓰기 권위를 RDS, DynamoDB 또는 다른 시스템에 두고 색인 지연과 재색인 경로를 정합니다. 검색 결과를 빠르게 만든다는 이유로 트랜잭션과 검색의 일관성 요구를 한 저장소에 섞지 않습니다.

ElastiCache는 재생성할 수 있는 자주 읽는 데이터의 ephemeral cache에 맞고, MemoryDB는 내구성 있는 in-memory 데이터베이스로 primary 데이터 역할까지 검토할 수 있습니다. 세션이나 계산 결과가 유실되어도 재생성할 수 있으면 ElastiCache가 단순합니다. 데이터 자체를 보존하고 Multi-AZ 내구성이 요구되면 MemoryDB와 원본 데이터의 책임을 비교합니다.

### 6.2. Aurora Serverless v2 전환과 기능 경계

Aurora Serverless v2는 DB 인스턴스 클래스를 고정하는 대신 ACU로 용량을 조정합니다. 1 ACU는 약 2GiB 메모리와 그에 대응하는 CPU 및 네트워킹을 나타내며, 용량은 0.5 ACU 단위로 조정됩니다. 문서상 클러스터 범위는 최소 0에서 최대 256 ACU이고 실제 최소값은 엔진 버전에 따라 다릅니다. `db.serverless` 인스턴스를 추가하려면 먼저 클러스터에 `ServerlessV2ScalingConfiguration`이 있어야 합니다.

Serverless v2를 선택할 때는 지원되지 않는 기능을 같은 표에 적어야 합니다. Database Activity Streams와 Aurora PostgreSQL cluster cache management는 serverless에서 지원되지 않으며, Aurora Auto Scaling으로 리더를 자동 증설하는 방식도 사용할 수 없습니다. 부하를 분산할 리더가 필요하면 낮은 용량의 serverless reader를 미리 만들고, 애플리케이션의 읽기 endpoint와 failover 동작을 검증합니다.

provisioned 클러스터에서 serverless로 점진 전환할 때는 기존 클러스터에 serverless reader를 추가하고 스케일 동작과 쿼리 호환성을 관찰합니다. 준비가 되면 failover로 reader를 승격하므로 클러스터 endpoint를 애플리케이션 설정에서 바꿀 필요가 없습니다. 다만 DAS 같은 필수 기능이 감사 요건에 포함되어 있으면 endpoint 보존만으로 전환 조건을 만족하지 못합니다.

최대 ACU를 낮추는 변경도 비용 숫자만 보고 실행하지 않습니다. 현재 workload나 `max_connections` 같은 커스텀 파라미터가 새 상한을 넘으면 Aurora가 변경을 취소하고 이전 설정으로 되돌릴 수 있으며, 이벤트로 결과를 알립니다. serverless 전환의 acceptance test에는 최소와 최대 ACU, 연결 수, 장애 조치, 데이터베이스 기능 지원 여부를 포함합니다.

### 6.3. 데이터베이스 전환 순서

1. 기존 스키마, 조인, 트랜잭션, 저장 프로시저와 배치 의존성을 목록으로 만듭니다.
2. 읽기와 쓰기 access pattern 및 최대 item, row, 객체 크기를 측정합니다.
3. 관리형 엔진이 제공해야 하는 확장, 암호화, 감사, 백업과 복구 조건을 확인합니다.
4. RDS와 Aurora의 호환성 검증, DynamoDB의 키 설계, OpenSearch 색인 설계를 각각 별도 실험합니다.
5. 이중 쓰기를 한다면 권위 있는 원본과 재처리 순서와 중복 방지를 정의합니다.
6. shadow read와 checksum 비교를 거친 뒤 읽기 weight를 옮기고, 쓰기 route는 데이터 검증 후에 전환합니다.

데이터베이스는 컴퓨트처럼 route 하나만 되돌리면 상태가 복구되는 계층이 아닙니다. 이전 시점의 스냅샷과 변경 캡처 지연과 재생 가능 시간을 계산하고, 새 모델로 들어간 쓰기를 이전 모델로 되돌릴 변환 경로가 없으면 rollback 대신 중단 후 보정 절차를 선택합니다.

---

## 7. 디커플링 서비스는 전달 보장과 대기 시간을 먼저 비교한다

모놀리스의 동기 호출을 이벤트로 바꿀 때는 어떤 서비스가 최신인지보다 소비자가 얼마나 늦게 처리해도 되는지, 순서가 필요한지, 메시지를 얼마 동안 보존해야 하는지, 한 이벤트를 몇 곳에 전달할지를 먼저 정합니다. SQS와 SNS와 EventBridge는 모두 메시지나 이벤트를 다루지만 pull, push, rule 기반 라우팅과 보존 의미가 서로 다릅니다.

{% include diagrams/static/sap-c02/modernization-integration-choice-boundaries.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/modernization-integration-choice-boundaries--7baf1478e5b376ca.png" %}

그림은 생산자에서 요구사항을 읽고 소비자별 버퍼와 순서가 필요한지, 콘텐츠에 따라 여러 대상에 보내는지, 긴 워크플로와 사람의 응답을 기다리는지를 차례로 가르는 흐름을 보여줍니다. Amazon MQ는 기존 브로커 프로토콜을 보존해야 하는 별도 경로입니다.

### 7.1. SQS는 버퍼와 소비자 독립성을 만든다

SQS는 소비자가 폴링하는 대기열입니다. 생산자는 소비자의 순간 처리량을 알 필요가 없고, 각 소비자는 자신의 속도로 메시지를 처리합니다. Standard queue는 at-least-once 전달이므로 처리 핸들러를 멱등하게 만들고 visibility timeout과 DLQ를 함께 설계합니다. FIFO queue는 같은 message group 안의 순서를 보장하고 중복 제거 설정을 제공하지만, 그룹 키를 잘못 잡으면 병렬성이 줄어듭니다.

현재 SQS 메시지 최대 크기는 1,048,576 bytes, 즉 1MiB입니다. 그보다 큰 payload는 Extended Client Library로 S3에 본문을 저장하고 큐에는 포인터를 보내는 방식을 사용할 수 있으며, 이 확장 경로는 동기 클라이언트에서 최대 2GB까지 다룹니다. 큐 보존 기간은 기본 4일이고 최대 14일이며 visibility timeout은 기본 30초에서 최대 12시간입니다. 30일 보존이나 장기 replay가 필요하면 SQS를 단독 보관소로 고르지 않습니다.

FIFO를 고를 때는 순서를 어디까지 보장해야 하는지 문장으로 적습니다. 주문 ID를 message group ID로 사용하면 같은 주문 이벤트의 순서는 지키면서 서로 다른 주문은 병렬 처리할 수 있습니다. 모든 메시지를 한 그룹에 넣으면 FIFO라는 선택은 맞아도 처리량과 지연을 스스로 제한하게 됩니다. 메시지 중복은 여전히 가능하다고 보고 receipt와 비즈니스 키로 멱등성을 확인합니다.

### 7.2. SNS는 push 팬아웃과 구독자별 필터를 만든다

SNS는 토픽에 발행한 메시지를 여러 구독자에게 push하는 팬아웃 계층입니다. 구독자별 SQS 큐를 두면 소비자 처리 속도를 분리할 수 있고, subscription filter policy로 속성이나 메시지 본문에 따라 필요한 이벤트만 보낼 수 있습니다. 주문 이벤트를 결제, 재고, 알림에 모두 전달하되 각 소비자가 자신의 유형만 받게 하는 구조가 이 조합입니다.

순서가 필요한 팬아웃은 SNS Standard가 아니라 SNS FIFO 토픽과 소비자별 SQS FIFO 큐를 함께 사용합니다. FIFO 토픽과 큐의 message group ID를 같은 비즈니스 키로 설계하고, 필터에 의해 특정 구독자가 메시지를 받지 못해도 다른 구독자의 순서와 처리 상태가 독립적으로 유지되는지 확인합니다. SNS 자체는 큐처럼 장기 보존하는 저장소가 아니므로 소비자별 재처리와 지연 흡수는 SQS가 맡습니다.

### 7.3. EventBridge는 콘텐츠 라우팅과 서비스 이벤트에 맞는다

EventBridge는 event pattern과 rule로 이벤트를 분류해 AWS 서비스, Lambda, API destination 또는 다른 event bus로 보냅니다. 생산자가 특정 소비자 endpoint를 알 필요가 없고 이벤트 속성과 소스에 따른 route가 핵심일 때 유용합니다. 기본 bus에서 archive를 설정하지 않은 경로는 이벤트를 큐처럼 장기간 보존하지 않고 전달 순서도 보장하지 않습니다. archive를 설정하면 정해진 기간 또는 무기한 보존과 replay가 가능하지만 replay 순서는 보장되지 않으므로 순서와 지연 버퍼가 요구되면 SQS 조합으로 내려갑니다.

현재 기본 쿼터에서 rule 하나에 연결할 수 있는 target은 5개이며 이 값은 조정할 수 없습니다. 더 많은 대상이 필요하면 SNS 팬아웃을 두거나 여러 rule로 분리합니다. 대상 재시도는 기본적으로 24시간 동안 최대 185회이며 exponential backoff와 jitter를 적용합니다. `PutEvents` 요청은 전체 1MB 미만이어야 하고 한 요청에 최대 10개 entry를 담습니다. 이 수치는 대형 객체를 event detail에 직접 넣지 말고 S3 포인터를 사용해야 하는 이유가 됩니다.

### 7.4. Step Functions는 긴 상태와 사람의 응답을 보존한다

Step Functions Standard는 최대 1년 실행할 수 있고 exactly-once 실행 의미론과 실행 이력을 제공합니다. API로 최근 90일 실행 이력을 조회할 수 있으며 콘솔에서 상태 전환을 시각적으로 확인할 수 있습니다. `.sync`와 `.waitForTaskToken`을 포함한 service integration을 지원하므로 담당자 승인, 외부 작업 완료, 비멱등 결제처럼 긴 대기와 명확한 재개 지점이 필요한 워크플로에 맞습니다.

Express는 최대 5분 실행입니다. Asynchronous Express는 at-least-once이고 Synchronous Express는 at-most-once이므로 멱등성이 필요한 짧은 변환과 높은 호출량에 사용합니다. Express는 Standard의 `.sync`와 `.waitForTaskToken` 패턴을 지원하지 않고 Step Functions가 실행 이력을 보존하지 않으므로 CloudWatch Logs를 별도로 설계해야 합니다. 이미 만든 state machine의 타입은 생성 후 바꿀 수 없으므로 Standard와 Express의 선택을 비용만으로 뒤집지 않습니다.

### 7.5. Amazon MQ는 프로토콜 의존성을 보존한다

기존 애플리케이션이 AMQP, MQTT, OpenWire 같은 브로커 프로토콜과 JMS 클라이언트에 의존하고 코드 변경이 제한되면 Amazon MQ를 우선 검토합니다. 애플리케이션이 AWS SDK로 SQS를 호출하도록 다시 작성할 여유가 없고 14일보다 긴 보존이 필요하면 프로토콜 호환 브로커가 마이그레이션 시간을 줄일 수 있습니다. Amazon MQ는 메시지를 보존할 수 있지만 Kafka처럼 임의 offset replay를 제공하는 서비스로 보지 않으므로 감사용 장기 이벤트 로그가 필요하면 별도 저장소를 둡니다.

### 7.6. 통합 서비스 선택표

| 질문 | SQS | SNS | EventBridge | Step Functions | Amazon MQ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 소비 모델 | pull, 소비자별 버퍼 | push 팬아웃 | rule과 target route | 상태 머신 실행 | 브로커 프로토콜 |
| 순서 | FIFO에서 보장 | FIFO 토픽에서 보장 | 보장하지 않음 | 상태 전환 순서 | 브로커와 클라이언트 계약 |
| 보존 | 최대 14일 | 장기 큐 아님 | 기본 archive 미설정 경로는 장기 큐 아님 | Standard 이력 90일 조회 | 브로커 보존 정책 |
| 핵심 용도 | 처리 속도 차이 흡수 | 여러 구독자 전달 | 콘텐츠와 AWS 이벤트 분류 | 긴 대기와 콜백 | 기존 AMQP 등 코드 보존 |
| 대표 함정 | at-least-once와 visibility 만료 | 구독자별 버퍼가 없음 | 순서와 버퍼가 없음 | Express 5분과 콜백 미지원 | replay와 분석 로그를 별도 설계 |

---

## 8. 외부 라우트와 내부 호출은 분해 패턴이 다르다

strangler fig과 branch by abstraction은 모두 점진적 분해를 위한 패턴이지만 가로챌 수 있는 경계가 다릅니다. 외부 HTTP 요청이 모놀리스 앞을 통과하면 proxy에서 기능별 route를 바꾸는 strangler fig이 자연스럽습니다. 모놀리스 내부 객체가 직접 호출되고 upstream 의존성이 깊으면 abstraction을 먼저 삽입하는 branch by abstraction이 맞습니다.

### 8.1. branch by abstraction의 여섯 단계

AWS Prescriptive Guidance의 절차를 실제 변경 순서로 옮기면 다음과 같습니다.

1. 분리할 내부 컴포넌트와 그 컴포넌트를 호출하는 클라이언트를 식별합니다.
2. 기존 구현의 계약을 표현하는 abstraction layer를 모놀리스 안에 추가합니다.
3. 모든 기존 클라이언트를 직접 구현 대신 abstraction을 호출하도록 바꿉니다.
4. 모놀리스 밖에 같은 계약을 제공하는 새 구현을 작성하고 독립적으로 배포합니다.
5. abstraction이 새 구현을 호출하도록 전환하고 필요하면 feature toggle로 범위를 조절합니다.
6. 비교와 안정화 기간이 끝난 뒤 구 구현과 더 이상 필요하지 않은 abstraction 코드를 정리합니다.

중간 단계에서는 구 구현과 신 구현을 모두 호출해 결과를 비교하는 fallback을 만들 수 있습니다. 비교 결과를 기록하되 두 구현이 모두 외부 상태를 변경하면 중복 부작용이 생기므로 읽기 전용 shadow 호출이나 한쪽만 쓰는 계약을 먼저 설계합니다. data consistency가 핵심인 트랜잭션 경로는 branch by abstraction의 부적합 조건에 해당할 수 있으므로 데이터 경계를 먼저 나눕니다.

### 8.2. feature toggle과 abstraction은 역할이 다르다

feature toggle은 기능을 배포한 뒤 런타임이나 배포 시점에 노출 여부를 바꾸는 제어입니다. branch by abstraction은 내부 호출을 공통 계약으로 바꾸는 개발 기법입니다. abstraction 위에 toggle을 두면 신구 구현을 빠르게 전환할 수 있지만, toggle만 추가한다고 내부 의존성과 데이터 계약이 분리되지는 않습니다. toggle의 소유자, 만료 날짜, 기본값, 감사 로그와 제거 조건을 함께 기록합니다.

### 8.3. subdomain으로 경계를 읽는 방법

모놀리스의 모듈 경계가 이미 업무 언어와 데이터 책임으로 나뉘어 있다면 DDD subdomain을 bounded context 단위로 매핑할 수 있습니다. 핵심 업무의 core subdomain, 차별화 기능을 보조하는 supporting subdomain, 공통 기능인 generic subdomain을 구분하고 각 경계를 독립 배포 가능한 서비스로 정리합니다. 기존 모듈을 repackaging하는 수준에서 시작할 수 있어 전체 재작성보다 위험을 낮출 수 있습니다.

다만 모든 모듈을 마이크로서비스로 만들면 서비스 수와 네트워크 호출과 운영 계층이 늘어납니다. subdomain을 업무 경계가 아니라 현재 코드 디렉터리 이름으로만 정하면 데이터 ownership과 트랜잭션 경계가 다시 모놀리스에 묶입니다. 한 bounded context의 데이터 쓰기 권한과 다른 context가 읽는 계약을 먼저 문서화하고, 공유 테이블을 양쪽이 쓰는 상태로 남기지 않습니다.

### 8.4. 세 패턴을 비교하는 질문

| 상황 | 우선 검토할 패턴 | 이유 | 주의할 점 |
| :--- | :--- | :--- | :--- |
| 외부 API path를 proxy에서 가를 수 있음 | strangler fig | route weight와 단계별 공존으로 전환 | proxy 병목과 단일 장애점 |
| 내부 깊은 컴포넌트와 upstream 의존성이 있음 | branch by abstraction | 호출자 계약을 먼저 고정 | 기존 코드 변경과 데이터 정합성 |
| 모듈과 업무 경계가 이미 명확함 | decompose by subdomain | bounded context 단위로 재포장 | 서비스 과다 생성과 경계 오판 |
| 짧은 기능 토글로 노출만 제어 | feature toggle | 배포와 노출을 분리 | 데이터와 호출 분리는 별도 작업 |

어떤 패턴을 골라도 데이터 ownership과 운영 observability를 먼저 정합니다. 서비스 하나를 분리했다는 상태는 HTTP endpoint가 생겼다는 뜻이 아니라, 책임지는 저장소와 계약과 배포 및 롤백 지점이 분리되었다는 뜻입니다.

---

## 9. 단계적 현대화는 매 단계의 중단 위치를 만든다

현대화 릴리스는 새 코드가 동작하는지 확인하는 작업과 트래픽을 옮기는 작업과 구 구현을 제거하는 작업을 나눕니다. 다음 순서는 strangler fig, branch by abstraction, 데이터베이스 전환에 공통으로 적용할 수 있는 최소 runbook입니다.

1. **baseline**: 기존 p50, p95, p99 latency, 오류율, 처리량, 비용, 데이터 지연과 운영 이벤트를 측정합니다. 같은 요청을 재현할 수 있는 trace ID와 테스트 fixture를 확보합니다.
2. **characterize**: 입력과 출력 계약, side effect, 트랜잭션, 파일과 네트워크 의존성, 최대 실행 시간과 메모리를 기록합니다. undocumented behavior를 별도 테스트로 고정합니다.
3. **choose seam**: 외부 API route인지 내부 abstraction인지 subdomain인지 선택하고, 변경할 범위와 공유할 계약을 한 문장으로 정합니다.
4. **create target**: ECR 이미지, ECS 또는 EKS 서비스, 저장소, 데이터베이스와 IAM 권한을 만들고 health check와 로그와 trace를 연결합니다. 새 계층이 기존 데이터에 쓸 수 있는 범위를 최소화합니다.
5. **dual-read or contract check**: 읽기는 신구 결과를 비교하고, 이벤트는 schema와 version을 검증합니다. 이중 쓰기는 권위 있는 원본과 재처리 키와 보정 절차가 없으면 시작하지 않습니다.
6. **deploy dark**: 사용자 트래픽을 받지 않는 상태에서 synthetic request와 canary fixture를 실행합니다. 오류가 나면 route를 열지 않고 target을 수정합니다.
7. **shift traffic**: path, tenant, header, version 또는 feature toggle 등 재현 가능한 기준으로 작은 범위를 이동합니다. route와 target set을 로그와 trace에서 식별할 수 있어야 합니다.
8. **observe and widen**: 오류, 지연, saturation, 데이터 비교, 비용과 알람을 기존 baseline과 비교하고 안정화 기간을 지킨 뒤 범위를 넓힙니다.
9. **rollback or commit**: 조건을 넘으면 route weight와 toggle과 abstraction을 이전 구현으로 되돌립니다. 데이터가 이미 새 모델에 쓰였다면 역변환이나 보정이 준비된 경우에만 쓰기 rollback을 실행합니다.
10. **eliminate**: 검증 기간과 보존 기간이 끝난 뒤에만 proxy route, 구 구현, 이중 쓰기와 임시 toggle을 제거합니다. 제거 후에도 감사 로그와 복구 가능한 데이터 스냅샷을 보존합니다.

CI/CD 파이프라인에는 이미지 digest 고정, IaC plan, contract test, migration dry run, 배포 후 health check와 자동 중단 조건을 넣습니다. 운영 대시보드는 새 서비스와 모놀리스와 proxy를 같은 시간축에 두어 route가 바뀐 시점과 오류 변화를 함께 볼 수 있게 합니다. 성공한 canary 비율만 기록하고 전체 트래픽 전환을 성공으로 선언하면 데이터 지연과 느린 배치 실패를 놓칠 수 있습니다.

### 9.1. 롤백 지점을 계층별로 분리한다

| 계층 | 전환 스위치 | 되돌릴 수 있는 조건 | 되돌리기 전에 확인 |
| :--- | :--- | :--- | :--- |
| ingress | proxy route 또는 DNS weight | target 오류와 지연이 임계치 초과 | 세션과 재시도 요청의 경로 |
| application | feature toggle 또는 abstraction | 결과 비교 불일치, side effect 오류 | toggle 상태와 캐시 무효화 |
| event | rule, subscription, consumer pause | 스키마 오류, DLQ 증가 | 이미 전달된 중복과 idempotency |
| data read | read weight 또는 endpoint | checksum 불일치, stale read | 복제 지연과 원본 권위 |
| data write | writer route | 역변환과 보정 경로가 준비됨 | 새 모델의 쓰기와 기존 모델의 충돌 |

DNS weight만 되돌리면 이미 새 저장소에 기록된 데이터가 사라지는 것은 아닙니다. route rollback과 데이터 보정은 별도의 승인 조건으로 두고, 두 조건이 모두 충족될 때만 이전 릴리스로 돌아갑니다.

---

## 10. 시험 전에 고정할 하드 리밋과 지원 경계

서비스를 선택할 때 숫자를 외우는 목적은 숫자 자체를 맞히기 위해서가 아니라, 요구사항이 서비스의 물리적 경계를 넘는 순간을 빠르게 알아차리기 위해서입니다. 다음 값은 2026년 9월 AWS 공식 문서를 기준으로 정리했습니다. 리전, 플랫폼 버전, 엔진 버전에 따라 별도 쿼터가 있는 항목은 문제의 조건을 먼저 확인합니다.

| 영역 | 현재 기준값 | 설계에 미치는 영향 |
| :--- | :--- | :--- |
| Lambda 실행 | 호출당 최대 900초 | 긴 배치는 Fargate 또는 다른 배치 실행 경로로 분리 |
| Lambda 메모리 | 128MB에서 10,240MB | 24GiB 작업을 함수 하나로 수용할 수 없음 |
| Lambda 동기 payload | 요청과 응답 각각 6MB | 큰 본문은 S3 포인터로 분리 |
| Lambda 비동기 payload | 1MB | 이벤트 본문에 파일을 넣지 않음 |
| Lambda `/tmp` | 512MB에서 10,240MB | 영구 상태나 공유 파일 계층으로 사용하지 않음 |
| Lambda 기본 동시성 | 리전당 1,000 | burst와 예약 동시성 및 증액 여부를 확인 |
| Fargate 태스크 | 최대 244GiB 메모리, 32 vCPU | CPU와 메모리 조합표 안에서만 선택 |
| Fargate 실행 시간 | 하드 리밋 없음 | 장시간 워커와 배치에 사용 가능 |
| Fargate ephemeral storage | Linux platform 1.4.0 이상에서 20GiB에서 200GiB | 이미지와 압축 해제 파일이 같은 공간을 사용 |
| Fargate Load Balancer | target type `ip` | `instance` target group으로 등록할 수 없음 |
| Fargate Spot | 회수 전 2분 경고 | 재시도 가능한 중단 허용 작업에만 사용 |
| EKS Fargate | private subnet, IP target, profile 매칭 필요 | DaemonSet, EBS, GPU, Spot 같은 노드 기능을 대체해야 함 |
| SQS 메시지 | 최대 1MiB, Extended Client S3 경로는 최대 2GB | 큰 payload와 장기 객체를 큐에서 분리 |
| SQS 보존과 visibility | 최대 보존 14일, visibility 최대 12시간 | 30일 보존과 사람 승인 대기를 큐 하나로 해결할 수 없음 |
| EventBridge rule | target 기본 5개, 조정 불가 | 대규모 팬아웃은 SNS 또는 여러 rule 사용 |
| EventBridge `PutEvents` | 요청 총량 1MB 미만, 배치 10 entry | 객체 본문 대신 포인터를 전달 |
| Step Functions Standard | 실행 최대 1년, 이력 API 조회 90일 | 긴 승인과 재개 및 비멱등 작업에 사용 |
| Step Functions Express | 실행 최대 5분 | 짧은 멱등 변환에 사용, callback 대기 불가 |
| DynamoDB item | 최대 400KB | 큰 문서와 파일은 S3와 조합 |
| Aurora Serverless v2 | 0.5 ACU 단위, 문서상 0에서 256 ACU 범위 | 엔진 버전과 지원 기능을 함께 확인 |

이 값들 중 하나라도 요구사항을 넘으면 기능을 추가해 억지로 맞추지 않습니다. 실행 시간을 분할하는 경우에는 분할 사이에 상태를 저장해야 하고, 보존 기간을 늘리는 경우에는 별도 저장소와 만료 정책이 필요합니다. 숫자 하나를 만족하는 것과 원래 애플리케이션의 의미를 보존하는 것은 별도 acceptance criteria입니다.

---

## 11. 자주 헷갈리는 선택지를 한 문장으로 가른다

| 헷갈리는 쌍 | 먼저 묻는 질문 | 선택 기준 |
| :--- | :--- | :--- |
| Lambda와 Fargate | 한 번의 실행이 15분과 10GiB 안에 들어오는가 | 짧은 이벤트면 Lambda, 장시간 컨테이너면 Fargate |
| Fargate와 EC2 | OS, 커널, GPU, 특수 드라이버를 직접 관리해야 하는가 | 필요하면 EC2, 아니면 Fargate의 관리 경계 검토 |
| ECS와 EKS | Kubernetes API와 생태계가 요구사항인가 | 아니면 ECS, 이미 표준이면 EKS |
| ECS Fargate와 EKS Fargate | DaemonSet, EBS, GPU, Spot이 필요한가 | 필요하면 EKS EC2 노드 또는 ECS 등 다른 실행 경로 |
| EBS와 EFS | 한 호스트의 블록인가, 여러 호스트의 파일인가 | 블록이면 EBS, 공유 NFS 파일이면 EFS |
| EFS와 FSx for Windows | NFS POSIX인가, SMB NTFS와 AD인가 | Windows 파일 계약이면 FSx for Windows |
| FSx와 S3 | 파일 잠금과 경로가 필요한가 | 파일 의미면 FSx, 객체 API면 S3 |
| RDS와 EC2 self-managed | 관리형 DB가 필요한 옵션과 패치를 제공하는가 | 지원 범위 밖이면 EC2, 유지 가능하면 RDS 또는 Aurora |
| RDS와 DynamoDB | 조인과 트랜잭션인가, 키 기반 access pattern인가 | 관계형이면 RDS, 모델 재설계 가능하면 DynamoDB |
| DynamoDB와 OpenSearch | 정합성 있는 원본인가, 검색 인덱스인가 | 원본은 DynamoDB 등, 검색은 OpenSearch |
| ElastiCache와 MemoryDB | 캐시를 잃어도 되는가 | 재생성 가능하면 ElastiCache, durable primary면 MemoryDB |
| SQS와 SNS | 소비자별 대기열이 필요한가 | 버퍼면 SQS, push 팬아웃이면 SNS |
| SNS와 EventBridge | 정해진 구독 팬아웃인가, 콘텐츠 기반 rule인가 | 구독자 팬아웃이면 SNS, event pattern이면 EventBridge |
| SQS FIFO와 EventBridge | 같은 키의 순서가 필수인가 | 순서와 버퍼면 FIFO, 순서가 필요 없고 route면 EventBridge |
| Step Functions Standard와 Express | 오래 기다리거나 비멱등인가 | Standard, 짧고 멱등이면 Express |
| Amazon MQ와 SQS | 기존 브로커 프로토콜을 바꿀 수 있는가 | AMQP 등 코드 보존이면 MQ, AWS API 전환이면 SQS |
| strangler fig과 branch by abstraction | 요청이 proxy에서 보이는가 | 외부 route면 strangler, 내부 직접 호출이면 abstraction |
| branch by abstraction과 feature toggle | 호출 계약을 바꿔야 하는가 | 계약 분리는 abstraction, 노출 제어만 toggle |
| subdomain과 단순 서비스 분리 | 업무 경계와 데이터 ownership이 명확한가 | 명확하면 bounded context, 아니면 작은 seam부터 검증 |
| App Runner와 ECS Express Mode | 신규 설계인가, 기존 서비스 유지인가 | 신규 고객 접수가 중단된 App Runner 대신 ECS 경로 검토 |

표의 왼쪽과 오른쪽은 상호 배타적인 서비스 목록이 아닙니다. 한 시스템에서 ECS Fargate와 DynamoDB와 SQS를 함께 사용할 수 있고, EKS는 일부 워크로드만 EC2 노드에 남길 수 있습니다. 중요한 것은 한 서비스가 해결할 수 없는 제약을 다른 서비스의 이름으로 덮지 않는 것입니다.

---

## 12. 그럴듯하지만 조건을 위반하는 조합

다음 제안은 각각 한 가지 요구만 보고 나머지 제약을 놓친 예입니다. 시험에서는 서비스의 장점보다 문제에 명시된 hard limit과 전달 의미를 먼저 대조합니다.

- 70분 동안 실행되는 24GiB 배치를 Lambda 하나로 옮긴다. 900초와 10,240MB 상한을 넘습니다.
- provisioned concurrency를 켜면 Lambda 함수의 15분 timeout이 늘어난다고 가정한다. provisioned concurrency는 cold start를 줄일 뿐 실행 시간과 메모리 상한을 바꾸지 않습니다.
- Lambda `/tmp`에 세션 파일을 두고 다음 호출에서 항상 읽는다. 실행 환경 재사용은 보장되지 않는 캐시이며 영구 상태가 아닙니다.
- Fargate 태스크를 `instance` target group에 등록한다. `awsvpc` 태스크는 ENI의 IP target을 사용해야 합니다.
- private subnet의 Fargate 태스크에 NAT와 ECR endpoint 없이 이미지를 pull한다. 이미지 경로가 없어 태스크가 기동하지 않습니다.
- Fargate 태스크에 GPU 또는 privileged flag를 추가한다. Fargate task definition의 지원 범위를 벗어납니다.
- EKS Fargate에 DaemonSet 로그 수집기를 그대로 배포한다. sidecar 또는 EC2 노드용 수집기로 재구성해야 합니다.
- EKS Fargate Pod에 EBS PVC를 붙인다. EBS mount가 지원되지 않으며 EFS도 static provisioning 조건을 확인해야 합니다.
- EKS Fargate에 Fargate Spot capacity provider를 지정한다. EKS Fargate는 Fargate Spot을 지원하지 않습니다.
- EKS Fargate Pod를 public subnet에 배치해 ECR pull 문제를 해결한다. Fargate Pod는 private subnet에만 배치됩니다.
- EventBridge rule 하나에 target 10개를 붙여 팬아웃한다. 기본 5개이고 조정 불가라 SNS 또는 rule 분할이 필요합니다.
- 순서가 필요한 주문 이벤트를 EventBridge만으로 전달한다. EventBridge는 순서를 보장하지 않습니다.
- SQS에 30일 보존과 사람 승인 대기를 맡긴다. 보존은 최대 14일이고 visibility timeout은 최대 12시간입니다.
- SQS Standard에서 중복이 없다고 가정하고 환불을 실행한다. at-least-once 전달이므로 멱등 키와 중복 처리가 필요합니다.
- Step Functions Express로 3일 승인 callback을 기다린다. 5분 상한과 callback integration 미지원에 걸립니다.
- Step Functions Express로 비멱등 결제 API를 실행한다. Async는 at-least-once이고 Sync는 at-most-once라 Standard를 검토해야 합니다.
- 이미 만든 Step Functions Standard state machine을 Express로 바꿔 비용을 줄인다. 워크플로 타입은 생성 후 변경할 수 없습니다.
- Aurora Serverless v2에서 Database Activity Streams를 켠 채 전환한다. DAS는 serverless에서 지원되지 않습니다.
- Aurora Serverless v2에서 Aurora Auto Scaling으로 리더를 자동 증설한다. serverless는 해당 기능을 지원하지 않으며 reader를 미리 구성하는 대안을 검토합니다.
- DynamoDB item 하나에 1MB 문서를 저장한다. 개별 item 최대 크기 400KB를 넘고 S3 포인터 구성이 필요합니다.
- Windows SMB와 NTFS ACL 애플리케이션의 공유 계층을 EFS로 바꾼다. EFS는 NFS POSIX 모델이며 SMB와 AD 계약을 보존하지 않습니다.
- SMB 파일 잠금 애플리케이션의 데이터를 S3 bucket mount로 감싼다. 객체 API는 파일 잠금과 rename 의미를 보장하지 않습니다.
- EBS Multi-Attach만으로 여러 EC2의 공유 파일 시스템을 만든다. cluster-aware 파일 시스템과 접근 조정 없이는 안전한 동시 쓰기가 아닙니다.
- 신규 프로젝트에 Migration Hub Refactor Spaces 또는 App Runner를 기본 선택지로 쓴다. 두 서비스 모두 현재 신규 고객 접수가 중단되어 AWS Transform 또는 ECS 경로를 검토해야 합니다.
- 내부 컴포넌트 호출을 모놀리스 앞 API proxy에서 route 전환한다. proxy가 보지 못하는 직접 호출이면 branch by abstraction이 필요합니다.
- 데이터 정합성이 걸린 트랜잭션 경로에 abstraction fallback을 두 구현 모두 쓰게 한다. 중복 side effect와 불일치가 생길 수 있어 읽기 비교와 단일 writer를 먼저 설계합니다.

---

## 13. 예상 문제 10문항

앞의 판단 기준을 서비스 이름과 숫자와 운영 조건이 함께 있는 상황에 적용합니다. 각 문항의 정답을 먼저 고른 뒤, 다른 선택지가 위반하는 제약을 한 가지씩 말해 보세요.

**Q1.** 야간 정산 배치가 온프레미스에서 평균 70분 동안 실행되고 최대 24GiB 메모리를 사용합니다. 배치는 하루 한 번 실행되며 실행 중 중간 집계 상태를 메모리에 유지합니다. 팀은 인스턴스 운영을 없애기 위해 서버리스 또는 관리형 컨테이너로 옮기려 합니다. MOST appropriate 타깃은 무엇입니까?

- A. Lambda 함수 하나로 옮기고 메모리를 10,240MB로 설정합니다.
- B. ECS on Fargate 태스크로 옮기고 EventBridge Scheduler로 하루 한 번 실행합니다.
- C. 처리를 나눠 Step Functions Express 워크플로와 Lambda 조합으로 실행합니다.
- D. Lambda 함수에 provisioned concurrency를 구성합니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Lambda 함수 timeout은 900초로 고정이고 메모리 상한은 10,240MB입니다. Fargate 태스크는 실행 시간 하드 리밋이 없고 태스크당 최대 244GiB 메모리와 32 vCPU를 사용할 수 있어 70분과 24GiB 요구를 그대로 수용합니다. 하루 한 번 실행하는 일정은 EventBridge Scheduler가 호출하도록 분리합니다.

- A가 틀린 이유: 70분은 15분 timeout을 넘고 24GiB는 Lambda 메모리 상한을 넘습니다.
- C가 틀린 이유: Express 워크플로 최대 실행 시간은 5분이고, 분할하더라도 개별 Lambda의 15분과 메모리 상한은 그대로입니다. 분할 사이에 메모리 상태를 유지하려면 외부 저장소가 필요합니다.
- D가 틀린 이유: provisioned concurrency는 cold start를 줄이는 기능이고 실행 시간이나 메모리 상한을 바꾸지 않습니다.

</details>

**Q2.** EKS 관리형 노드 그룹에서 도는 워크로드를 EKS on Fargate로 옮기려 합니다. 현재 구성에는 DaemonSet으로 도는 로그 수집기, EBS PersistentVolumeClaim을 쓰는 상태 저장 Pod가 있고, 팀은 Fargate Spot으로 비용을 줄이려 합니다. 이전 전에 반드시 해야 하는 재구성 두 가지는 무엇입니까? (2개 선택)

- A. 로그 수집기를 DaemonSet에서 애플리케이션 Pod의 sidecar 컨테이너로 재구성합니다.
- B. Service가 사용하는 target group의 target type을 `instance`로 변경합니다.
- C. Fargate profile에 Spot capacity provider를 지정합니다.
- D. EBS PersistentVolumeClaim을 EFS static provisioning으로 대체하거나 해당 Pod를 EC2 노드에 남깁니다.
- E. Pod가 IMDS를 통해 노드 인스턴스 role을 받도록 노드 role 권한을 확장합니다.
- F. Fargate Pod를 public subnet에 배치해 이미지 pull 경로를 확보합니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, D**

EKS on Fargate는 DaemonSet을 지원하지 않으므로 daemon 성격의 워크로드는 sidecar로 재구성해야 합니다. EBS 볼륨을 마운트할 수 없고 EFS는 static provisioning만 지원하므로 상태 저장 Pod는 EFS로 바꾸거나 EC2 노드에 남겨야 합니다.

- B가 틀린 이유: Fargate Pod는 EC2 인스턴스가 아니라 ENI에 연결되므로 ALB와 NLB 모두 IP target 모드로 동작합니다.
- C가 틀린 이유: EKS는 Fargate Spot을 지원하지 않습니다. Spot 절감은 ECS on Fargate이거나 EC2 Spot 노드 그룹에서 가능합니다.
- E가 틀린 이유: Fargate Pod는 IMDS에 접근할 수 없고 IRSA로 권한을 받아야 합니다.
- F가 틀린 이유: Fargate Pod는 private subnet에만 배치할 수 있습니다.

</details>

**Q3.** 12명 규모 개발팀이 모놀리스를 컨테이너로 옮깁니다. 팀에 Kubernetes 운영 경험자가 없고 전담 SRE도 없습니다. VPC subnet과 security group 수준의 네트워크 제어를 유지하고 ALB 뒤에서 blue/green 배포를 해야 합니다. LEAST operational overhead 선택은 무엇입니까?

- A. ECS on Fargate
- B. EKS on Fargate
- C. AWS App Runner
- D. EKS와 관리형 노드 그룹

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

AWS 컨테이너 결정 가이드는 ECS를 규모와 기능을 유지하면서 네트워크와 보안 설정을 더 제어하는 선택지로 설명합니다. Fargate는 blue/green, canary, linear 배포를 지원하고 EC2 노드 패치 부담을 줄입니다.

- B가 틀린 이유: control plane 버전 업그레이드와 Kubernetes 운영 부담이 남고 DaemonSet, EBS, Fargate Spot 미지원 제약도 추가됩니다.
- C가 틀린 이유: App Runner는 신규 고객을 더 이상 받지 않으며 서브넷과 security group 수준의 제어를 직접 제공하는 경로가 아닙니다.
- D가 틀린 이유: 클러스터 업그레이드에 더해 노드 그룹의 AMI와 패치 수명주기까지 팀이 관리해야 합니다.

</details>

**Q4.** Windows 애플리케이션 서버 8대가 하나의 SMB 파일 서버를 공유 마운트합니다. 애플리케이션은 NTFS ACL과 Active Directory 인증에 의존하고 파일 잠금 동작을 그대로 기대합니다. 이 워크로드를 EC2로 rehost하면서 파일 계층만 관리형 서비스로 옮기려 합니다. MOST appropriate 스토리지는 무엇입니까?

- A. Amazon EBS Multi-Attach 볼륨
- B. S3 bucket을 각 인스턴스에 mount 도구로 연결
- C. Amazon EFS
- D. Amazon FSx for Windows File Server

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

FSx for Windows File Server는 SMB 프로토콜, NTFS ACL, Active Directory 통합과 Windows 파일 잠금을 제공하는 관리형 파일 스토리지입니다. 애플리케이션 코드와 파일 접근 방식을 바꾸지 않고 파일 계층을 이전할 수 있습니다.

- A가 틀린 이유: EBS Multi-Attach는 여러 인스턴스 연결 기능일 뿐 SMB 공유와 AD 인증을 제공하지 않으며 cluster-aware 파일 시스템이 필요합니다.
- B가 틀린 이유: 객체 스토리지는 POSIX 또는 NTFS 파일 잠금과 ACL 모델을 제공하지 않습니다.
- C가 틀린 이유: EFS는 NFS 기반 파일 시스템이라 SMB 프로토콜과 NTFS ACL과 Active Directory 인증 모델을 제공하지 않습니다.

</details>

**Q5.** Oracle 기반 애플리케이션이 관리형 서비스가 지원하지 않는 데이터베이스 옵션과 OS 수준 스크립트에 의존하고, 소프트웨어 벤더는 특정 패치 레벨만 인증합니다. 데이터센터 종료까지 5개월이 남았고 재작성 예산은 없습니다. MOST appropriate 타깃 데이터베이스 플랫폼은 무엇입니까?

- A. 액세스 패턴을 다시 설계해 DynamoDB로 옮깁니다.
- B. RDS for Oracle로 replatform합니다.
- C. EC2에 Oracle을 설치해 self-managed로 운영합니다.
- D. DMS와 DMS Schema Conversion으로 Aurora PostgreSQL로 refactor합니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

관리형 서비스가 제공하지 않는 엔진 옵션과 OS 접근과 벤더 인증 패치 레벨이 요건이면 EC2 self-managed가 남습니다. AWS 데이터베이스 결정 가이드는 이 경로를 rehost로 설명하며 업그레이드, 패치, 백업, 용량 계획과 성능 및 가용성 목표를 계속 운영해야 한다고 명시합니다.

- A가 틀린 이유: 관계형 스키마와 트랜잭션 애플리케이션을 key-value 모델로 옮기려면 데이터 모델과 access pattern을 전면 재설계해야 합니다.
- B가 틀린 이유: RDS는 OS 수준 접근을 제공하지 않고 벤더 인증 특정 패치 레벨을 임의로 고정할 수 없습니다.
- D가 틀린 이유: heterogeneous refactor는 stored procedure와 애플리케이션 코드 재작성을 수반해 5개월과 예산 제약을 만족하지 못합니다.

</details>

**Q6.** 야간에는 유휴이고 낮에는 부하가 급변하는 Aurora PostgreSQL 클러스터를 provisioned에서 serverless로 옮기려 합니다. 보안팀은 감사 요건 때문에 Database Activity Streams를 상시 켜 두라고 요구하고, 운영팀은 전환 중 애플리케이션 endpoint를 바꾸지 않기를 원합니다. MOST appropriate 판단은 무엇입니까?

- A. serverless reader를 기존 클러스터에 추가하고 failover로 승격하면 endpoint를 바꾸지 않아도 되지만, Database Activity Streams 요구가 유지되는 한 serverless로 전환할 수 없습니다.
- B. 최대 ACU를 낮게 잡아 비용을 통제하면서 serverless로 전환합니다.
- C. serverless로 전환하고 Aurora Auto Scaling으로 리더를 자동 증설해 낮 시간 부하를 흡수합니다.
- D. serverless로 전환하고 전환 후 Database Activity Streams를 다시 활성화합니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Aurora Serverless v2는 Database Activity Streams와 Aurora PostgreSQL cluster cache management를 지원하지 않고 Aurora Auto Scaling도 지원하지 않습니다. 무중단 전환 경로는 기존 클러스터에 serverless reader를 추가해 스케일 동작을 관찰한 뒤 failover로 승격하는 방식이며 애플리케이션 endpoint를 바꿀 필요가 없습니다. 따라서 전환 경로는 성립하지만 감사 요건이 유지되는 한 전환 자체가 막힙니다.

- B가 틀린 이유: 최대 용량을 낮출 때 현재 workload나 `max_connections` 같은 커스텀 파라미터가 새 상한을 넘으면 변경이 취소되고 이전 설정으로 되돌아갈 수 있으며 DAS 요구도 해결되지 않습니다.
- C가 틀린 이유: Aurora Serverless v2는 Aurora Auto Scaling을 지원하지 않습니다. 낮은 용량의 serverless reader를 미리 만드는 대안을 검토합니다.
- D가 틀린 이유: DAS는 serverless에서 지원되지 않으므로 전환 후에도 활성화할 수 없습니다.

</details>

**Q7.** 모놀리스의 주문 처리 모듈을 분리해 결제, 재고, 알림 세 소비자에게 이벤트를 전달합니다. 소비자마다 처리 속도가 달라 버퍼가 필요하고, 같은 주문 ID의 이벤트는 생성된 순서대로 처리되어야 하며, 각 소비자는 자신에게 해당하는 이벤트만 받아야 합니다. MOST appropriate 구성은 무엇입니까?

- A. EventBridge custom event bus에 발행하고 rule로 세 대상에 라우팅합니다.
- B. SNS FIFO 토픽에 발행하고 소비자마다 SQS FIFO 큐를 구독시키며 subscription filter policy로 필터링합니다.
- C. SQS Standard queue 하나를 세 소비자가 함께 폴링합니다.
- D. SNS Standard topic에 발행하고 SQS Standard queue 세 개를 구독시킵니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

순서 보장은 SQS FIFO 큐와 SNS FIFO 토픽에 있습니다. 소비자별 SQS 큐가 처리 속도 차이를 흡수하는 버퍼가 되고 SNS subscription filter policy로 소비자별 라우팅을 합니다. FIFO 토픽에서 필터링을 사용할 때 메시지 속성과 본문 조건을 설계하고 message group ID를 주문 ID처럼 업무 키로 정합니다.

- A가 틀린 이유: EventBridge는 순서를 보장하지 않고 기본 archive 미설정 경로는 소비자 속도 차이를 흡수하는 버퍼가 되지 않습니다. archive replay를 켜도 소비자별 처리 큐를 대신하지 않습니다.
- C가 틀린 이유: 하나의 큐를 여러 소비자가 폴링하면 각 메시지가 한 소비자에게만 전달되고 SQS 자체에는 소비자별 콘텐츠 라우팅 기능이 없습니다.
- D가 틀린 이유: Standard 토픽과 Standard 큐는 순서를 보장하지 않습니다.

</details>

**Q8.** 주문 취소 워크플로를 만듭니다. 환불 API 호출은 멱등하지 않고, 중간에 담당자 승인이 필요해 최대 3일까지 대기할 수 있으며 승인 결과는 callback으로 돌아옵니다. 감사팀은 개별 실행 이력을 콘솔에서 시각적으로 확인할 수 있기를 요구합니다. MOST appropriate 선택은 무엇입니까?

- A. Step Functions Asynchronous Express 워크플로
- B. Step Functions Synchronous Express 워크플로
- C. Express 워크플로와 Lambda 폴링 조합
- D. Step Functions Standard 워크플로

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

Standard 워크플로는 최대 1년 실행, exactly-once 실행 보장, API로 90일까지 조회 가능한 실행 이력과 콘솔 시각 디버깅을 제공합니다. `.sync`와 `.waitForTaskToken`을 포함한 service integration을 지원해 비멱등 환불과 사람 승인 callback 조건을 함께 만족합니다.

- A가 틀린 이유: Express는 최대 5분이고 Asynchronous Express는 at-least-once라 비멱등 환불에 부적합합니다. Step Functions가 실행 이력을 보관하지 않아 CloudWatch Logs도 별도로 필요합니다.
- B가 틀린 이유: Synchronous Express는 at-most-once이고 역시 5분 상한이 걸립니다.
- C가 틀린 이유: Express는 `.waitForTaskToken` callback 패턴을 지원하지 않고 5분 상한을 폴링으로 우회할 수 없습니다.

</details>

**Q9.** 모놀리스 안 깊숙한 요금 계산 컴포넌트를 별도 서비스로 분리하려 합니다. 이 컴포넌트는 HTTP 진입점이 아니라 모놀리스 내부에서 직접 호출되고 상위 모듈 여러 개가 의존합니다. 검증 기간 동안 신구 구현을 나란히 호출해 결과를 비교한 뒤 전환하려 합니다. MOST appropriate 패턴은 무엇입니까?

- A. decompose by subdomain으로 전체 모놀리스를 재작성합니다.
- B. strangler fig을 적용합니다.
- C. branch by abstraction을 적용합니다.
- D. 모놀리스 앞에 API Gateway를 두고 route를 새 서비스로 전환합니다.

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

branch by abstraction은 모놀리스 경계에서 호출을 가로챌 수 없고 upstream dependency가 있는 깊은 컴포넌트를 현대화할 때 적합합니다. 대상 식별, abstraction layer 생성, 기존 클라이언트 전환, 모놀리스 밖 새 구현 작성, abstraction 전환, 구 구현 정리의 여섯 단계로 진행하며 중간에 신구 구현을 비교하는 fallback을 만들 수 있습니다.

- A가 틀린 이유: decompose by subdomain은 모듈 경계가 이미 명확한 모놀리스에 적용하는 분리 방식이고 요구는 컴포넌트 하나의 분리입니다.
- B가 틀린 이유: strangler fig의 부적합 조건이 백엔드 요청을 가로채 라우팅할 수 없는 시스템입니다. 내부 직접 호출은 proxy가 볼 수 없습니다.
- D가 틀린 이유: API Gateway route 전환은 strangler fig의 구현 형태이며 내부 호출 경로에는 적용되지 않습니다. proxy가 단일 장애점이 될 위험도 있습니다.

</details>

**Q10.** 온프레미스 애플리케이션 두 개가 AMQP 1.0 브로커로 통신합니다. 두 애플리케이션을 6주 안에 EC2로 rehost해야 하고 메시징 관련 코드는 변경할 수 없습니다. 규정상 메시지를 30일 동안 보존해야 합니다. MOST appropriate 선택은 무엇입니까?

- A. Amazon EventBridge
- B. Amazon MQ
- C. Amazon SQS Standard queue
- D. Amazon MSK

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Amazon MQ는 AMQP 같은 브로커 프로토콜 의존성을 유지하면서 큰 payload와 장기 보존을 제공하는 경로입니다. 애플리케이션이 AWS SDK로 다시 작성되지 않아도 되므로 6주 rehost와 30일 보존 조건을 함께 검토할 수 있습니다.

- A가 틀린 이유: EventBridge 기본 bus는 archive를 설정하지 않으면 장기 보존하지 않으며, archive를 설정해도 AMQP 브로커 endpoint를 제공하지 않습니다.
- C가 틀린 이유: SQS는 AWS API를 사용하므로 AMQP 클라이언트 코드를 바꿔야 하고 메시지 보존 최대치가 14일입니다.
- D가 틀린 이유: MSK는 Kafka 프로토콜을 제공하므로 AMQP 클라이언트가 코드 변경 없이 접속할 수 없습니다.

</details>

---

## 14. Reference

- [AWS Prescriptive Guidance - Strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/strangler-fig.html)
- [AWS Prescriptive Guidance - Branch by abstraction pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/branch-by-abstraction.html)
- [AWS Prescriptive Guidance - Decompose by subdomain](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/decompose-subdomain.html)
- [AWS Migration Hub Refactor Spaces - How it works](https://docs.aws.amazon.com/migrationhub-refactor-spaces/latest/userguide/how-it-works.html)
- [AWS Migration Hub Refactor Spaces - Availability change](https://docs.aws.amazon.com/migrationhub-refactor-spaces/latest/userguide/migrationhub-availability-change.html)
- [AWS App Runner - Availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)
- [AWS Containers decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/choosing-aws-container-service.html)
- [AWS Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [Amazon ECS - AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [Amazon ECS - Fargate tasks and services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html)
- [Amazon ECS - Fargate task storage](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-storage.html)
- [Amazon EKS - AWS Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)
- [AWS databases decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/databases-on-aws-how-to-choose.html)
- [Amazon Aurora Serverless v2 requirements](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.requirements.html)
- [Amazon Aurora Serverless v2](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html)
- [Amazon DynamoDB item and attribute sizes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html)
- [Amazon SNS, SQS, and EventBridge decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/sns-or-sqs-or-eventbridge.html)
- [Amazon SQS message quotas](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-messages.html)
- [Amazon EventBridge quotas](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-quota.html)
- [Amazon EventBridge PutEvents](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-putevents.html)
- [Amazon EventBridge archive and replay](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-archive.html)
- [AWS Step Functions workflow types](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [AWS application integration decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/application-integration-on-aws-how-to-choose.html)
- [AWS Storage Gateway Volume Gateway](https://docs.aws.amazon.com/storagegateway/latest/vgw/WhatIsStorageGateway.html)
- [Amazon EBS features](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-features.html)
- [Amazon EFS features](https://docs.aws.amazon.com/efs/latest/ug/whatisefs.html)
- [Amazon FSx for Windows File Server](https://docs.aws.amazon.com/fsx/latest/WindowsGuide/what-is.html)
- [Elastic Beanstalk platform retirement schedule](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/platforms-schedule.html)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
