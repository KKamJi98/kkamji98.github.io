---
title: zot으로 HomeLab CI registry 구성하기 - Docker Hub mirror와 digest로 고정한 CI 이미지
date: 2026-10-20 01:30:00 +0900
author: kkamji
categories: [CI/CD, GitHub Actions]
tags: [zot, container-registry, docker-hub-mirror, github-actions, self-hosted-runner, kubernetes, cilium, ci-performance]
comments: true
image:
  path: /assets/img/github/github.webp
---

HomeLab Kubernetes의 GitHub Self-hosted Runner에서 웹 저장소의 테스트 job은 매번 Rust base image 338MB를 Docker Hub에서 받았습니다. 한 번 받는 데 38.8초와 50.0초가 걸렸습니다. Rust 저장소는 job마다 1.65GB짜리 CI 이미지를 직접 빌드했고, 그 이미지를 GHCR에 미리 올려 두어도 회선 다운로드가 약 8MB/s라 pull 시간이 빌드 시간과 비슷했습니다. 병목은 runner가 아니라 WAN이었습니다.

그래서 클러스터 안에 registry 하나를 두고 두 가지 용도로 쓰기로 했습니다. 하나는 Docker Hub pull-through mirror이고, 다른 하나는 CI 이미지 저장소입니다. 저는 zot을 골랐고, 이 글에는 배포하면서 확인한 설정과 측정값을 기록합니다. runner 구성 전체는 [GitHub Actions Self-hosted Runner 환경 구축하기]({% post_url 2026-10-18-github-actions-self-hosted-runner-on-kubernetes %})에 있습니다.

> **TL;DR**  
> - zot v2.1.22 하나로 Docker Hub mirror와 CI 이미지 저장소를 함께 운영한다. 배포 직후 메모리는 46Mi였다.  
> - v2.1.22에서 sync의 `preserveDigest`는 무시된다. digest로 고정한 base image를 그대로 받으려면 `http.compat: ["docker2s2"]`가 필요하다.  
> - registry에 닿는 job이 tag를 먼저 만들 수 있으므로 tag를 신뢰하지 않는다. main이 GitHub Actions cache에 기록한 digest로만 pull한다. 첫 PR run에서 CI 이미지 단계가 job당 102초에서 12~13초가 됐다.  
> - warm mirror에서 338MB image pull은 50.0초, 38.8초에서 7.2초, 8.5초가 됐다. 처음 받는 cold 요청은 이전과 같은 약 41초였다.  
{: .prompt-info}

측정은 2026-10-19부터 2026-10-20까지의 실제 CI run과, 같은 버전의 zot과 Docker로 한 로컬 실험 기준입니다. 표본이 적은 값은 건수를 함께 적었습니다.

---

## 1. registry를 고른 기준

필요한 조건은 세 가지였습니다. 두 저장소의 runner가 같은 registry를 써야 하고, Docker Hub를 mirror하면서 CI가 직접 만든 이미지도 push할 수 있어야 하며, 노드 자원을 적게 써야 했습니다. worker 노드 두 대의 메모리 요청이 이미 56~70%였기 때문입니다.

| 후보 | 확인한 내용 | 판단 |
| --- | --- | --- |
| distribution(registry) | 공식 mirror 문서는 한 번에 upstream 하나만 mirror할 수 있다고 설명한다. pull-through cache로 설정한 인스턴스에 이미지를 올리는 용도가 아니다 | mirror와 CI 저장소를 위해 인스턴스를 나눠야 한다 |
| Harbor | 공식 chart가 core, database, exporter, jobservice, nginx, portal, redis, registry, trivy를 배포한다 | 기능은 충분하지만 이 용도에는 구성 요소가 많다 |
| zot | 단일 바이너리이고, 같은 인스턴스에서 sync(mirror)와 push를 지원한다. 저장소 경로별 접근 정책을 둘 수 있다 | 선택 |

**zot은 배포 직후 메모리 46Mi, CPU 3m를 썼습니다.** Docker Hub image 다섯 종류를 mirror해 저장소가 539Mi가 된 뒤에는 145Mi였습니다.

---

## 2. 배포 구성

공식 Helm chart 0.1.128(appVersion v2.1.22)을 wrapper chart로 감싸고 Argo CD로 배포했습니다. image는 tag와 digest를 함께 고정했습니다.

