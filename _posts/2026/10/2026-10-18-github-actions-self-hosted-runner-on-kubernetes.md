---
title: GitHub Actions Self-hosted Runner 환경 구축하기 - 홈랩 Kubernetes와 ARC
date: 2026-10-18 19:00:00 +0900
author: kkamji
categories: [CI/CD, GitHub Actions]
tags: [github-actions, arc, actions-runner-controller, kubernetes, self-hosted-runner, rootless-docker, ci-performance]
comments: true
image:
  path: /assets/img/github/github.webp
---

개인 저장소 두 곳의 GitHub Actions job이 시작되지 않았습니다. Hosted runner는 계정 결제 한도에 걸려 있었고, workflow는 대기열에서 움직이지 않았습니다. 저는 같은 Windows PC의 Hyper-V VM으로 운영하는 홈랩 Kubernetes에 Actions Runner Controller(ARC)를 설치하고 두 저장소의 CI를 옮겼습니다. ARC의 구성 요소와 수명주기, 실행 방식과 신뢰 경계는 [GitHub Actions Runner Controller - 개념과 아키텍처]({% post_url 2026-10-15-actions-runner-controller-overview %})에 정리했습니다.

옮긴 뒤 첫 측정에서 Rust 저장소의 gate workflow는 약 2시간이 걸렸습니다. 같은 job이 hosted runner에서는 병렬로 약 25분이었습니다. 이후 runner 슬롯, CPU 한도, job 배치를 바꾸면서 측정한 값과, CI를 15분 안팎으로 줄이기 위한 설계를 함께 기록합니다.

> **TL;DR**  
> - Docker가 필요 없는 제어 job은 light 풀, 빌드와 테스트는 rootless DinD를 쓰는 full 풀로 나눴다.  
> - full 풀은 privileged 없이 Pod user namespace, capability 3개, 전용 seccomp profile, device plugin으로 할당한 TUN 장치로 Docker를 실행한다.  
> - 동시 실행 상한은 노드당 TUN 슬롯 1개와 namespace ResourceQuota로 걸었다. ARC 0.15는 quota에 거부된 runner Pod를 30초마다 다시 만든다.  
> - 제어 job을 light 풀로 옮기자 웹 저장소 CI가 64분에서 30분으로 줄었다. 남은 병목은 Rust 저장소의 중복 컴파일과 오라클 테스트 2개이고, fixture 캐싱과 build once로 줄이는 작업을 진행하고 있다.  
{: .prompt-info}

측정은 2026-10-15부터 2026-10-18까지의 실제 run 기준입니다. 아직 적용하지 않은 설계의 효과는 **예상**으로 따로 표시했습니다.

---

## 1. 환경과 옮길 CI

| 항목 | 값 |
| --- | --- |
| 호스트 | Windows PC, Ryzen 9 5950X(16코어 32스레드), 메모리 64GB |
| 클러스터 | kubeadm, Kubernetes 1.36, control plane 1대와 worker 2대(Hyper-V VM) |
| worker | 처음 3 vCPU, 지금 8 vCPU(할당 가능 7.4코어), 메모리 12GiB |
| ARC | `gha-runner-scale-set` 0.15.0, 공식 chart와 digest 고정 이미지 |
| 배포 | Argo CD가 Helm chart 저장소를 GitOps로 동기화 |

옮길 CI는 성격이 다른 두 저장소입니다.

| 저장소 | CI 구성 | 특징 |
| --- | --- | --- |
| 웹 플랫폼 | Java/Gradle API, Node 프런트엔드, PostgreSQL 컨테이너, 이미지 빌드와 e2e | job 실행은 짧고 Docker가 필요하다. main merge는 이미지 게시와 배포로 이어진다 |
| Rust 퀀트 연구 | Ubuntu 26.04 컨테이너에서 Tier A/B 테스트, Python 오라클 비교, release 빌드 | 컴파일이 무겁고 bwrap sandbox 테스트가 user namespace와 새 `/proc` mount를 요구한다 |

