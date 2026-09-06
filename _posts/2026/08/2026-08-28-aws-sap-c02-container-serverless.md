---
title: "SAP-C02 박살내기 6 - 컨테이너와 서버리스"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, ecs, eks, fargate, lambda, api-gateway, appsync, containers, serverless]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-28 10:00:00 +0900
---

ECS on EC2에서 돌던 서비스를 Fargate로 옮기면서 비용을 줄이려고 Spot을 섞으려 하면, 태스크 정의를 아무리 뒤져도 Spot을 켜는 자리가 나오지 않습니다. `CreateService` 요청의 `launchType`에는 `EC2`, `FARGATE`, `EXTERNAL`, `MANAGED_INSTANCES` 네 값만 있고 Spot이라는 값이 없기 때문입니다. Fargate Spot은 launch type이 아니라 `FARGATE_SPOT`이라는 capacity provider이고, capacity provider를 쓰려면 `capacityProviderStrategy`를 지정해야 하며, 그 필드를 쓰는 순간 `launchType`은 아예 생략해야 합니다. 두 필드는 상호 배타입니다.

여기서 한 번 더 막힙니다. 온디맨드 2태스크를 최소로 깔고 나머지를 Spot으로 채우려고 두 provider에 각각 `base`를 주면 요청이 거부됩니다. `base`는 strategy 안에서 하나의 provider만 가질 수 있고, 나머지 배분은 전부 `weight` 비율입니다. 그리고 그 `weight`를 전부 0으로 두면 `RunTask`와 `CreateService`가 실패합니다.

SAP-C02 Domain 2에서 컨테이너와 서버리스 문항이 갈리는 곳이 이 층입니다. ECS와 Lambda가 무엇인지 아는 것으로는 선지가 좁혀지지 않습니다. 선지를 자르는 것은 조합 규칙과 하드 리밋입니다. Fargate가 받아주는 CPU와 메모리 조합, Lambda 함수 타임아웃 900초, API Gateway 통합 타임아웃 기본 29초, Service Connect가 동작하지 않는 네트워크 모드, ECR 복제가 옮기지 않는 것 같은 값들이 답을 하나로 만듭니다.

> **TL;DR**  
> - Fargate 태스크는 정해진 CPU와 메모리 조합표 안에서만 등록된다. 4 vCPU는 8 GB에서 30 GB까지이고 64 GB를 쓰려면 16 vCPU를 사야 한다.  
> - `launchType`과 `capacityProviderStrategy`는 상호 배타다. Fargate Spot은 후자로만 쓴다. `base`는 strategy 안에서 provider 하나만 가진다.  
> - Service Connect는 `bridge`와 `awsvpc`에서 동작하고 `host`에서는 동작하지 않는다. 태스크별 security group은 `awsvpc`가 전제다.  
> - ECR 복제는 규칙 설정 이후에 push되거나 restore된 것만 옮기고, 전이되지 않으며, lifecycle policy와 repository policy를 함께 옮기지 않는다.  
> - EKS에서 Windows와 custom CNI와 launch template 부트스트랩은 managed node group과 self-managed node에서 가능하다. Auto Mode는 셋 다 지원하지 않는다.  
> - Lambda 함수 타임아웃 900초는 조정할 수 없다. API Gateway 통합 타임아웃 기본 29초는 Regional과 private REST API만 증설을 요청할 수 있고, HTTP API는 30초로 고정된다.  
> - 계정 동시성 1,000에서 함수 레벨로 예약할 수 있는 총량은 900이다. Lambda가 미예약 함수용 100을 항상 남긴다.  
> - 동기 호출의 계정 rps 상한은 동시성 쿼터의 10배다. 짧은 함수는 동시성이 남아도 rps에서 먼저 막힌다.  
> - VPC에 붙이는 순간 기본 인터넷 접근이 사라진다. 퍼블릭 서브넷에 연결해도 퍼블릭 IP도 인터넷 경로도 생기지 않는다.  
> - SnapStart는 발행된 버전과 alias에서만 동작하고 provisioned concurrency와 함께 쓸 수 없다.  
> - API key, usage plan, per-client throttling, WAF, resource policy, 캐싱은 REST API 전용이다. HTTP API에는 하나도 없다.  
{: .prompt-info}

---

## 1. 같은 요청 경로를 다섯 가지로 구현하면 무엇이 달라지는가

HTTP 요청 하나를 받아 처리하고 응답하는 동일한 기능을 EC2, ECS on EC2, Fargate, Lambda, API Gateway와 Lambda 조합으로 각각 구현할 수 있습니다. 기능은 같지만 각 경로가 가진 상한과 배포 단위가 다르고, 시험 문항은 요구사항 하나를 이 표의 어느 칸에 걸어 답을 확정합니다.

| 축 | EC2 직접 | ECS on EC2 | ECS Fargate | ALB와 Lambda | API Gateway와 Lambda |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 실행 시간 상한 | 없다 | 없다 | 없다 | 900초 | 900초에 API Gateway 통합 타임아웃 기본 29초가 겹친다 |
| 요청 payload 상한 | 애플리케이션이 정한다 | 애플리케이션이 정한다 | 애플리케이션이 정한다 | 요청과 응답 각 1 MB | API Gateway 10 MB, Lambda 동기 호출 각 6 MB |
| 확장 단위 | 인스턴스 | 태스크와 컨테이너 인스턴스 | 태스크 | 실행 환경 | 실행 환경 |
| 확장 속도 제약 | ASG 정책과 부팅 시간 | ASG 정책과 태스크 기동 | 태스크 기동 | 10초에 실행 환경 1,000개 | 같음 |
| 콜드 스타트 | 없다 | 없다 | 태스크 기동 시간 | 있다 | 있다 |
| 네트워크 신원 | 인스턴스 ENI | 모드에 따라 다르다 | 태스크마다 ENI | Hyperplane ENI | Hyperplane ENI |
| CPU와 메모리 지정 | 인스턴스 타입 | 0.125에서 192 vCPU | 정해진 조합표 | 메모리만 지정하고 CPU는 비례 배분 | 같음 |
| OS 패치 책임 | 사용자 | 사용자 | AWS | AWS | AWS |
| 배포와 롤백 단위 | AMI와 인스턴스 | 태스크 정의 리비전 | 태스크 정의 리비전 | 함수 버전과 alias | 함수 버전과 alias, 스테이지 |
| 프라이빗 백엔드 접근 | VPC 안에 있다 | VPC 안에 있다 | VPC 안에 있다 | VPC 연결이 필요하다 | VPC link 또는 함수 VPC 연결 |
| 요청당 과금 | 없다 | 없다 | 없다 | 있다 | 있다 |

![API Gateway와 Lambda 경로에 겹친 두 개의 타임아웃 상한과, 실행 시간 상한이 없는 ALB와 ECS 경로를 나란히 놓은 비교](/assets/img/sap-c02/serverless-request-path-timeouts.webp)

같은 요청을 서버리스 경로와 컨테이너 경로로 각각 태웠을 때 어느 지점에 어떤 상한이 걸려 있는지를 나란히 놓은 그림입니다. 서버리스 경로에는 서로 다른 층에서 만들어지는 상한 두 개가 겹쳐 있고, 컨테이너 경로에는 실행 시간 상한 대신 용량과 패치와 스케일 정책을 직접 정해야 하는 책임이 있습니다.

이 표에서 문항으로 가장 자주 나오는 칸은 실행 시간 상한 줄입니다. 20분짜리 작업을 API Gateway와 Lambda로 만들면 기본 설정에서 두 번 잘립니다. 먼저 API Gateway가 통합 타임아웃 기본값인 29초에서 504를 돌려주고, 그 뒤에도 함수는 계속 돌다가 900초에서 강제 종료됩니다. Regional과 private REST API는 통합 타임아웃 quota 증설을 요청할 수 있지만 Lambda 함수의 900초 상한은 바뀌지 않습니다. 클라이언트는 504를 받았는데 결과 파일이 나중에 생기는 기묘한 증상이 여기서 나옵니다.

---

## 2. task definition이 태스크의 상한을 정하고 service가 유지 방식을 정한다

ECS에서 무엇을 어디에 적는지가 흔들리면 선지 해석이 흔들립니다. task definition은 태스크 한 개의 사양이고, service는 그 태스크를 몇 개, 어떤 방식으로 유지할지를 정합니다.

| 항목 | 적는 곳 | 값과 제약 |
| :--- | :--- | :--- |
| `networkMode` | task definition | 기본값은 `bridge`. Fargate는 `awsvpc` 필수 |
| task `cpu`와 `memory` | task definition | Fargate는 필수, EC2와 external은 선택. Windows 컨테이너에서는 무시된다 |
| `requiresCompatibilities` | task definition | `EC2`, `FARGATE`, `EXTERNAL`, `MANAGED_INSTANCES` |
| `ephemeralStorage` | task definition | Fargate에서 20 GiB에서 200 GiB |
| placement constraint | task definition과 실행 시점 | 합쳐서 태스크당 최대 10개 |
| `pidMode`와 `ipcMode` | task definition | Fargate Linux는 `pidMode`에 `task`만, `ipcMode`는 Fargate와 Windows에서 미지원 |
| `launchType` 또는 `capacityProviderStrategy` | service와 `RunTask` | 상호 배타 |
| `schedulingStrategy` | service | `REPLICA`와 `DAEMON`. Fargate는 `DAEMON` 불가 |
| `deploymentController` | service | 기본 `ECS`. 그 외 `CODE_DEPLOY`, `EXTERNAL` |
| desired count와 오토스케일링 | service와 Application Auto Scaling | ECS 자체 기능이 아니라 Application Auto Scaling이 수행한다 |

태그는 리소스당 최대 50개이고, Elastic Inference를 지정하는 `inferenceAccelerators`는 deprecated되어 신규 고객에게 제공되지 않습니다.

---

## 3. 네트워크 모드 네 가지가 갈리는 지점

EC2에 호스팅되는 태스크의 네트워크 모드는 `awsvpc`, `bridge`, `host`, `none`이고 Windows 전용 `default`가 따로 있습니다. 이 중 Linux와 Windows 양쪽을 지원하는 것은 `awsvpc` 하나뿐입니다.

| 모드 | 태스크의 네트워크 신원 | dynamic port mapping | Service Connect | 태스크별 security group | Windows |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `awsvpc` | 태스크마다 ENI와 private IP | 개념이 없다 | 동작한다 | 가능하다 | 지원한다 |
| `bridge` | 호스트 ENI를 공유한다 | 가능하다 | 동작한다 | 불가능하다 | 지원하지 않는다 |
| `host` | 호스트 네트워크 스택을 그대로 쓴다 | 불가능하다 | 동작하지 않는다 | 불가능하다 | 지원하지 않는다 |
| `none` | 외부 연결이 없다 | port mapping을 지정할 수 없다 | 대상이 아니다 | 불가능하다 | 지원하지 않는다 |

`host` 모드는 컨테이너가 `hostPort`를 명시해야 하고 한 호스트에서 같은 포트를 두 태스크가 쓸 수 없으므로, 같은 task definition의 태스크를 한 인스턴스에 여러 개 띄우지 못합니다. 한 인스턴스에 같은 서비스를 여러 개 올리면서 ALB에 붙이려면 `bridge` 모드의 dynamic port mapping을 씁니다.

성능만 보면 `host`와 `awsvpc`가 유리합니다. 두 모드는 가상화된 네트워크 스택 대신 EC2 네트워크 스택을 그대로 쓰기 때문입니다. 다만 `host`를 고르는 순간 Service Connect와 태스크별 security group을 둘 다 포기하게 되므로, 성능 요구와 이 두 요구가 함께 나오는 지문에서는 `awsvpc`가 답이 됩니다.

---

## 4. Fargate는 정해진 CPU와 메모리 조합에서만 태스크를 등록한다

Fargate에서 CPU와 메모리는 자유 값이 아니라 조합표입니다. 표 밖의 값을 쓰면 태스크 정의 등록 자체가 실패합니다.

| task CPU | 사용 가능한 메모리 |
| :--- | :--- |
| 256 (.25 vCPU) | 512 MiB, 1 GB, 2 GB |
| 512 (.5 vCPU) | 1 GB에서 4 GB, 1 GB 단위 |
| 1024 (1 vCPU) | 2 GB에서 8 GB, 1 GB 단위 |
| 2048 (2 vCPU) | 4 GB에서 16 GB, 1 GB 단위 |
| 4096 (4 vCPU) | 8 GB에서 30 GB, 1 GB 단위 |
| 8192 (8 vCPU) | 16 GB에서 60 GB, 4 GB 단위 |
| 16384 (16 vCPU) | 32 GB에서 120 GB, 8 GB 단위 |

8 vCPU 이상은 Linux platform version 1.4.0 이상이 필요합니다. Windows on Fargate가 지원하는 조합은 1024, 2048, 4096 세 가지뿐이므로 0.25와 0.5 vCPU, 그리고 8 vCPU 이상은 Linux 전용입니다.

