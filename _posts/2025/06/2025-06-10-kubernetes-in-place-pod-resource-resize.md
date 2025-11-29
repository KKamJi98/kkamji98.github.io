---
title: In-Place Pod Resource Resize 소개 및 PoC
date: 2025-06-10 21:52:33 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, pod, resource, resize, in-place, devops, eks]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

**Kubernetes v1.33 Release Note** - <https://kubernetes.io/blog/2025/04/23/kubernetes-v1-33-release/>  
**In-Place Pod Resource Resize 소개** - <https://kubernetes.io/blog/2025/05/16/kubernetes-v1-33-in-place-pod-resize-beta/>  

Kubernetes v1.33에서 In-Place Pod Resource Resize 기능이 베타로 승격되었습니다. 기존에는 Pod의 CPU/Memory requests나 limits를 변경하려면 Pod를 재생성해야 했지만, 이제는 Pod를 재시작하지 않고 자원 크기를 조정할 수 있습니다.

이번 글에서는 해당 기능의 개념을 설명하고, PoC를 통해 실제로 개념에 맞게 동작하는지를 확인해보도록 하겠습니다.

---

## 1. PoC 환경

- `Kubernetes` v1.33 (EKS)
- `kubectl` v1.33
- `InPlacePodVerticalScaling` Feature Gate 활성화 확인

```shell
# Client & Server 버전 확인
❯ kubectl version
Client Version: v1.33.1
Kustomize Version: v5.6.0
Server Version: v1.33.1-eks-1fbb135

# feature-gates 확인
❯ kubectl get --raw /metrics | grep -i InPlacePodVerticalScaling
kubernetes_feature_enabled{name="InPlacePodVerticalScaling",stage="BETA"} 1
```

---

## 2. In-Place Pod Resource Resize 기능 소개

In-Place Pod Resource Resize 기능은 Kubernetes v1.33에서 베타로 제공되는 기능으로, Pod의 리소스 크기를 조정할 때 Pod를 재시작하지 않고도 변경할 수 있게 해줍니다. 이 기능은 다음과 같은 장점을 제공합니다:

- **Downtime 최소화**: Pod를 재시작하지 않고 리소스 크기를 조정할 수 있어, 서비스 중단 없이 리소스를 조정할 수 있습니다.
- **유연한 리소스 관리**: Pod의 리소스 크기를 동적으로 조정할 수 있어, 애플리케이션의 리소스 사용량에 따라 유연하게 대응할 수 있습니다.
- **간편한 리소스 조정**: 기존의 Pod를 재시작하지 않고도 리소스 크기를 조정할 수 있어, 관리가 간편해집니다.

> Memory Decrease: Memory limits cannot be decreased unless the resizePolicy for memory is RestartContainer. Memory requests can generally be decreased.
{: .prompt-danger}

=> **Memory limits는 `RestartContainer`로 설정하지 않는 이상 감소시킬 수 없습니다.**

---

## 3. PoC 진행

test용 nginx pod를 생성하고, In-Place Pod Resource Resize 기능을 활용하여 Pod의 리소스 크기를 조정한 뒤, Pod가 재시작 없이 리소스 크기가 조정되는 것을 확인해보겠습니다.

### 3.1. 테스트용 nginx Pod 생성

```shell
# pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
spec:
  containers:
  - name: nginx
    image: nginx:latest
    resources:
      requests:
        memory: "64Mi"
      limits:
        memory: "128Mi"
```

```shell
# Pod 생성
❯ kubectl apply -f pod.yaml
pod/nginx-pod created
```

```shell
# Pod 상태 확인
❯ kubectl get po            
NAME        READY   STATUS    RESTARTS   AGE
nginx-pod   1/1     Running   0          3m31s

# Resource request limit 확인
❯ kubectl get po nginx-pod -o yaml | yq '.spec.containers[].resources'
limits:
  memory: 128Mi
requests:
  memory: 64Mi
```

### 3.2. In-Place Pod Resource Resize 적용

```shell
# Pod 리소스 크기 조정
❯ kubectl edit pod nginx-pod --subresource resize
...
...
spec:                                                                                    
  containers:                                                                            
  - image: nginx:latest                                                                  
    imagePullPolicy: Always                                                              
    name: nginx                                                                          
    resources:                                                                           
      limits:                                                                            
        memory: 256Mi # 128Mi -> 256Mi 수정                                                                    
      requests:                                                                          
        memory: 128Mi # 64Mi -> 128Mi 수정
...
...
```

```shell
# 확인
❯ kubectl get po nginx-pod -o yaml | yq '.spec.containers[].resources' 
limits:
  memory: 256Mi
requests:
  memory: 128Mi

❯ kubectl describe pod nginx-pod | grep -i events -A10
Events:
  Type    Reason     Age   From               Message
  ----    ------     ----  ----               -------
  Normal  Scheduled  12m   default-scheduler  Successfully assigned default/nginx-pod to ip-10-0-1-129.ap-northeast-2.compute.internal
  Normal  Pulling    12m   kubelet            Pulling image "nginx:latest"
  Normal  Pulled     11m   kubelet            Successfully pulled image "nginx:latest" in 6.458s (6.458s including waiting). Image size: 68857691 bytes.
  Normal  Created    11m   kubelet            Created container: nginx
  Normal  Started    11m   kubelet            Started container nginx
```

---

## 4. 마무리

In-Place Pod Resource Resize 기능은 `vertical scaling`을 무중단으로 지원하며, Pod를 재시작하지 않고도 리소스 크기를 조정할 수 있는 유용한 기능입니다. Kubernetes 공식문서에 따르면 해당 기능은 다음과 같이 앞으로도 꾸준히 고도화될 것으로 보입니다.

- **Stability and Productionization**: Continued focus on hardening the feature, improving performance, and ensuring it is robust for production environments.
- **Addressing Limitations**: Working towards relaxing some of the current limitations noted in the documentation, such as allowing memory limit decreases.
- **VerticalPodAutoscaler (VPA) Integration**: Work to enable VPA to leverage in-place Pod resize is already underway. A new InPlaceOrRecreate update mode will allow it to attempt non-disruptive resizes first, or fall back to recreation if needed. This will allow users to benefit from VPA's recommendations with significantly less disruption.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