Rust 저장소의 sandbox 테스트가 이 작업의 가장 큰 제약이었습니다. 기존 workflow는 hosted runner에서 호스트 sysctl을 바꾸고 컨테이너의 seccomp와 AppArmor를 끈 상태로 실행했습니다. **runs-on만 바꾸거나 실패하는 sandbox 테스트를 빼는 방식은 처음부터 선택지에서 제외했습니다.**

---

## 2. Runner 풀을 두 종류로 나눴습니다

모든 job이 Docker를 쓰지는 않습니다. 변경 경로를 판단하는 `gate`나 결과를 모으는 `ci-ok` 같은 job은 몇 초면 끝납니다. 그래서 runner를 두 풀로 나눴습니다.

| 풀 | namespace | 실행 환경 | 용도 |
| --- | --- | --- | --- |
| light | `ci-pr` | nonroot, Kubernetes token 미마운트, Docker 없음 | 제어 job, canary |
| full | `ci-full` | runner 컨테이너와 rootless Docker sidecar | 빌드, 테스트, 이미지 |

두 풀은 controller도 따로 둡니다. full 풀의 controller는 `ci-full`만 감시하고, 기존 controller는 `ci-pr`만 감시합니다. CRD는 기존 controller Application이 소유하고 full 쪽 Application은 CRD를 건너뜁니다.

Namespace는 default-deny NetworkPolicy로 시작했습니다. DNS, GitHub, Actions 결과 업로드 같은 목적지만 Cilium FQDN 규칙으로 열었습니다. job Pod는 Kubernetes API와 노드, 사설 대역, metadata 주소로 나갈 수 없고, controller와 listener만 API에 접근합니다.

---

## 3. privileged 없이 rootless DinD를 실행했습니다

공식 ARC 문서의 DinD 구성은 privileged를 요구합니다. 저는 같은 노드에 다른 서비스도 있어서 privileged를 쓰지 않기로 했고, 대신 권한을 하나씩 확인하며 필요한 만큼만 열었습니다.

### 3.1. Pod 구성

full runner Pod는 컨테이너 두 개로 구성됩니다.

| 역할 | 실행 사용자 | 권한 |
| --- | --- | --- |
| runner(SDK) 컨테이너 | UID 1001 | capability 0개, `allowPrivilegeEscalation: false`, 읽기 전용 root, RuntimeDefault seccomp |
| Docker daemon sidecar | UID 1001 | `SETUID`, `SETGID`, `SETFCAP`만 추가, `procMount: Unmasked`, 전용 Localhost seccomp profile |

Pod 전체에는 `hostUsers: false`를 걸었습니다. Pod 안의 UID 0과 65536개 UID 범위가 노드의 다른 UID로 매핑되므로, sidecar가 가진 capability도 그 user namespace 안에서만 의미가 있습니다. 두 컨테이너가 공유하는 것은 작업 디렉터리와 Docker API socket뿐이고, runner의 private HOME과 등록 파일은 daemon에 마운트하지 않습니다.

```yaml
spec:
  hostUsers: false
  automountServiceAccountToken: false
  resources:            # Pod 수준 예산, 두 컨테이너가 함께 사용
    requests: {cpu: 500m, memory: 5Gi}
    limits: {cpu: "4", memory: 5Gi}
  initContainers:
  - name: dind
    restartPolicy: Always   # native sidecar
    securityContext:
      runAsUser: 1001
      privileged: false
      readOnlyRootFilesystem: true
      procMount: Unmasked
      capabilities:
        drop: [ALL]
        add: [SETUID, SETGID, SETFCAP]
      seccompProfile:
        type: Localhost
        localhostProfile: arc-docker-runtime-v2.json
    resources:
      limits:
        kkamji.net/arc-tun: "1"
```

