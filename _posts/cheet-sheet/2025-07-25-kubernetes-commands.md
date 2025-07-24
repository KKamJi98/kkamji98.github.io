---
title: Kubernetes Command Cheat Sheet
date: 2025-07-25 01:42:00 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, kubectl, devops, k8s, container]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Kubernetes를 사용하며 자주 사용하는 kubectl 명령어들을 정리한 치트시트입니다.

## 기본 설정 및 컨텍스트

```shell
kubectl config view                                  # kubeconfig 설정 확인
kubectl config get-contexts                          # 사용 가능한 컨텍스트 목록
kubectl config current-context                       # 현재 컨텍스트 확인
kubectl config use-context <context-name>            # 컨텍스트 변경
kubectl config set-context --current --namespace=<namespace>  # 기본 네임스페이스 설정
kubectl cluster-info                                 # 클러스터 정보 확인
kubectl version                                      # kubectl 및 클러스터 버전 확인
```

## 네임스페이스 관리

```shell
kubectl get namespaces                               # 네임스페이스 목록
kubectl get ns                                       # 네임스페이스 목록 (축약)
kubectl create namespace <namespace-name>            # 네임스페이스 생성
kubectl delete namespace <namespace-name>            # 네임스페이스 삭제
kubectl describe namespace <namespace-name>          # 네임스페이스 상세 정보
```

## Pod 관리

```shell
# Pod 조회
kubectl get pods                                     # 현재 네임스페이스의 Pod 목록
kubectl get pods -A                                  # 모든 네임스페이스의 Pod 목록
kubectl get pods -o wide                             # Pod 상세 정보 (IP, 노드 등)
kubectl get pods --show-labels                       # 라벨과 함께 Pod 목록
kubectl get pods -l app=nginx                        # 라벨 셀렉터로 Pod 필터링
kubectl get pods --field-selector status.phase=Running  # 필드 셀렉터로 필터링

# Pod 생성 및 실행
kubectl run nginx --image=nginx                      # Pod 생성 및 실행
kubectl run busybox --image=busybox --rm -it -- sh   # 임시 Pod 생성 및 접속
kubectl create -f pod.yaml                           # YAML 파일로 Pod 생성
kubectl apply -f pod.yaml                            # YAML 파일로 Pod 적용

# Pod 상세 정보 및 로그
kubectl describe pod <pod-name>                      # Pod 상세 정보
kubectl logs <pod-name>                              # Pod 로그 확인
kubectl logs <pod-name> -f                           # Pod 로그 실시간 확인
kubectl logs <pod-name> -c <container-name>          # 멀티 컨테이너 Pod의 특정 컨테이너 로그
kubectl logs <pod-name> --previous                   # 이전 컨테이너 로그

# Pod 접속 및 명령 실행
kubectl exec -it <pod-name> -- /bin/bash             # Pod에 접속
kubectl exec -it <pod-name> -c <container-name> -- /bin/bash  # 특정 컨테이너에 접속
kubectl exec <pod-name> -- ls /                      # Pod에서 명령 실행

# Pod 삭제
kubectl delete pod <pod-name>                        # Pod 삭제
kubectl delete pod <pod-name> --force --grace-period=0  # 강제 삭제
kubectl delete pods --all                            # 모든 Pod 삭제
```

## Deployment 관리

```shell
# Deployment 조회
kubectl get deployments                              # Deployment 목록
kubectl get deploy                                   # Deployment 목록 (축약)
kubectl describe deployment <deployment-name>        # Deployment 상세 정보

# Deployment 생성 및 관리
kubectl create deployment nginx --image=nginx        # Deployment 생성
kubectl create deployment nginx --image=nginx --replicas=3  # 레플리카 수 지정
kubectl apply -f deployment.yaml                     # YAML 파일로 Deployment 적용

# 스케일링
kubectl scale deployment <deployment-name> --replicas=5  # 레플리카 수 변경
kubectl autoscale deployment <deployment-name> --min=2 --max=10 --cpu-percent=80  # HPA 설정

# 롤아웃 관리
kubectl rollout status deployment/<deployment-name>   # 롤아웃 상태 확인
kubectl rollout history deployment/<deployment-name>  # 롤아웃 히스토리 확인
kubectl rollout undo deployment/<deployment-name>     # 이전 버전으로 롤백
kubectl rollout restart deployment/<deployment-name>  # Deployment 재시작

# 이미지 업데이트
kubectl set image deployment/<deployment-name> <container-name>=<new-image>  # 이미지 업데이트
```