### 2.1. 실행 사용자와 권한

zot image의 기본 실행 사용자는 `0`입니다. namespace에 Pod Security `restricted`를 걸고, Pod에서 사용자를 다시 지정했습니다.

```yaml
zot:
  image:
    tag: "v2.1.22@sha256:96cda11459ce6f8c60da3b03f03e9f67fd11b3ae2d82c4c04c92b3c608996080"
  service:
    type: ClusterIP
  strategy:
    type: Recreate
  podSecurityContext:
    runAsNonRoot: true
    runAsUser: 65532
    fsGroup: 65532
    seccompProfile: {type: RuntimeDefault}
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities: {drop: [ALL]}
```

### 2.2. 저장 공간의 상한

클러스터의 StorageClass는 local-path 하나이고, local-path PVC는 요청한 크기를 강제하지 않습니다. registry가 노드 디스크를 채우면 같은 노드의 runner가 시작 조건에서 멈추거나 eviction됩니다. **그래서 저장소를 PVC가 아니라 `sizeLimit`이 있는 emptyDir에 두었습니다.** 한도를 넘으면 kubelet이 Pod를 eviction하고, cache는 비어 있는 상태로 다시 시작합니다.

chart는 데이터 볼륨을 크기 제한 없는 `emptyDir: {}`로 고정해 두었기 때문에 values로 `sizeLimit`을 줄 수 없었습니다. 대신 `extraVolumes`로 볼륨을 하나 더 붙이고 zot의 `rootDirectory`를 그쪽으로 바꿨습니다.

```yaml
  extraVolumes:
  - name: store
    emptyDir: {sizeLimit: 30Gi}
  - name: tmp
    emptyDir: {sizeLimit: 1Gi}
  extraVolumeMounts:
  - {name: store, mountPath: /var/lib/zot-store}
  - {name: tmp, mountPath: /tmp}
```

### 2.3. 켜지 않은 기능

zot의 search 확장은 CVE 검사를 위해 trivy DB를 내려받습니다. 이 registry에는 CVE 검사가 필요 없어서 sync 확장만 켰습니다. 시작 로그에 `cve config not provided, skipping cve-db update`가 남습니다.

---

## 3. Docker Hub mirror 설정

```json
{
  "http": {
    "address": "0.0.0.0",
    "port": "5000",
    "compat": ["docker2s2"],
    "accessControl": {
      "repositories": {
        "**": {"anonymousPolicy": ["read"]},
        "ci/**": {"anonymousPolicy": ["read", "create"]}
      }
    }
  },
  "extensions": {
    "sync": {
      "enable": true,
      "registries": [{
        "urls": ["https://registry-1.docker.io"],
        "onDemand": true,
        "tlsVerify": true,
        "content": [{"prefix": "library/**"}]
      }]
    }
  }
}
```

### 3.1. digest를 유지하는 설정

웹 저장소는 base image를 `rust:1.99.0-alpine3.22@sha256:...`처럼 digest로 고정합니다. registry가 Docker manifest를 OCI 형식으로 바꿔 저장하면 digest가 달라지고, 고정한 digest로는 이미지를 찾을 수 없습니다. 예전 설정 예시에는 sync 옵션 `preserveDigest`가 있습니다. v2.1.22 소스의 sync 설정 구조체에는 이 필드에 `deprecated: ignored; docker media types need http.compat docker2s2`라는 주석이 달려 있습니다. **digest를 유지하려면 sync 옵션이 아니라 `http.compat`에 `docker2s2`를 넣어야 합니다.**

### 3.2. 필요한 이미지만 받기

`content`를 쓰면 주기 동기화가 켜질 수 있다고 생각했습니다. `library/**` 전체를 주기적으로 받기 시작하면 저장 공간이 바로 찹니다. v2.1.22의 `extension_sync.go`는 주기 동기화를 `len(registryConfig.Content) != 0 && registryConfig.PollInterval != 0`일 때만 켭니다. `pollInterval`을 쓰지 않았으므로 `content`는 요청 시 동기화할 저장소를 거르는 데만 쓰입니다.

요청 시 동기화에서 zot은 tag 요청이 올 때마다 upstream manifest와 비교합니다. 그래서 `ubuntu:26.04`처럼 움직이는 tag도 오래된 버전을 내주지 않습니다. digest 요청은 로컬에 있으면 upstream에 묻지 않습니다. 또 multi-arch index에서 클라이언트가 요청한 플랫폼만 받기 때문에, 로그에 다음 경고가 반복됩니다.