메모리 5Gi는 Pod 수준 예산입니다. Kubernetes 1.36에서 두 컨테이너의 cgroup 상위 한도가 각각 5Gi가 아니라 합계 5Gi로 잡히는 것을 별도 Pod로 먼저 확인했습니다.

### 3.2. 막힌 지점과 바꾼 것

한 번에 동작하지 않았습니다. 권한을 하나 열 때마다 다음 실패 지점이 드러났고, 각 단계에서 바꾼 것은 다음과 같습니다.

| 관측 | 원인 | 바꾼 것 |
| --- | --- | --- |
| 기본 seccomp에서 `unshare`와 namespace clone 실패 | RuntimeDefault가 중첩 user namespace 생성을 막음 | 필요한 syscall만 허용한 Localhost profile을 DaemonSet으로 worker에 배포 |
| UID 매핑 helper 실패 | 매핑에 필요한 capability 부족 | `SETUID`, `SETGID`, `SETFCAP`만 추가 |
| 중첩 namespace의 사용자 ID가 의도와 다르게 바뀜 | 이미지의 SUID `mount`, `umount` | 두 파일의 SUID 비트만 제거 |
| 분리된 network namespace bind 실패 | rootless 진입점의 기본 동작 | 공식 진입점의 `DETACH_NETNS=0` 사용 |
| slirp가 `/dev/net/tun` 없음으로 실패 | 노드에 장치가 있어도 Pod에 할당되지 않음 | device plugin으로 `kkamji.net/arc-tun` 리소스를 노드당 1개 등록 |
| BuildKit `docker-container` driver가 sysfs mount에서 거부됨 | 해당 driver가 privileged sysfs를 요구 | containerd image store와 기본 `docker` driver 사용 |

**노드에 `/dev/net/tun`이 있다는 사실과 Pod가 그 장치를 쓸 수 있다는 사실은 다릅니다.** containerd 기본 설정은 TUN을 device cgroup에 허용하지 않고, kubelet은 임의의 Pod annotation을 CRI의 CDI annotation으로 넘기지 않습니다. 파일 mount나 annotation만으로는 해결되지 않아 device plugin을 썼습니다. device plugin 자체도 UID 0이지만 capability 0개, 읽기 전용, `no_new_privs`로 실행되고 privileged가 아닙니다.

이 구성에서 Docker 29의 pull, build와 cache, 컨테이너 실행, bridge, published port, bind mount, named volume을 확인했습니다. 그 뒤 실제 GitHub JIT 등록과 원래 workflow로 검증했습니다.

---

## 4. 첫 실제 run에서 실패한 것

고정된 진단 Pod에서 통과해도 실제 GitHub job에서는 다른 곳에서 실패했습니다.

### 4.1. checkout 위치와 작업 디렉터리

Rust 저장소의 첫 run은 테스트 전에 exit code 125로 멈췄습니다. checkout이 runner의 private HOME 아래에 생겼고, Docker daemon은 공유 작업 볼륨 밖의 그 경로를 만들 수 없었습니다. ARC 0.15 소스에서 JIT 설정의 WorkFolder는 runner 컨테이너의 `workingDir`에서 정해집니다. `workingDir`을 공유 작업 경로인 `/home/runner/_work`로 지정하자 checkout 위치가 맞았습니다.

### 4.2. Docker 데이터 크기

다음 run은 Tier A 도중 Pod가 eviction됐습니다. 원인은 메모리가 아니라 Docker 데이터 emptyDir가 한도 10Gi를 넘은 것이었습니다. 12Gi와 16Gi에서도 같은 이유로 실패했고, 16Gi에서는 테스트 바이너리 277개를 빌드한 뒤 한도에 닿았습니다. 실패한 run은 기록으로 남겼고, 한도를 높인 값이 최소 필요량이라고 보지 않았습니다. 테스트를 빼거나 ELF를 strip하는 방식도 쓰지 않았습니다.