이 표가 비용 문항으로 바뀌는 방식은 단순합니다. 메모리 64 GiB가 필요한 Java 서비스를 Fargate에 올리려면 16384(16 vCPU)를 골라야 하고, 실제로 필요한 CPU가 4 vCPU라도 나머지 12 vCPU분을 함께 냅니다. 같은 태스크를 EC2 launch type에 두면 task `cpu`를 128 CPU units(0.125 vCPU)에서 196,608 units(192 vCPU) 사이 아무 값으로나 지정할 수 있고, 메모리 최적화 인스턴스를 골라 CPU 대 메모리 비율을 맞춥니다.

Fargate와 EC2는 CPU를 배분하는 방식도 다릅니다. Fargate는 CPU shares로 나누고, EC2는 cgroup의 CPU period와 quota로 hard limit을 겁니다.

ephemeral storage는 platform version 1.4.0 이상에서 최소 20 GiB이고 `ephemeralStorage`로 최대 200 GiB까지 늘립니다. 컨테이너 이미지가 이 공간을 함께 쓰므로 실제로 애플리케이션이 쓸 수 있는 양은 이미지 크기만큼 줄어듭니다. 2020년 5월 28일 이후 기동된 1.4.0 이상 태스크의 ephemeral storage는 AES-256으로 암호화되고 기본 키는 AWS owned key이며 customer managed key로 바꿀 수 있습니다.

---

## 5. launchType과 capacityProviderStrategy는 함께 지정할 수 없다

용량을 지정하는 방법은 두 가지이고, 둘 중 하나만 씁니다. 어느 쪽도 지정하지 않으면 클러스터의 `defaultCapacityProviderStrategy`가 적용됩니다.

![RunTask 호출이 launchType과 capacityProviderStrategy 중 하나로 갈라지고, strategy 경로에서 base를 먼저 채운 뒤 나머지를 weight로 나누는 순서](/assets/img/sap-c02/ecs-capacity-provider-placement.webp)

용량 지정이 두 갈래로 나뉘는 지점과, strategy 쪽에서 태스크가 실제로 배치되는 순서를 담은 그림입니다. `base`와 `weight`가 각각 어떤 범위를 갖고 어떤 값에서 호출이 실패하는지도 함께 적어 두었습니다.

Fargate capacity provider는 `FARGATE`와 `FARGATE_SPOT` 두 개이고 모든 계정에서 쓸 수 있어 클러스터에 연결만 하면 됩니다. ASG capacity provider는 `CreateClusterCapacityProvider`로 미리 만들어야 하고 `ACTIVE`나 `UPDATING` 상태여야 strategy에 들어갑니다.

| 파라미터 | 기본값 | 범위 | 동작 |
| :--- | :--- | :--- | :--- |
| strategy의 provider 수 | 없음 | 최대 20 | 하나 이상 필요하다 |
| `base` | 0 | 0에서 100,000 | strategy 안에서 하나의 provider만 정의한다 |
| `weight` | 0 | 0에서 1,000 | 0인 provider에는 배치되지 않고 전부 0이면 호출이 실패한다 |

배치 순서는 `base`를 먼저 채우고 남은 태스크를 `weight` 비율로 나누는 것입니다. `FARGATE_SPOT`은 여유 컴퓨트를 할인 요금으로 쓰고 AWS가 용량을 회수할 때 2분 경고 후 태스크가 중단되며, Linux X86_64는 platform version 1.3.0 이상, Linux ARM64는 1.4.0 이상이 필요합니다.

`PutClusterCapacityProviders`는 클러스터의 provider 목록을 통째로 덮어씁니다. 새 provider 하나를 추가하려고 그것만 넘기면 기존 provider가 전부 분리되고, 태스크가 사용 중인 provider는 분리되지 않아 호출이 실패합니다. 기본 strategy를 없애려면 빈 배열을 명시해야 합니다.

ASG capacity provider의 managed scaling은 ECS 관리형 CloudWatch 메트릭에 target tracking 정책을 걸어 ASG를 조정합니다.

| 항목 | 기본값 | 범위 |
| :--- | :--- | :--- |
| `targetCapacity` | 100(여유 용량 0) | 1에서 100 퍼센트 |
| `minimumScalingStepSize` | 1 | 1에서 10,000 |
| `maximumScalingStepSize` | 10,000 | 1에서 10,000 |
| `instanceWarmupPeriod` | 300초 | 0에서 10,000 |

managed termination protection은 기본이 off이고, 켜려면 managed scaling이 함께 켜져 있어야 하며 ASG와 그 안의 각 인스턴스에도 scale-in instance protection이 켜져 있어야 합니다. 셋 중 하나라도 빠지면 태스크가 도는 인스턴스가 축소 대상이 됩니다.

---

## 6. ECS service auto scaling은 배포 중에 scale-in만 멈춘다

ECS 서비스의 desired count를 자동으로 조정하는 것은 ECS 자체 기능이 아니라 Application Auto Scaling입니다. 지원하는 정책은 target tracking, step scaling, scheduled action, predictive scaling 네 가지입니다.

ECS는 1분 간격으로 CloudWatch에 메트릭을 보내고, 메트릭이 아직 존재하지 않는 새 서비스에는 알람을 만들 수 없습니다. 최소 용량을 0으로 두면 태스크 수가 0까지 줄어듭니다.

배포가 진행되는 동안의 동작이 문항이 됩니다. ECS 배포 중에 Application Auto Scaling은 scale-in을 중단하고 scale-out은 계속합니다. 배포 중 트래픽이 몰려도 용량은 늘어나되, 배포로 태스크가 교체되는 동안 축소로 인해 용량이 흔들리지 않게 하려는 동작입니다. 이 동작은 `EXTERNAL` 배포 컨트롤러를 쓰는 서비스에는 적용되지 않습니다. 배포 중 scale-out까지 막고 싶으면 `register-scalable-target`에서 `DynamicScalingInSuspended`와 `DynamicScalingOutSuspended`를 둘 다 true로 둡니다.

---

## 7. 서비스 간 연결 세 가지가 네트워크 모드에서 갈린다

ECS가 제공하는 서비스 간 연결 수단은 Service Connect, Cloud Map 기반 service discovery, VPC Lattice 세 가지입니다. 외부 인터넷에서 들어오는 트래픽에는 ELB를 권장하고, 서비스 사이 호출의 기본 권장 수단으로 문서가 명시한 것은 Service Connect입니다.

| 축 | Service Connect | service discovery | VPC Lattice |
| :--- | :--- | :--- | :--- |
| 네트워크 모드 | `bridge`, `awsvpc` | `bridge`, `awsvpc`, `host` | 세 모드 모두 |
| `host` 모드 | 동작하지 않는다 | 동작하지만 클라이언트가 SRV 레코드를 이해해야 한다 | 동작한다 |
| 재시도와 메트릭 | ECS가 관리하는 프록시가 제공한다 | 애플리케이션이 직접 구현한다 | 서비스 네트워크가 제공한다 |
| 엔드포인트 갱신 | 배포로 클라이언트 태스크를 교체해 반영한다 | DNS TTL 만료를 기다린다 | 서비스 네트워크가 관리한다 |
| 홉 | 프록시 한 단계가 추가된다 | 컨테이너 사이 직결이라 지연이 낮다 | 서비스 네트워크를 경유한다 |
| 범위 | 같은 리전 안에서 다른 클러스터와 다른 VPC까지 | Cloud Map 네임스페이스 범위 | 서비스 네트워크 범위 |

service discovery의 구조적 약점은 DNS TTL입니다. 레코드가 갱신되고 나서 캐시가 만료되기까지 사이에 이미 사라진 컨테이너 주소로 요청이 갈 수 있고, 재시도와 나쁜 백엔드를 무시하는 로직을 애플리케이션이 직접 넣어야 합니다. Service Connect는 클라이언트 태스크를 교체해 설정을 갱신하는 방식이라 같은 문제를 배포 절차 안으로 옮깁니다. 대신 프록시 홉이 하나 늘어 지연이 조금 붙습니다.

지문이 "배포 직후 사라진 컨테이너로 요청이 간다", "계측 코드 없이 서비스 간 지연과 오류율을 본다", "서비스마다 다른 security group"을 함께 요구하면 답은 `awsvpc` 전환과 Service Connect 조합입니다. `host` 모드를 유지한 채로는 두 요구 모두 성립하지 않습니다.

---

## 8. ECS 배포 컨트롤러 두 갈래와 전략 이름

ECS의 배포 경로는 `deploymentController` 값으로 갈립니다. 기본값은 `ECS`이고 `CODE_DEPLOY`와 `EXTERNAL`이 따로 있습니다. 두 경로 중 어느 쪽이 다른 쪽을 대체한 것이 아니라 병존합니다.

| 축 | `ECS` 컨트롤러 | `CODE_DEPLOY` 컨트롤러 |
| :--- | :--- | :--- |
| 트래픽 전환 주체 | ECS가 직접 수행한다 | CodeDeploy가 task set 두 벌을 두고 전환한다 |
| 전략 | `ROLLING`(기본), `BLUE_GREEN`, `LINEAR`, `CANARY` | `CodeDeployDefault.ECS*` 사전 정의 구성과 커스텀 |
| 검증 훅 | Lambda lifecycle hook과 pause point | CodeDeploy hook과 테스트 리스너 |
| 필요 조건 | `BLUE_GREEN`은 ALB, NLB, Service Connect 중 하나. `LINEAR`와 `CANARY`는 ALB나 Service Connect | ALB나 NLB, target group 2개, 리스너 최대 2개 |
| NLB 제약 | 트래픽 전환 단계마다 10분이 추가된다 | `ECSAllAtOnce`만 지원한다 |
| 스케줄링 전략 | `REPLICA`와 `DAEMON` | `REPLICA` 필수 |

`ECS` 컨트롤러의 blue/green에서 bake time은 프로덕션 트래픽이 green으로 넘어간 뒤에도 blue와 green이 함께 떠 있는 기간입니다. 이 기간에는 blue가 살아 있으므로 롤백이 빠른 대신 리소스 사용량이 일시적으로 두 배가 될 수 있습니다. NLB를 쓰면 `TEST_TRAFFIC_SHIFT`와 `PRODUCTION_TRAFFIC_SHIFT` 단계에 각각 10분이 더 붙습니다.

lifecycle hook은 Lambda 함수이거나 pause point입니다. pause hook은 배포를 멈추고 `ContinueServiceDeployment` 호출을 기다리므로 수동 승인 게이트가 됩니다.

로드밸런서나 Service Connect를 쓰는 서비스는 ECS가 트래픽 전환을 직접 수행하고, headless 서비스는 blue 태스크를 green으로 교체만 하고 트래픽 전환을 관리하지 않습니다.

CodeDeploy 사전 정의 구성 이름은 그대로 선지에 나옵니다.

| 대상 | 사전 정의 구성 |
| :--- | :--- |
| ECS | `CodeDeployDefault.ECSLinear10PercentEvery1Minutes`, `ECSLinear10PercentEvery3Minutes`, `ECSCanary10Percent5Minutes`, `ECSCanary10Percent15Minutes`, `ECSAllAtOnce` |
| Lambda | `CodeDeployDefault.LambdaCanary10Percent5Minutes`, `LambdaCanary10Percent10Minutes`, `LambdaCanary10Percent15Minutes`, `LambdaCanary10Percent30Minutes`, `LambdaLinear10PercentEvery1Minute`, `LambdaLinear10PercentEvery2Minutes`, `LambdaLinear10PercentEvery3Minutes`, `LambdaLinear10PercentEvery10Minutes`, `LambdaAllAtOnce` |

canary는 첫 증분 10퍼센트를 보낸 뒤 지정한 시간이 지나면 나머지 90퍼센트를 한 번에 넘기고, linear는 10퍼센트씩 반복해서 넘깁니다. NLB 뒤 ECS 서비스는 `ECSAllAtOnce`만 지원하므로 점진 전환이 요구사항이면 ALB나 Service Connect가 전제입니다. CloudFormation의 blue/green 경로에서는 커스텀 canary와 linear 구성을 만들 수 없습니다.

Lambda 쪽 롤백 단위는 함수 버전과 alias입니다. alias에 두 버전의 가중치를 두어 트래픽을 나누고, CodeDeploy가 그 가중치를 위 구성 이름대로 옮깁니다.

---

## 9. ECS Anywhere에서 사라지는 기능들

ECS Anywhere는 온프레미스나 다른 환경의 인스턴스를 ECS 클러스터에 등록해 `EXTERNAL` launch type으로 태스크를 돌리는 방식입니다. control plane은 AWS 리전의 ECS를 그대로 씁니다. 등록된 인스턴스에는 `ecs.capability.external` 속성이 붙어 task placement constraint로 쓸 수 있습니다.

외부 인스턴스에서 지원되지 않는 것이 문항의 재료입니다.

- service load balancing
- service discovery
- `awsvpc` 네트워크 모드. `bridge`, `host`, `none`만 가능하다
- capacity provider
- EFS 볼륨(`EFSVolumeConfiguration`)
- App Mesh 통합
- SELinux
- `UpdateContainerAgent` API