## Service 관리

```shell
# Service 조회
kubectl get services                                 # Service 목록
kubectl get svc                                      # Service 목록 (축약)
kubectl describe service <service-name>              # Service 상세 정보

# Service 생성
kubectl expose deployment <deployment-name> --port=80 --target-port=8080  # Deployment를 Service로 노출
kubectl expose pod <pod-name> --port=80 --target-port=8080 --type=NodePort  # Pod를 NodePort Service로 노출
kubectl create service clusterip <service-name> --tcp=80:8080  # ClusterIP Service 생성
kubectl create service nodeport <service-name> --tcp=80:8080   # NodePort Service 생성
kubectl create service loadbalancer <service-name> --tcp=80:8080  # LoadBalancer Service 생성

# 포트 포워딩
kubectl port-forward service/<service-name> 8080:80  # Service 포트 포워딩
kubectl port-forward pod/<pod-name> 8080:80          # Pod 포트 포워딩
```

## ConfigMap 및 Secret 관리

```shell
# ConfigMap
kubectl get configmaps                               # ConfigMap 목록
kubectl get cm                                       # ConfigMap 목록 (축약)
kubectl create configmap <configmap-name> --from-literal=key1=value1 --from-literal=key2=value2
kubectl create configmap <configmap-name> --from-file=<file-path>  # 파일에서 ConfigMap 생성
kubectl create configmap <configmap-name> --from-env-file=<env-file>  # 환경 파일에서 생성
kubectl describe configmap <configmap-name>          # ConfigMap 상세 정보

# Secret
kubectl get secrets                                  # Secret 목록
kubectl create secret generic <secret-name> --from-literal=username=admin --from-literal=password=secret
kubectl create secret generic <secret-name> --from-file=<file-path>  # 파일에서 Secret 생성
kubectl create secret docker-registry <secret-name> --docker-server=<server> --docker-username=<username> --docker-password=<password>  # Docker 레지스트리 Secret
kubectl describe secret <secret-name>                # Secret 상세 정보
kubectl get secret <secret-name> -o yaml            # Secret YAML 형식으로 출력
```

## Volume 및 PersistentVolume 관리

```shell
# PersistentVolume
kubectl get pv                                       # PersistentVolume 목록
kubectl describe pv <pv-name>                        # PV 상세 정보

# PersistentVolumeClaim
kubectl get pvc                                      # PVC 목록
kubectl describe pvc <pvc-name>                      # PVC 상세 정보
kubectl delete pvc <pvc-name>                        # PVC 삭제
```

## Ingress 관리

```shell
kubectl get ingress                                  # Ingress 목록
kubectl get ing                                      # Ingress 목록 (축약)
kubectl describe ingress <ingress-name>              # Ingress 상세 정보
kubectl create ingress <ingress-name> --rule="host/path=service:port"  # Ingress 생성
```

## 노드 관리

```shell
kubectl get nodes                                    # 노드 목록
kubectl get nodes -o wide                            # 노드 상세 정보
kubectl describe node <node-name>                    # 노드 상세 정보
kubectl top nodes                                    # 노드 리소스 사용량 (metrics-server 필요)
kubectl cordon <node-name>                           # 노드 스케줄링 비활성화
kubectl uncordon <node-name>                         # 노드 스케줄링 활성화
kubectl drain <node-name>                            # 노드에서 Pod 제거 (유지보수 시)
kubectl taint nodes <node-name> key=value:NoSchedule  # 노드에 Taint 추가
kubectl taint nodes <node-name> key:NoSchedule-      # 노드에서 Taint 제거
```

## 리소스 모니터링 및 디버깅

```shell
# 리소스 사용량 확인 (metrics-server 필요)
kubectl top nodes                                    # 노드 리소스 사용량
kubectl top pods                                     # Pod 리소스 사용량
kubectl top pods -A                                  # 모든 네임스페이스 Pod 리소스 사용량

# 이벤트 확인
kubectl get events                                   # 이벤트 목록
kubectl get events --sort-by=.metadata.creationTimestamp  # 시간순 정렬
kubectl get events --field-selector involvedObject.name=<pod-name>  # 특정 객체 이벤트

# 디버깅
kubectl describe <resource-type> <resource-name>     # 리소스 상세 정보
kubectl logs <pod-name> --previous                   # 이전 컨테이너 로그
kubectl get pods --show-labels                       # 라벨과 함께 Pod 목록
kubectl get all                                      # 모든 리소스 목록
kubectl api-resources                                # 사용 가능한 API 리소스 목록
kubectl explain <resource-type>                      # 리소스 타입 설명
```

