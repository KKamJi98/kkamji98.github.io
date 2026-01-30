---
title: Nginx Ingress Controller 구축하기
date: 2024-09-16 20:20:45 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, nginx-ingress-controller]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

**Nginx Ingress Controller**는 Kubernetes Cluster에서 Ingress 리소스를 처리하여 외부 트래픽을 서비스로 라우팅하는 역할을 합니다. 해당 포스트에서는 **Helm**을 사용해 **Nginx Ingress Controller**를 구축하는 과정에 대해 다뤄보도록 하겠습니다.

---

## 1. Nginx Ingress Controller 설치

### 1.1. Helm Repository 추가

```bash
❯ helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
❯ helm repo update
```

### 1.2. Helm을 사용해 Nginx Ingress Controller 설치

```bash
helm install nginx-ingress ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace
```

---

## 2. 설치 확인

```bash
❯ kubectl get svc -n ingress-nginx
NAME                                               TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                      AGE
nginx-ingress-ingress-nginx-controller             LoadBalancer   10.111.215.81   10.0.0.240    80:32251/TCP,443:31300/TCP   3m
nginx-ingress-ingress-nginx-controller-admission   ClusterIP      10.97.125.60    <none>        443/TCP                      3m

❯ k get ingressclass
NAME    CONTROLLER             PARAMETERS   AGE
nginx   k8s.io/ingress-nginx   <none>       52m
```

---

## 3. 테스트

### 3.1. 테스트용 어플리케이션 배포

```bash
❯ kubectl create deployment nginx-test --image=nginx --port=80

deployment.apps/nginx-test created
❯ kubectl expose deployment nginx-test --port=80 --target-port=80 --name=nginx-test-service

service/nginx-test-service exposed
```

### 3.2. 테스트용 Ingress 리소스 설정

> 기존에 사용하고 있는 kkamji.net 도메인을 사용하였습니다.
{: .prompt-info}

```bash
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-test-ingress
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: test.kkamji.net
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx-test-service
            port:
              number: 80

❯ k apply -f nginx-test-ingress.yaml
ingress.networking.k8s.io/nginx-test-ingress created
```

### 3.3. ingress 확인

```bash
❯ k get ingress
NAME                 CLASS   HOSTS             ADDRESS   PORTS   AGE
nginx-test-ingress   nginx   test.kkamji.net             80      4m53s
```

### 3.4. test.kkamji.net으로 접속 확인

```bash
❯ curl test.kkamji.net
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }
</style>
</head>
<body>
<h1>Welcome to nginx!</h1>
<p>If you see this page, the nginx web server is successfully installed and
working. Further configuration is required.</p>

<p>For online documentation and support please refer to
<a href="http://nginx.org/">nginx.org</a>.<br/>
Commercial support is available at
<a href="http://nginx.com/">nginx.com</a>.</p>

<p><em>Thank you for using nginx.</em></p>
</body>
</html>
```

---

## 4. Reference

- nginx 공식 문서 - <https://docs.nginx.com/nginx-ingress-controller/installation/installing-nic/installation-with-helm/>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
