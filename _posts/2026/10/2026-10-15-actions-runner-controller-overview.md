---
title: GitHub Actions Runner Controller - Overview
date: 2026-10-15 16:00:00 +0900
author: kkamji
categories: [CI/CD, GitHub Actions]
tags: [github-actions, arc, actions-runner-controller, kubernetes, self-hosted-runner, security]
comments: true
arc_diagram_fixed_fhd: true
image:
  path: /assets/img/github/github.webp
---

GitHub Actions의 테스트와 빌드를 개인 PC에서 실행하려면 어디까지 직접 운영해야 할까요? Workflow 파일을 개인 PC로 옮기는 것은 아닙니다. GitHub는 계속 작업을 접수하고 결과를 보여 주며, 실제 명령을 실행할 runner만 개인 환경에 둡니다. Kubernetes에서 이 runner를 필요할 때 만들고 정리하는 도구가 **Actions Runner Controller(ARC)**입니다.

저는 같은 Windows PC의 Hyper-V VM에서 운영하는 개인 Kubernetes에 ARC를 설치해 CI를 실행하려고 합니다. 아직 ARC 설치, GitHub runner 등록, 실제 job 실행을 검증한 상태는 아닙니다. 먼저 작업이 어디서 실행되는지, 어떤 비용과 권한을 직접 책임져야 하는지 정리했습니다. 아래의 구성과 설정값은 도입 설계이며 운영 성공 기록이 아닙니다.

> **TL;DR**  
> - GitHub는 workflow의 작업 대기열과 결과를 관리하고, 개인 Kubernetes의 runner가 테스트와 빌드를 실행한다. ARC는 runner의 수량과 수명주기를 관리한다.  
> - 일회성 runner Pod가 사라져도 controller, listener, Kubernetes VM과 외부 저장 데이터는 남을 수 있다.  
> - 실행 위치를 바꿔도 Docker 명령, 계정 결제 잠금, PR 코드의 신뢰 문제까지 자동으로 해결되지는 않는다.  
{: .prompt-info}

공식 문서 확인 기준일은 **2026-10-15**입니다. 요금과 지원 기능은 바뀔 수 있으므로 적용 전 하단 Reference의 최신 문서를 다시 확인해야 합니다.

---

## 1. Runner는 job을 실행하는 환경입니다

GitHub Actions에서 Workflow는 자동화 절차를 정의한 YAML 파일입니다. Workflow 안의 Job은 하나의 runner에 배정되고, Job 안의 Step은 순서대로 실행됩니다. Workflow, Job, Step의 관계가 낯설다면 [GitHub Actions 소개 및 구성 요소]({% post_url 2025-04-27-github_actions_basic %})를 먼저 참고하면 좋습니다.

GitHub-hosted runner는 GitHub가 준비하고 관리하는 실행 환경입니다. Self-hosted runner는 사용자가 준비한 머신에서 runner 애플리케이션을 실행하는 방식입니다. 물리 PC, VM, Kubernetes의 Pod도 실행 환경이 될 수 있지만 운영 책임과 격리 수준은 서로 다릅니다.

예를 들어 Job이 소스 코드를 내려받고 테스트한 뒤 이미지를 빌드한다면, 그 명령은 runner 쪽 CPU와 메모리, 디스크를 사용합니다. GitHub 화면에 실행 로그가 보인다고 해서 실제 빌드도 GitHub의 머신에서 수행되는 것은 아닙니다.

**Self-hosted라는 말만으로 job마다 깨끗한 환경이 보장되지는 않습니다.** 같은 머신의 runner를 계속 재사용하면 이전 job의 파일과 프로세스가 남을 수 있습니다. ARC의 일회성 runner는 이 재사용을 줄이기 위한 구성입니다.

---

## 2. GitHub의 작업 관리와 Kubernetes의 실행을 연결합니다

ARC는 Kubernetes의 operator입니다. Operator는 사용자가 선언한 상태와 실제 리소스 상태를 비교하면서 필요한 작업을 수행합니다. ARC에서는 기다리는 job과 설정된 수량에 맞춰 runner를 준비하고 정리합니다.