```text
skipping missing manifest blob in image index, continuing sync with other manifests
```

받지 않은 다른 플랫폼 manifest에 대한 경고라 동작에는 영향이 없습니다.

### 3.3. runner의 Docker daemon 설정

runner Pod의 rootless Docker daemon은 시작 인자로 mirror를 받습니다. 클러스터 내부 평문 HTTP라 `--insecure-registry`도 함께 줍니다. 이미지 무결성은 Docker가 layer와 manifest를 digest로 검증합니다.

```text
--registry-mirror=http://zot.ci-cache.svc.cluster.local:5000
--insecure-registry=zot.ci-cache.svc.cluster.local:5000
```

웹 저장소의 이미지 빌드는 buildx의 `docker` driver를 쓰므로, daemon의 mirror 설정이 BuildKit의 `FROM`에도 적용됩니다.

---

## 4. 네트워크 경계

runner namespace의 job Pod는 원래 사설 대역으로 나갈 수 없습니다. 예외로 registry Pod의 5000 포트 하나만 열었고, registry 쪽에서도 그 job Pod만 받습니다. registry가 나갈 수 있는 곳은 DNS와 Docker Hub뿐입니다.

```yaml
# registry namespace: 받는 쪽
endpointSelector:
  matchLabels: {arc.kkamji.net/role: cache}
ingress:
- fromEndpoints:
  - matchLabels:
      k8s:io.kubernetes.pod.namespace: ci-full
      arc.kkamji.net/role: job
  toPorts:
  - ports: [{port: "5000", protocol: TCP}]
```

Docker Hub는 blob 요청을 CDN으로 redirect합니다. 제가 확인했을 때의 redirect 호스트는 `production.cloudfront.docker.com`이었고, Docker 문서에 나온 Cloudflare 호스트와 함께 FQDN 허용 목록에 넣었습니다. 목록이 틀리면 zot의 sync가 실패하고, Docker는 Docker Hub에서 직접 받습니다. CI가 깨지지는 않지만 mirror 효과가 사라지므로 측정에서 드러납니다.

namespace 전체의 default-deny 정책은 처음에 `ingress: []`, `egress: []`로 썼습니다. 배포 후 `kubectl get cnp`에서 이 정책만 `VALID False`였고, 상태 메시지는 `rule must have at least one of Ingress, IngressDeny, Egress, EgressDeny`였습니다. **빈 목록은 아무것도 막지 않는 무효 정책이 됩니다.** registry Pod에는 ingress와 egress를 각각 선택하는 유효한 정책이 따로 있어서, Cilium 규칙상 두 방향 모두 이미 허용 목록 방식으로 동작하고 있었습니다. default-deny는 아무것도 허용하지 않는 규칙 `[{}]`로 고쳤고, 고친 뒤 세 정책 모두 `VALID True`가 됐습니다.

---

## 5. CI 이미지 저장소와 신뢰 경계

이 registry에는 credential이 없습니다. 비공개 저장소의 PR job도 repository secret을 읽을 수 있고, main에서만 쓸 수 있는 secret은 GitHub Environment가 있어야 만들 수 있습니다. 두 저장소 모두 Environment가 없어서, credential을 나눠도 PR job과 main job을 구분할 수 없었습니다.

경로별 권한은 다음과 같습니다.

| 경로 | 익명 권한 | 용도 |
| --- | --- | --- |
| `library/**` | `read` | Docker Hub mirror |
| `ci/**` | `read`, `create` | CI 이미지. `update`와 `delete`가 없어 한 번 올린 tag는 바뀌지 않는다 |

처음에는 tag를 입력 hash로 만들고 덮어쓰기를 막으면 충분하다고 판단했습니다. commit 직후 보안 리뷰에서 이 판단이 틀렸다는 지적을 받았습니다. **registry에 닿는 job에는 PR job과, 그 job이 실행하는 서드파티 build script도 포함됩니다.** 주차가 들어간 key는 미리 계산할 수 있으므로, 누군가 다음 주 key로 다른 이미지를 먼저 올려 두면 main은 그 tag를 덮어쓸 수 없습니다.

그래서 tag 대신 digest를 신뢰의 기준으로 바꿨습니다.

