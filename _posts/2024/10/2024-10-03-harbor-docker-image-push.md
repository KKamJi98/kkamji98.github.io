---
title: Harbor에 컨테이너 이미지 업로드하기
date: 2024-10-03 23:44:21 +0900
author: kkamji
categories: [DevOps, Container]
tags: [kubernetes, harbor]     # TAG names should always be lowercase
comments: true
content_kind: lab
image:
  path: /assets/img/registry/harbor/harbor.webp
---

Harbor는 OCI registry에 project 단위 권한, 취약점 scan, retention, content trust 같은 운영 기능을 더한 container image registry입니다. 이 글은 project에 versioned image를 push하고 digest로 검증해 pull하는 기본 흐름을 다룹니다.

> **TL;DR**  
> - Harbor에 push하려면 먼저 project를 만들고 `<harbor-address>/<project>/<repository>:<tag>` 형식으로 image를 tag합니다.  
> - self-signed CA를 쓰는 HTTPS registry는 client가 해당 CA를 신뢰하도록 설정합니다. HTTP 또는 무분별한 insecure registry 설정은 피합니다.  
> - CI에는 사람 계정보다 project-scoped robot account와 만료, 최소 권한을 사용하고 deployment는 mutable tag 대신 digest를 사용합니다.  
{: .prompt-info}

---

## 1. 이미지 이름과 project 이해하기

Harbor에서 project는 image repository와 권한을 묶는 최상위 단위입니다. private project는 member 또는 권한이 있는 robot account만 pull할 수 있고, public project는 누구나 pull할 수 있습니다.

| 구성 요소 | example | 의미 |
| --- | --- | --- |
| registry | `harbor.example.com` | Harbor endpoint입니다. port가 기본 HTTPS port가 아니면 port도 포함합니다. |
| project | `platform` | 권한과 policy를 적용하는 Harbor namespace입니다. |
| repository | `api` | 하나의 image 계열과 tag를 보관합니다. |
| tag | `1.0.0` | 사람이 읽는 version label입니다. 같은 tag는 변경될 수 있습니다. |
| digest | `sha256:...` | image content를 식별하는 immutable hash입니다. |

Harbor UI에서 project를 먼저 생성합니다. CI가 push할 project는 기본적으로 private으로 두고, 필요한 pull 권한만 부여합니다. proxy cache project에는 직접 push할 수 없습니다.

```text
local image -- tag --> harbor.example.com/platform/api:1.0.0
                              |
                            push
                              |
                         Harbor project
                              |
                    digest-pinned image pull
                              |
                       Kubernetes workload
```

---

## 2. TLS trust와 로그인

Docker client는 registry에 HTTPS로 연결하려고 합니다. Harbor가 사설 CA로 서명한 certificate를 사용한다면 CA certificate를 client host의 아래 경로에 설치합니다. `<harbor-address>`에는 registry port가 있으면 port까지 포함합니다.

```bash
sudo install -d -m 0755 /etc/docker/certs.d/<harbor-address>
sudo install -m 0644 ca.crt /etc/docker/certs.d/<harbor-address>/ca.crt
```

그 후 project에 push 권한이 있는 account로 로그인합니다.

```bash
docker login <harbor-address>
```

`insecure-registries`는 plain HTTP 또는 검증되지 않은 certificate를 허용하게 하므로 production 해결책으로 사용하지 않습니다. CA trust 문제는 certificate chain, DNS name, client trust store를 수정해 해결합니다.

CI에서는 project-scoped robot account를 만들고 `Pull Repository`와 필요한 경우 `Push Repository`만 부여합니다. robot secret은 생성 화면에서 한 번만 받을 수 있으므로 secret manager에 저장하고, 만료일과 rotation 절차를 설정합니다.

---

## 3. Image tag와 push

예시로 public image를 가져와 project namespace와 version tag를 붙입니다. `latest`는 이후 다른 image를 가리킬 수 있으므로 release와 deployment에는 명시적인 version tag를 사용합니다.

```bash
docker pull alpine:3.20
docker tag alpine:3.20 <harbor-address>/platform/alpine:3.20
docker push <harbor-address>/platform/alpine:3.20
```

push가 끝나면 Harbor UI의 repository에서 artifact, tag, digest, scan 결과와 project policy를 확인합니다. tag immutability, vulnerability severity policy, retention policy는 production project별로 결정합니다.

---

## 4. Digest로 pull 검증

push 결과에 표시된 digest 또는 Harbor UI의 digest를 사용하면 정확히 같은 artifact를 다시 가져올 수 있습니다.

```bash
docker pull <harbor-address>/platform/alpine@sha256:<digest>
docker image inspect <harbor-address>/platform/alpine@sha256:<digest>
```

특정 image만 삭제해 pull을 다시 확인하려면 대상 reference를 명시합니다. `docker rmi $(docker images -q) -f`처럼 host의 모든 local image를 제거하는 명령은 build cache와 실행 중인 workload에 영향을 줄 수 있으므로 사용하지 않습니다.

```bash
docker image rm <harbor-address>/platform/alpine:3.20
docker pull <harbor-address>/platform/alpine@sha256:<digest>
```

Kubernetes에서 private Harbor project의 image를 pull하려면 node runtime에도 registry CA trust가 필요하며, Pod에는 project pull 권한을 가진 `imagePullSecret`이 필요합니다. registry credential을 Pod manifest에 평문으로 넣지 않습니다.

---

## 5. 정리

Harbor push의 핵심은 단순 upload가 아니라 project 경계와 artifact 식별을 함께 정하는 일입니다. HTTPS CA trust와 최소 권한 robot account로 push 경로를 제한하고, deployment에서는 version tag를 추적용으로 남기되 digest를 사용하면 재현 가능한 pull 기준을 만들 수 있습니다.

---

## 6. Reference

- [Harbor Docs - Create Projects](https://goharbor.io/docs/2.15.0/working-with-projects/create-projects/)
- [Harbor Docs - Pulling and Pushing Images in the Docker Client](https://goharbor.io/docs/2.15.0/working-with-projects/working-with-images/pulling-pushing-images/)
- [Harbor Docs - Create Project Robot Accounts](https://goharbor.io/docs/2.15.0/working-with-projects/project-configuration/create-robot-accounts/)
- [Kubernetes Docs - Pull an Image from a Private Registry](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