문서는 ECS Anywhere가 outbound 트래픽을 만들거나 데이터를 처리하는 워크로드에 맞고, inbound가 필요한 웹 서비스에는 ELB를 지원하지 않아 비효율적이라고 직접 명시합니다. 온프레미스 웹 서비스를 ALB 타깃 그룹에 넣는 선지는 여기서 걸러집니다.

자격 증명은 SSM Agent가 hardware fingerprint를 기준으로 30분마다 회전하고, 연결이 끊겼다가 복구되면 자동으로 갱신합니다. 필요한 엔드포인트는 `ecs-a-*`, `ecs-t-*`, `ecs`, `ssm`, `ec2messages`, `ssmmessages`입니다.

2026년 8월 7일부터 Windows Server 전 버전과 Amazon Linux 2, RHEL 7과 8, Debian 전 버전이 지원 목록에서 빠졌습니다. 현재 지원 OS는 Amazon Linux 2023, Ubuntu 20과 22와 24, RHEL 9이고 x86_64와 ARM64를 지원합니다.

---

## 10. ECR 복제가 하지 않는 일

ECR private registry는 cross-Region과 cross-account 복제를 모두 지원합니다. DR 리전 확보 문항에서 답을 가르는 것은 복제가 무엇을 하느냐가 아니라 무엇을 하지 않느냐입니다.

| 질문 | 답 |
| :--- | :--- |
| 기존 이미지가 복제되는가 | 복제되지 않는다. 규칙 설정 이후 push되거나 restore된 콘텐츠만 대상이다 |
| 복제가 전이되는가 | 전이되지 않는다. A에서 B, B에서 C 규칙을 걸어도 A의 이미지는 B까지만 간다 |
| 리포지토리 이름을 바꿀 수 있는가 | 바꿀 수 없다 |
| repository policy와 lifecycle policy가 함께 복제되는가 | 복제되지 않는다. repository creation template로 목적지에 적용한다 |
| 삭제가 전파되는가 | 전파되지 않는다. 소스에서 지워도 목적지 사본은 남는다 |
| partition을 넘을 수 있는가 | 넘을 수 없다. us-west-2에서 cn-north-1로 복제하지 못한다 |
| 소요 시간이 보장되는가 | 보장되지 않는다. 대부분 30분 이내라는 서술이 있을 뿐이다 |

cross-account 복제에 필요한 정책은 목적지 계정의 registry permissions policy 하나뿐입니다. 소스 계정이 `ecr:ReplicateImage`와 `ecr:CreateRepository`를 수행하도록 허용하면 되고, 소스 리포지토리에는 어떤 정책도 필요 없습니다. `ecr:CreateRepository`를 허용하지 않으면 목적지에 같은 이름의 리포지토리를 미리 만들어 두어야 합니다.

복제 설정 상한은 규칙 최대 10개, 전체 규칙에 걸친 고유 목적지 최대 25개, 규칙당 필터 최대 100개입니다. 필터는 리포지토리 prefix로 겁니다. 양쪽 계정이 대상 리전에 opt-in 되어 있어야 하고, tag immutability가 켜진 목적지에 같은 태그의 이미지가 오면 이미지는 복제되되 태그가 붙지 않아 untagged 상태로 남을 수 있습니다.

이미지 취약점 스캔은 이 편의 범위가 아니라 Amazon Inspector 쪽 주제입니다.

---

## 11. EKS가 Pod를 올릴 수 있는 컴퓨트 다섯 가지

EKS 클러스터가 Pod를 스케줄할 수 있는 대상은 EKS Auto Mode managed node, self-managed node, managed node group, Fargate, Hybrid Nodes입니다. hybrid node를 제외한 노드는 클러스터를 만들 때 지정한 서브넷과 같은 VPC 안에 있어야 하고, 같은 서브넷일 필요는 없습니다.

![Windows와 custom CNI 요구가 managed node group으로, 노드 운영 위임이 Auto Mode로, Pod별 VM 격리가 Fargate로, 온프레미스 하드웨어가 Hybrid Nodes로 이어지는 갈림](/assets/img/sap-c02/eks-compute-option-split.webp)

포기할 수 없는 요구 하나가 컴퓨트 선택을 확정하는 구조를 담은 그림입니다. 네 갈래 각각에 그 선택지가 못 하는 것을 함께 적어 두었습니다.

managed node group 열에서 지원되는 항목은 다음과 같습니다. self-managed node도 같은 기능을 지원하지만 노드 운영을 직접 맡습니다. Local Zone은 managed node group뿐 아니라 Auto Mode도 지원합니다.

일반 `eks-compute.html` 비교표에는 Local Zone이 Auto Mode 미지원으로 남아 있지만, 별도의 Auto Mode Local Zone 가이드와 release note는 NodeClass와 NodePool을 Local Zone subnet에 배치하는 경로를 명시합니다. 이 글은 기능별 최신 가이드를 기준으로 Local Zone을 지원으로 정리합니다.

- Windows 컨테이너
- Local Zone 배포
- custom AMI와 custom CNI
- launch template로 부트스트랩 인자 전달
- Pod별 VPC security group(Linux 전용)
- EC2 dedicated host

Auto Mode는 Windows, custom CNI와 launch template 부트스트랩을 지원하지 않습니다. 지문에 표준 CNI 플러그인 설치나 커널 파라미터 조정 스크립트나 Windows 컨테이너가 하나라도 등장하고 AWS 관리형 노드 운영을 원하면 managed node group을 고릅니다. self-managed node도 기능상 가능하지만 운영 책임이 사용자에게 있습니다.

데이터 볼륨은 또 다른 갈림입니다. managed node group과 Auto Mode는 EBS, EFS, S3 Files, FSx for Lustre CSI를 모두 쓸 수 있고, Hybrid Nodes는 이 네 가지를 전부 쓸 수 없으며 NLB도 target type `ip`만 지원합니다.

---

## 12. EKS Auto Mode가 흡수하는 것과 포기하는 것

Auto Mode는 노드 운영을 AWS 쪽으로 넘기는 대신 커스터마이즈 여지를 줄이는 선택입니다.

Auto Mode가 적용하는 것은 Karpenter 기반 오토스케일링, Bottlerocket 계열 immutable AMI(SELinux enforcing과 read-only root filesystem), SSH와 SSM 직접 접근 차단, 노드 최대 수명 21일 후 자동 교체입니다. 수명은 더 짧게 줄일 수 있습니다.

Auto Mode가 core component로 흡수해 별도 add-on 설치가 필요 없어지는 것은 다음과 같습니다.

- 컴퓨트 오토스케일링
- Pod와 Service 네트워킹, network policy
- ELB 연동
- 클러스터 DNS
- EBS 블록 스토리지
- GPU 플러그인
- Pod Identity Agent

기본 NodePool과 NodeClass는 편집하지 않고, 조정이 필요하면 별도 NodePool과 NodeClass를 추가합니다. Spot 선택, 워크로드 격리, ephemeral storage의 IOPS와 크기와 처리량 조정이 이 경로로 들어갑니다.

| 축 | Auto Mode | managed node group |
| :--- | :--- | :--- |
| 스케일링 | Karpenter 기반으로 unschedulable Pod를 감지해 노드를 만든다 | ASG 기반. Cluster Autoscaler나 Karpenter를 따로 설치한다 |
| 노드 접근 | SSH와 SSM 차단 | SSH 가능 |
| 노드 수명 | 최대 21일 후 자동 교체 | 사용자가 관리한다 |
| custom AMI와 CNI | 불가 | launch template로 가능 |
| Windows | 불가 | 가능 |
| Pod별 security group(SGPP) | 불가. NodeClass의 별도 Pod 보안 그룹 방식은 가능 | 가능(Linux 전용) |
| Local Zone | 가능 | 가능 |

GPU와 Local Zone은 Auto Mode도 지원합니다. "Auto Mode는 GPU나 Local Zone을 못 쓴다"는 서술은 틀립니다. SGPP 방식의 Pod 보안 그룹과 Windows와 SSH 접근과 custom CNI는 지원되지 않습니다.

---

## 13. EKS Fargate에서 못 하는 것들

EKS Fargate는 Pod마다 전용 커널을 갖는 VM 경계로 격리되는 대신 목록이 긴 제약을 받습니다.

불가능한 것은 DaemonSet, privileged container, `HostPort`와 `HostNetwork`, GPU, Arm, Windows, Bottlerocket, EBS 볼륨 mount, Fargate Spot, 그리고 Outposts와 Wavelength와 Local Zones 배포입니다.

가능한 것도 조건이 붙습니다. EFS는 자동 mount되지만 정적 프로비저닝만 되고 동적 PV 프로비저닝은 되지 않습니다. Pod별 security group을 지정할 수 있고 ALB와 NLB에 붙일 수 있지만 target type은 `ip`로 한정됩니다. Pod는 private subnet에만 뜨고 IMDS가 없어 IAM 자격 증명을 IRSA로 받습니다.

Pod가 Fargate에 뜨려면 Fargate profile에 매칭되어야 합니다. 매칭되는 profile이 없으면 Pod가 `Pending`에 머뭅니다. Fargate 노드에는 Amazon VPC CNI가 설치되고 대체 CNI를 쓸 수 없으며, Fargate 워커 노드는 버전 롤백이 지원되지 않습니다.

로그 수집 DaemonSet과 EBS PVC를 함께 요구하는 지문은 EKS Fargate를 배제합니다. 로그 수집은 사이드카로, 스토리지는 EFS 정적 프로비저닝으로 바꾸거나 노드 기반 컴퓨트로 옮겨야 합니다.

`eks-compute.html`의 컴퓨트 비교표는 managed node group과 Auto Mode와 Hybrid Nodes 세 열로 되어 있고 Fargate는 별도 페이지에 자체 비교표로 있습니다. Fargate 페이지에 deprecation 공지는 없지만, 기본 선택지로 제시하기보다 위 제약이 문제되지 않는 워크로드에 한정해 고르는 편이 안전합니다.

---

## 14. EKS Anywhere와 ECS Anywhere는 다른 층에 있다

이름이 비슷해서 같은 종류로 묶기 쉽지만 두 제품은 control plane의 위치가 다릅니다.

| 축 | ECS Anywhere | EKS Anywhere |
| :--- | :--- | :--- |
| control plane | AWS 리전의 ECS control plane을 그대로 쓴다 | 클러스터 전체를 사용자 인프라에 설치한다 |
| 기반 | ECS 에이전트와 SSM Agent | EKS Distro |
| 리전 연결 | 안정적인 리전 연결이 전제이고 필수 엔드포인트가 6종 있다 | AWS Cloud 연결 없이도, air-gapped 환경에서도 동작한다 |
| launch type | `EXTERNAL` | 해당 없음 |
| 로드밸런싱 | service load balancing 미지원 | 온프레미스 로드밸런서를 직접 구성한다 |
| 네트워크 모드 | `bridge`, `host`, `none` | Kubernetes CNI를 고른다 |

EKS Anywhere의 현재 주요 인프라 provider는 VMware vSphere, bare metal, Nutanix입니다. Docker provider는 개발 용도 전용입니다. AWS Snow provider는 현재 문서의 provider 목록과 설치 경로에 남아 있지만, v0.26.0부터 AWS Snowball Edge는 신규 고객에게 제공되지 않습니다. CloudStack provider는 v0.26.0에서 배포판에서 제거되었습니다. 따라서 신규 설계에서는 Snow의 신규 사용 가능 여부와 CloudStack 제거를 나누어 판단해야 합니다. 오픈 소스라 사용 자체는 무료이고 지원과 큐레이션 패키지가 별도 구독입니다.

두 제품이 답을 가르는 기준은 리전 연결 가능 여부입니다. 리전과의 연결이 끊긴 상태에서도 워크로드를 계속 스케줄해야 한다면 ECS Anywhere는 후보에서 빠집니다.

---

## 15. Lambda 하드 리밋이 설계를 자르는 지점

Lambda 문항의 절반은 아래 수치 중 하나에 걸립니다.

| 항목 | 값 |
| :--- | :--- |
| 메모리 | 128 MB에서 10,240 MB, 1 MB 단위 |
| vCPU 환산 | 1,769 MB에서 1 vCPU 상당 |
| 함수 타임아웃 | 900초(15분). 조정 불가 |
| `/tmp` | 512 MB에서 10,240 MB, 1 MB 단위 |
| 배포 패키지 zip | 50 MB(직접 업로드), 압축 해제 250 MB. 더 크면 S3 경유 |
| 컨테이너 이미지 | 압축 해제 기준 10 GB |
| 동기 payload | 요청과 응답 각 6 MB |
| response streaming | 200 MB |
| 비동기 payload | 1 MB |
| request line과 header 합계 | 1 MB |
| layer | 5개 |
| 환경 변수 합계 | 4 KB |
| resource-based policy | 20 KB |
| 파일 디스크립터, 프로세스와 스레드 | 각 1,024 |
| 관리형 코드 스토리지 | 300 GB(압축 해제 기준), 증설 불가 |
| VPC당 ENI | 500개 기본, 증설 가능 |
| 실행 환경당 네트워크 대역폭 | 625 Mbps |
| 함수 스케일링 | 10초에 실행 환경 1,000개 |

