---
title: Liveness, Readiness, Startup Probes 개념, 사용방법
date: 2024-11-25 21:51:24 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, liveness-probe, readiness-probe, startup-probe, health-check, liveness, readiness, startup, probe]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

컨테이너 기반 애플리케이션을 **Kubernetes** 환경에서 운영하다 보면, `kubectl get pods` 명령어를 통해 Pod의 상태가 **Running**임을 확인했음에도 불구하고 애플리케이션에 접속했을 때 에러가 발생하는 상황을 종종 마주하게 됩니다. Pod는 실행 중이지만 내부 애플리케이션은 아직 서비스 준비를 마치지 못했거나, 초기화 과정(예: 데이터베이스 커넥션 풀 생성, 캐시 로딩)이 완료되지 않은 상태일 수 있기 때문입니다.

이런 문제를 방지하고자 쿠버네티스는 **Liveness**, **Readiness**, **Startup Probe**를 제공합니다. 이를 통해 Pod가 실제로 트래픽을 받을 준비가 되었는지, 정상 작동 중인지, 그리고 충분한 기동 시간을 거쳤는지를 판단할 수 있습니다. 이번 포스팅에서는 이들 Probe의 개념과 활용 방법을 살펴보며, 안정적이고 예측 가능한 애플리케이션 배포 전략을 구축하는 방법에 대해 알아보겠습니다.

---

## 1. Probe란?

**Probe**는 쿠버네티스 **Kubelet이 주기적으로 Pod 내 컨테이너 상태를 점검하는 수단**입니다. **HTTP 요청**, **TCP 소켓 연결**, **컨테이너 내부 명령어 실행** 등 다양한 방식으로 애플리케이션의 상태를 확인합니다. 이를 통해 컨테이너의 상태(health)를 판단하고, 비정상 상태일 경우 자동 조치(재시작 등)를 취할 수 있습니다.  

Probe에는 크게 아래 3가지 유형이 있습니다.

### 1.1. Liveness Probe

컨테이너가 "여전히 살아있는지"를 확인하는 Probe입니다. 만약 컨테이너 내부에 데드락(deadlock)이나 치명적 오류가 발생하여 더 이상 정상 응답을 하지 않는다면, Liveness Probe 실패 시 kubelet은 해당 컨테이너를 재시작하여 문제를 해결하려고 합니다.

### 1.2. Readiness Probe

컨테이너가 "트래픽을 받을 준비가 되었는지"를 확인하는 Probe입니다. 애플리케이션이 기동되었지만, 아직 완전한 처리 준비가 되지 않은 경우(예: DB 커넥션 풀 준비, 캐시 로딩), Readiness Probe를 통해 이 기간 동안은 Service 엔드포인트에서 Pod를 제외하여 실제 요청이 전달되지 않도록 합니다.

### 1.3. Startup Probe

애플리케이션 기동에 많은 시간이 걸리는 경우, Startup Probe를 사용하여 "애플리케이션이 완전히 시작되었는지" 확인할 수 있습니다. Startup Probe가 성공하기 전까지는 Liveness와 Readiness Probe 체크를 지연시킴으로써, 초기화 시간이 긴 애플리케이션이 Liveness Probe에 의해 조기 재시작되는 문제를 예방할 수 있습니다.

---

## 2. Probe 동작 방식

Probe는 아래와 같은 방식으로 상태를 확인합니다.  

- **HTTP GET Probe**: 지정한 포트와 경로에 HTTP GET 요청을 보내고 응답 코드(2xx, 3xx 등)에 따라 정상/비정상을 판단합니다.  
- **TCP Socket Probe**: 특정 포트에 TCP 연결 시도를 통해 연결 가능 여부로 상태를 판단합니다.  
- **Exec Command Probe**: 컨테이너 내부에서 명령어를 실행하고 종료 코드를 통해 상태를 판단합니다(0이면 성공).  

각 Probe는 **주기(period)**, **초기 대기 시간(initialDelaySeconds)**, **타임아웃(timeoutSeconds)**, **연속 실패 횟수(failureThreshold)** 등을 세밀하게 조정할 수 있어, 애플리케이션 특성에 맞는 유연한 헬스 체크 전략을 수립할 수 있습니다.  

---

## 3. 예시 YAML

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp-pod
spec:
  containers:
    - name: myapp
      image: myapp:latest
      ports:
        - containerPort: 8080
      livenessProbe: # Startup Probe 성공 후 10초 뒤부터 /healthz로 5초 마다 요청 (실패 시 컨테이너를 재시작)
        httpGet:
          path: /healthz
          port: 8080
        initialDelaySeconds: 10
        periodSeconds: 5
      readinessProbe: # Startup Probe 성공 후 5초 뒤부터 /ready를 확인 (OK 응답을 받아야 Service 엔드포인트에 Pod가 포함)
        httpGet:
          path: /ready
          port: 8080
        initialDelaySeconds: 5
        periodSeconds: 5
      startupProbe: # 최대 30회(각 10초 간격) -> 약 5분동안 애플리케이션 시작을 기다림. 해당 기간 동안에는 Liveness/Readiness Probe가 동작하지 않음
        httpGet:
          path: /startup
          port: 8080
        failureThreshold: 30
        periodSeconds: 10
```

---

## 4. 마무리

- Liveness Probe: 애플리케이션이 정상 동작 중인지 판별하여, 비정상 시 컨테이너를 자동 재시작.
- Readiness Probe: Pod가 트래픽을 처리할 준비 여부 판단. 준비 안 된 Pod는 Service로부터 제외.
- Startup Probe: 초기화 시간이 긴 애플리케이션의 기동 완료를 판단하여 Liveness/Readiness Probe 오탐을 방지.

> 여기서 `initialDelaySeconds`나 `periodSeconds`와 같은 파라미터를 적절히 설정하지 않으면, 아직 준비되지 않은 애플리케이션을 재시작하거나 반대로 지나치게 오랜 시간 대기하여 배포 효율이 저하되는 문제를 겪을 수 있습니다.  
>
> 따라서 Startup Probe를 적극적으로 활용하고, 지속적인 모니터링을 통해 Probe 파라미터를 주기적으로 검토하고 조정함으로써 최적의 상태를 유지하는 것이 중요합니다. 이러한 전략적 설정을 통해 안정적이고 탄력적인 Kubernetes 기반 애플리케이션 운영 환경을 구축할 수 있습니다.  
{: .prompt-tip}

---

## 5. Reference

Kubernetes 공식문서 - <https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
