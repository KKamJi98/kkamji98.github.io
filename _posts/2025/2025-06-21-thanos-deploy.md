---
title: Kubernetes 리소스 모니터링 (4) - Prometheus & Thanos 연동
date: 2025-06-21 01:31:49 +0900
author: kkamji
categories: [Monitoring & Observability, Metric]
tags: [kubernetes, monitoring, observability, devops, prometheus, thanos, minio]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/kubernetes/thanos.webp
---

**Thanos**는 **Prometheus**의 확장성과 고가용성 문제를 해결하기 위해 개발된 오픈소스 프로젝트입니다. 2017년에 시작되어 현재 **CNCF(Cloud Native Computing Foundation) Incubating** 프로젝트로 발전하고 있습니다. **Thanos**는 **Prometheus**의 장기 데이터 저장, 고가용성, 글로벌 쿼리 뷰 등의 기능을 제공하여 대규모 모니터링 환경에서 아래와 같은 한계를 극복할 수 있게 해줍니다.

### 1.1. Prometheus의 한계

| 한계 항목             | 설명                                                                      |
| --------------------- | ------------------------------------------------------------------------- |
| 데이터 장기 보존 불가 | 로컬 디스크 기반으로 장기 저장에 제약이 있으며 일정 기간 이후 데이터 삭제 |
| 고가용성 미지원       | Prometheus 자체적으로는 이중화 또는 클러스터링 기능이 없음                |
| 수평 확장 어려움      | 단일 서버에서만 작동하며 다중 서버 간 병렬 수집 및 집계가 어려움          |
| 전역 쿼리 불가능      | 여러 Prometheus 인스턴스 간 데이터를 통합 쿼리할 수 없음                  |
| 스토리지 확장성 부족  | 로컬 TSDB 기반으로 저장소 확장이 어렵고 중앙 스토리지 연동이 제한적       |
| 멀티 클러스터 한계    | 다수 클러스터에서의 통합 모니터링 구성이 복잡하고 별도 솔루션 필요        |

---

### 관련 글

1. [Kubernetes 리소스 모니터링 (1) - Prometheus]({% post_url 2024/2024-11-07-prometheus %})
2. [Kubernetes 리소스 모니터링 (2) - Grafana]({% post_url 2024/2024-11-08-grafana %})
3. [Kubernetes 리소스 모니터링 (3) - Prometheus & Grafana 연동]({% post_url 2024/2024-11-09-prometheus-grafana %})
4. [Kubernetes 리소스 모니터링 (4) - Prometheus & Thanos 연동 (현재 글)]({% post_url 2025/2025-06-21-thanos-deploy %})

---

## 2. Thanos란?

Thanos는 여러 Prometheus가 수집한 데이터를 통합하여, 대규모 클러스터 환경에서 확장성 있는 모니터링 시스템을 제공합니다.  
  
Prometheus가 모니터링 데이터를 로컬에만 저장하여 오래 보관하기 어려운 한계를 Sidecar를 통해 객체 스토리지(S3, GCS 등)에 저장해 해결하고, Querier 컴포넌트를 통해 여러 Prometheus 인스턴스의 중복된 데이터를 하나로 통합하여 정확한 모니터링 결과를 제공합니다. 또한 여러 클러스터에 분산된 데이터를 Store Gateway를 통해 하나의 PromQL로 조회할 수 있도록 지원합니다.  
  
Thanos의 모든 주요 컴포넌트는 무상태(stateless)로 동작하여 필요에 따라 손쉽게 수평 확장이 가능하며, Compactor를 통해 오래된 데이터를 효율적으로 압축하고 다운샘플링하여 비용을 최적화합니다.

---

## 3. Thanos의 구성요소

| 컴포넌트           | 핵심 역할                                                           | 배포 형태                 |
| ------------------ | ------------------------------------------------------------------- | ------------------------- |
| **Sidecar**        | Prometheus 데이터를 객체 스토리지에 업로드, 최신 데이터 조회        | Prometheus Pod 내 Sidecar |
| **Store Gateway**  | 객체 스토리지의 장기 저장 데이터를 조회·노출                        | Deployment                |
| **Querier**        | 여러 StoreAPI 데이터를 통합하고 하나로 병합하여 Prometheus API 제공 | Deployment                |
| **Compactor**      | 저장 데이터 병합, 다운샘플링, 보존 정책 적용                        | Deployment / CronJob      |
| **Ruler**          | 전역 알림(Alert) 및 기록 규칙(Recording Rule) 평가 및 관리          | Deployment                |
| **Receiver**       | Prometheus Remote-Write 데이터 수신 및 저장 (멀티테넌시 지원)       | StatefulSet               |
| **Bucket Web**     | 객체 스토리지(S3/GCS) 데이터 시각화 및 관리 WEB UI 제공             | Deployment                |
| **Query Frontend** | Querier 앞에서 쿼리 캐싱·최적화 (대규모 환경)                       | Deployment                |