메모리를 올리면 CPU가 비례해 배분되고 1,769 MB에서 1 vCPU 상당이 됩니다. 이 환산값은 강의 자료에 따라 2 vCPU로 적힌 경우가 있는데 현행 quotas 문서는 1 vCPU라고 명시합니다. 시험 지문에서 vCPU 환산이 나오면 1,769 MB 기준 1 vCPU로 계산합니다.

관리형 코드 스토리지 300 GB는 증설되지 않습니다. 함수와 버전이 쌓여 이 한도에 닿으면 오래된 버전을 지우거나 self-managed S3 code storage로 전환합니다.

VPC에 연결되지 않은 함수는 대역폭 증설을 요청할 수 있고, 승인되면 2,048 MB부터 메모리에 비례해 올라가 10,240 MB에서 최대 3,000 Mbps가 됩니다.

---

## 16. 동시성 세 층과 rps 상한

동시성은 세 층으로 되어 있고 각 층이 다른 것을 제한합니다.

![요청이 rps 게이트와 함수 동시성과 스케일 속도를 차례로 지나며, 각 게이트에서 429로 빠지는 경로와 provisioned 환경으로 가는 경로가 갈리는 구조](/assets/img/sap-c02/lambda-concurrency-gates.webp)

호출이 실제로 실행 환경에 도달하기까지 지나는 게이트 세 개와, 각 게이트에서 스로틀될 때 어떤 응답이 나가는지를 담은 그림입니다. provisioned 환경과 새 실행 환경이 갈리는 지점도 함께 표시했습니다.

| 층 | 기본값 | 성격 |
| :--- | :--- | :--- |
| 계정 동시성 | 리전별 1,000, 전 함수 합산 | soft limit이라 증설 가능하다 |
| reserved concurrency | 없음 | 함수에 할당하는 상한이자 하한. 추가 과금이 없다 |
| provisioned concurrency | 없음 | 사전 초기화된 실행 환경 수. 과금 대상이다 |

함수 레벨에서 예약할 수 있는 총량은 계정 한도에서 100을 뺀 값입니다. 기본 1,000이면 900이고, 계정 한도를 2,000으로 올리면 1,900이 됩니다. Lambda가 예약하지 않은 함수용으로 항상 100을 남기기 때문입니다. 중요한 함수 하나에 1,000을 통째로 예약하는 선지는 이 규칙에서 걸립니다.

reserved concurrency의 성격은 두 방향입니다. 예약한 만큼 다른 함수가 쓸 수 없고, 예약한 함수는 미예약 pool을 쓸 수 없습니다. 폭주하는 함수를 격리해 나머지 함수를 보호하는 수단이 여기서 나옵니다. 반대로 폭주 함수의 처리량을 늘리는 수단은 아닙니다.

provisioned concurrency는 reserved concurrency보다 크게 설정할 수 없습니다. 두 값을 같게 만들면 `$LATEST`가 쓸 동시성이 남지 않아 스로틀됩니다. 할당 속도는 함수당 분당 최대 6,000 실행 환경이고, 전부 할당될 때까지는 어떤 요청도 그 환경을 쓰지 못합니다.

rps 상한은 별도 축입니다. 동기 호출의 초당 요청 수 한계는 계정 동시성 쿼터의 10배이고 기본 1,000에서는 10,000 rps입니다. 평균 실행 시간이 100 ms 미만인 함수는 동시성이 남아도 rps에서 먼저 막힙니다. 평균 30 ms짜리 함수라면 동시성 1,000이 이론상 초당 33,000건을 감당할 것 같지만 실제로는 10,000 rps에서 스로틀됩니다.

스케일 속도는 리전별로도 함수별로도 10초당 실행 환경 1,000개입니다. 함수 단위 한계이므로 함수끼리는 서로 독립입니다.

---

## 17. 동기, 비동기, 스트림에서 재시도 주체가 다르다

같은 함수라도 어떻게 호출되느냐에 따라 실패를 누가 다시 시도하는지가 달라집니다. 이 차이가 실패 이벤트 보존과 멱등성 요구를 만드는 문항의 뼈대입니다.

![동기와 비동기와 스트림 세 경로가 각각 다른 재시도 주체와 다른 실패 포착 지점으로 이어지는 세 갈래](/assets/img/sap-c02/lambda-invocation-retry-paths.webp)

호출 모델 세 가지를 나란히 놓고 각 경로에서 재시도를 누가 수행하며 실패한 이벤트가 어디에 남는지를 담은 그림입니다.

| 축 | 동기 | 비동기 | 스트림 event source mapping |
| :--- | :--- | :--- | :--- |
| 호출 형태 | `RequestResponse` | `InvocationType=Event`, 202만 반환 | Lambda가 폴링해 배치로 넘긴다 |
| payload 상한 | 요청과 응답 각 6 MB | 1 MB | 배치 크기 설정에 따른다 |
| 함수 에러 재시도 | Lambda가 재시도하지 않는다 | 기본 2회. 1분 뒤, 다시 2분 뒤 | 배치 전체를 재시도한다 |
| 스로틀과 시스템 에러 | 호출자에게 429나 5xx를 전달한다 | 큐로 되돌려 기본 6시간까지 재시도한다 | 폴링이 계속된다 |
| 실패 포착 | 호출자 코드 | DLQ, on-failure destination | Iterator Age 감시, 실패 레코드 destination |
| 중복 | 호출자의 재시도에 좌우된다 | 큐가 eventually consistent라 중복 전달이 있다 | 배치 재시도로 중복이 생긴다 |

비동기 재시도의 간격은 두 종류가 다릅니다. 함수 에러는 1분과 2분 간격으로 두 번 다시 시도하고, 스로틀과 시스템 에러는 이벤트를 큐로 되돌려 1초에서 최대 5분까지 지수적으로 늘어나는 간격으로 최대 6시간까지 재시도합니다. 큐가 길어지면 Lambda가 큐를 읽는 속도를 줄입니다.

비동기 큐는 eventually consistent라 같은 이벤트를 여러 번 받을 수 있고, 함수가 처리 속도를 따라가지 못하면 전달 없이 삭제될 수도 있습니다. 멱등성은 애플리케이션 책임입니다. S3 이벤트 알림으로 함수가 호출되는 구성에서 "실패 이벤트를 보존해 재처리하고 중복 레코드를 막아야 한다"는 요구가 나오면, 답은 on-failure destination 설정과 애플리케이션 멱등 처리의 조합입니다. 한쪽만으로는 두 요구를 덮지 못합니다.

스트림 기반 event source mapping은 배치 단위로 실패를 처리합니다. 반복해서 실패하는 배치는 해당 샤드의 처리를 막으므로 Iterator Age 메트릭으로 정체를 감시합니다.

API Gateway와 Lambda의 동기 경로에서 API Gateway는 Lambda 함수를 재시도하지 않습니다. 함수 에러 응답은 상황에 따라 매핑됩니다. 호출 거부는 500, 함수 에러나 잘못된 응답 형식은 502와 일반화된 오류 응답으로 돌아올 수 있습니다. Lambda proxy 통합에서 정해진 `statusCode` 응답을 반환하거나, custom REST 통합에서 `IntegrationResponse`와 `selectionPattern`을 설정해야 오류 매핑을 제어할 수 있습니다.

---

## 18. VPC에 붙이는 순간 도달 범위가 바뀐다

VPC에 연결하지 않은 함수는 기본적으로 퍼블릭 인터넷에 접근합니다. VPC에 붙이면 그 VPC 안에서 도달 가능한 것만 접근할 수 있게 되고, 인터넷 접근이 필요하면 VPC 쪽에 경로를 따로 만들어야 합니다.

![VPC 미연결 함수가 퍼블릭 인터넷으로 바로 나가는 경로와, VPC 연결 함수가 Hyperplane ENI를 거쳐 프라이빗 RDS와 NAT gateway로 나뉘어 가는 경로](/assets/img/sap-c02/lambda-vpc-reachability.webp)

VPC 연결 여부에 따라 함수가 닿을 수 있는 대상이 어떻게 달라지는지를 담은 그림입니다. 퍼블릭 서브넷에 연결하면 인터넷으로 나갈 수 있다는 흔한 오해도 함께 표시했습니다.

**퍼블릭 서브넷에 연결해도 인터넷 접근이나 퍼블릭 IP가 생기지 않습니다.** 함수가 만드는 것은 Hyperplane ENI이고 이 ENI는 인터넷 게이트웨이로 직접 나가지 않습니다. 외부 API 호출이 필요하면 프라이빗 서브넷에 배치하고 NAT gateway를 경유하는 경로를 라우팅 테이블에 만듭니다. AWS 서비스 호출은 VPC endpoint로도 해결됩니다.

Hyperplane ENI는 subnet과 security group 조합당 하나가 만들어지고 같은 조합을 쓰는 다른 함수가 공유합니다. ENI 하나가 최대 65,000 connection 또는 port를 지원하고 초과하면 Lambda가 자동으로 ENI 수를 늘립니다.

수명 주기도 문항이 됩니다.

| 상태 | 언제 | 결과 |
| :--- | :--- | :--- |
| `Pending` | ENI 생성 중 | 함수를 호출할 수 없다. 수 분이 걸릴 수 있다 |
| `Inactive` | 14일 유휴 후 Lambda가 ENI를 회수 | 다음 호출이 실패하고 다시 `Pending`을 거친다 |
| VPC 설정 제거 | 제거 요청 후 | ENI 삭제까지 최대 20분이 걸린다 |

VPC 연결에는 `AWSLambdaVPCAccessExecutionRole` 수준의 EC2 권한이 execution role에 필요합니다. 이 권한은 함수 코드에도 암묵적으로 부여되므로, 문서는 `lambda:SourceFunctionArn` 조건을 쓴 Deny 정책으로 코드 쪽 사용만 막는 패턴을 권장합니다.

dedicated instance tenancy VPC에는 함수를 직접 연결할 수 없고 default tenancy VPC를 peering으로 경유해야 합니다. 배치를 조직 차원에서 강제하려면 `lambda:VpcIds`, `lambda:SubnetIds`, `lambda:SecurityGroupIds` 조건 키를 씁니다.

---

## 19. SnapStart가 성립하는 조건과 배제되는 조합

SnapStart는 초기화가 끝난 실행 환경의 스냅샷을 재사용해 콜드 스타트를 줄입니다. 지원 런타임은 Java 11 이상, Python 3.12 이상, .NET 8 이상이고 Node.js와 Ruby와 OS-only 런타임은 지원하지 않습니다.

함께 쓸 수 없는 것이 명확합니다.

- provisioned concurrency
- EFS
- S3 Files
- 512 MB를 넘는 ephemeral storage

동작 범위도 제한됩니다. **발행된 버전과 그 버전을 가리키는 alias에서만 동작하고 `$LATEST`에서는 쓰지 못합니다.** 콜드 스타트를 줄이려고 SnapStart를 켰는데 `$LATEST`를 호출하고 있으면 아무 효과가 없습니다.

비용은 런타임에 따라 갈립니다. Java 관리형 런타임에서는 추가 비용이 없고, 그 밖에는 스냅샷 캐싱 비용(최소 3시간 과금)과 복원 비용이 붙습니다. 유휴 시간이 대부분이면서 콜드 스타트를 줄여야 하고 상시 비용이 허용되지 않는 Java 워크로드는 SnapStart가 정답 자리에 앉는 대표 조건입니다.

주의할 부작용은 상태입니다. 초기화 단계에서 만든 고유값과 네트워크 연결은 스냅샷이 재사용되면서 깨지므로 핸들러 안에서 다시 만들어야 합니다. 초기화에서 생성한 난수 시드나 유일 식별자를 그대로 쓰면 여러 실행 환경이 같은 값을 갖게 됩니다.

---

## 20. REST API와 HTTP API는 기능 목록이 다르다

API Gateway 문항은 대부분 요구사항 하나가 REST API 전용 기능인지를 묻습니다.

| 축 | REST API | HTTP API |
| :--- | :--- | :--- |
| 엔드포인트 타입 | edge-optimized, Regional, Private | Regional만 |
| API key와 usage plan | 있다 | 없다 |
| per-client rate limiting | 있다 | 없다 |
| AWS WAF | 있다 | 없다 |
| resource policy | 있다 | 없다 |
| request validation과 body transformation | 있다 | 없다 |
| 응답 캐싱 | 있다 | 없다 |
| canary release deployment | 있다 | 없다 |
| X-Ray, execution log, Firehose 액세스 로그 | 있다 | 없다 |
| mock 통합, 클라이언트 인증서, custom gateway response | 있다 | 없다 |
| authorizer | IAM, Cognito, Lambda | IAM, JWT(Cognito 포함), Lambda |
| private 통합 | NLB와 ALB(VPC link V2). Cloud Map 불가 | NLB, ALB, Cloud Map |
| 배포 | 사용자가 배포한다 | 자동 배포 |
| mutual TLS | 지원한다 | 지원한다 |

