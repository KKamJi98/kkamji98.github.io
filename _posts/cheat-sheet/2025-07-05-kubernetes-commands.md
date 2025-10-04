---
title: Kubernetes Command Cheat Sheet
date: 2025-07-05 01:12:59 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, kubectl, cheat-sheet, devops, k8s, container, cli]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

Kubernetes를 사용하며 알게된 CLI 명령어들을 공유합니다.

---

## 1. 기본 설정 및 컨텍스트

```shell
kubectl config view                                  # kubeconfig 설정 확인
kubectl config get-contexts                          # 사용 가능한 컨텍스트 목록
kubectl config current-context                       # 현재 컨텍스트 확인
kubectl config use-context <context-name>            # 컨텍스트 변경
kubectl config set-context --current --namespace=<namespace>  # 기본 네임스페이스 설정
kubectl cluster-info                                 # 클러스터 정보 확인
kubectl version                                      # kubectl 및 클러스터 버전 확인
```

---

## 2. 네임스페이스 관리

```shell
kubectl get namespaces                               # 네임스페이스 목록
kubectl get ns                                       # 네임스페이스 목록 (축약)
kubectl create namespace <namespace-name>            # 네임스페이스 생성
kubectl delete namespace <namespace-name>            # 네임스페이스 삭제
kubectl describe namespace <namespace-name>          # 네임스페이스 상세 정보
```

---

## 3. Pod 관리

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

---

## 4. Deployment 관리

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

---

## 5. Service 관리

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

---

## 6. ConfigMap 및 Secret 관리

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

---

## 7. Volume 및 PersistentVolume 관리

```shell
# PersistentVolume
kubectl get pv                                       # PersistentVolume 목록
kubectl describe pv <pv-name>                        # PV 상세 정보

# PersistentVolumeClaim
kubectl get pvc                                      # PVC 목록
kubectl describe pvc <pvc-name>                      # PVC 상세 정보
kubectl delete pvc <pvc-name>                        # PVC 삭제
```

---

## 8. Ingress 관리

```shell
kubectl get ingress                                  # Ingress 목록
kubectl get ing                                      # Ingress 목록 (축약)
kubectl describe ingress <ingress-name>              # Ingress 상세 정보
kubectl create ingress <ingress-name> --rule="host/path=service:port"  # Ingress 생성
```

---

## 9. 노드 관리

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

---

## 10. 리소스 모니터링 및 디버깅

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

---

## 11. YAML 파일 관리

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

---

## 12. 라벨 및 어노테이션 관리

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

---

## 13. 네트워크 정책 및 보안

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

---

## 14. Helm 관련 명령어

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

---

## 15. 유용한 별칭 및 단축키

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

---

## 16. 고급 모니터링 및 실시간 감시

```shell
# 실시간 Pod 모니터링
watch -n2 'kubectl get pods -A --sort-by=.metadata.creationTimestamp | tail -20'  # 2초마다 최근 Pod 20개
watch -n2 'kubectl get pods -A -o wide --sort-by=.metadata.creationTimestamp | tail -20'  # Pod IP, Node 정보 포함
watch -n2 'kubectl get pods -A | grep -v Running'    # Running이 아닌 Pod 실시간 모니터링
watch -n1 'kubectl top pods -A --sort-by=cpu | head -20'  # CPU 사용량 상위 20개 Pod

# 실시간 Node 모니터링
watch -n2 'kubectl get nodes --sort-by=.metadata.creationTimestamp'  # 생성 시간순 Node 조회
watch -n2 'kubectl get nodes -L topology.ebs.csi.aws.com/zone -L node.kubernetes.io/app --sort-by=.metadata.creationTimestamp'  # AZ, NodeGroup 라벨 표시
watch -n2 'kubectl get nodes | grep -v Ready'        # Ready가 아닌 Node 실시간 모니터링
watch -n1 'kubectl top nodes --sort-by=cpu'          # CPU 사용량 기준 Node 정렬
watch -n1 'kubectl top nodes --sort-by=memory'       # 메모리 사용량 기준 Node 정렬

# 실시간 Event 모니터링
watch -n2 'kubectl get events -A --sort-by=.metadata.managedFields[].time | tail -20'  # 시간순 이벤트 조회
watch -n2 'kubectl get events -A --field-selector type!=Normal --sort-by=.metadata.managedFields[].time | tail -20'  # 비정상 이벤트만
watch -n2 'kubectl get events --field-selector involvedObject.kind=Pod --sort-by=.lastTimestamp | tail -15'  # Pod 관련 이벤트만

# Pod 상태별 개수 모니터링
watch -n2 'kubectl get pods -A --no-headers | awk "{print \$4}" | sort | uniq -c'  # Pod 상태별 개수
watch -n2 'kubectl get pods -A --no-headers | awk "{print \$1}" | sort | uniq -c'  # 네임스페이스별 Pod 개수
```

