---
title: Kubernetes 환경에서 TLS 인증서 적용하기 - (2)
date: 2024-10-20 01:44:21 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, harbor, jenkins, tls, ssl, cert-manager, ingress-controller]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

이전 글([Kubernetes 환경에서 TLS 인증서 적용하기 - (1)]({% post_url 2024/2024-10-19-kubernetes-tls-1 %}))에서는 TLS(Transport Layer Security)의 개념과 인증 과정을 살펴보았습니다. 이어서 이번 포스트에서는 실제로 Kubernetes 환경에서 Let's Encrypt에서 발급받은 TLS 인증서를 적용하는 방법에 대해 다뤄보도록 하겠습니다.

> [Let's Encrypt](https://letsencrypt.org/)는 무료로 SSL/TLS 인증서를 발급해주는 공개 인증 기관입니다. Cert-Manager를 사용하면 Let's Encrypt에서 인증서를 자동으로 발급받고 갱신할 수 있습니다.
{: .prompt-tip}

---

## 1. 사전 준비 사항

- Kubernetes Cluster 1.22+
- Helm
- Domain
- Ingress Controller (Nginx Ingress Controller)

---

## 2. Kubernetes에 Cert-Manager 설치

### 2.1 Namespace 생성

```bash
❯ kubectl create namespace cert-manager
namespace/cert-manager created
❯ kubectl get ns
NAME                 STATUS   AGE
cert-manager         Active   2s
~~~
~~~
~~~
```

### 2. Helm 저장소 추가 및 업데이트

```bash
❯ helm repo add jetstack https://charts.jetstack.io
❯ helm repo update
```

### 3. Cert-Manager 설치

```bash
❯ kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.crds.yaml
❯ helm install cert-manager --namespace cert-manager --version v1.16.1 jetstack/cert-manager
```

### 4. 확인

```bash
❯ kubens cert-manager
✔ Active namespace is "cert-manager"
❯ kubectl get pods
NAME                                      READY   STATUS    RESTARTS   AGE
cert-manager-859bc755b6-wq6fs             1/1     Running   0          6m38s
cert-manager-cainjector-dc59548c5-6q47g   1/1     Running   0          6m38s
cert-manager-webhook-d45c9fbd6-ph2r8      1/1     Running   0          6m38s
```

---

## ClusterIssuer 생성

**ClusterIssuer**는 Cert-Manager에서 인증서를 발급받기 위한 설정을 정의하는 리소스입니다. Let's Encrypt를 사용하여 인증서를 발급받기 위해 **ClusterIssuer**를 생성합니다. ACME(Automatic Certificate Management Environment)는 인증서의 자동 발급과 갱신을 위한 프로토콜입니다.  

ACME는 Let's Encrypt에서 개발했으며, 클라이언트와 인증 기관 간의 상호 작용을 자동화하여 인증서 관리를 효율적으로 할 수 있도록 합니다.

### 1. ClusterIssuer Manifest 작성

```yaml
# cluster-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    # Let's Encrypt의 ACME 서버 주소
    server: https://acme-v02.api.letsencrypt.org/directory
    # 인증서 갱신 관련 이메일 주소
    email: {your-email}
    # ACME 계정 비밀키를 저장할 Secret 이름
    privateKeySecretRef:
      name: letsencrypt-prod
    # 챌린지 방식 설정 -> 인증 기관(CA)이 도메인 소유권을 확인하기 위해 사용하는 방법 지정
    # HTTP-01, DNS-01, TLS-ALPN-01 챌린지 등이 있음
    # HTTP-01 -> 가장 일반적으로 사용되는 방법으로, 웹 서버를 통한 도메인 소유권 확인
    solvers:
    - http01:
        ingress:
          class: nginx
```

### 2. ClusterIssuer 생성

```bash
❯ kubectl apply -f cluster-issuer.yaml
clusterissuer.cert-manager.io/letsencrypt-prod created
```

---

## Ingress 리소스 수정

> 이전에 구축했던 Jenkins Server의 Ingress를 수정해 TLS 인증서를 사용하도록 해보겠습니다.
{: .prompt-tip}

```yaml
# jenkins-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: jenkins-ingress
  namespace: jenkins
  labels:
    name: jenkins-ingress
  annotations:
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    ## 수정
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ## 수정 (해당 부분에 secretName을 지정하면 cert-manager가 자동으로 해당 Secret을 생성하고 관리)
  tls:
  - hosts:
    - {jenkins domain}
    secretName: jenkins-tls
  ingressClassName: nginx
  rules:
  - host: {jenkins domain}
    http:
      paths:
      - pathType: Prefix
        path: "/"
        backend:
          service:
            name: jenkins-service
            port: 
              number: 8080
```

```bash
❯ kubectl apply -f jenkins-ingress.yaml
ingress.networking.k8s.io/jenkins-ingress configured

# Secert 생성 확인
❯ kubectl get secrets
NAME          TYPE                DATA   AGE
jenkins-tls   kubernetes.io/tls   2      5m30s

# Certificate 리소스 확인
❯ kubectl get certificate
NAME          READY   SECRET        AGE
jenkins-tls   True    jenkins-tls   6m27s

# 인증서 상태 확인
❯ kubectl describe certificate jenkins-tls
Name:         jenkins-tls
Namespace:    jenkins
Labels:       name=jenkins-ingress
Annotations:  <none>
API Version:  cert-manager.io/v1
Kind:         Certificate
~~~
~~~
~~~
~~~
Events:
  Type    Reason     Age    From                                       Message
  ----    ------     ----   ----                                       -------
  Normal  Issuing    9m21s  cert-manager-certificates-trigger          Issuing certificate as Secret does not exist
  Normal  Generated  9m21s  cert-manager-certificates-key-manager      Stored new private key in temporary Secret resource "jenkins-tls-k9nkx"
  Normal  Requested  9m21s  cert-manager-certificates-request-manager  Created new CertificateRequest resource "jenkins-tls-1"
  Normal  Issuing    8m33s  cert-manager-certificates-issuing          The certificate has been successfully issued
```

---

## TLS 인증서 적용 확인

### Before

![jenkins-no-tls](/assets/img/ci-cd/jenkins/no-tls.png)

### After

![jenkins-yes-tls](/assets/img/ci-cd/jenkins/yes-tls.png)

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