파트너별 쿼터, 발급 키, 엣지에서의 SQL injection 차단, 응답 캐싱을 함께 요구하는 지문은 네 요구가 모두 REST API 전용이므로 답이 하나로 확정됩니다. "비용을 아끼려고 HTTP API로 옮기면서 usage plan을 유지한다"는 선지는 그래서 성립하지 않습니다.

반대로 Cloud Map 서비스를 private 통합 타깃으로 잡아야 하는 요구는 HTTP API로만 됩니다. private 엔드포인트 타입과 Cloud Map 타깃을 동시에 요구하는 지문이 나오면 어느 API 타입으로도 풀리지 않으므로 아키텍처 자체를 바꾸는 선지를 찾아야 합니다.

---

## 21. 엔드포인트 타입 세 가지가 custom domain과 헤더를 바꾼다

| 타입 | 진입 경로 | custom domain | HTTP 헤더 이름 |
| :--- | :--- | :--- | :--- |
| edge-optimized(REST 기본) | CloudFront POP를 경유한다 | 전 리전에 걸쳐 적용된다 | capitalize된다 |
| Regional | 배포 리전에서 직접 받는다 | 배포 리전에 종속된다 | 그대로 통과한다 |
| Private | VPC 안의 interface VPC endpoint를 통해서만 | 리전 안에서 적용된다 | 그대로 통과한다 |

Regional 엔드포인트의 custom domain은 리전에 종속되는 대신 같은 도메인 이름을 여러 리전에 두고 Route 53 latency-based routing과 조합할 수 있습니다. 리전 장애 시 다른 리전으로 넘기는 구성은 이 조합으로 만듭니다. edge-optimized의 custom domain은 전 리전에 걸쳐 적용되므로 이런 리전별 제어가 어렵습니다.

헤더 이름 처리 차이는 백엔드가 헤더 이름을 대소문자로 구분해 파싱할 때 문제가 됩니다. edge-optimized에서 Regional로 옮기고 나서 헤더 파싱이 깨지는 증상이 여기서 나옵니다.

Private API는 VPC 안의 interface VPC endpoint를 통해서만 접근할 수 있고, HTTP API는 Private 엔드포인트 타입을 지원하지 않습니다.

---

## 22. private integration은 VPC link V2로 ALB에 직접 붙는다

REST API가 VPC 안의 백엔드를 호출하는 경로는 VPC link입니다. V2는 NLB 없이 ALB에 직접 연결할 수 있고, V1은 legacy라 신규 생성이 권장되지 않습니다. REST API의 private integration에서 Cloud Map은 지원되지 않습니다.

소유권 제약이 하나 있습니다. load balancer와 VPC link와 REST API가 모두 같은 AWS 계정 소유여야 합니다. 계정을 나눠 운영하는 구조에서 이 조건이 선지를 자릅니다.

private integration은 기본적으로 HTTP로 나갑니다. HTTPS로 나가게 하려면 통합 `uri`에 보안 서버 이름을 지정합니다. 요청 경로에는 stage 이름이 포함되고, 백엔드가 stage 없는 경로를 기대하면 parameter mapping으로 `$context.requestOverride.path`를 덮어써 제거합니다.

---

## 23. API Gateway 실행 쿼터

| 항목 | 값 |
| :--- | :--- |
| 계정 throttle | 리전당 10,000 rps, token bucket 최대 용량 5,000 |
| 일부 리전 기본 throttle | 2,500 rps, burst 1,250 |
| non-WebSocket payload | 10 MB, 조정 불가 |
| 통합 타임아웃 | 기본 29초. Regional과 private REST API는 quota 증설 요청 가능 |
| 통합 타임아웃 증설 | Regional과 private REST API만 가능 |
| HTTP API 통합 타임아웃 | 30초 고정 |
| REST response streaming | 별도 전송 모드. buffered 통합 타임아웃과 다른 상한을 적용 |
| Lambda authorizer 결과 크기 | 8 KB |
| 결합 헤더 크기 | 10,240 bytes |
| 캐시된 응답 | 최대 1,048,576 bytes |
| 최대 캐싱 TTL | 3,600초 |
| resource policy | 8,192 bytes |
| REST와 WebSocket의 resource와 route | 300 |
| HTTP API route | 300 |
| API당 stage | 10 |
| stage당 stage variable | 100 |
| usage plan | 300 |
| API key | 10,000 |
| VPC link V1 | 20 |
| VPC link V2 | 10, V2 link당 subnet 10 |
| edge-optimized API | 120 |
| Regional API와 private API | 각 600 |
| custom domain name | 120 |
| WebSocket 연결 지속 시간 | 최대 7,200초 |
| WebSocket idle 연결 타임아웃 | 600초 |
| WebSocket 메시지 payload | 128 KB, frame 32 KB |
| WebSocket 신규 연결 | 500 rps |

계정 throttle 쿼터는 HTTP API, REST API, WebSocket API, WebSocket callback API를 합산합니다. 증설을 요청할 수 있지만 burst 값 자체는 고객이 조정하지 못합니다. Cape Town, Milan, Jakarta, UAE, Hyderabad, Melbourne, Spain, Zurich, Tel Aviv, Calgary, Malaysia, Thailand, Mexico Central은 기본이 2,500 rps와 burst 1,250입니다.

통합 타임아웃 증설에는 조건이 붙습니다. 쿼터 요청이 승인되어도 계정 레벨 throttle 쿼터 축소를 요구할 수 있고, 올린 뒤에는 각 통합의 타임아웃 값을 바꾸고 API를 다시 배포해야 적용됩니다. edge-optimized REST API는 증설 대상이 아니며 HTTP API는 30초로 고정됩니다. REST response streaming은 buffered 응답과 별도 전송 모드라 스트리밍 전용 제한을 확인해야 합니다.

payload 10 MB는 조정할 수 없으므로 대용량 업로드는 S3 presigned URL로 우회합니다. WebSocket 연결 지속 시간 상한이 7,200초라 그보다 긴 세션에는 재연결 로직이 필요합니다.

---

## 24. AppSync 데이터 소스 일곱 가지와 None

AppSync는 GraphQL API와 Events API 두 가지를 제공합니다. Events API는 WebSocket 기반 pub/sub이고 2025년 3월 13일부터 사용할 수 있습니다.

GraphQL API가 붙일 수 있는 데이터 소스는 일곱 가지입니다.

- Amazon DynamoDB
- AWS Lambda
- Amazon RDS(Aurora Serverless의 Data API 경유)
- Amazon EventBridge
- Amazon OpenSearch Service
- HTTP endpoint
- None

None은 저장소를 호출하지 않고 request와 response만 실행하는 pass-through입니다. subscription 브로드캐스트를 위해 반드시 DynamoDB 같은 저장소를 붙여야 한다는 서술은 여기서 틀립니다. 알림만 뿌리는 mutation에는 None 데이터 소스를 씁니다.

인가 모드는 API key, IAM, Amazon Cognito, OpenID Connect provider, Lambda authorization 다섯 가지입니다. Private API로 접근을 제한할 수 있고 AWS WAF와 통합되며 서버 사이드 캐싱과 Merged API를 지원합니다. 과금은 요청 수와 실시간 메시지 전달 수 기준이고 인증과 인가에 실패한 요청은 과금되지 않습니다.

기존 IAM role을 데이터 소스에 재사용하려면 `appsync.amazonaws.com`을 principal로 두는 trust policy가 필요하고, `aws:SourceAccount`와 `aws:SourceArn` 조건으로 특정 계정이나 특정 API로 좁힐 수 있습니다.

---

## 25. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 자르는 수치와 동작입니다.

**Lambda**

| 항목 | 값 |
| :--- | :--- |
| 메모리 | 128 MB에서 10,240 MB, 1 MB 단위 |
| vCPU 환산 | 1,769 MB에서 1 vCPU 상당 |
| 함수 타임아웃 | 900초. 조정 불가 |
| `/tmp` | 512 MB에서 10,240 MB |
| 배포 패키지 | zip 50 MB, 압축 해제 250 MB, 컨테이너 이미지 10 GB |
| payload | 동기 요청과 응답 각 6 MB, response streaming 200 MB, 비동기 1 MB |
| layer | 5개 |
| 환경 변수 합계 | 4 KB |
| 관리형 코드 스토리지 | 300 GB, 증설 불가 |
| 실행 환경 대역폭 | 625 Mbps |
| 계정 동시성 | 리전별 기본 1,000, 증설 가능 |
| 예약 가능 총량 | 계정 한도에서 100을 뺀 값. 기본 900 |
| 동기 호출 rps 상한 | 동시성 쿼터의 10배. 기본 10,000 rps |
| 스케일 속도 | 10초에 실행 환경 1,000개 |
| provisioned 할당 속도 | 함수당 분당 최대 6,000 실행 환경 |
| 비동기 함수 에러 재시도 | 2회. 1분 뒤, 2분 뒤 |
| 비동기 스로틀 재시도 | 기본 6시간, 간격 1초에서 5분 |
| VPC ENI | VPC당 500개 기본, ENI 하나가 65,000 connection |
| ENI 회수 | 14일 유휴 후 `Inactive` |
| VPC 설정 제거 후 ENI 삭제 | 최대 20분 |

**ECS와 Fargate**

| 항목 | 값 |
| :--- | :--- |
| Fargate CPU와 메모리 | 정해진 조합표. 4 vCPU는 8에서 30 GB, 16 vCPU는 32에서 120 GB |
| Windows on Fargate | 1024, 2048, 4096만 |
| Fargate ephemeral storage | 20 GiB에서 200 GiB, 이미지가 함께 쓴다 |
| EC2 launch type task CPU | 128 units(0.125 vCPU)에서 196,608 units(192 vCPU) |
| task placement constraint | 태스크당 최대 10개 |
| 리소스당 태그 | 50개 |
| capacity provider strategy | provider 최대 20개 |
| `base` | 0에서 100,000. strategy 안에서 provider 하나만 |
| `weight` | 0에서 1,000. 전부 0이면 호출 실패 |
| `targetCapacity` | 1에서 100 퍼센트, 기본 100 |
| `minimumScalingStepSize` | 기본 1, 범위 1에서 10,000 |
| `maximumScalingStepSize` | 기본 10,000, 범위 1에서 10,000 |
| `instanceWarmupPeriod` | 기본 300초, 범위 0에서 10,000 |
| Fargate Spot 회수 경고 | 2분 |
| NLB blue/green 추가 시간 | 트래픽 전환 단계마다 10분 |
| ECS 메트릭 전송 간격 | 1분 |

**ECR**

| 항목 | 값 |
| :--- | :--- |
| 복제 규칙 | 최대 10개. 전체 고유 destination은 최대 25개 |
| 고유 목적지 | 전체 규칙에 걸쳐 최대 25개 |
| 규칙당 필터 | 최대 100개 |
| 복제 대상 | 규칙 설정 이후 push되거나 restore된 콘텐츠만 |
| 전이 복제 | 되지 않는다 |
| partition 간 복제 | 되지 않는다 |

**EKS**

| 항목 | 값 |
| :--- | :--- |
| Auto Mode 노드 최대 수명 | 21일, 단축 가능 |
| Auto Mode 노드 접근 | SSH와 SSM 차단 |
| Fargate Pod 배치 | private subnet, IMDS 없음, 자격 증명은 IRSA |
| Fargate 로드밸런서 target type | `ip`만 |
| Hybrid Nodes CSI | EBS, EFS, S3 Files, FSx 전부 불가 |

**API Gateway와 AppSync**

| 항목 | 값 |
| :--- | :--- |
| 계정 throttle | 리전당 10,000 rps, burst 5,000 |
| payload | 10 MB, 조정 불가 |
| 통합 타임아웃 | 기본 29초. Regional과 private REST API는 quota 증설 요청 가능 |
| 통합 타임아웃 증설 | Regional과 private REST API만 |
| HTTP API 통합 타임아웃 | 30초 고정 |
| REST response streaming | buffered 응답과 다른 전송 모드와 상한 |
| 캐시된 응답 | 1,048,576 bytes, TTL 최대 3,600초 |
| Lambda authorizer 결과 | 8 KB |
| WebSocket 연결 | 최대 7,200초, idle 600초, payload 128 KB |
| AppSync 인가 모드 | API key, IAM, Cognito, OIDC, Lambda 다섯 가지 |
| AppSync 데이터 소스 | DynamoDB, Lambda, RDS, EventBridge, OpenSearch, HTTP, None 일곱 가지 |

---