![Thanos Architecture](/assets/img/kubernetes/thanos_architecture.webp)

---

## 4. Thanos 배포하기 (Helm)

Bitnami Helm Chart를 사용해 Thanos를 배포하고. 기존에 동작하고 있는 Minio와 연동해 보도록 하겠습니다.

### 4.1. Thanos `kkamji_local_values.yaml` 파일 생성

> 실제 운영에서는 `objstoreConfig` 를 Secret 으로 분리하거나 SOPS 로 암호화해 Git 에 노출되지 않도록 합니다.  
{: .prompt-tip}

```yaml
# kkamji_local_values.yaml
objstoreConfig: |-
  type: s3
  config:
    bucket: thanos
    endpoint: minio.minio.svc.cluster.local:9000
    access_key: xxxxxxxxxxxxx
    secret_key: xxxxxxxxxxxxx
    insecure: true

# existingObjstoreSecret: thanos-objstore # objstoreConfig 파일의 내용을 Secret으로 생성하는 것이 보안적으로 유리 (실제 환경)
query:
  dnsDiscovery:
    sidecarsService: kube-prometheus-stack-thanos-discovery # Prometheus Operator가 생성할 Headless Service 이름
    sidecarsNamespace: monitoring
  ingress:
    enabled: true
    hostname: thanos-query.kkamji.net
    ingressClassName: nginx
    annotations:
      nginx.ingress.kubernetes.io/force-ssl-redirect: "true"            # HTTP -> HTTPS 리다이렉트
      cert-manager.io/cluster-issuer: letsencrypt-prod                  # TLS 인증서 발급용 ClusterIssuer
      nginx.ingress.kubernetes.io/auth-type: "basic"                    # Nginx-ingress 전용 id/password 인증 방식 적용
      nginx.ingress.kubernetes.io/auth-secret: "prometheus-basic-auth"  # basic-auth 자격증명 Secret
      nginx.ingress.kubernetes.io/auth-realm: "Authentication Required" # 브라우저 프롬프트 메시지
      external-dns.alpha.kubernetes.io/target: xxx.xxx.xxx.xxx          # External-DNS가 가리킬 A 레코드 값 (On-Premise 에서 주로 사용)
    tls: true                                                           # cert-manager 로 TLS Secret 자동 생성

bucketweb:
  enabled: true
  ingress:
    enabled: true
    hostname: thanos-bucket.kkamji.net
    ingressClassName: nginx
    annotations:
      nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
      cert-manager.io/cluster-issuer: letsencrypt-prod
      nginx.ingress.kubernetes.io/auth-type: "basic"
      nginx.ingress.kubernetes.io/auth-secret: "prometheus-basic-auth"
      nginx.ingress.kubernetes.io/auth-realm: "Authentication Required"
      external-dns.alpha.kubernetes.io/target: xxx.xxx.xxx.xxx
    tls: true

compactor:
  enabled: true
  retentionResolutionRaw: 3d # 원본(1s 해상도)
  retentionResolution5m:  15d  # 5m down-sampling
  retentionResolution1h: 90d  # 1h down-sampling

storegateway:
  enabled: true

metrics:
  enabled: true
  serviceMonitor:
    enabled: true
```

### 4.2. Helm 배포 (Thanos)

```bash
❯ helm upgrade --install -n monitoring thanos oci://registry-1.docker.io/bitnamicharts/thanos -f kkamji_local_values.yaml
```

---

## 5. Prometheus Operator 배포하기 (Helm)

### 5.1. Prometheus Operator `value.yaml` 파일 생성

```yaml
## kkamji_local_with_thanos.yaml
grafana:
  defaultDashboardsTimezone: browser # TimeZone 설정 (default: UTC)
  sidecar:
    datasources:
      url: http://thanos-query-frontend.monitoring.svc.cluster.local:9090/

prometheus:
  thanosService:
    enabled: true # Thanos Sidecar용 Service 생성
  prometheusSpec:
    retention: 7d # 메트릭 데이터 보존 기간
    thanos:
      objectStorageConfig:
        existingSecret: # Thanos Helm에서 생성한 objectStorageConfig Secret 지정
          name: "thanos-objstore"
          key: "objstore.yml"
```

