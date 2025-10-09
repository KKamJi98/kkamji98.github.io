---
title: Keycloak & ArgoCD SSO 구현하기
date: 2025-02-23 22:52:55 +0900
author: kkamji
categories: [DevOps, SSO]
tags: [keycloak, sso, realm, argocd, rbac, pkce]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/security/keycloak/keycloak.webp
---

저번 시간에([Keycloak 개념, Helm으로 배포하기]({% post_url 2025/2025-02-22-keycloak %})) Keycloak을 배포하고 기본적인 설정을 해보았습니다. 이번 시간에는 Keycloak과 ArgoCD를 연동하여 SSO를 구현해보도록 하겠습니다.

---

## 1. 실행 환경

> ArgoCD, Keycloak이 배포되어있는 Kubernetes 환경에서 시작하도록 하겠습니다.
{: .prompt-tip}

- Kubernetes (v1.32.0)
- Keycloak (v26.1.2)
- ArgoCD (v2.14.2)

---

## 2. Keycloak Client 생성하기

1. Keycloak 관리자 페이지에 접속 후, 설정할 **Realm**을 선택합니다.  
2. 왼쪽 사이드바의 **Clients** 메뉴로 이동한 뒤, **Create** 버튼을 클릭합니다.

![Create Client-1](/assets/img/security/keycloak/client-1.webp)

> 사진과 같이 Client Type을 OpenID Connect로 설정 후, Client ID, Name을 `ArgoCD` 등으로 지정합니다.
{: .prompt-tip}

![Create Client-2](/assets/img/security/keycloak/client-2.webp)

> 기본 값인 `Standard Flow`, `Direct Access Grants` 옵션은 그대로 두고 넘어갑니다.
{: .prompt-tip}

![Create Client-3](/assets/img/security/keycloak/client-3.webp)

> 마킹된 부분에 ArgoCD 도메인을 넣어주시면 됩니다. ex) `argocd.example.com`
>
> **Root URL** - ArgoCD의 Root URL을 입력합니다. 사용자가 Keycloak 인증 후 돌아올 서비스의 Root 경로입니다.  
> **Home URL** - 사용자가 로그인에 성공한 뒤 이동할 경로 (로그인 하면 /applications로 이동하도록 설정)  
> **Valid Redirect URIs** - OIDC 인증 후 Keycloak에서 리다이렉트할 URL을 입력합니다. (Callback URL)  
> > 위에 기재된 주소가 아니라면 Keycloak이 리다이렉트를 거부하며 에러를 발생시킵니다.  
>
> **Web origins** - CORS 허용 범위를 지정하기 위한 필드입니다. (ArgoCD의 URL을 입력합니다.)  
{: .prompt-tip}

---

## 3. PKCE 설정하기

> OIDC 인증 시 **Proof Key for Code Exchange(PKCE)** 방식을 사용하면, 클라이언트 보안을 한층 더 강화할 수 있습니다.  
> Keycloak과 ArgoCD의 인증 흐름에서 `S256` 암호화 기법을 사용하도록 설정하면, **Code Challenge**와 **Code Verifier**로 이루어지는 인증 과정을 안전하게 진행할 수 있습니다.  
{: .prompt-tip}

1. 생성한 Client의 `Advanced Settings`(고급 설정) 탭으로 이동합니다.
2. **Proof Key for Code Exchange Code Challenge Method** 옵션을 **S256**으로 선택합니다.

![PKCE](/assets/img/security/keycloak/pkce.webp)

---

## 4. Client Scope 설정하기

> Keycloak에서는 Client Scope를 통해 **Client에게 제공할 권한과 Scope**를 확장하거나 제한할 수 있습니다.  
> ArgoCD와의 연동에서, 사용자의 **Group** 정보를 전달하기 위해 `groups` Scope가 활성화되어야 합니다.  
{: .prompt-tip}

1. 왼쪽 사이드바의 **Client Scopes** 메뉴로 이동한 뒤, **Create client scope** 버튼을 클릭합니다.

![Client Scope-1](/assets/img/security/keycloak/client-scope-1.webp)

---

## 5. Mapper 설정하기

> 사용자에게 할당된 **Group** 정보를 **ID Token** 혹은 **Access Token**으로 전달하기 위해 **Mapper**를 설정합니다.  
{: .prompt-tip}

1. 생성한 Client Scope 설정 화면에서 `Mappers` 탭으로 이동합니다.  
2. Configure New Mapper를 클릭한 뒤, `Group Membership`을 선택한 뒤, 아래의 예시처럼 설정합니다.
3. Assigned Type을 `Default`로 설정합니다.

![Client Scope Mappers-1](/assets/img/security/keycloak/client-scope-mappers-1.webp)  

![Client Scope Mappers-2](/assets/img/security/keycloak/client-scope-mappers-2.webp)  

![Client Scope Mappers-3](/assets/img/security/keycloak/client-scope-mappers-3.webp)  

---

## 6. Group 생성하기

> ArgoCD에 맵핑할 Keycloak Group을 생성합니다.
{: .prompt-tip}

1. 왼쪽 사이드바의 **Groups** 메뉴로 이동한 뒤, **Create Group** 버튼을 클릭합니다.
2. `ArgoCDAdmins` 라는 이름으로 그룹을 생성합니다.

![ArgoCDAdmins Group](/assets/img/security/keycloak/keycloak-group.webp)

---

## 7. Group에 User 추가하기

> Keycloak Groups에 사용자를 할당하여, 해당 사용자들이 인증 시 Group 정보를 받도록 구성합니다.
{: .prompt-tip}

1. 생성한 Group으로 이동한 뒤, **Members** 탭으로 이동합니다.
2. `Add Member` 버튼을 클릭하여 사용자를 추가합니다.

![ArgoCDAdmins Member](/assets/img/security/keycloak/keycloak-member.webp)

---

## 8. ArgoCD 설정하기 (argocd-cm)

> ArgoCD에 Keycloak SSO를 적용하기 위해, ArgoCD의 설정 파일을 수정합니다.
{: .prompt-tip}

```shell
❯ kubectl edit cm -n argocd argocd-cm

apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  url: https://{YOUR_DOMAIN}
  oidc.config: |
    name: Keycloak
    issuer: https://{YOUR_KEYCLOAK_DOMAIN}/realms/master
    clientID: argocd
    enablePKCEAuthentication: true
    requestedScopes: ["openid", "profile", "email", "groups"]
    # clientSecret을 사용하는 경우라면 별도로 아래 항목 추가:
    # clientSecret: <YOUR_CLIENT_SECRET>
```

---

## 9. ArgoCD RBAC 구성 (argocd-rbac-cm)

> Keycloak Group과 ArgoCD의 Role을 연결하기 위해, ArgoCD의 RBAC 설정 파일을 수정합니다.  
> 필요에 따라 role:readonly, role:developer 등을 추가할 수 있습니다.  
{: .prompt-tip}

```shell
❯ kubectl edit cm -n argocd argocd-rbac-cm

apiVersion: v1
data:
  policy.csv: |
    # Keycloak 그룹 /ArgoCDAdmins -> ArgoCD의 admin 역할 매핑
    g, /ArgoCDAdmins, role:admin
```

---

## 10. 결과 확인

![ArgoCD Keycloak](/assets/img/security/keycloak/argocd-keycloak.webp)  
![Keycloak Login](/assets/img/security/keycloak/keycloak-login.webp)  
![ArgoCD Application](/assets/img/security/keycloak/argocd-applications.webp)  
![ArgoCD Group](/assets/img/security/keycloak/argocd-group.webp)  

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