## 26. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| ECS on EC2 대 Fargate | EC2는 task CPU를 0.125에서 192 vCPU 사이 아무 값으로 지정하고 GPU와 dedicated host를 쓸 수 있다. Fargate는 정해진 조합표 안에서만 등록되고 `awsvpc`가 강제되며 OS 패치가 AWS 몫이다 |
| `launchType` 대 `capacityProviderStrategy` | 상호 배타다. Fargate Spot과 On-Demand 혼합 배치는 strategy로만 되고, strategy를 쓰면 `launchType`을 생략해야 한다 |
| reserved concurrency 대 provisioned concurrency | reserved는 상한이자 하한이고 과금이 없으며 콜드 스타트가 그대로 있다. provisioned는 사전 초기화된 환경 수이고 과금 대상이며 reserved보다 크게 설정하지 못한다 |
| Lambda 동기 호출 대 비동기 호출 | 동기는 payload 6 MB이고 Lambda가 재시도하지 않는다. 비동기는 1 MB이고 함수 에러를 2회 재시도하며 DLQ와 destination으로 실패를 잡는다 |
| SnapStart 대 provisioned concurrency | SnapStart는 스냅샷 재사용이고 Java 관리형 런타임에서 추가 비용이 없으며 발행 버전과 alias에서만 동작한다. provisioned는 상시 과금이고 `$LATEST`에도 걸 수 있다. 둘은 같은 함수 버전에 함께 쓰지 못한다 |
| Service Connect 대 service discovery | Service Connect는 프록시가 재시도와 메트릭을 제공하고 `host` 모드에서 동작하지 않는다. service discovery는 세 모드 모두 되지만 DNS TTL 문제와 재시도 구현이 애플리케이션 몫이다 |
| `awsvpc` 대 `bridge` | `awsvpc`는 태스크마다 ENI와 security group을 준다. `bridge`는 dynamic port mapping으로 한 인스턴스에 같은 태스크를 여러 개 올릴 수 있다 |
| `host` 대 `awsvpc` | 둘 다 EC2 네트워크 스택을 그대로 써 성능이 높다. `host`는 dynamic port mapping과 Service Connect와 태스크별 security group을 전부 못 쓴다 |
| `ECS` 컨트롤러 blue/green 대 `CODE_DEPLOY` 컨트롤러 | 전자는 ECS가 직접 전환하고 `LINEAR`와 `CANARY` 전략과 pause hook을 갖는다. 후자는 task set 두 벌과 사전 정의 구성 이름을 쓰고 `REPLICA`가 필수다 |
| `REPLICA` 대 `DAEMON` | `DAEMON`은 컨테이너 인스턴스마다 하나를 유지한다. Fargate launch type과 `CODE_DEPLOY`와 `EXTERNAL` 컨트롤러는 지원하지 않는다 |
| ECS Anywhere 대 EKS Anywhere | 전자는 리전의 ECS control plane을 그대로 쓰므로 연결이 전제다. 후자는 클러스터 전체를 사용자 인프라에 설치해 air-gapped에서도 동작한다 |
| EKS Auto Mode 대 managed node group | Auto Mode는 Karpenter와 immutable AMI와 21일 노드 교체를 적용하고 SSH를 막는다. Windows, custom AMI와 CNI, launch template 부트스트랩, SGPP 방식의 Pod별 security group은 managed node group에서 지원되며 self-managed node도 기능상 가능하다. Local Zone은 Auto Mode와 managed node group 모두 지원한다 |
| EKS Fargate 대 managed node group | Fargate는 Pod마다 VM 경계를 주지만 DaemonSet, EBS mount, GPU, Arm, Windows, Fargate Spot이 전부 불가하고 로드밸런서 target type이 `ip`로 한정된다 |
| ECR 복제 대 이미지 재push | 복제는 규칙 설정 이후의 push와 restore만 옮긴다. 기존 이미지를 옮기는 수단이 아니다 |
| REST API 대 HTTP API | API key, usage plan, per-client throttling, WAF, resource policy, 캐싱, request validation, canary release, X-Ray는 REST 전용이다. JWT authorizer, 자동 배포, Cloud Map private 통합은 HTTP 전용이다 |
| edge-optimized 대 Regional | edge-optimized는 CloudFront POP를 경유하고 custom domain이 전 리전에 걸리며 헤더 이름을 capitalize한다. Regional은 리전에 종속되어 Route 53 latency-based routing과 조합할 수 있다 |
| Private API 대 private integration | 전자는 API를 VPC 안에서만 호출하게 만드는 엔드포인트 타입이다. 후자는 API가 VPC 안 백엔드를 호출하는 통합 방식이고 VPC link를 쓴다 |
| VPC link V1 대 V2 | V1은 legacy이고 NLB만 대상이다. V2는 ALB에 직접 붙을 수 있다. 두 링크의 쿼터도 20과 10으로 다르다 |
| API Gateway 대 AppSync | 전자는 REST와 HTTP와 WebSocket 프로토콜을 다룬다. 후자는 GraphQL과 Events API이고 데이터 소스를 리졸버로 직접 연결하며 subscription을 관리형으로 제공한다 |
| API Gateway 캐싱 대 CloudFront | REST API 스테이지 캐싱은 API Gateway 안에서 TTL 최대 3,600초로 동작한다. HTTP API로 옮기면 캐싱이 사라지므로 CloudFront를 앞에 두는 구성으로 바꾼다 |

---

## 27. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| VPC에 Lambda를 붙이면 프라이빗 리소스와 인터넷을 둘 다 쓴다 | VPC에 붙는 순간 기본 인터넷 접근이 사라진다. NAT gateway나 VPC endpoint를 따로 만들어야 한다 |
| Lambda를 퍼블릭 서브넷에 두면 인터넷으로 나간다 | 퍼블릭 서브넷 연결은 퍼블릭 IP도 인터넷 경로도 주지 않는다. Hyperplane ENI는 인터넷 게이트웨이로 직접 나가지 않는다 |
| Lambda 함수에 Elastic IP를 붙여 고정 공인 IP로 호출한다 | 함수에 EIP를 직접 붙이는 구성이 없다. NAT gateway에 EIP를 붙이는 구조로 만든다 |
| 콜드 스타트를 줄이려고 SnapStart와 provisioned concurrency를 함께 켠다 | 같은 함수 버전에 둘을 함께 쓸 수 없다. 런타임이 Node.js나 Ruby면 SnapStart 자체가 후보에서 빠진다 |
| 긴 초기화가 있는 Java 함수를 `$LATEST`에 SnapStart로 배포한다 | SnapStart는 발행된 버전과 그 버전을 가리키는 alias에서만 동작한다 |
| 중요 함수 하나에 reserved concurrency 1,000을 잡아 계정 동시성을 독점시킨다 | 기본 계정 한도 1,000에서 예약 가능한 총량은 900이다. Lambda가 미예약 함수용 100을 항상 남긴다 |
| 평균 30 ms짜리 함수라 동시성 1,000이면 초당 30,000건을 처리한다 | 동기 호출 rps 상한이 동시성의 10배라 10,000 rps에서 막힌다 |
| provisioned concurrency를 reserved와 같은 값으로 맞춰 전부 예열한다 | 두 값이 같아지면 `$LATEST`가 쓸 동시성이 남지 않아 스로틀된다 |
| 폭주 함수의 처리량을 늘리려고 reserved concurrency를 건다 | reserved는 상한이자 하한이라 그 값을 넘어 확장하지 못하게 만든다. 격리 수단이지 증설 수단이 아니다 |
| API Gateway 뒤에서 20분짜리 배치를 Lambda 동기 호출로 처리한다 | 기본 통합 타임아웃 29초에서 504가 나고, 그 뒤에도 함수는 900초에서 끊긴다. quota 증설을 해도 함수 상한은 그대로다 |
| 함수 메모리를 10,240 MB로 올려 20분 작업을 15분 안에 넣는다 | 들어간다는 보장이 없고, 들어가도 API Gateway 기본 29초 제한이 남는다 |
| edge-optimized API의 통합 타임아웃을 60초로 올린다 | 증설은 Regional과 private REST API에서만 가능하다 |
| API Gateway REST API로 20 MB 파일 업로드를 프록시한다 | non-WebSocket payload 상한이 10 MB이고 조정할 수 없다. S3 presigned URL로 우회한다 |
| WebSocket API로 3시간 이상 지속되는 세션을 유지한다 | 연결 지속 시간 상한이 7,200초이고 idle 타임아웃이 600초다 |
| 비용을 아끼려고 HTTP API로 바꾸면서 usage plan과 API key로 파트너별 쿼터를 유지한다 | HTTP API에는 API key, usage plan, per-client throttling, WAF, resource policy가 전부 없다 |
| HTTP API로 옮기면서 응답 캐싱으로 백엔드 부하를 줄인다 | 캐싱은 REST API 전용이다. REST를 유지하거나 CloudFront를 앞에 둔다 |
| REST API private integration을 Cloud Map 서비스로 연결한다 | REST private integration은 Cloud Map을 지원하지 않는다. Cloud Map 타깃이 필요하면 HTTP API다 |
| 다른 계정의 ALB를 VPC link로 붙인다 | load balancer와 VPC link와 REST API가 모두 같은 계정 소유여야 한다 |
| Fargate 태스크를 4 vCPU와 64 GB로 잡는다 | 4096 CPU는 8에서 30 GB만 허용한다. 64 GB에는 16384가 필요하다 |
| Windows on Fargate로 8 vCPU 태스크를 돌린다 | Windows는 1024, 2048, 4096만 지원한다 |
| Fargate Spot 할인을 받으려고 `launchType: FARGATE`에 Spot 옵션을 함께 지정한다 | Fargate Spot에는 launch type이 없다. `capacityProviderStrategy`로만 쓰고 그때 `launchType`은 생략한다 |
| On-Demand 최소 2태스크와 Spot 최소 4태스크를 각각 `base`로 보장한다 | `base`는 strategy 안에서 하나의 provider만 가진다. 나머지는 `weight`로만 나뉜다 |
| `weight`를 전부 0으로 두고 `base`로만 배치를 제어한다 | 전부 0이면 `RunTask`와 `CreateService`가 실패한다 |
| `PutClusterCapacityProviders`로 새 provider 하나만 추가 호출한다 | 이 API는 전체 목록을 덮어쓴다. 빠진 provider는 클러스터에서 분리된다 |
| 태스크가 도는 인스턴스를 지키려고 managed termination protection만 켠다 | managed scaling이 켜져 있어야 하고 ASG와 각 인스턴스에도 scale-in instance protection이 필요하다 |
| Fargate 서비스에 `DAEMON` 스케줄링으로 노드별 로그 수집 태스크를 붙인다 | Fargate launch type과 `CODE_DEPLOY`와 `EXTERNAL` 컨트롤러는 `DAEMON`을 지원하지 않는다. 사이드카로 바꾼다 |
| ECS 배포 중에도 오토스케일링이 완전히 멈춘다 | scale-in만 멈추고 scale-out은 계속된다. 둘 다 막으려면 두 suspend 플래그를 켠다 |
| `host` 네트워크 모드로 성능을 올리면서 Service Connect로 서비스 간 통신을 관리한다 | Service Connect는 `host`에서 동작하지 않는다 |
| `host` 모드에서 태스크마다 다른 security group을 적용한다 | 태스크별 security group은 `awsvpc`가 전제다 |
| `host` 모드로 같은 서비스를 한 인스턴스에 여러 개 올린다 | 같은 포트를 두 태스크가 쓸 수 없다. dynamic port mapping이 필요하면 `bridge`다 |
| NLB 뒤 ECS 서비스에 CodeDeploy canary 10퍼센트 배포를 건다 | NLB에서는 `ECSAllAtOnce`만 지원한다 |
| ECS Anywhere 외부 인스턴스를 ALB 타깃 그룹에 넣어 온프레미스 웹 서비스를 노출한다 | 외부 인스턴스는 service load balancing과 service discovery를 지원하지 않는다 |
| ECS Anywhere 태스크에 `awsvpc`를 써서 태스크별 security group을 준다 | 외부 인스턴스는 `bridge`, `host`, `none`만 가능하고 capacity provider와 EFS 볼륨도 못 쓴다 |
| DR 리전 확보를 위해 ECR 복제를 켜면 기존 이미지도 넘어간다 | 규칙 설정 이후 push되거나 restore된 것만 복제된다 |
| 허브 리전을 두고 A에서 B, B에서 C로 연결해 세 리전에 배포한다 | 복제는 전이되지 않는다. A에서 B와 C 각각으로 규칙을 건다 |
| cross-account 복제를 위해 소스 리포지토리에 repository policy를 붙인다 | 필요한 것은 목적지 계정의 registry permissions policy 하나다. 소스에는 어떤 정책도 필요 없다 |
| ECR 복제로 목적지 리포지토리에도 lifecycle policy가 적용된다 | repository policy, IAM policy, lifecycle policy는 복제되지 않는다. repository creation template를 쓴다 |
| lifecycle policy로 다른 리전의 이미지를 가져온다 | lifecycle policy는 리포지토리 안의 이미지를 만료시키는 규칙이고 리전 간 이동 기능이 없다 |
| EKS Fargate Pod에 EBS PVC를 붙이고 로그 수집 DaemonSet을 함께 돌린다 | Fargate는 EBS mount와 DaemonSet을 둘 다 지원하지 않는다 |
| EKS Auto Mode로 Windows 노드를 운영하고 노드에 SSH로 들어가 디버깅한다 | Auto Mode는 Windows를 지원하지 않고 SSH와 SSM 접근을 차단한다 |
| EKS Auto Mode는 GPU를 쓸 수 없다 | GPU 플러그인은 Auto Mode의 core component에 포함된다. 못 쓰는 것은 Windows와 custom CNI와 노드 접근이다 |
| Auto Mode의 기본 NodePool을 편집해 Spot을 섞는다 | 기본 NodePool과 NodeClass는 편집하지 않고 별도 NodePool과 NodeClass를 추가한다 |
| Hybrid Nodes에 EFS를 붙여 공유 스토리지를 쓴다 | Hybrid Nodes는 EBS, EFS, S3 Files, FSx CSI를 모두 쓸 수 없다 |
| 리전 연결이 끊긴 환경에 ECS Anywhere로 워크로드를 둔다 | ECS Anywhere는 리전의 control plane에 의존하고 필수 엔드포인트 6종이 필요하다. air-gapped 요구는 EKS Anywhere다 |
| AppSync subscription 브로드캐스트를 위해 반드시 저장소 데이터 소스를 붙인다 | None 데이터 소스가 저장소 호출 없는 pass-through로 존재한다 |
| 비동기 payload를 256 KB 기준으로 설계한다 | 현재 문서 값은 1 MB다 |