---

## 17. API 리소스 및 고급 쿼리

```shell
# API 리소스 탐색
kubectl api-resources                                # 사용 가능한 모든 API 리소스 목록
kubectl api-resources --verbs=list --namespaced -o name  # 네임스페이스 리소스 중 list 가능한 것들
kubectl api-resources --api-group=apps              # 특정 API 그룹의 리소스
kubectl api-resources --namespaced=false            # 클러스터 레벨 리소스만
kubectl api-resources --namespaced=true             # 네임스페이스 레벨 리소스만
kubectl api-resources --verbs=get,list,create,update,patch,watch,delete  # 모든 CRUD 동작 가능한 리소스

# API 버전 확인
kubectl api-versions                                 # 사용 가능한 API 버전 목록
kubectl explain <resource>                           # 리소스 스키마 설명
kubectl explain pod.spec                             # 특정 필드 설명
kubectl explain pod.spec.containers                  # 중첩된 필드 설명

# 모든 리소스 조회 (고급)
kubectl api-resources --verbs=list --namespaced -o name | xargs -n 1 kubectl get --show-kind --ignore-not-found -A  # 모든 네임스페이스 리소스
kubectl api-resources --verbs=list --namespaced=false -o name | xargs -n 1 kubectl get --show-kind --ignore-not-found  # 모든 클러스터 리소스
kubectl get all -A                                   # 기본 리소스들만 (pod, service, deployment 등)
kubectl get $(kubectl api-resources --namespaced=true --verbs=list -o name | tr '\n' ',' | sed 's/,$//') -A  # 모든 네임스페이스 리소스 한번에
```

---

## 18. 컨테이너 재시작 및 로그 분석

```shell
# 재시작된 컨테이너 찾기
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{"\t"}{.restartCount}{"\n"}{end}{end}' | sort -k4 -nr  # 재시작 횟수 기준 정렬
kubectl get pods -A --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{if gt .restartCount 0}{.name}{"\t"}{.restartCount}{"\n"}{end}{end}{end}'  # 재시작된 컨테이너만

# 이전 컨테이너 로그 (재시작된 경우)
kubectl logs -n <namespace> <pod-name> -c <container-name> --previous  # 이전 컨테이너 로그
kubectl logs -n <namespace> <pod-name> -c <container-name> --previous --tail=100  # 이전 컨테이너 로그 100줄
kubectl logs -n <namespace> <pod-name> --all-containers --previous  # 모든 컨테이너의 이전 로그

# 로그 스트리밍 및 필터링
kubectl logs -n <namespace> <pod-name> -f --tail=50  # 실시간 로그 스트리밍 (최근 50줄부터)
kubectl logs -n <namespace> <pod-name> -f | grep ERROR  # 에러 로그만 필터링
kubectl logs -n <namespace> <pod-name> --since=1h    # 최근 1시간 로그만
kubectl logs -n <namespace> <pod-name> --since-time=2023-01-01T10:00:00Z  # 특정 시간 이후 로그
```

---

## 19. 노드 그룹 및 라벨 기반 필터링

