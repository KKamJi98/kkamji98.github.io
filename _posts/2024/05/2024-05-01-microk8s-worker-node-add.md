---
title: MicroK8s에 Worker Node 추가하기
date: 2024-05-01 23:41:11 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, k8s, k8s-cluster, cluster, microk8s, aws, ec2, tls, ssl, kubeconfig, worker-node]     # TAG names should always be lowercase
comments: true
content_kind: lab
image:
  path: /assets/img/kubernetes/kubernetes.webp
---

MicroK8s 클러스터에 계산 자원을 늘리고 싶을 때 worker node를 추가할 수 있습니다. 이 글은 EC2의 private network 안에서 기존 control plane에 worker를 안전하게 조인하고, 실제 Pod가 해당 node에 배치되는지 확인하는 흐름을 다룹니다.

> **TL;DR**  
> - `microk8s add-node`가 만든 일회성 조인 명령을 새 node에서 `--worker`와 함께 실행합니다.  
> - worker는 workload를 실행하지만 Kubernetes control plane과 datastore를 실행하지 않으므로 HA 용량에는 기여하지 않습니다.  
> - 조인 포트 25000과 cluster 내부 통신은 Internet이 아니라 필요한 private CIDR에서만 허용합니다.  
{: .prompt-info}

---

## 1. 먼저 확인할 것

MicroK8s의 worker는 kubelet과 kube-proxy가 local API server proxy를 통해 control plane의 API server와 통신하는 node입니다. 따라서 worker를 늘리는 것은 Pod 실행 capacity를 늘리는 작업이지 control plane 장애 허용성을 높이는 작업은 아닙니다. HA가 목적이라면 control plane node 수와 datastore quorum을 별도로 설계해야 합니다.

| 항목 | 확인 이유 |
| --- | --- |
| MicroK8s channel | control plane과 worker는 같은 안정 channel을 사용해 version skew를 피합니다. |
| private IP 경로 | 조인 명령에 control plane의 worker가 도달 가능한 private IP를 사용합니다. |
| security group | 25000/TCP는 조인에 필요하며, cluster 내부 Pod와 Service 통신도 node 사이에서 허용되어야 합니다. |
| storage | hostpath storage는 node-local입니다. Stateful workload에는 공유 또는 분산 storage를 검토합니다. |

EC2에서는 control plane security group의 25000/TCP source를 worker subnet 또는 worker security group으로 제한합니다. 0.0.0.0/0으로 여는 것은 조인 token 노출 위험을 키우므로 피합니다. 필요한 node 간 통신 범위는 사용하는 CNI, addon, control plane 구성에 따라 다르므로 배포한 MicroK8s의 services and ports 문서와 security group rule을 함께 점검합니다.

```text
control plane                         worker
microk8s add-node                     microk8s join ... --worker
cluster-agent :25000  <------------   join request
Kubernetes API and CNI <----------->  kubelet and workload Pods
```

조인 전에는 두 instance의 시간이 동기화되어 있는지도 확인합니다. MicroK8s는 node 간 통신을 위해 각 node에 독립된 실행 환경과 올바른 시간이 필요하다고 안내합니다.

---

## 2. Worker node 준비

Ubuntu instance를 준비한 뒤 control plane과 같은 MicroK8s channel을 설치합니다. 아래의 `<channel>`은 이미 운영 중인 control plane의 channel 값으로 바꿉니다.

```bash
sudo snap install microk8s --classic --channel=<channel>
sudo microk8s status --wait-ready
```

`status --wait-ready`가 끝나기 전에 조인하면 snap 초기화 중인 서비스 때문에 실패할 수 있습니다. node의 hostname과 private DNS가 운영 규칙에 맞는지도 이 단계에서 확인합니다.

---

## 3. Control plane에서 조인 명령 만들기

control plane node에서 다음 명령을 실행합니다.

```bash
sudo microk8s add-node
```

출력에는 `microk8s join <private-ip>:25000/<token>/<node-id>` 형태의 명령이 포함됩니다. 이 token은 cluster 가입 권한을 주는 민감 정보이므로 ticket, terminal history 공유, 블로그에 그대로 남기지 않습니다. 출력된 여러 주소 중 worker에서 실제로 도달 가능한 private IP를 선택합니다.

---

## 4. Worker로 조인

새 worker node에서 출력된 명령에 `--worker`를 붙여 실행합니다.

```bash
sudo microk8s join <private-ip>:25000/<token>/<node-id> --worker
```

`--worker` 없이 조인하면 일반 cluster member로 추가되어 control plane 구성에 영향을 줄 수 있습니다. 조인이 완료되면 worker의 API server proxy가 control plane endpoint 목록을 관리합니다. control plane endpoint를 load balancer 뒤에 둘 때는 MicroK8s 문서의 worker endpoint 설정 절차를 따릅니다.

---

## 5. Cluster 상태 확인

control plane에서 node가 `Ready`인지 확인합니다.

```bash
sudo microk8s kubectl get nodes -o wide
sudo microk8s status
```

`NotReady`라면 먼저 worker에서 `sudo microk8s inspect`를 실행하고, private DNS, security group, CNI network, 서로 다른 MicroK8s channel을 확인합니다. 조인 직후 바로 `Ready`가 되지 않을 수 있으므로 원인을 보기 전에 상태 변화와 kube-system Pod를 함께 확인합니다.

---

## 6. Worker에 workload가 배치되는지 확인

간단한 Deployment를 배포한 뒤 Pod의 `NODE` column을 확인합니다.

```bash
sudo microk8s kubectl create deployment web --image=nginx:stable --replicas=2
sudo microk8s kubectl rollout status deployment/web
sudo microk8s kubectl get pods -l app=web -o wide
```

이 결과는 scheduler가 해당 worker를 사용할 수 있음을 보여주지만, replica가 모든 node에 균등 분산된다는 보장은 아닙니다. node별 배치가 요구되면 resource request와 limit을 설정하고, 필요에 따라 node affinity, topology spread constraint, taint와 toleration을 명시합니다.

실습을 마쳤다면 리소스를 정리합니다.

```bash
sudo microk8s kubectl delete deployment web
```

---

## 7. 운영 시 주의점

- worker를 private subnet에 두더라도 snap과 container image를 내려받을 egress 경로, DNS, proxy 정책이 필요합니다.
- worker-only node는 control plane HA를 높이지 않습니다. control plane 장애 시에도 API를 제공해야 한다면 quorum을 충족하는 control plane 구성을 먼저 검토합니다.
- hostpath 기반 PersistentVolume은 Pod가 다른 node로 이동하면 데이터를 자동으로 따라가지 않습니다. stateful workload에는 storage class의 failure domain과 reclaim policy를 확인합니다.
- node 제거는 단순 instance 종료보다 `microk8s leave`, workload drain, 남은 cluster에서 `microk8s remove-node` 순서로 수행해 cluster membership을 정리합니다.

---

## 8. 정리

worker 추가의 완료 기준은 조인 명령의 성공이 아니라 node가 `Ready`가 되고 실제 workload가 의도한 node에서 정상 실행되는 것입니다. 먼저 private network와 필요한 port를 최소 범위로 열고, 조인 후에는 scheduling과 storage의 node 의존성을 함께 확인하면 단순 용량 확장이 운영 문제로 이어지는 일을 줄일 수 있습니다.

---

## 9. Reference

- [MicroK8s Docs - Create a MicroK8s cluster](https://canonical.com/microk8s/docs/clustering)
- [MicroK8s Docs - Services and ports](https://canonical.com/microk8s/docs/services-and-ports)
- [Kubernetes Docs - Assigning Pods to Nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