대신 runner가 저장소 코드를 실행하기 전에 노드 여유를 확인합니다. 필요한 디스크 예산에 `max(5Gi, 파일시스템 15% + 1Gi)`를 더한 값보다 여유가 적으면 job을 시작하지 않습니다. kubelet의 imagefs eviction 기본값 15%를 반영한 값입니다. 현재 Docker 데이터는 16Gi이고, 30Gi로 늘리는 변경을 준비하고 있습니다.

---

## 5. Runner 이미지는 private GHCR digest로 고정했습니다

처음에는 직접 빌드한 runner 이미지를 한 worker에만 import하고 `imagePullPolicy: Never`로 썼습니다. 그래서 runner가 그 노드에만 배치될 수 있었습니다.

이미지 레시피를 Helm chart 저장소에 두고 private GHCR에 올린 뒤, values에는 digest와 `IfNotPresent`를 썼습니다. 레지스트리 digest는 기존 로컬 이미지 digest와 같았습니다. pull secret은 External Secrets Operator가 기존 Parameter Store 항목에서 `dockerconfigjson`으로 만듭니다. 토큰은 `read:packages` 권한만 가진 classic PAT이고, 값은 소유자가 직접 입력했습니다.

이미지가 없던 worker에서 측정한 cold pull은 Docker sidecar 이미지 4분 53초, runner 이미지 20초였습니다. 첫 배치 한 번의 비용이고 이후에는 노드 cache를 씁니다.

---

## 6. 동시 실행 상한은 TUN 슬롯과 quota로 걸었습니다

처음 측정한 Rust 저장소 gate는 약 2시간이었습니다. full 풀이 `maxRunners: 1`이었고 quota도 runner 하나만 허용했기 때문에 job 여섯 개가 차례로 실행됐습니다(Tier A 34분, Tier B 13분, release 8분, proof receipts 8분 등).

이미지를 GHCR로 옮긴 뒤 노드 고정을 풀고 다음처럼 바꿨습니다.

- runner Pod는 worker 2대 중 어디에나 배치한다. 노드당 `kkamji.net/arc-tun` 슬롯이 1개라 노드마다 runner는 최대 1개다.
- 저장소별 풀은 `maxRunners: 2`.
- `ci-full` quota는 runner 2개만 허용한다. `requests.kkamji.net/arc-tun` 2, 메모리 요청 10752Mi 등 실측 사용량에 여유를 더한 값이다.

세 번째 runner는 노드에서 Pending으로 남지 않고 quota에서 거부됩니다. ARC 0.15의 `ephemeralrunner_controller.go`는 `exceeded quota:` 오류를 받으면 30초 뒤 다시 시도하고, 만든 지 10분이 지난 EphemeralRunner는 지워서 새로 만들게 합니다. job은 실패하지 않고 기다립니다. runner set을 교체할 때 job을 실행 중인 runner는 건너뛰므로(`ephemeralrunnerset_controller.go`), 템플릿을 바꾸는 merge가 진행 중인 job을 끊지 않습니다.

**이 quota는 동시 실행 상한일 뿐 공정한 대기열이 아닙니다.** 두 저장소가 슬롯 2개를 먼저 잡는 쪽이 쓰는 방식으로 나눠 씁니다. 저장소별로 1개를 보장하는 방법도 검토했지만, quota로는 "평소에는 나눠 쓰고 상대가 쉬면 모두 쓴다"를 표현할 수 없어서 적용하지 않았습니다. 고정하면 Rust 저장소가 다시 직렬 실행으로 돌아갑니다.

---

## 7. 측정으로 찾은 병목과 바꾼 것

### 7.1. CPU 한도

