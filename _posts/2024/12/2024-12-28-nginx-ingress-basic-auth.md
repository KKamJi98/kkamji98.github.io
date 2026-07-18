---
title: Nginx Ingress에 간단 인증 절차 추가하기(Basic Auth)
date: 2024-12-28 02:16:33 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, ingress, basic-auth, nginx, authentication]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Basic Auth는 별도 identity provider 없이 HTTP request에 사용자 이름과 password를 보내는 단순한 인증 방식입니다. 이 글은 `ingress-nginx` controller를 이미 설치한 cluster에서 특정 Ingress path를 htpasswd Secret으로 보호하는 방법을 다룹니다.

> **TL;DR**  
> - 이 예제는 `ingress-nginx` 전용 annotation을 사용합니다. Ingress resource만 만들면 동작하지 않고 해당 IngressClass를 처리하는 controller가 필요합니다.  
> - Secret의 key는 반드시 `auth`여야 합니다. key가 다르면 controller가 503을 반환할 수 있습니다.  
> - Basic Auth는 encoding일 뿐 encryption이 아닙니다. TLS, secret 접근 제어, rate limit을 함께 적용하고 장기적인 사용자 인증에는 SSO 또는 external auth를 검토합니다.  
{: .prompt-info}

---

## 1. 선택 전에 알아둘 점

Kubernetes Ingress API는 stable이지만 동결되어 있으며, Kubernetes 프로젝트는 새 traffic API 설계에 Gateway API를 권장합니다. 다만 Basic Auth는 Gateway API의 공통 기능이 아니라 controller별 extension일 수 있습니다. 기존 `ingress-nginx` 환경에 간단한 접근 장벽이 필요할 때는 아래 방식이 유효하지만, 새 platform을 설계한다면 선택한 Gateway implementation의 인증 정책과 external auth 연동을 먼저 확인합니다.

| 용어 | 의미 |
| --- | --- |
| Ingress | 외부 HTTP(S) request를 cluster Service로 route하는 Kubernetes resource입니다. |
| IngressClass | 어떤 controller가 Ingress를 처리할지 나타내는 field입니다. |
| `ingress-nginx` | Ingress resource와 `nginx.ingress.kubernetes.io/*` annotation을 해석하는 controller입니다. |
| Basic Auth | `Authorization` header에 Base64 encoded credential을 보내는 HTTP authentication scheme입니다. |
| htpasswd | 사용자 이름과 password hash를 저장하는 file format입니다. |

---

## 2. htpasswd Secret 만들기

Ubuntu에서는 `apache2-utils` package에 `htpasswd`가 포함됩니다. bcrypt hash를 사용해 `auth` file을 만듭니다.

```bash
sudo apt update
sudo apt install -y apache2-utils
htpasswd -cB auth myuser
```

`-c`는 file을 새로 만들거나 덮어씁니다. 기존 사용자를 유지한 채 사용자를 추가할 때는 `-c` 없이 실행합니다. `auth` file은 password hash를 포함하므로 repository에 commit하거나 chat에 올리지 않습니다.

아래 명령은 Secret을 원하는 namespace에 apply합니다. `--from-file=auth`가 Secret의 `data.auth` key를 만듭니다.

```bash
kubectl -n <namespace> create secret generic basic-auth \
  --from-file=auth \
  --dry-run=client -o yaml | kubectl apply -f -
```

Secret과 Ingress는 기본적으로 같은 namespace에 둡니다. `ingress-nginx`는 `namespace/secretName` 형식도 지원하지만 namespace 경계를 넘는 Secret 참조는 RBAC와 운영 책임을 더 복잡하게 만들 수 있습니다.

---

## 3. TLS Ingress에 Basic Auth 연결

`ingressClassName`은 cluster에 설치한 class 이름과 일치해야 합니다. TLS Secret은 신뢰 가능한 certificate를 포함한 별도 Secret을 사용합니다.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: <namespace>
  annotations:
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth
    nginx.ingress.kubernetes.io/auth-realm: "Restricted Access"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls
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

```bash
kubectl apply -f ingress.yaml
kubectl -n <namespace> describe ingress myapp-ingress
```

`auth-secret`의 Secret name이나 `auth` key가 틀리면 정상 backend가 있어도 인증 구성 실패로 503이 발생할 수 있습니다. annotation은 controller마다 호환되지 않으므로 다른 NGINX 기반 controller에 그대로 복사하지 않습니다.

---

## 4. 동작과 보안 확인

인증 없이 요청하면 401과 `WWW-Authenticate` header를, 올바른 credential을 넣으면 backend response를 확인할 수 있습니다.

```bash
curl -I https://myapp.example.com/
curl --user myuser https://myapp.example.com/
```

Basic Auth credential은 request마다 전송됩니다. TLS가 없거나 TLS termination 이후 구간이 안전하지 않으면 credential을 보호할 수 없습니다. 다음 운영 기준을 함께 적용합니다.

- HTTPS redirect만으로 충분하다고 보지 말고 HTTP listener와 certificate renewal 상태를 점검합니다.
- Secret `get` 권한을 필요한 workload와 운영자에게만 부여하고, etcd encryption at rest와 backup 접근 권한을 검토합니다.
- browser에 credential이 cache될 수 있으므로 password rotation과 account 폐기 절차를 둡니다.
- Internet-facing endpoint에는 WAF, IP allowlist, rate limit을 함께 검토합니다. Basic Auth만으로 brute-force 공격을 방어하지 못합니다.
- 사용자 lifecycle, MFA, audit, fine-grained authorization이 필요해지면 OIDC, OAuth2 proxy, external auth 같은 중앙 인증 방식을 사용합니다.

---

## 5. Reference

- [Kubernetes Docs - Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Gateway API Docs - Concepts](https://gateway-api.sigs.k8s.io/concepts/api-overview/)
- [Ingress-NGINX Docs - Basic Authentication](https://kubernetes.github.io/ingress-nginx/examples/auth/basic/)
- [Ingress-NGINX Docs - Annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