---

## 28. 예상 문제 10문항

**Q1.** 한 팀이 AWS Lambda 함수에서 프라이빗 서브넷의 Amazon RDS 인스턴스와 외부 결제 SaaS API를 모두 호출합니다. 함수를 VPC에 연결한 직후부터 데이터베이스 조회는 정상인데 결제 API 호출이 전부 타임아웃됩니다. 함수는 프라이빗 서브넷 두 곳에 배치되어 있고 보안 그룹 아웃바운드는 전부 허용 상태입니다. 아웃바운드 접근을 복구하면서 운영 부담이 LEAST인 방법은 무엇입니까?

- A. 함수를 퍼블릭 서브넷에 연결하고 서브넷의 자동 퍼블릭 IP 할당을 켠다
- B. 프라이빗 서브넷의 라우팅 테이블에서 기본 경로를 퍼블릭 서브넷의 NAT gateway로 향하게 한다
- C. 함수에 Elastic IP를 연결해 고정 공인 IP로 외부 API를 호출한다
- D. 함수의 VPC 설정을 제거하고 RDS 인스턴스를 publicly accessible로 바꾼다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

VPC에 연결하지 않은 Lambda 함수는 기본적으로 퍼블릭 인터넷에 접근하지만, VPC에 연결하는 순간 그 VPC 안에서 도달 가능한 대상만 접근할 수 있습니다. 인터넷 접근이 필요하면 프라이빗 서브넷에 배치하고 NAT gateway를 경유하는 경로를 VPC 쪽에 구성해야 합니다.

- A가 틀린 이유: Lambda를 퍼블릭 서브넷에 연결해도 인터넷 접근이나 퍼블릭 IP가 생기지 않는다. Lambda가 만드는 Hyperplane ENI는 인터넷 게이트웨이로 직접 나가지 않는다.
- C가 틀린 이유: Lambda 함수에 Elastic IP를 직접 연결하는 구성은 존재하지 않는다. 고정 공인 IP가 필요하면 NAT gateway에 Elastic IP를 붙이는 구조로 만든다.
- D가 틀린 이유: 결제 API 호출은 복구되지만 데이터베이스를 인터넷에 노출하게 되어 보안 요건을 훼손한다. 요구는 아웃바운드 복구이지 데이터베이스 노출이 아니다.

</details>

**Q2.** 한 회사가 파트너 40곳에 REST 스타일 API를 제공합니다. 파트너마다 월간 호출 쿼터와 초당 요청 상한이 다르고, 파트너를 식별할 발급 키가 필요하며, SQL injection 시도를 엣지에서 차단해야 합니다. 응답 캐싱으로 백엔드 부하도 줄이려 합니다. 팀은 API Gateway 도입을 확정했습니다. MOST appropriate API 타입과 구성은 무엇입니까?

- A. HTTP API를 만들고 Lambda authorizer 안에서 파트너별 호출 횟수를 DynamoDB로 집계해 쿼터를 강제한다
- B. Regional 엔드포인트의 REST API를 만들고 usage plan과 API key로 파트너별 쿼터와 throttling을 적용하며, 스테이지에 AWS WAF web ACL과 캐싱을 연결한다
- C. HTTP API를 만들고 JWT authorizer로 파트너를 식별한 뒤 CloudFront 배포에 AWS WAF를 연결한다
- D. Application Load Balancer 뒤에 컨테이너 API를 두고 Amazon Cognito 인증과 ALB 규칙으로 파트너를 구분한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

API key, usage plan, per-client rate limiting, AWS WAF 연동, 응답 캐싱, resource policy는 모두 REST API에만 있는 기능입니다. 네 가지 요구가 동시에 걸리므로 REST API가 유일한 선택지입니다.

- A가 틀린 이유: HTTP API에는 API key와 usage plan, per-client throttling, WAF 연동이 전부 없다. Lambda authorizer 안에서 쿼터를 직접 구현하면 호출마다 DynamoDB 왕복이 붙고 정확한 rate limiting 구현 부담이 애플리케이션으로 넘어온다.
- C가 틀린 이유: HTTP API는 Regional 엔드포인트만 지원하며 API key와 usage plan이 없어 파트너별 쿼터를 강제하지 못한다. 응답 캐싱도 없다.
- D가 틀린 이유: 파트너별 쿼터와 호출 횟수 집계, 캐싱, 키 발급 체계를 전부 직접 구현해야 하며 관리형 서비스로 위임하는 요구에 어긋난다.

</details>

**Q3.** 한 리전의 계정에서 Lambda 함수 30개가 동작합니다. 이 중 로그 파싱 함수가 야간에 폭주해 계정 동시성을 대부분 소진하면서, 같은 계정의 결제 처리 함수가 `TooManyRequestsException`으로 스로틀됩니다. 로그 파싱 지연은 허용되지만 결제 함수는 스로틀되면 안 됩니다. 운영 부담이 LEAST인 해결책은 무엇입니까?

- A. 결제 함수에 provisioned concurrency를 설정한다
- B. 로그 파싱 함수에 reserved concurrency를 설정해 사용 가능한 동시성 상한을 고정한다
- C. 계정 동시성 쿼터 증설을 요청한다
- D. 결제 함수를 별도 AWS 계정으로 옮기고 EventBridge로 이벤트를 전달한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

reserved concurrency는 상한이자 하한입니다. 로그 파싱 함수에 설정하면 그 함수가 예약분을 넘어 미예약 pool을 잠식하지 못하므로 나머지 함수의 동시성이 보호됩니다. 추가 과금도 없고 설정 하나로 끝납니다.

- A가 틀린 이유: provisioned concurrency는 사전 초기화된 실행 환경을 확보해 콜드 스타트를 줄이는 기능이며 과금 대상이다. 원인인 폭주 함수의 동시성 잠식을 막지 못한다.
- C가 틀린 이유: 한도를 올려도 폭주 함수가 상한 없이 확장하면 같은 상황이 재현된다. 격리 수단이 아니라 여유분을 늘릴 뿐이다.
- D가 틀린 이유: 격리는 되지만 계정 분리, 크로스 계정 이벤트 라우팅, 배포 파이프라인 이중화가 뒤따라 운영 부담이 가장 크다.

</details>

**Q4.** 한 분석 팀이 Amazon API Gateway REST API 뒤의 Lambda 함수로 월간 리포트를 생성합니다. 리포트 생성에 약 20분이 걸리고 결과는 Amazon S3에 저장됩니다. 현재 구현은 항상 504 응답을 반환하지만 리포트 파일은 나중에 생성되어 있습니다. 클라이언트는 요청 직후 작업 ID를 받고 진행 상태를 폴링할 수 있어야 합니다. MOST appropriate 재설계는 무엇입니까?

- A. Lambda 함수 타임아웃을 30분으로 늘리고 API Gateway 통합 타임아웃 상향을 요청한다
- B. Lambda 함수 메모리를 10,240 MB로 올려 실행 시간을 15분 이내로 줄인다
- C. API Gateway가 작업 ID를 발급하고 AWS Step Functions Standard workflow를 시작한 뒤 즉시 응답하게 하며, 실제 생성은 workflow가 호출하는 AWS Fargate task가 수행하고 별도 엔드포인트가 실행 상태를 조회하게 한다
- D. API Gateway 통합을 Lambda 비동기 호출로 바꾸고 함수 안에서 20분 처리를 계속한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Lambda 함수 타임아웃 상한은 900초이고 API Gateway 통합 타임아웃 기본값은 29초입니다. 20분 작업은 두 제약 모두에 걸리므로 요청과 처리를 분리해야 합니다. Step Functions Standard workflow는 최대 1년까지 실행되며 `.sync` 통합으로 Fargate task 완료를 기다릴 수 있고, `DescribeExecution`으로 상태 폴링 엔드포인트를 구성할 수 있습니다.

- A가 틀린 이유: Lambda 함수 타임아웃 900초는 조정 불가능한 하드 리밋이다. API Gateway 통합 타임아웃을 올려도 Lambda 쪽에서 15분에 끊긴다.
- B가 틀린 이유: 메모리를 올리면 CPU가 비례해 늘지만 20분 작업이 15분 안으로 들어온다는 보장이 없고, 들어와도 API Gateway 통합 타임아웃 29초를 넘어 여전히 504가 난다.
- D가 틀린 이유: 비동기 호출로 504는 사라지지만 함수 자체가 900초에 끊긴다. 작업 ID 발급과 상태 조회 요구도 충족하지 못한다.

</details>

**Q5.** 한 팀이 Java 17로 작성한 Lambda 함수의 콜드 스타트가 3초에 달해 사용자 대면 지연이 문제가 된다고 보고합니다. 호출 패턴이 불규칙해 하루 대부분은 유휴이고 짧게 몰립니다. 재무팀은 상시 유지 비용이 붙는 구성을 승인하지 않았고, 런타임을 다시 쓰는 작업도 허용하지 않았습니다. MOST cost-effective 해결책은 무엇입니까?

- A. 함수 버전을 발행하고 그 버전에 Lambda SnapStart를 활성화한 뒤 alias를 통해 호출한다
- B. provisioned concurrency를 상시 10으로 설정한다
- C. 5분마다 함수를 호출하는 EventBridge Scheduler 규칙을 만들어 실행 환경을 유지한다
- D. 함수 메모리를 10,240 MB로 올려 초기화 시간을 단축한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

SnapStart는 Java 11 이상 관리형 런타임을 지원하고 초기화가 끝난 실행 환경의 스냅샷을 재사용해 콜드 스타트를 줄입니다. Java 관리형 런타임에서는 SnapStart 추가 비용이 없습니다. 발행된 버전과 그 버전을 가리키는 alias에서만 동작하므로 버전 발행과 alias 호출이 함께 필요합니다.

- B가 틀린 이유: provisioned concurrency는 사전 초기화된 실행 환경 수에 과금되므로 유휴 시간이 대부분인 워크로드에서 상시 비용이 발생한다. 재무 제약에 어긋난다.
- C가 틀린 이유: 주기 호출은 실행 환경 하나 정도만 살려 둘 뿐 동시 호출이 몰리면 나머지가 콜드 스타트를 겪는다. 불필요한 호출 비용도 계속 든다.
- D가 틀린 이유: 메모리를 올리면 초기화가 다소 빨라지지만 JVM 기동 자체를 없애지 못하고 모든 호출의 GB-second 단가가 올라 비용이 늘어난다.

</details>

**Q6.** 한 회사가 메모리 집약 Java 서비스를 컨테이너로 옮깁니다. 태스크 하나가 4 vCPU와 64 GiB 메모리를 요구하고, 태스크마다 별도 ENI와 보안 그룹이 필요하며, 인스턴스 수십 대 규모로 수평 확장합니다. 팀은 Amazon ECS를 쓰기로 했습니다. MOST cost-effective 태스크 배치는 무엇입니까?

- A. Fargate 시작 유형으로 태스크 CPU 4096, 메모리 65536을 지정한다
- B. Fargate 시작 유형으로 태스크 CPU 16384, 메모리 65536을 지정한다
- C. EC2 시작 유형으로 메모리 최적화 인스턴스를 컨테이너 인스턴스로 두고 `awsvpc` 네트워크 모드로 태스크 CPU 4096, 메모리 65536을 지정한다
- D. Amazon EKS로 옮기고 Fargate profile로 Pod를 실행한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

Fargate는 CPU와 메모리 조합이 정해진 표에서만 선택할 수 있고, CPU 4096(4 vCPU)은 8 GB에서 30 GB까지만 허용합니다. 64 GiB를 쓰려면 CPU 16384(16 vCPU) 이상을 골라야 해서 필요 없는 vCPU 12개분을 함께 과금합니다. EC2 시작 유형은 태스크 CPU를 128 CPU units(0.125 vCPU)에서 196,608 units(192 vCPU)까지 자유롭게 지정할 수 있고 `awsvpc` 모드에서 태스크마다 ENI와 보안 그룹을 받습니다.