worker가 3 vCPU이고 runner CPU 한도가 2였던 3일 동안 runner Pod는 CFS 기간의 14~21%에서 throttle됐습니다. 노드 사용률은 최대 84~86%였고 hypervisor steal은 0%였습니다. 호스트에는 여유가 있었기 때문에 worker를 8 vCPU로 늘리고 runner CPU 한도를 4로 올렸습니다. CPU 요청은 500m로 그대로 두어 다른 workload의 스케줄링 보장은 바뀌지 않습니다.

### 7.2. 제어 job을 light 풀로

웹 저장소 run 하나가 64분 걸렸을 때 job 실행 시간의 합은 약 12분이었습니다. 나머지는 full 슬롯 대기였고, 몇 초짜리 `gate`가 4~11분, 결과 집계 `ci-ok`가 약 34분을 기다렸습니다.

`gate`와 `ci-ok`를 light 풀로 옮겼습니다. 계약 테스트로 이 두 job은 light, 나머지는 full에서 실행되도록 고정했습니다.

| 지표 | 변경 전 | 변경 후 |
| --- | --- | --- |
| `gate` 대기 | 4~11분 | 28초 |
| 웹 저장소 CI 전체 | 64분 | 30분 |

30분 중에서도 대부분은 여전히 full 슬롯 대기입니다. `e2e` job 하나가 28분을 기다리고 1분 실행된 기록도 있습니다. **웹 저장소가 느린 직접 원인은 Rust 저장소가 PR마다 runner를 약 104분 점유하는 것입니다.**

---

## 8. CI를 15분 안팎으로 줄이는 설계

### 8.1. Rust 저장소 측정

| 구분 | 시간 | 내용 |
| --- | --- | --- |
| 컴파일 | 약 48분 | job 5개가 같은 소스를 각자 처음부터 컴파일. Tier A 19분 21초, Tier B 10분 9초, source qualification 6분 24초, release 5분 48초. `CARGO_BUILD_JOBS=1` |
| 테스트 | 약 38분 | source qualification 1659초 중 오라클 테스트 2개가 1652초(1081초, 571초) |
| 이미지 빌드 | 약 10분 | job마다 Ubuntu 26.04 CI 이미지를 92~138초 동안 빌드 |

직렬로 합하면 117분입니다. 슬롯이 무한해도 가장 긴 job인 source qualification 36분이 하한입니다. 메모리는 최대 4.98GiB로 한도 5Gi에 붙어 있었고 CPU 사용은 여유가 있었습니다. **지금 병목은 CPU보다 메모리와 슬롯 수입니다.**

### 8.2. 미리 만든 CI 이미지는 이득이 없었습니다

처음 안에는 CI 이미지를 GHCR에 미리 올려 job마다 빌드를 건너뛰는 단계가 있었습니다. 측정해 보니 이미지는 1.65GB이고 집 회선의 실측 다운로드는 약 8MB/s라 pull에도 60~90초가 걸립니다. 로컬 빌드 92초와 차이가 거의 없어서 이 단계는 뺐습니다. 병목은 WAN 다운로드이므로 클러스터 내부 pull-through registry mirror를 대신 검토하고 있습니다.

### 8.3. 4단계

1. **오라클 결과 fixture 캐싱.** Python 오라클은 같은 입력에 같은 결과를 냅니다. 오라클 커밋과 driver, 테스트, CI 이미지 정의, Python 환경 고정 스크립트의 hash를 key로 결과를 저장하고, PR에서는 Rust 결과를 저장된 fixture와 비교합니다. 기록과 저장은 main에서만 실행되는 별도 workflow가 맡고, 두 번 기록해 byte 단위로 같을 때만 저장합니다. PR job은 복원만 하고, cache가 없으면 지금처럼 오라클을 직접 실행합니다. main에 저장한 cache는 모든 PR이 읽을 수 있지만 PR이 저장한 cache는 그 PR 범위에만 남으므로 PR이 main의 fixture를 바꿀 수 없습니다.
2. **한 번 컴파일하고 나눠 실행.** 큰 runner 하나가 테스트 바이너리를 빌드해 `cargo nextest archive`로 묶고, 테스트 job은 archive를 받아 partition 단위로 실행합니다. tier별 컴파일 설정을 먼저 통일해야 합니다.
3. **클러스터 내부 cache.** 이미지 layer는 내부 registry mirror로 받습니다. sccache는 build once 뒤에 검토합니다. Tier A 테스트 컨테이너가 `--network=none`이라 테스트 단계 안에서는 네트워크 cache를 쓸 수 없습니다.
4. **작업 크기별 슬롯.** 웹 저장소 runner의 실측 최대 메모리는 2.76GiB, CPU는 0.76코어였는데 할당은 5Gi와 슬롯 하나 전체입니다. worker 메모리를 16GiB로 늘린 뒤 웹 저장소 runner를 약 3.5Gi로 줄이고 노드당 슬롯을 늘려 두 저장소가 서로 기다리지 않게 합니다.

