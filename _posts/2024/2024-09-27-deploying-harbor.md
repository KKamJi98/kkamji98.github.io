---
title: Kubernetes에서 Harbor 구축하기
date: 2024-09-27 21:31:41 +0900
author: kkamji
categories: [DevOps, Container]
tags: [kubernetes, harbor]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/harbor/harbor.webp
---

**Harbor**는 오픈소스 컨테이너 이미지 레지스트리로, Docker 및 OCI 이미지 포맷을 저장하고 관리할 수 있는 솔루션입니다. 기본적으로 안전한 이미지 관리를 위해 보안 스캠, 서명, 복제 등의 기능을 제공하며, 대규모 엔터프라이즈 환경에서 다양한 이미지 관리 요구를 충족시키기 위해 설계되었습니다. **Harbor**는 특히 프라이빗 이미지 레지스트리를 구축하는 데 유용하며, 클라우드 환경뿐만 아니라 온프레이스에서도 사용할 수 있어 다양한 인프라 요구사항에 적용할 수 있습니다.

이전에 진행했던 **Weasel** 프로젝트를 클라우드에서 로컬 Kubernetes로 마이그레이션하는 작업을 시작하며 컨테이너 이미지를 ECR이 아닌 온프레미스에서 관리해볼까? 라는 생각에 여러가지 솔루션을 고민하였습니다. [Line Engineering](https://engineering.linecorp.com/ko/blog/harbor-for-private-docker-registry)과 [SKT Enterprise](https://www.sktenterprise.com/bizInsight/blogDetail/dev/6171) 기술 블로그를 보고 오픈소스 기반, 강력한 보안 기능을 갖춘 **Harbor**에 매력을 느끼게 되었고, 도입을 확정하게 되었습니다. 해당 포스트에서는 Kubernetes에서 **Harbor**를 구축하는 과정에 대해 다뤄보도록 하겠습니다.

---

## 1. 사전 조건

- Kubernetes cluster 1.10+
- Helm 2.8.0+
- High available Ingress Controller
- High available PostgreSQL database
- High available Redis
- PVC (Persistent Volume Claim) 또는 외부 오브젝트 스토리지

---

## 2. 실습 환경

- Kubernetes cluster v1.29.6
- Helm v3.15.3
- Nginx Ingress Controller
- Local Path Provisioner

---

## 3. Helm 저장소 추가

> Helm 패키지를 사용하여 **Harbor**를 구축하기 위해 **Harbor Chart**가 있는 Helm 저장소를 추가합니다.
{: .prompt-tip}

```bash
❯ helm repo add harbor https://helm.goharbor.io
"harbor" has been added to your repositories
❯ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "aws-secrets-manager" chart repository
...Successfully got an update from the "secrets-store-csi-driver" chart repository
...Successfully got an update from the "harbor" chart repository
...Successfully got an update from the "fluent" chart repository
...Successfully got an update from the "cilium" chart repository
...Successfully got an update from the "prometheus-community" chart repository
Update Complete. ⎈Happy Helming!⎈
```

---

## 4. Namespace 생성

> **Harbor**를 설치할 Namespace를 생성합니다.
{: .prompt-tip}

```bash
❯ kubectl create namespace harbor
namespace/harbor created
```

---

## 5. Helm으로 Harbor 설치

> Helm을 사용해 Harbor를 설치하기 위해 values.yaml 파일을 다운로드 후 필요에 맞게 설정하고 설치를 진행하도록 하겠습니다.
{: .prompt-tip}

### 5.1 values.yaml 다운로드

```bash
❯ helm show values harbor/harbor > values.yaml
❯ ls
values.yaml
```

### 5.2 values.yaml 파일 수정

> Redis, PostgreSQL, Ingress, externalURL, AdminPassword 등 관련된 설정을 올바르게 수정합니다. TLS 인증서는 자동으로 생성하도록 설정 해주었으며, 여기 나와있는 내용 이외의 이미지 서명 기능인 Notary, 이미지 취약점 스캐너인 Clair, Webhook 등의 설정도 가능합니다.
{: .prompt-tip}

```yaml
expose:
  type: ingress
  tls:
    enabled: true  # TLS 활성화
    certSource: auto  # TLS 인증서 자동 생성
    auto:
      commonName: "~~~~"  # 인증서에 사용할 도메인
  ingress:
    hosts:
      core: ~~~~  # Harbor에 접근할 도메인
    controller: default  # NGINX Ingress Controller 사용
    className: "nginx" # ingress className 입력
    annotations:
      nginx.ingress.kubernetes.io/ssl-redirect: "true"  # HTTPS 리디렉션
      nginx.ingress.kubernetes.io/proxy-body-size: "0"  # 업로드 크기 제한 해제
...
...
...
externalURL: # Harbor에 접근할 도메인
...
...
...
persistence:
  enabled: true
  resourcePolicy: "keep"
  persistentVolumeClaim:
    registry:
      existingClaim: ""
      storageClass: "local-path" # 사용할 StorageClass
      subPath: ""
      accessMode: ReadWriteOnce
      size: 10Gi # 이미지 저장을 위한 스토리지 용량
      annotations: {}
    database:
      existingClaim: ""
      storageClass: "local-path" # 사용할 StorageClass
      subPath: ""
      accessMode: ReadWriteOnce
      size: 1Gi
      annotations: {}
    redis:
      existingClaim: ""
      storageClass: "local-path" # 사용할 StorageClass
      subPath: ""
      accessMode: ReadWriteOnce
      size: 1Gi
      annotations: {}
...
...
...
harborAdminPassword: # Admin Password
```

### 5.3 Harbor 배포

```bash
helm install harbor harbor/harbor --namespace harbor -f values.yaml
```

---

## 6. 접속 확인

> values.yaml 파일에 입력한 AdminPassword를 사용해 접속해봅니다.
{: .prompt-tip}

![harbor connection](/assets/img/harbor/harbor_connection_test.webp)

![harbor login](/assets/img/harbor/harbor_login_test.webp)

---

## 7. Reference

- Harbor 공식문서 - <https://www.sktenterprise.com/bizInsight/blogDetail/dev/6171>
- Line Engineering - <https://goharbor.io/docs/2.0.0/install-config/harbor-ha-helm/>
- SKT Enterprise - <https://engineering.linecorp.com/ko/blog/harbor-for-private-docker-registry>

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