### 5.2. Helm 배포 (Prometheus Operator)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring -f kkamji_local_with_thanos.yaml
```

---

## 6. 확인 (Status, Log)

```bash
❯ k get po -n monitoring
NAME                                                        READY   STATUS    RESTARTS   AGE
alertmanager-kube-prometheus-stack-alertmanager-0           2/2     Running   0          22h
kube-prometheus-stack-grafana-64b8dcff56-cvb7s              3/3     Running   0          22h
kube-prometheus-stack-kube-state-metrics-686c86b5db-xrgnj   1/1     Running   0          22h
kube-prometheus-stack-operator-85b7cd9fb7-s8s5c             1/1     Running   0          22h
kube-prometheus-stack-prometheus-node-exporter-47lx5        1/1     Running   0          22h
kube-prometheus-stack-prometheus-node-exporter-5npfn        1/1     Running   0          22h
kube-prometheus-stack-prometheus-node-exporter-m648n        1/1     Running   0          22h
prometheus-kube-prometheus-stack-prometheus-0               3/3     Running   0          22h
thanos-bucketweb-b6765f78-wrwbb                             1/1     Running   0          22h
thanos-compactor-5dbbc4c9cd-l9bzm                           1/1     Running   0          22h
thanos-query-744b655c5d-ggkf2                               1/1     Running   0          22h
thanos-query-frontend-bd4bf86f8-5ggtz                       1/1     Running   0          22h
thanos-storegateway-0                                       1/1     Running   0          22h


❯ k logs -n monitoring thanos-storegateway-0                                                            
ts=2025-06-23T14:20:23.620784154Z caller=factory.go:54 level=info msg="loading bucket configuration"
ts=2025-06-23T14:20:23.621142797Z caller=inmemory.go:184 level=info msg="created in-memory index cache" maxItemSizeBytes=131072000 maxSizeBytes=262144000 maxItems=maxInt
ts=2025-06-23T14:20:23.621398058Z caller=options.go:29 level=info protocol=gRPC msg="disabled TLS, key and cert must be set to enable"
ts=2025-06-23T14:20:23.624017801Z caller=store.go:589 level=info msg="starting store node"
ts=2025-06-23T14:20:23.625525118Z caller=intrumentation.go:75 level=info msg="changing probe status" status=healthy
ts=2025-06-23T14:20:23.626003283Z caller=http.go:74 level=info service=http/server component=store msg="listening for requests and metrics" address=0.0.0.0:10902
ts=2025-06-23T14:20:23.626492356Z caller=handler.go:83 level=info service=http/server component=store caller=tls_config.go:347 time=2025-06-23T14:20:23.626479157Z msg="Listening on" address=[::]:10902
ts=2025-06-23T14:20:23.626559891Z caller=handler.go:83 level=info service=http/server component=store caller=tls_config.go:350 time=2025-06-23T14:20:23.626553861Z msg="TLS is disabled." http2=false address=[::]:10902
ts=2025-06-23T14:20:23.626603068Z caller=store.go:487 level=info msg="initializing bucket store"
ts=2025-06-23T14:20:23.682151288Z caller=fetcher.go:627 level=info component=block.BaseFetcher msg="successfully synchronized block metadata" duration=55.468956ms duration_ms=55 cached=0 returned=0 partial=0
ts=2025-06-23T14:20:23.6822549Z caller=store.go:504 level=info msg="bucket store ready" init_duration=55.644313ms
ts=2025-06-23T14:20:23.682884543Z caller=intrumentation.go:56 level=info msg="changing probe status" status=ready
ts=2025-06-23T14:20:23.682978595Z caller=grpc.go:167 level=info service=gRPC/server component=store msg="listening for serving gRPC" address=0.0.0.0:10901
ts=2025-06-23T14:20:23.68384688Z caller=fetcher.go:627 level=info component=block.BaseFetcher msg="successfully synchronized block metadata" duration=1.558953ms duration_ms=1 cached=0 returned=0 partial=0
ts=2025-06-23T14:35:23.689840725Z caller=fetcher.go:627 level=info component=block.BaseFetcher msg="successfully synchronized block metadata" duration=7.409484ms duration_ms=7 cached=0 returned=0 partial=0a
```

---

## 7. 확인 (Minio, Query 접속)

![Minio Thanos Blocks](/assets/img/kubernetes/thanos-minio.png)

![Thanos Bucket Web](/assets/img/kubernetes/thanos-bucket.png)

---

## 8. Reference

- Thanos GitHub - <https://github.com/thanos-io/thanos>
- Thanos Docs — <https://thanos.io/tip/thanos/>
- Prometheus Docs — <https://prometheus.io/docs/introduction/overview/>
- Bitnami Thanos Helm Chart — <https://artifacthub.io/packages/helm/bitnami/thanos>
- kube-prometheus-stack Helm Chart — <https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack>

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