- A가 틀린 이유: CPU 4096과 메모리 65536은 유효하지 않은 조합이라 태스크 정의 등록 자체가 실패한다.
- B가 틀린 이유: 유효한 조합이지만 요구 vCPU의 4배를 프로비저닝하게 되어 비용 최소화 조건에 어긋난다.
- D가 틀린 이유: EKS Fargate도 같은 Fargate CPU와 메모리 조합 제약을 받으며, 추가로 클러스터 운영 부담과 control plane 비용이 붙는다.

</details>

**Q7.** 한 회사가 ECS on EC2 클러스터에서 마이크로서비스 12개를 `host` 네트워크 모드로 운영합니다. 서비스 간 호출이 늘면서 배포 직후 사라진 컨테이너로 요청이 향하는 오류가 반복되고, 팀은 서비스 간 호출 지연과 오류율을 별도 계측 코드 없이 보고 싶어 합니다. 서비스마다 다른 보안 그룹을 적용하라는 보안팀 요구도 새로 생겼습니다. 애플리케이션 코드 변경이 LEAST인 해결책은 무엇입니까?

- A. `host` 모드를 유지하고 ECS Service Connect를 활성화한다
- B. 태스크 정의를 `awsvpc` 네트워크 모드로 바꾼 뒤 ECS Service Connect를 활성화한다
- C. `host` 모드를 유지하고 AWS Cloud Map 기반 service discovery를 구성한다
- D. 서비스마다 내부 Application Load Balancer를 두고 호출 대상을 로드밸런서 DNS 이름으로 바꾼다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Service Connect는 ECS가 관리하는 프록시로 짧은 이름 기반 연결, 재시도, 서비스 간 트래픽 메트릭을 제공하고 배포 시 클라이언트 태스크를 교체해 엔드포인트 정보를 갱신하므로 DNS 캐시로 인한 잘못된 대상 호출 문제를 없앱니다. 다만 Service Connect는 `bridge`와 `awsvpc`에서만 동작하고 `host`에서는 동작하지 않습니다. 태스크별 보안 그룹 요구도 `awsvpc`가 전제이므로 네트워크 모드 전환이 필요합니다.

- A가 틀린 이유: `host` 네트워크 모드에서는 Service Connect를 쓸 수 없다.
- C가 틀린 이유: service discovery는 DNS TTL이 만료되기 전까지 사라진 컨테이너 주소를 계속 반환할 수 있고, 재시도와 나쁜 백엔드 회피 로직을 애플리케이션이 직접 구현해야 한다. `host` 모드에서는 클라이언트가 SRV 레코드를 이해해야 하고 태스크별 보안 그룹도 얻지 못한다.
- D가 틀린 이유: 요구는 충족할 수 있으나 호출 대상 주소를 전부 바꿔야 하고 서비스마다 로드밸런서 비용과 홉이 추가된다.

</details>

**Q8.** 한 회사가 us-east-1의 Amazon ECR private repository에 컨테이너 이미지 400개를 보관합니다. 재해 복구를 위해 eu-west-1과 ap-northeast-1에서도 같은 이미지로 서비스를 기동할 수 있어야 합니다. 이미지의 대부분은 최근 6개월간 push된 적이 없는 안정 버전입니다. 기존 이미지와 앞으로의 이미지를 두 리전에서 모두 쓸 수 있게 만드는 방법은 무엇입니까?

- A. us-east-1에서 eu-west-1로, eu-west-1에서 ap-northeast-1로 이어지는 복제 규칙을 구성한다
- B. us-east-1 레지스트리에 eu-west-1과 ap-northeast-1을 각각 목적지로 하는 복제 규칙을 만들고, 기존 이미지는 다시 push하거나 restore한다
- C. us-east-1 레지스트리에 두 리전 목적지 복제 규칙만 구성하면 기존 이미지까지 자동으로 복제된다
- D. 각 리전 repository에 lifecycle policy를 만들어 us-east-1 이미지를 가져오게 한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

ECR 복제는 규칙 설정 이후에 push되거나 restore된 콘텐츠만 대상으로 합니다. 기존 이미지를 옮기려면 재push나 restore가 필요합니다. 또한 복제는 전이되지 않으므로 목적지 리전마다 소스 레지스트리에서 직접 규칙을 걸어야 합니다.

- A가 틀린 이유: 복제는 전이되지 않는다. us-east-1에 push한 이미지는 eu-west-1까지만 가고 ap-northeast-1로 이어지지 않는다.
- C가 틀린 이유: 기존 이미지는 복제 대상이 아니다. 400개 중 대부분이 최근 push되지 않았으므로 두 리전에 이미지가 거의 생기지 않는다.
- D가 틀린 이유: lifecycle policy는 repository 안의 이미지를 만료시키는 정리 규칙이며 리전 간 이미지 이동 기능이 없다. lifecycle policy 자체도 복제 대상이 아니다.

</details>

**Q9.** 한 기업이 Amazon EKS 클러스터에 두 종류 워크로드를 올립니다. 하나는 Windows Server 컨테이너로 동작하는 레거시 .NET 서비스이고, 다른 하나는 Linux 컨테이너입니다. 네트워크팀은 클러스터에 자사 표준 CNI 플러그인을 설치하라고 요구하며, 인스턴스 부트스트랩 단계에서 커널 파라미터를 조정하는 스크립트도 필요합니다. 이 요구를 충족하는 컴퓨트 옵션은 무엇입니까?

- A. EKS Auto Mode를 활성화하고 커스텀 NodePool과 NodeClass를 추가한다
- B. launch template을 지정한 managed node group을 Windows와 Linux 각각 생성한다
- C. Fargate profile을 두 워크로드에 각각 생성한다
- D. EKS Auto Mode를 기본으로 쓰고 Windows 워크로드만 Fargate profile로 분리한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Windows 컨테이너, custom AMI와 custom CNI, launch template을 통한 부트스트랩 인자는 managed node group에서 지원됩니다. self-managed node도 기능상 가능하지만 보기의 운영 요구처럼 AWS가 노드 패치와 교체를 맡아야 하면 managed node group을 고릅니다.

- A가 틀린 이유: EKS Auto Mode는 Windows 컨테이너, custom AMI와 custom CNI, launch template 부트스트랩을 모두 지원하지 않는다. NodePool과 NodeClass로 조정할 수 있는 범위는 인스턴스 선택과 ephemeral storage 수준이다.
- C가 틀린 이유: EKS Fargate는 Windows를 지원하지 않고 CNI도 Amazon VPC CNI 고정이라 대체 CNI를 설치할 수 없다. `HostNetwork`와 privileged container도 불가하다.
- D가 틀린 이유: Fargate가 Windows를 지원하지 않으므로 분리 자체가 성립하지 않는다. Auto Mode에서 custom CNI 요구도 여전히 충족되지 않는다.

</details>

**Q10.** 한 보험사가 Amazon S3에 업로드되는 청구 서류 PDF의 객체 생성 이벤트로 Lambda 함수를 비동기 호출해 본문 텍스트를 추출하고 검색 인덱스에 등록합니다. 다운스트림 추출 엔진의 일시적 오류로 일부 이벤트가 처리되지 못했고, 팀은 어떤 이벤트가 유실됐는지조차 파악하지 못했습니다. 앞으로 실패한 이벤트를 보존해 재처리하고, 같은 이벤트가 여러 번 도착해도 인덱스에 중복 레코드가 쌓이지 않아야 합니다. MOST appropriate 해결책은 무엇입니까?

- A. S3 이벤트 알림을 제거하고 애플리케이션이 Lambda를 동기 호출하도록 바꾼다
- B. 함수에 on-failure destination으로 Amazon SQS 큐를 지정하고 최대 재시도 횟수와 이벤트 최대 수명을 설정하며, 객체 키와 버전 ID 기반 멱등 처리를 함수에 구현한다
- C. 함수의 reserved concurrency를 늘려 스로틀을 없앤다
- D. 함수 타임아웃을 900초로 늘리고 코드 안에서 재시도 루프를 돈다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

비동기 호출에서 Lambda는 함수 에러를 기본 2회 재시도하고, 재시도가 소진된 이벤트는 on-failure destination이나 DLQ로 보낼 수 있습니다. 비동기 이벤트 큐는 eventually consistent라 같은 이벤트가 여러 번 전달될 수 있으므로 멱등성은 애플리케이션 책임입니다. 두 요구를 모두 덮는 조합입니다.

- A가 틀린 이유: S3 이벤트 알림은 Lambda를 비동기로 호출하는 통합이며, 동기 호출로 바꾸려면 애플리케이션이 S3에 쓰는 경로를 전부 고쳐야 한다. 동기 호출에서는 Lambda가 재시도하지 않으므로 실패 보존 문제도 호출자가 다시 풀어야 한다.
- C가 틀린 이유: 실패 원인은 다운스트림 추출 엔진 오류이지 스로틀이 아니다. 동시성을 늘려도 함수 에러로 인한 이벤트 유실은 그대로다.
- D가 틀린 이유: 타임아웃 연장과 코드 내 재시도는 실행 시간과 비용을 늘리면서 다운스트림이 오래 죽어 있으면 결국 실패한다. 실패 이벤트 보존과 중복 방지 요구는 다루지 못한다.

</details>

---

## 29. Reference

- [AWS Lambda - Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [AWS Lambda - Understanding Lambda function scaling](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html)
- [AWS Lambda - Asynchronous invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html)
- [AWS Lambda - Error handling for asynchronous invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)
- [AWS Lambda - Understanding retry behavior in Lambda](https://docs.aws.amazon.com/lambda/latest/dg/invocation-retries.html)
- [AWS Lambda - Error handling for Lambda integrations with API Gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway-errors.html)
- [AWS Lambda - Giving Lambda functions access to resources in a VPC](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html)
- [AWS Lambda - Improving startup performance with Lambda SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
- [Amazon ECS - Amazon ECS task networking options](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html)
- [Amazon ECS - Amazon ECS task definition parameters for CPU and memory](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)
- [Amazon ECS - Fargate task ephemeral storage](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-storage.html)
- [Amazon ECS - Interconnecting Amazon ECS services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/interconnecting-services.html)
- [Elastic Load Balancing - Use Lambda functions as targets](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/lambda-functions.html)
- [Amazon ECS - Blue/green deployments](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-blue-green.html)
- [Amazon ECS - Automatically scale your Amazon ECS service](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html)
- [Amazon ECS - Amazon ECS Anywhere](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-anywhere.html)
- [Amazon ECS API - RegisterTaskDefinition](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RegisterTaskDefinition.html)
- [Amazon ECS API - CreateService](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateService.html)
- [Amazon ECS API - CapacityProviderStrategyItem](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CapacityProviderStrategyItem.html)
- [Amazon ECS API - PutClusterCapacityProviders](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_PutClusterCapacityProviders.html)
- [Amazon ECS API - AutoScalingGroupProvider](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_AutoScalingGroupProvider.html)
- [Amazon ECS API - ManagedScaling](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ManagedScaling.html)
- [Amazon ECR - Private registry replication](https://docs.aws.amazon.com/AmazonECR/latest/userguide/replication.html)
- [Amazon EKS - Manage compute resources by using nodes](https://docs.aws.amazon.com/eks/latest/userguide/eks-compute.html)
- [Amazon EKS - Automate cluster infrastructure with EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/automode.html)
- [Amazon EKS - Deploy Auto Mode nodes onto Local Zones](https://docs.aws.amazon.com/eks/latest/userguide/auto-local-zone.html)
- [Amazon EKS - Review EKS Auto Mode release notes](https://docs.aws.amazon.com/eks/latest/userguide/auto-change.html)
- [Amazon EKS - Simplify compute management with AWS Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)
- [EKS Anywhere - Overview](https://anywhere.eks.amazonaws.com/docs/overview/)
- [EKS Anywhere - Changelog](https://anywhere.eks.amazonaws.com/docs/whatsnew/changelog/)
- [AWS CodeDeploy - Deployment configurations](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html)
- [Amazon API Gateway - Choose between REST APIs and HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html)
- [Amazon API Gateway - Choose an endpoint type to deploy an API](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-endpoint-types.html)
- [Amazon API Gateway - Set up private integrations in API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/private-integration.html)
- [Amazon API Gateway - Amazon API Gateway quotas and important notes](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html)
- [Amazon API Gateway - Handle errors in Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/handle-errors-in-lambda-integration.html)
- [Amazon API Gateway - HTTP API quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html)
- [Amazon API Gateway - Response transfer mode](https://docs.aws.amazon.com/apigateway/latest/developerguide/response-transfer-mode.html)
- [AWS General Reference - Amazon API Gateway endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/apigateway.html)
- [AWS Step Functions - Choose workflow type in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [AWS AppSync - What is AWS AppSync?](https://docs.aws.amazon.com/appsync/latest/devguide/what-is-appsync.html)
- [AWS AppSync - Attaching a data source](https://docs.aws.amazon.com/appsync/latest/devguide/attaching-a-data-source.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