## YAML 파일 관리

```shell
kubectl apply -f <file.yaml>                         # YAML 파일 적용
kubectl apply -f <directory>/                        # 디렉토리 내 모든 YAML 파일 적용
kubectl apply -k <kustomization-directory>           # Kustomize 적용
kubectl delete -f <file.yaml>                        # YAML 파일로 리소스 삭제
kubectl create -f <file.yaml>                        # YAML 파일로 리소스 생성
kubectl replace -f <file.yaml>                       # YAML 파일로 리소스 교체

# YAML 생성 및 출력
kubectl create deployment nginx --image=nginx --dry-run=client -o yaml  # YAML 생성 (실행하지 않음)
kubectl get deployment nginx -o yaml                 # 기존 리소스를 YAML로 출력
kubectl get deployment nginx -o json                 # 기존 리소스를 JSON으로 출력
```

## 라벨 및 어노테이션 관리

```shell
# 라벨 관리
kubectl label pods <pod-name> env=production          # Pod에 라벨 추가
kubectl label pods <pod-name> env-                    # Pod에서 라벨 제거
kubectl get pods -l env=production                    # 라벨로 Pod 필터링
kubectl get pods -l 'env in (production,staging)'     # 여러 라벨 값으로 필터링

# 어노테이션 관리
kubectl annotate pods <pod-name> description="My pod"  # Pod에 어노테이션 추가
kubectl annotate pods <pod-name> description-         # Pod에서 어노테이션 제거
```

## 네트워크 정책 및 보안

```shell
kubectl get networkpolicies                          # NetworkPolicy 목록
kubectl get netpol                                   # NetworkPolicy 목록 (축약)
kubectl describe networkpolicy <policy-name>         # NetworkPolicy 상세 정보

# RBAC
kubectl get roles                                    # Role 목록
kubectl get rolebindings                             # RoleBinding 목록
kubectl get clusterroles                             # ClusterRole 목록
kubectl get clusterrolebindings                      # ClusterRoleBinding 목록
kubectl auth can-i create pods                       # 권한 확인
kubectl auth can-i create pods --as=system:serviceaccount:default:default  # 특정 사용자 권한 확인
```

## Helm 관련 명령어

```shell
helm list                                            # 설치된 Helm 차트 목록
helm list -A                                         # 모든 네임스페이스의 Helm 차트
helm install <release-name> <chart>                  # Helm 차트 설치
helm upgrade <release-name> <chart>                  # Helm 차트 업그레이드
helm uninstall <release-name>                        # Helm 차트 제거
helm rollback <release-name> <revision>              # Helm 차트 롤백
helm status <release-name>                           # Helm 릴리스 상태 확인
helm get values <release-name>                       # Helm 릴리스 값 확인
```

## 유용한 별칭 및 단축키

```shell
# kubectl 별칭 설정
alias k=kubectl
alias kg='kubectl get'
alias kd='kubectl describe'
alias kd='kubectl delete'
alias kl='kubectl logs'
alias kla='kubectl logs --all-containers'
alias kexec='kubectl exec -it'

# 자주 사용하는 조합
kubectl get pods -o wide --sort-by=.spec.nodeName    # 노드별로 정렬된 Pod 목록
kubectl get pods --field-selector status.phase!=Running  # 실행 중이 아닌 Pod 목록
kubectl get events --sort-by=.metadata.creationTimestamp | tail  # 최근 이벤트
```

## 문제 해결 및 디버깅

```shell
# 클러스터 상태 확인
kubectl cluster-info dump                            # 클러스터 전체 정보 덤프
kubectl get componentstatuses                        # 컴포넌트 상태 확인
kubectl get cs                                       # 컴포넌트 상태 확인 (축약)

# 리소스 정리
kubectl delete pods --field-selector status.phase=Succeeded  # 완료된 Pod 삭제
kubectl delete pods --field-selector status.phase=Failed     # 실패한 Pod 삭제
kubectl delete all --all                             # 모든 리소스 삭제 (주의!)

# 성능 및 용량 확인
kubectl describe nodes | grep -A 5 "Allocated resources"  # 노드 리소스 할당 현황
kubectl get pods --all-namespaces -o=custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName  # Pod와 노드 매핑
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