{% include diagrams/static/ci-cd/arc-overview.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ci-cd/arc-overview--0ad953d070c8283b.png" %}

그림의 GitHub와 Kubernetes는 역할의 경계입니다. Controller와 listener는 runner를 관리하며, 테스트나 빌드 명령은 runner에서 실행합니다. 결과는 다시 GitHub Actions에 전달됩니다. 아래 구성 요소는 이름이 비슷하지만 서로 같은 Pod를 뜻하지 않습니다.

| 구성 요소 | 역할 | Job이 없을 때 |
| --- | --- | --- |
| GitHub Actions Service | Workflow 실행 접수, job 대기열, 배정과 결과 관리 | GitHub 쪽 서비스로 유지 |
| ARC controller | Runner 관련 Kubernetes 리소스 조정, GitHub API 연동, runner Pod 생성과 정리 관리 | 관리 프로세스로 유지 |
| Runner ScaleSet Listener | GitHub의 job 알림 수신, 처리 가능한 수량 확인, Kubernetes API로 원하는 runner 수 갱신 | 알림을 기다리며 유지 |
| Runner scale set | Job을 배정받는 runner의 논리 그룹과 자동 조정 설정 | 실행 Pod가 없어도 구성은 유지 |
| 일회성 runner Pod | Runner 애플리케이션으로 job을 받아 테스트와 빌드 실행 | 유휴 수량 설정에 따라 0개 가능 |

Runner scale set은 Pod 하나의 이름이 아닙니다. GitHub가 job을 보낼 대상과 ARC가 늘리거나 줄일 runner 집합을 연결합니다. Workflow의 `runs-on`이 해당 scale set의 이름이나 설정된 label과 맞아야 작업이 배정됩니다.

Listener는 GitHub Actions Service와 HTTPS long polling 연결을 유지하며 새 job 알림을 기다립니다. 알림을 처리할 수 있으면 Kubernetes API를 통해 원하는 runner 수를 갱신합니다. Controller 쪽에서는 runner 리소스를 조정하고, 등록에 필요한 Just-in-Time(JIT) 구성을 받아 Pod를 준비합니다. 이후 runner 애플리케이션이 GitHub에 연결해 실제 job 정보를 받습니다.

따라서 listener가 workflow의 셸 명령을 대신 실행하는 것은 아닙니다. Job 수신을 위해 개인 PC의 runner에 인터넷에서 직접 접속할 포트를 열어 주는 구조도 아닙니다. 다만 GitHub API, 작업 수신, 소스 다운로드, 패키지 저장소와 이미지 registry에 필요한 외부 통신은 허용되어야 합니다.

---

## 3. Job 하나가 끝날 때까지의 수명주기

테스트와 이미지 빌드를 수행하는 job 하나를 기준으로 보면 다음 순서입니다.

| 순서 | 동작 | 실행 또는 관리 주체 |
| --- | --- | --- |
| 1 | Push 등의 이벤트로 workflow를 시작하고 job을 대기열에 넣음 | GitHub Actions |
| 2 | Scale set에 배정 가능한 작업 알림을 받고 runner 수를 조정 | Listener와 ARC controller |
| 3 | Runner Pod를 스케줄링하고 이미지와 실행 환경을 준비 | Kubernetes와 ARC |
| 4 | Runner를 연결하고 소스 다운로드, 테스트와 빌드를 실행 | Runner 애플리케이션과 job 코드 |
| 5 | 실행 로그와 job 상태를 전달하고, 선언된 artifact가 있으면 업로드 | Runner와 GitHub Actions |
| 6 | 완료 상태를 확인한 뒤 일회성 runner와 Pod를 정리 | GitHub Actions와 ARC |

Job은 workflow 전체와 다릅니다. `test`와 `build`를 별도 Job으로 나누면 각각 별도의 runner 실행이 필요할 수 있습니다. 두 Job 사이에 필요한 파일도 자동으로 공유되지 않으므로 artifact나 registry 같은 전달 경로를 명시해야 합니다.

유휴 runner를 0개로 두면 첫 작업은 Pod 생성, 이미지 pull, 도구 준비와 runner 연결을 기다립니다. ARC가 runner를 만들 수 있어도 Kubernetes에 CPU나 메모리 여유가 없으면 Pod가 Pending 상태로 남을 수 있습니다. GitHub의 job 대기와 Kubernetes의 Pod 대기는 구분해서 확인해야 합니다.

### 3.1. 일회성 등록과 디스크 정리는 다릅니다

일반 self-hosted runner를 `--ephemeral`로 등록하면 GitHub Actions는 그 runner에서 job 하나를 처리한 뒤 등록을 해제합니다. 공식 문서는 등록 해제 이후 runner를 지우는 자동화는 운영자가 준비해야 한다고 설명합니다. ARC는 runner와 Pod의 수명주기를 관리하지만, **등록 해제나 Pod 삭제가 전체 디스크의 안전한 삭제를 뜻하지는 않습니다.**

Pod의 임시 파일이 사라지는 것과 PVC, `hostPath`, 노드의 이미지 cache, 외부 artifact 및 로그가 삭제되는 것은 별개입니다. 볼륨 종류와 reclaim 정책에 따라 남는 데이터가 달라지며, 삭제된 파일의 물리적 복구 불가까지 보장하는 것도 아닙니다. 일회성 runner를 쓰더라도 저장소별 보존과 정리 정책이 필요합니다.

실패 원인을 분석할 runner 로그 역시 Pod와 함께 잃지 않도록 외부에 보관해야 합니다. 이때 자격증명이나 민감한 환경 변수가 로그에 남지 않게 해야 합니다.

---

## 4. Runner 0개는 PC가 꺼진다는 뜻이 아닙니다

다음은 개인 환경에서 작은 규모로 시작하기 위한 values 일부의 설계 예시입니다. 설치 명령이나 적용 완료 설정이 아닙니다.

```yaml
minRunners: 0
maxRunners: 1
```

`minRunners`는 유지할 유휴 runner 수입니다. `maxRunners`는 scale set이 늘릴 수 있는 runner 수의 상한입니다. 위 예시는 작업이 없을 때 runner를 0개로 줄이고, 작업이 생기면 최대 1개까지 준비하는 구성입니다. 동시 job 요청이 많아도 이 scale set에서 처리할 runner는 1개이므로 나머지 작업은 기다릴 수 있습니다.

**줄어드는 것은 job을 실행하는 runner이며, ARC 관리 Pod나 Hyper-V VM이 아닙니다.** Controller와 listener, Kubernetes의 관리 및 시스템 Pod는 계속 필요합니다. VM을 자동 종료하고 다시 켜는 기능도 이 설정에 포함되지 않습니다.

또한 최대 runner 1개가 클러스터 전체 Pod 1개를 의미하지는 않습니다. Kubernetes mode에서는 job이나 service를 위한 추가 Pod가 생성될 수 있습니다. CPU와 메모리 예산에는 이 작업용 Pod와 상시 관리 리소스를 함께 포함해야 합니다.

---

## 5. Kubernetes mode는 Docker 명령의 번역기가 아닙니다

Runner가 Kubernetes 안에서 실행된다는 사실과, workflow의 컨테이너를 어떤 방식으로 실행할지는 별도 선택입니다.

| 실행 방식 | 일반적인 실행 위치 | 먼저 확인할 사항 |
| --- | --- | --- |
| 기본 runner Pod, 이 글에서는 plain으로 구분 | 일반 `run` step을 runner 컨테이너 안에서 실행 | 필요한 CLI와 런타임을 이미지에 준비. 기본 runner만으로 Docker daemon이 생기지는 않음 |
| Docker-in-Docker(DinD) | Runner Pod 안의 별도 Docker daemon으로 컨테이너 실행 | Docker 의존 workflow와의 호환성, privileged 권한과 저장 공간 |
| Kubernetes mode | Runner container hooks가 같은 namespace에 job, service 또는 container action용 Pod를 생성 | Job container, hooks용 권한, 작업 파일 공유와 스토리지 구성 |

여기서 plain은 별도 `containerMode`를 설정하지 않은 기본 구성을 설명하기 위한 표현입니다. 공식 chart의 `containerMode.type: plain` 값을 뜻하지 않습니다.

### 5.1. 기존 Docker workflow를 그대로 옮길 수 있는가

기존 workflow가 단순한 셸 명령이나 JavaScript Action을 사용한다면 runner 이미지에 필요한 도구를 준비하는 것으로 시작할 수 있습니다. 반면 job container, service container 또는 Docker 기반 Action을 사용한다면 그 컨테이너를 실행할 지원 방식이 필요합니다.

Kubernetes mode는 runner container hooks를 이용하는 방식입니다. Workflow에 적힌 임의의 `docker run`을 Kubernetes Pod 생성으로 바꾸지 않습니다. `docker buildx build --load`도 빌드 결과를 로컬 Docker image store에 넣는 동작이므로, 사용할 Docker daemon과 builder가 없는 환경에서 그대로 동작한다고 기대하면 안 됩니다.

이런 workflow는 Docker 호환 실행 환경을 선택하거나, 별도 이미지 빌더와 registry를 사용하는 흐름으로 수정해야 합니다. ARC를 설치하는 작업과 기존 workflow의 호환성을 검증하는 작업을 분리해야 하는 이유입니다.

공식 문서에는 Kubernetes mode의 파일 공유 방식으로 persistent volume을 사용하는 구성과 container lifecycle hooks를 사용하는 `kubernetes-novolume` 구성이 함께 있습니다. 따라서 Kubernetes mode에 항상 같은 PVC와 StorageClass가 필요하다고 일반화하지 않고, 사용할 chart와 구성에서 실제 요구사항을 확인해야 합니다.

또한 Kubernetes mode의 기본 설정은 job container를 선언하지 않은 workflow를 거부합니다. `ACTIONS_RUNNER_REQUIRE_JOB_CONTAINER=false`로 이를 해제하면 Kubernetes API 권한을 가진 runner 컨테이너에서 명령이 직접 실행될 수 있습니다. 오류를 없애기 위한 기본 처방으로 적용하지 말고, 실행 코드가 얻는 권한부터 검토해야 합니다.

### 5.2. DinD의 편의와 권한 비용

공식 ARC 문서의 DinD 구성은 privileged 모드를 요구합니다. Docker와 비슷한 사용 방식을 유지하기 쉬워도, runner가 공격받았을 때의 영향까지 같아지는 것은 아닙니다. Rootless DinD 이미지로 바꾸는 것만으로 공식 구성의 privileged 요구가 없어지는 것도 아닙니다.

**Docker 호환성을 위해 privileged를 허용하는 결정은 별도의 보안 판단입니다.** 개인 클러스터라는 이유로 기존 서비스와 같은 노드에서 바로 허용하지 않고, 실행할 코드의 신뢰 수준과 노드 분리 가능성, 호스트 접근 경로를 먼저 검토해야 합니다.

---

## 6. Self-hosted 실행 요금과 전체 운영 비용

2026-10-15에 확인한 GitHub 공식 문서는 GitHub Actions의 self-hosted runner 실행 자체를 무료로 안내합니다. 다만 runner 머신을 유지하는 비용은 사용자 책임이라고 명시합니다.

| 비용 항목 | ARC로 실행 위치를 옮겼을 때 |
| --- | --- |
| GitHub-hosted runner의 실행 시간 | Self-hosted로 배정한 job은 개인 실행 환경을 사용 |
| GitHub Actions artifact와 cache | GitHub 저장 서비스의 포함량, 보존 기간과 과금 정책을 별도 확인 |
| 개인 PC와 Hyper-V VM | 전기, CPU와 메모리 사용, 장비 및 운영 부담 유지 |
| 로컬 디스크와 registry | 이미지 layer, 빌드 cache, 볼륨, 로그 및 외부 저장 공간 관리 필요 |

Artifact와 cache도 같은 저장 한도를 공유한다고 가정하면 안 됩니다. 현재 공식 문서는 artifact와 GitHub Packages의 공유 저장량, repository별 cache 포함량을 구분합니다. Cache는 포함량보다 큰 저장 한도를 설정했는지에 따라서도 초과 과금 조건이 달라집니다. 실행 위치를 개인 클러스터로 바꿔도 `upload-artifact`나 cache 기능이 자동으로 로컬 저장소로 바뀌지는 않습니다.

이미 켜 둔 개인 PC를 사용하더라도 추가 전력과 저장 공간이 0이라고 단정할 수 없습니다. 실제 비용 판단에는 job 횟수와 실행 시간, VM의 상시 자원, 이미지 및 cache가 쌓이는 속도를 측정해야 합니다. 아직 실행하지 않은 제 환경의 절감액을 수치로 제시하지 않는 이유입니다.

### 6.1. 계정 결제 잠금은 별도로 해결해야 합니다

Self-hosted 실행이 무료라는 설명만 보고 계정의 billing lock도 해결된다고 생각하기 쉽습니다. 하지만 공식 locked-account 문서는 결제 승인 보류 실패가 개인 계정의 billing을 잠그고, GitHub Actions나 다른 무료 등급 기능 접근까지 막을 수 있다고 설명합니다.

**ARC는 GitHub 계정의 결제 잠금을 해제하는 수단이 아닙니다.** GitHub가 workflow 접수나 실행을 차단하면 개인 클러스터에 runner를 준비해도 정상 처리된다고 보장할 수 없습니다. 공식 절차에 따라 결제 정보를 수정하거나, 화면에 해결할 결제 문제가 보이지 않는 경우 GitHub Support에 검토를 요청해야 합니다. runner를 바꾸거나 검사 결과를 수동으로 성공 처리해서 해결할 문제가 아닙니다.

---

## 7. 개인 Kubernetes에 코드를 실행시킬 때의 신뢰 경계

CI는 저장소의 코드를 내려받아 실행하는 시스템입니다. 테스트 스크립트도 파일을 읽고, 네트워크에 접속하고, 실행 환경에 주어진 권한을 사용할 수 있습니다. 개인망의 서비스에 접근 가능한 runner라면 공개 PR의 코드가 그 네트워크 안에서 실행될 수 있다는 점부터 검토해야 합니다.

Namespace를 분리하면 리소스 이름과 정책 범위를 구분할 수 있지만, 별도의 커널을 가진 VM처럼 격리되지는 않습니다. RBAC와 네트워크 정책을 명시하지 않거나 privileged, 호스트 볼륨 또는 Docker socket을 노출하면 다른 경로로 영향이 이어질 수 있습니다.

| 경계 | 확인할 내용 |
| --- | --- |
| GitHub 인증 | ARC용 자격증명과 job의 `GITHUB_TOKEN`을 구분. 등록 대상과 필요한 권한에 맞게 GitHub App 또는 지원되는 인증 방식 선택 |
| Secrets | Controller의 등록용 비밀을 job에 불필요하게 노출하지 않음. Workflow와 로그에도 비밀 값을 포함하지 않음 |
| ServiceAccount와 RBAC | Controller, listener, runner의 역할을 분리. Kubernetes hooks에 필요한 권한도 대상 namespace와 작업 범위로 검토 |
| NetworkPolicy | 개인 서비스, Kubernetes API와 외부 목적지 접근을 제한. CNI가 정책을 실제 강제하는지 검증 |
| 호스트와 저장소 | Privileged, `hostPath`, Docker socket, 공유 PVC와 cache의 신뢰 경계 확인 |
| PR CI와 배포 | 신뢰하지 않는 변경의 테스트와 배포 권한을 가진 실행 경로를 분리 |

NetworkPolicy YAML이 생성되었다는 사실만으로 통신이 차단되는 것은 아닙니다. 공식 Kubernetes 문서도 이를 구현하는 네트워크 플러그인이 없으면 효과가 없다고 설명합니다. 실제 CNI 지원 여부와 허용 및 차단 통신을 확인해야 합니다.

PR 테스트에 배포 secret을 주지 않는 것만으로 모든 문제가 끝나지는 않습니다. GitHub의 보안 가이드도 공개 저장소에 self-hosted runner를 사용하는 것을 강하게 경고합니다. Runner 자체가 가진 ServiceAccount 권한, 볼륨과 네트워크 접근도 job 코드가 이용할 수 있습니다. 공개 PR을 개인망 runner에 바로 연결하지 않고, PR CI와 검토된 변경의 배포는 runner 접근 범위와 GitHub Environment 승인 등으로 분리하는 설계가 필요합니다. Environment 승인은 배포 시작과 해당 secret 접근을 통제하지만, runner 실행 환경 자체를 격리하지는 않습니다.

---

## 8. 개인 환경에서 확인할 실행 결과

개인 Hyper-V Kubernetes에서 ARC를 실제 운영하는 것이 목표입니다. 설치 작업에서는 먼저 controller와 runner의 namespace, RBAC, 사용할 실행 모드와 자원 예산을 확정해야 합니다. 이 글을 작성하는 과정에서는 클러스터 설치나 runner 등록, 자격증명 생성 및 권한 변경을 수행하지 않았습니다.

설치 후에는 최소한 다음 결과를 구분해서 기록하려고 합니다.

- 관리 리소스의 준비 완료와 GitHub의 scale set 연결 상태
- 테스트 job의 배정, runner Pod 준비, 실제 테스트 및 빌드 결과
- Job 완료 후 runner Pod 정리와 잔여 볼륨, 이미지 및 로그 상태
- PR 코드와 배포 경로의 권한 분리, 실제 네트워크 차단 결과

이 기록이 있어야 구성 예시를 제 환경의 운영 결과로 바꿀 수 있습니다. 지금 단계에서 ARC의 역할은 명확합니다. GitHub의 작업 관리 기능은 유지하면서, 개인 Kubernetes가 준비한 일회성 runner에서 코드를 실행하도록 연결합니다. 그 대신 **실행 환경의 호환성, 격리와 유지 비용은 직접 책임져야 합니다.**

---

## 9. Reference

- [GitHub Docs - Self-hosted runners](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)
- [GitHub Docs - Actions Runner Controller](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller)
- [GitHub Docs - Deploying runner scale sets with Actions Runner Controller](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets)
- [GitHub Docs - Self-hosted runners reference](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
- [GitHub Docs - Authenticating to the GitHub API](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/authenticate-to-the-api)
- [GitHub Docs - GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub Docs - Unlocking a locked account](https://docs.github.com/en/billing/how-tos/troubleshooting/locked-account)
- [Kubernetes Docs - Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes Docs - Multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/)
- [GitHub Docs - Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
- [Docker Docs - docker buildx build](https://docs.docker.com/reference/cli/docker/buildx/build/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
