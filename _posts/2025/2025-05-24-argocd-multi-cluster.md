---
title: ArgoCD로 Multi-Cluster Application 배포하기
date: 2025-05-24 20:19:03 +0900
author: kkamji
categories: [ArgoCD]
tags: [kubernetes, argocd, argocd-cli, metrics-server, gitops, declarative, application]
comments: true
image:
  path: /assets/img/argocd/argocd.webp
---

## 개요

이 포스트에서는 ArgoCD를 사용하여 여러 Kubernetes 클러스터에 애플리케이션을 배포하는 방법에 대해 알아보겠습니다. Multi-Cluster 환경에서 GitOps 방식으로 애플리케이션을 관리하는 방법과 이를 위한 ArgoCD의 설정 방법을 상세히 다룰 예정입니다.

## 사전 준비사항

- 2개 이상의 Kubernetes 클러스터
- ArgoCD가 설치된 관리용 클러스터
- Git 저장소 접근 권한
- kubectl CLI 도구

## ArgoCD Multi-Cluster 아키텍처

ArgoCD를 사용한 Multi-Cluster 배포 아키텍처는 다음과 같습니다:

1. 중앙 관리용 클러스터에 ArgoCD 설치
2. 대상 클러스터들을 ArgoCD에 등록
3. Git 저장소에서 애플리케이션 매니페스트 관리
4. ArgoCD를 통한 여러 클러스터로의 동시 배포

## 클러스터 등록하기

먼저 대상 클러스터를 ArgoCD에 등록해야 합니다. 이는 다음 단계로 수행됩니다:

```bash
# 대상 클러스터의 kubeconfig 컨텍스트 이름 확인
kubectl config get-contexts

# ArgoCD CLI를 사용하여 클러스터 추가
argocd cluster add <context-name>
```

## Application Sets 구성

ApplicationSet을 사용하면 여러 클러스터에 동일한 애플리케이션을 배포할 수 있습니다. 예시 구성은 다음과 같습니다:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: multi-cluster-app
spec:
  generators:
  - clusters: {}  # 등록된 모든 클러스터를 대상으로 함
  template:
    metadata:
      name: '{{name}}-app'
    spec:
      project: default
      source:
        repoURL: https://github.com/your-org/your-app.git
        targetRevision: HEAD
        path: manifests
      destination:
        server: '{{server}}'
        namespace: your-namespace
```

## 클러스터별 설정 관리

각 클러스터별로 다른 설정이 필요한 경우, 다음과 같은 방법을 사용할 수 있습니다:

1. Git 저장소에서 클러스터별 값 파일 관리
2. Kustomize overlays 사용
3. Helm 차트의 values 파일 활용

예시 디렉토리 구조:

```
.
├── base
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
└── overlays
    ├── cluster1
    │   ├── kustomization.yaml
    │   └── config.yaml
    └── cluster2
        ├── kustomization.yaml
        └── config.yaml
```

## 배포 상태 모니터링

ArgoCD UI에서 각 클러스터의 배포 상태를 모니터링할 수 있습니다:

1. ArgoCD 대시보드 접속
2. Applications 메뉴에서 각 클러스터별 배포 상태 확인
3. Sync 상태 및 Health 상태 모니터링

## 문제 해결

일반적인 문제 해결 방법:

1. ArgoCD 애플리케이션 로그 확인
```bash
argocd app logs <app-name>
```

2. 클러스터 연결 상태 확인
```bash
argocd cluster list
```

3. 애플리케이션 동기화 상태 확인
```bash
argocd app get <app-name>
```

## 보안 고려사항

Multi-Cluster 환경에서 고려해야 할 보안 사항들:

1. 클러스터 간 네트워크 보안
2. RBAC 설정
3. Secret 관리
4. 클러스터 접근 권한 제어

## 결론

ArgoCD를 사용한 Multi-Cluster 애플리케이션 배포는 GitOps 방식으로 여러 클러스터를 효율적으로 관리할 수 있게 해줍니다. 적절한 설정과 보안 고려사항을 잘 적용한다면, 안정적이고 확장 가능한 멀티 클러스터 환경을 구축할 수 있습니다.

## 참고 자료

- [ArgoCD 공식 문서](https://argo-cd.readthedocs.io/)
- [ApplicationSet 문서](https://argocd-applicationset.readthedocs.io/)
- [Kubernetes Multi-Cluster 가이드](https://kubernetes.io/docs/concepts/cluster-administration/cluster-management/)