1. main에서만 실행되는 workflow가 이미지를 직접 빌드하고, 실행마다 고유한 tag로 push한다. tag가 이미 있으면 `create`만 있는 권한 때문에 push가 실패하고 아무것도 기록하지 않는다.
2. 그 workflow가 push한 이미지의 digest를 GitHub Actions cache에 저장한다.
3. PR job은 cache에서 digest를 읽고 `이미지@sha256:...` 형식으로만 pull한다. 실패하면 이전처럼 직접 빌드한다.

GitHub Actions cache는 main에서 저장한 항목을 PR이 읽을 수 있고, PR에서 저장한 항목은 그 PR 안에만 남깁니다. 이 범위 규칙이 credential 없이도 "main이 기록한 것만 믿는다"를 보장합니다. 남는 위험은 익명 `create`로 저장 공간을 채우는 것뿐이고, 이는 30Gi 상한과 보존 정책으로 막습니다. 채워지더라도 결과는 느려지는 것이지 틀린 이미지가 아닙니다.

CI에 넣기 전에 같은 버전의 zot과 Docker 29.9.1로 실제 CI 이미지를 써서 확인했습니다.

| 확인 | 결과 |
| --- | --- |
| 빌드와 push | 96초 |
| 빈 daemon에서 digest로 pull | 9.6초, 두 daemon의 image ID가 같음 |
| 같은 tag로 다시 push | `authorization failed`로 거부, digest를 기록하지 않음 |
| digest 없음, 형식 오류, 없는 digest, registry 중지 | 각각 약 0.3초 안에 로컬 빌드로 전환 |

main에 적용한 뒤 첫 PR run에서 이미지 단계는 job당 12~13초였습니다. digest 복원에 2~3초, pull에 10~11초가 걸렸습니다. 이전 66건의 중앙값 102초보다 약 89초 짧고, job 4개를 합치면 PR 하나당 약 6분입니다. 표본은 아직 1건입니다.

### 5.1. 보존 정책

```json
"retention": {
  "delay": "24h",
  "policies": [
    {"repositories": ["ci/**"], "deleteUntagged": true,
     "keepTags": [{"pulledWithin": "336h"}, {"pushedWithin": "336h"}],
     "keepUntagged": {"pushedWithin": "24h"}},
    {"repositories": ["library/**"], "deleteUntagged": true,
     "keepTags": [{"pulledWithin": "336h"}],
     "keepUntagged": {"pulledWithin": "336h"}}
  ]
}
```

zot 문서는 보존 규칙 중 하나라도 맞으면 남긴다고 설명합니다. 그래서 `ci/**`의 tag는 14일 안에 pull되거나 push된 것만 남습니다. digest로만 받아 간 mirror 이미지는 tag가 없을 수 있어서, `library/**`에는 `keepUntagged`에도 pull 기준을 두었습니다.

---

## 6. registry가 죽으면

registry를 넣으면 CI가 registry에 의존하게 됩니다. Docker는 mirror가 실패하면 Docker Hub로 다시 시도하는데, 실패 방식마다 걸리는 시간이 다릅니다. 같은 버전의 Docker로 세 가지 실패를 만들어 측정했습니다.

| mirror 실패 방식 | 클러스터에서 생기는 경우 | `docker pull` | BuildKit `FROM` |
| --- | --- | --- | --- |
| 연결 거부 | registry Pod가 없고 Service만 남은 경우 | 3.1초 | 3.5초 |
| 이름 해석 실패 | registry namespace가 없는 경우 | 3.3초 | 3.4초 |
| 응답 없이 패킷이 버려짐 | network policy가 막는 경우 | 3분 34초 | 2분 35초 |

**registry가 죽는 것보다 network policy를 잘못 바꾸는 쪽이 훨씬 비쌉니다.** 마지막 경우에는 pull 한 번마다 2~3분이 더 걸립니다. 그래서 정책을 바꾼 뒤에는 첫 CI run의 pull 시간을 확인합니다. CI 이미지 스크립트는 registry 확인에 `curl -m 5`를 써서, 이 경우에도 5초 안에 로컬 빌드로 넘어갑니다.

이 대비가 실제로 쓰인 적도 있습니다. 처음 배포에서 registry의 Argo CD Application이 참조할 프로젝트를 만들지 못해 registry가 생성되지 않았습니다. 그 사이 runner의 mirror 요청은 이름 해석 실패로 Docker Hub에서 바로 받았고, 그 시간대의 job은 실패하지 않았습니다.

