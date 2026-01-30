---
title: Nginx Ingress에 간단 인증절차 추가하기(Basic Auth)
date: 2024-12-28 02:16:33 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, ingress, basic-auth, nginx, authentication]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

일반적으로 **쿠버네티스 환경**에서 애플리케이션을 노출할 때, Ingress Controller를 활용해 HTTP/HTTPS 트래픽을 라우팅합니다. 그런데 간단한 테스트나 내부용 서비스처럼 **전체 인증/인가 시스템을 구축하기엔 오버**지만, 그래도 **외부에 바로 열고 싶지 않은 경우**가 있습니다.

예컨대:

- 사내 POC 서비스나 개발용 애플리케이션을 일단 인터넷에서 접속 가능하게 하되, 팀원 외에는 못 들어오게 하고 싶을 때
- 별도의 OAuth/OpenID/SAML 같은 인증 시스템까지는 필요 없고, 임시로 **ID/Password** 한 세트를 걸어두고 싶을 때

이럴 때 **Nginx Ingress**가 제공하는 **Basic Authentication** 기능을 사용하면 **손쉽게 인증 절차**를 추가할 수 있습니다.

---

## 1. 개념

**Basic Auth**는 가장 간단한 형태의 HTTP 인증 방식 중 하나로, **Base64로 인코딩된 ID/PW**를 HTTP Header(`Authorization`)에 넣어 전송합니다. SSL 없이 사용하면 Credential이 노출될 위험이 있으므로, **HTTPS 환경**(TLS Ingress)에서 사용하는 것이 바람직합니다.

Nginx Ingress Controller에서는 **Ingress 리소스**에 **특정 Annotation**을 달고, 별도로 **htpasswd 포맷**의 Secret을 만들어 등록하면, 해당 Host/Path에 접속 시 Basic Auth 창이 뜨게 됩니다.

---

## 2. 사용 방법

### 2.1. htpasswd 파일 생성

> Nginx의 Basic Auth를 사용하려면, **htpasswd** 유틸리티로 사용자 정보를 생성해야 합니다.  
> 우분투의 경우 `apache2-utils`, 레드햇 계열의 경우 `httpd-tools`의 패키지를 설치해야 합니다.  
{: .prompt-tip}

```bash
htpasswd -c auth myuser
```

- `-c`: 새 파일 생성  
- `auth`: 결과가 들어갈 파일 이름  
- `myuser`: 사용자명 (ID)

이렇게 하면 비밀번호 입력 후, `auth` 파일에 아래와 같은 내용이 생깁니다:

```shell
myuser:$apr1$1CYkL3..$hKr3YnMXrRRvNcY/Knmhf/
```

### 2.2. Secret으로 변환

생성된 `auth` 파일(= htpasswd 파일)을 쿠버네티스 Secret으로 만들어야 Nginx Ingress가 참조할 수 있습니다.

```bash
kubectl create secret generic basic-auth \
  --from-file=auth \
  -n <namespace>
```

- **Secret 이름**: `basic-auth` (임의로 설정 가능)  
- `--from-file=auth` : key가 `auth`인 데이터 항목으로 저장

### 2.3. Ingress 리소스에 Annotation 추가

이제 Ingress에 **Annotation**을 달아 Basic Auth를 활성화합니다.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: <namespace>
  annotations:
    # Basic Auth 설정
    nginx.ingress.kubernetes.io/auth-type: "basic"
    nginx.ingress.kubernetes.io/auth-secret: "basic-auth"
    nginx.ingress.kubernetes.io/auth-realm: "Restricted Access"
spec:
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: myapp-service
            port:
              number: 80
```

- `nginx.ingress.kubernetes.io/auth-type: "basic"`: Basic Auth를 사용한다고 지정  
- `nginx.ingress.kubernetes.io/auth-secret: "basic-auth"`: 위에서 만든 Secret 이름과 동일해야 함  
- `nginx.ingress.kubernetes.io/auth-realm`: 로그인 창에 보일 Realm 메시지 (선택)

> **중요**: 여기서 `auth-secret`이 가리키는 것은 **htpasswd 파일**을 담은 Secret(위에서 `basic-auth`로 만든 것)입니다.  
{: .prompt-danger}

### 2.4. 옵션들

- **Whitelist IP**: 특정 IP에서 인증 없이 접근하게 하려면, `nginx.ingress.kubernetes.io/whitelist-source-range` 사용
- **Force HTTPS**: Basic Auth를 쓸 때는 `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"`로 HTTP->HTTPS 리다이렉트 권장
- **custom-error-page** 등 다른 Annotation도 조합 가능

---

## 3. 마무리

Nginx 혹은 Nginx Ingress Controller의 **Basic Auth**를 사용해 별도의 인증 서버를 구축하지 않고 웹사이트에 간단한 인증 절차를 추가할 수 있습니다. 사이드 프로젝트나 테스트용 애플리케이션을 외부에 노출할 때 간단한 인증 보호를 위해 효과적으로 사용할 수 있습니다.  

> **HTTPS** 환경에서만 사용하는 것을 권장합니다.(**HTTP**로 Basic Auth 쓰면 PW가 그대로 노출될 위험이 있음)  
{: .prompt-danger}

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