```shell
# 노드 그룹별 필터링 (AWS EKS 환경)
kubectl get nodes -l node.kubernetes.io/app=my-nodegroup  # 특정 NodeGroup 필터링
kubectl get pods -A --field-selector spec.nodeName=<node-name>  # 특정 노드의 Pod들
kubectl get nodes -L topology.ebs.csi.aws.com/zone -L node.kubernetes.io/app  # AZ, NodeGroup 라벨 표시
kubectl get nodes -l topology.ebs.csi.aws.com/zone=us-west-2a  # 특정 AZ의 노드들

# 라벨 기반 고급 필터링
kubectl get pods -A -l 'environment in (production,staging)'  # 여러 라벨 값으로 필터링
kubectl get pods -A -l 'environment!=development'    # 특정 라벨 값 제외
kubectl get pods -A -l 'environment,tier'            # 두 라벨이 모두 있는 Pod
kubectl get pods -A -l '!environment'                # 특정 라벨이 없는 Pod

# 필드 셀렉터 고급 사용
kubectl get pods -A --field-selector=status.phase!=Running,spec.restartPolicy=Always  # 여러 필드 조건
kubectl get events --field-selector involvedObject.kind=Pod,type=Warning  # Pod 관련 경고 이벤트
kubectl get pods --field-selector metadata.namespace!=kube-system  # 특정 네임스페이스 제외
```

---

## 20. 리소스 사용량 및 성능 분석

```shell
# 리소스 사용량 상세 분석
kubectl top pods -A --containers                     # 컨테이너별 리소스 사용량
kubectl top pods -A --sort-by=cpu                    # CPU 사용량 기준 정렬
kubectl top pods -A --sort-by=memory                 # 메모리 사용량 기준 정렬
kubectl top nodes --sort-by=cpu                      # 노드 CPU 사용량 정렬
kubectl top nodes --sort-by=memory                   # 노드 메모리 사용량 정렬

# 리소스 제한 및 요청 확인
kubectl describe pods -A | grep -A 5 "Limits\|Requests"  # 모든 Pod의 리소스 제한/요청
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .spec.containers[*]}{.resources.requests.cpu}{"\t"}{.resources.requests.memory}{"\t"}{.resources.limits.cpu}{"\t"}{.resources.limits.memory}{"\n"}{end}{end}'  # 리소스 요청/제한 테이블 형식

# 노드 리소스 할당 현황
kubectl describe nodes | grep -A 5 "Allocated resources"  # 노드별 리소스 할당 현황
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.cpu}{"\t"}{.status.allocatable.memory}{"\n"}{end}'  # 노드별 할당 가능한 리소스
```

---

## 21. 고급 디버깅 및 문제 해결

```shell
# 클러스터 전체 상태 점검
kubectl cluster-info dump --output-directory=/tmp/cluster-dump  # 클러스터 전체 정보 덤프
kubectl get componentstatuses                        # 컴포넌트 상태 확인
kubectl get --raw /healthz                           # 클러스터 헬스 체크
kubectl get --raw /metrics                           # 메트릭 엔드포인트 확인

# 네트워킹 디버깅
kubectl get pods -A -o wide | grep -v Running        # 네트워크 문제로 실행되지 않는 Pod
kubectl get endpoints -A                             # 서비스 엔드포인트 확인
kubectl get networkpolicies -A                       # 네트워크 정책 확인
kubectl describe service <service-name> -n <namespace>  # 서비스 상세 정보

# DNS 문제 해결
kubectl get pods -n kube-system -l k8s-app=kube-dns  # CoreDNS Pod 상태
kubectl logs -n kube-system -l k8s-app=kube-dns      # CoreDNS 로그
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default.svc.cluster.local  # DNS 해상도 테스트

# RBAC 디버깅
kubectl auth can-i --list --as=system:serviceaccount:<namespace>:<serviceaccount>  # 서비스 계정 권한 확인
kubectl get clusterrolebindings -o wide | grep <user-or-group>  # 클러스터 역할 바인딩 확인
kubectl get rolebindings -A -o wide | grep <user-or-group>  # 역할 바인딩 확인
kubectl describe clusterrole <role-name>             # 클러스터 역할 상세 정보

# 리소스 정리 및 유지보수
kubectl delete pods --field-selector status.phase=Succeeded -A  # 완료된 Pod 삭제
kubectl delete pods --field-selector status.phase=Failed -A     # 실패한 Pod 삭제
kubectl get pods -A --field-selector=status.phase=Evicted       # Evicted Pod 확인
kubectl delete pods -A --field-selector=status.phase=Evicted    # Evicted Pod 삭제
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