---

## 7. 측정 결과

cold 요청과 warm 요청을 나눠야 비교가 맞았습니다. 처음 받는 이미지는 zot이 Docker Hub에서 받아 저장한 뒤 내주기 때문입니다. zot 로그에서 Rust base image의 첫 manifest 요청은 32초, PostgreSQL은 11초가 걸렸습니다.

**cold 요청에서는 그 시간이 BuildKit의 `FROM` 단계가 아니라 앞의 `load metadata` 단계로 옮겨 갑니다.** 웹 저장소의 PR 이미지 빌드에서 `FROM` 단계만 보면 38.5초가 7.6초로 줄었지만, 두 단계를 합치면 40.5초와 41.4초로 같았습니다. 처음에 `FROM` 시간만 비교했다면 개선을 다섯 배로 잘못 적었을 것입니다.

| 측정(웹 저장소) | mirror 전 | mirror 후 | 요청 |
| --- | --- | --- | --- |
| Rust base image 338MB, BuildKit `load metadata`와 `FROM` 합계 | 40.5초 | 41.4초 | cold |
| 같은 image를 테스트 job에서 `docker run` | 50.0초, 38.8초 | 7.2초, 8.5초 | warm |
| PostgreSQL image, 테스트 job | 19.0초, 21.3초 | 16.2초 | cold |
| PostgreSQL image, 테스트 job | 19.0초, 21.3초 | 5.5초 | warm |

warm 요청에서 273MB layer 하나를 내주는 데 zot 로그 기준 1초가 걸렸습니다. Docker Hub에서는 같은 layer를 받는 데 33.2초가 걸렸습니다.

Rust 저장소는 Docker Hub에서 42MB짜리 Ubuntu base image 하나만 받습니다. 첫 요청은 5초, 다음 runner부터는 0초였지만, CI 이미지 빌드 단계는 94초로 이전 66건의 중앙값 102초(90~126초) 범위 안이었습니다. **mirror는 큰 base image를 반복해서 받는 저장소에서 효과가 있고, 이미지를 직접 빌드하는 저장소는 빌드 결과 자체를 registry에 두어야 빨라집니다.** 5절의 CI 이미지 저장소가 그 단계입니다.

---

## 8. 남은 일과 위험

- 저장소가 emptyDir라 Pod가 다시 만들어지면 cold 상태로 시작한다. 설정을 바꿀 때마다 Pod가 다시 만들어지므로, 측정 중에는 설정 변경을 몰아서 한다.
- 익명 `create`로 저장 공간을 채울 수 있다. 상한 30Gi와 보존 정책으로만 막는다.
- warm 표본은 Rust image 2건, PostgreSQL 1건이다. 다음 CI run들로 늘린다.
- CI 이미지 저장소의 CI 효과 표본은 1건이다(job당 102초에서 12~13초). 다음 PR run으로 늘린다.
- 클러스터 내부 평문 HTTP다. 무결성은 digest로 지키지만, 전송 내용은 암호화되지 않는다.

---

## 9. Reference

- [zot - OCI-native container registry](https://zotregistry.dev/)
- [GitHub - zot configuration examples (v2.1.22)](https://github.com/project-zot/zot/blob/v2.1.22/examples/README.md)
- [GitHub - zot extension_sync.go (v2.1.22)](https://github.com/project-zot/zot/blob/v2.1.22/pkg/extensions/extension_sync.go)
- [GitHub - zot sync config.go (v2.1.22)](https://github.com/project-zot/zot/blob/v2.1.22/pkg/extensions/config/sync/config.go)
- [GitHub - zot Helm charts](https://github.com/project-zot/helm-charts)
- [CNCF Distribution - Registry as a pull through cache](https://distribution.github.io/distribution/recipes/mirror/)
- [Harbor Docs - Installation and Configuration](https://goharbor.io/docs/main/install-config/)
- [Docker Docs - Mirror the Docker Hub library](https://docs.docker.com/docker-hub/image-library/mirror/)
- [Docker Docs - dockerd](https://docs.docker.com/reference/cli/dockerd/)
- [GitHub Docs - Dependency caching reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)
- [Cilium Docs - Policy language](https://docs.cilium.io/en/stable/security/policy/language/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