### 8.4. 예상 효과

아래 표의 오른쪽 열은 측정값이 아니라 **예상**입니다. 각 단계를 적용한 뒤 실제 run으로 다시 측정합니다.

| 대상 | 측정 | 적용 후 예상 |
| --- | --- | --- |
| 웹 저장소 PR | 30분(64분 사례) | 약 10~12분 |
| Rust 저장소 PR | 직렬 117분, 최장 job 36분 | 약 13~15분 |
| Rust 저장소 runner 사용 | PR당 104분 | 30분대 |

1단계 없이 나머지만 적용하면 Rust 저장소는 오라클 테스트 18분 때문에 약 20~22분에서 멈출 것으로 봅니다.

---

## 9. 운영하면서 남은 위험

- 두 저장소가 슬롯 2개를 공정성 보장 없이 나눠 쓴다.
- Docker 데이터를 30Gi로 늘리면 시작 조건이 노드 여유 약 49GiB가 된다. 이미지가 쌓이면 kubelet image GC(85%)보다 시작 조건이 먼저 걸린다.
- 다른 workload의 PriorityClass가 `PreemptLowerPriority`라 노드가 꽉 차면 runner를 선점할 수 있다. runner 자신은 선점하지 않는 우선순위 0 class를 쓴다.
- runner 이미지에 공식 이미지에서 온 setuid `sudo`가 남아 있다. runner 컨테이너는 `no_new_privs`와 capability 0개라 막히지만 제거 대상이다.
- 하나의 GitHub App 키를 두 namespace가 공유한다. 저장소별 자격증명 격리가 아니다.

---

## 10. Reference

- [GitHub Docs - Actions Runner Controller](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller)
- [GitHub Docs - Deploying runner scale sets with Actions Runner Controller](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets)
- [GitHub Docs - Dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
- [GitHub - actions-runner-controller ephemeralrunner_controller.go (0.15.0)](https://github.com/actions/actions-runner-controller/blob/gha-runner-scale-set-0.15.0/controllers/actions.github.com/ephemeralrunner_controller.go)
- [GitHub - actions-runner-controller ephemeralrunnerset_controller.go (0.15.0)](https://github.com/actions/actions-runner-controller/blob/gha-runner-scale-set-0.15.0/controllers/actions.github.com/ephemeralrunnerset_controller.go)
- [Kubernetes Docs - User Namespaces](https://kubernetes.io/docs/concepts/workloads/pods/user-namespaces/)
- [Kubernetes Docs - Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
- [Kubernetes Docs - Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes Docs - Restrict a Container's Syscalls with seccomp](https://kubernetes.io/docs/tutorials/security/seccomp/)
- [Docker Docs - Rootless mode](https://docs.docker.com/engine/security/rootless/)
- [Docker Docs - containerd image store](https://docs.docker.com/engine/storage/containerd/)
- [cargo-nextest - Archiving and reusing builds](https://nexte.st/docs/ci-features/archiving/)
- [GitHub - mozilla/sccache](https://github.com/mozilla/sccache)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
