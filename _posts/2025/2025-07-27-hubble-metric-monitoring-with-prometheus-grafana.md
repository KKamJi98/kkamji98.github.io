---
title: Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차]
date: 2025-07-27 10:21:35 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, monitoring, observability, sli, slo, sla, cilium-study, cloudnet]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

**Cilium**과 **Hubble**은 모두 **Prometheus** 메트릭을 제공하도록 구성할 수 있습니다. **Prometheus**는 플러그형 메트릭 수집 및 저장 시스템이며, 메트릭 시각화 프런트엔드인 Grafana 의 데이터 소스 역할을 할 수 있습니다. 

**Prometheus**에 대한 추가적인 내용은 [Kubernetes 리소스 모니터링 (1) - Prometheus]({% post_url 2024/2024-11-07-prometheus %}) 해당 글을 참고하시면 좋을 것 같습니다.

- [Cilium Docs - Monitoring & Metrics](https://docs.cilium.io/en/stable/observability/metrics/)

### 관련 글

1. [Vagrant와 VirtualBox로 Kubernetes Cluster 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-commands %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})
8. [Hubble Exporter와 Dynamic Exporter Configuration [Cilium Study 2주차]]({% post_url 2025/2025-07-25-hubble-exporter %})
9. [Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-26-monitoring-observability-sli-slo-sla %})
10. [Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana %})
11. [Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차]]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차]]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})
19. [Cilium Service Mesh [Cilium Study 6주차]]({% post_url 2025/2025-08-18-cilium-service-mesh %})
20. [Kube-burner 소개 및 실습 [Cilium Study 7주차]]({% post_url 2025/2025-08-25-kube-burner %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})
21. [Cilium Network Security [Cilium Study 8주차]]({% post_url 2025/2025-09-03-cilium-network-security %})

---

## 1. Cilium Metrics

**Cilium Metric**은 `cilium-agent`, `cilium-envoy`, `cilium-operator`와 같은 **Cilium Processes** 자체의 상태에 대한 인사이트를 제공합니다. Prometheus 메트릭을 활성화하려면. Helm으로 배포할 때 `prometheus.enabled=true` 값을 설정해야 합니다.

### 1.1 Cilium Metrics 활성화

```shell
❯ helm upgrade --install cilium cilium/cilium --version 1.17.6 --reuse-values \
  --namespace kube-system \
  --set prometheus.enabled=true \
  --set operator.prometheus.enabled=true
```

### 1.2 Cilium Metrics 활성화 확인

```shell
❯ kubectl get ds/cilium -n kube-system -o yaml | yq '.spec.template.metadata.annotations'
kubectl.kubernetes.io/restartedAt: "2025-07-27T03:40:31+09:00"
prometheus.io/port: "9962"
prometheus.io/scrape: "true"

❯ kubectl get deploy/cilium-operator -n kube-system -o yaml | yq '.spec.template.metadata.annotations'
kubectl.kubernetes.io/restartedAt: "2025-07-20T01:51:33+09:00"
prometheus.io/port: "9963"
prometheus.io/scrape: "true"

## Cilium Envoy는 위와 cilium-envoy라는 별도의 headless service를 통해 노출
❯ kubectl describe svc -n kube-system cilium-envoy                                     
Name:                     cilium-envoy
Namespace:                kube-system
Labels:                   app.kubernetes.io/managed-by=Helm
                          app.kubernetes.io/name=cilium-envoy
                          app.kubernetes.io/part-of=cilium
                          io.cilium/app=proxy
                          k8s-app=cilium-envoy
Annotations:              meta.helm.sh/release-name: cilium
                          meta.helm.sh/release-namespace: kube-system
                          prometheus.io/port: 9964 ## 확인
                          prometheus.io/scrape: true ## 확인
Selector:                 k8s-app=cilium-envoy
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       None  ## Headless Service
IPs:                      None
Port:                     envoy-metrics  9964/TCP
TargetPort:               envoy-metrics/TCP
Endpoints:                10.0.0.201:9964,10.0.0.202:9964,10.0.0.101:9964
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

---

## 2. Hubble Metrics

**Cilium Metric**을 사용하면 **Cilium** 자체의 상태를 모니터링할 수 있는 반면, **Hubble Metric**을 사용하면 연결 및 보안과 관련하여 **Cilium에서 관리하는 Kubernetes Pod의 네트워크 동작을 모니터링**할 수 있습니다.

### 2.1 Hubble Metrics 활성화

```shell
❯ helm upgrade --install cilium cilium/cilium --version 1.17.6 --reuse-values \
  --namespace kube-system \
  --set prometheus.enabled=true \
  --set operator.prometheus.enabled=true \
  --set hubble.enabled=true \
  --set hubble.metrics.enableOpenMetrics=true \
  --set hubble.metrics.enabled="{dns,drop,tcp,flow,port-distribution,icmp,httpV2:exemplars=true;labelsContext=source_ip\,source_namespace\,source_workload\,destination_ip\,destination_namespace\,destination_workload\,traffic_direction}"
```

### 2.2 Hubble Metrics 활성화 확인

```shell
❯ kubectl describe svc -n kube-system hubble-metrics              
Name:                     hubble-metrics
Namespace:                kube-system
Labels:                   app.kubernetes.io/managed-by=Helm
                          app.kubernetes.io/name=hubble
                          app.kubernetes.io/part-of=cilium
                          k8s-app=hubble
Annotations:              meta.helm.sh/release-name: cilium
                          meta.helm.sh/release-namespace: kube-system
                          prometheus.io/port: 9965 ## 확인
                          prometheus.io/scrape: true ## 확
Selector:                 k8s-app=cilium
Type:                     ClusterIP
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       None ## Headless Service
IPs:                      None
Port:                     hubble-metrics  9965/TCP
TargetPort:               hubble-metrics/TCP
Endpoints:                10.0.0.201:9965,10.0.0.202:9965,10.0.0.101:9965
Session Affinity:         None
Internal Traffic Policy:  Cluster
Events:                   <none>
```

---

## 3. Prometheus & Grafana 설정 (Cilium & Hubble Metric Monitoring)

위에서 `Cilium`과 `Hubble`의 Metrics를 Prometheus가 수집할 수 있도록 설정해주었습니다. 이제 Prometheus를 배포해 Metrics를 수집하고 Grafana를 사용해 수집된 Metrics를 확인해보도록 하겠습니다. 이를 위해서는 아래와 같이 Prometheus가 Cilium과 Hubble의 Metrics을 수집할 수 있도록 Scrape Config를 추가해야합니다.

### 3.1 Cilium Scrape Config

```yaml
scrape_configs:
- job_name: 'kubernetes-pods'
  kubernetes_sd_configs:
  - role: pod
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
    - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
      action: replace
      regex: ([^:]+)(?::\d+)?;(\d+)
      replacement: ${1}:${2}
      target_label: __address__

```

### 3.2 Hubble Scrape Config

```yaml
scrape_configs:
  - job_name: 'kubernetes-endpoints'
    scrape_interval: 30s
    kubernetes_sd_configs:
      - role: endpoints
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__address__, __meta_kubernetes_service_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)(?::\d+);(\d+)
        replacement: $1:$2
```

### 3.3 Prometheus & Grafana 배포하기 (kube-prometheus-stack)

위의 scrape config 설정은 `kube-prometheus-stack` Helm Chart의 Values의 `prometheus.prometheusSpec.additionalScrapeConfigs`에 정의해주겠습니다. `ingress`, `NodePort`혹은 `kubectl port-forward`를 사용해서 접속하실 수 있습니다.

```shell
❯ cat << EOF > kube-prometheus-stack-with-cilium-hubble-values.yaml
prometheus:
  prometheusSpec:
    additionalScrapeConfigs:
    # Hubble & Cilium Metric 수집을 위한 설정
    - job_name: 'kubernetes-pods' ## Cilium
      kubernetes_sd_configs:
      - role: pod
      relabel_configs:
      - source_labels: [ __meta_kubernetes_pod_annotation_prometheus_io_scrape ]
        action: keep
        regex: true
      - source_labels: [ __address__, __meta_kubernetes_pod_annotation_prometheus_io_port ]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: ${1}:${2}
        target_label: __address__

    - job_name: 'kubernetes-endpoints' ## Hubble
      scrape_interval: 30s
      kubernetes_sd_configs:
      - role: endpoints
      relabel_configs:
      - source_labels: [ __meta_kubernetes_service_annotation_prometheus_io_scrape ]
        action: keep
        regex: true
      - source_labels: [ __address__, __meta_kubernetes_service_annotation_prometheus_io_port ]
        action: replace
        target_label: __address__
        regex: (.+)(?::\d+);(\d+)
        replacement: $1:$2
EOF

❯ helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
❯ helm repo update
❯ helm upgrade --install  kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring \
    --version 75.12.0 --reuse-values -f kube-prometheus-stack-with-cilium-hubble-values.yaml
```

### 3.4 Scrape Config 확인

Prometheus 웹 UI에 접속 후 상단의 `Status > Target Health`에서 추가한 `kubernetes-pods`, `kubernetes-endpoints` Target의 State를 확인하고, `Status > Configuration`에서 실제 `kubernetes-pods`, `kubernetes-endpoints` Job을 확인하실 수 있습니다.

#### 3.4.1 Target Health 확인

![Prometheus Target Health](/assets/img/kubernetes/cilium/prometheus_target_health.webp)

#### 3.4.2 Scrape Config Job 확인 (kubernetes-pods)

![Scrape Config - kubernetes-pods](/assets/img/kubernetes/cilium/scrape_config_kubernetes_pods.webp)

#### 3.4.3 Scrape Config Job 확인 (kubernetes-endpoints)

![Scrape Config - kubernetes-endpoints](/assets/img/kubernetes/cilium/scrape_config_kubernetes_endpoints.webp)

#### 3.4.4 Scrape Config Job 확인 (secret 내용 확인 & pod 내부에서 config 파일 확인)

```shell
## Secrets 확인
❯ kubectl get secret -n monitoring prometheus-kube-prometheus-stack-prometheus \
  -o jsonpath='{.data.prometheus\.yaml\.gz}' \
| base64 -d | gunzip -c \
| yq '.scrape_configs[] | select(.job_name=="kubernetes-pods" or .job_name=="kubernetes-endpoints")'

job_name: kubernetes-pods
kubernetes_sd_configs:
  - role: pod
relabel_configs:
  - action: keep
    regex: true
    source_labels:
      - __meta_kubernetes_pod_annotation_prometheus_io_scrape
  - action: replace
    regex: ([^:]+)(?::\d+)?;(\d+)
    replacement: ${1}:${2}
    source_labels:
      - __address__
      - __meta_kubernetes_pod_annotation_prometheus_io_port
    target_label: __address__
job_name: kubernetes-endpoints
kubernetes_sd_configs:
  - role: endpoints
relabel_configs:
  - action: keep
    regex: true
    source_labels:
      - __meta_kubernetes_service_annotation_prometheus_io_scrape
  - action: replace
    regex: (.+)(?::\d+);(\d+)
    replacement: $1:$2
    source_labels:
      - __address__
      - __meta_kubernetes_service_annotation_prometheus_io_port
    target_label: __address__
scrape_interval: 30s

## 내부에서 확인
❯ kubectl exec -n monitoring sts/prometheus-kube-prometheus-stack-prometheus -c prometheus -- cat "/etc/prometheus/config_out/prometheus.env.yaml" \
| yq '.scrape_configs[] | select(.job_name=="kubernetes-pods" or .job_name=="kubernetes-endpoints")' 
job_name: kubernetes-pods
kubernetes_sd_configs:
  - role: pod
relabel_configs:
  - action: keep
    regex: true
    source_labels:
      - __meta_kubernetes_pod_annotation_prometheus_io_scrape
  - action: replace
    regex: ([^:]+)(?::\d+)?;(\d+)
    replacement: ${1}:${2}
    source_labels:
      - __address__
      - __meta_kubernetes_pod_annotation_prometheus_io_port
    target_label: __address__
job_name: kubernetes-endpoints
kubernetes_sd_configs:
  - role: endpoints
relabel_configs:
  - action: keep
    regex: true
    source_labels:
      - __meta_kubernetes_service_annotation_prometheus_io_scrape
  - action: replace
    regex: (.+)(?::\d+);(\d+)
    replacement: $1:$2
    source_labels:
      - __address__
      - __meta_kubernetes_service_annotation_prometheus_io_port
    target_label: __address__
scrape_interval: 30s
```

---

## 4. Cilium & Hubble Metrics 확인하기 (Prometheus)

간단한 Prometheus Query를 통해 Cilium과 Hubble의 Metrics을 확인해보겠습니다. 우측 상단 톱니 바퀴 모양에서 `autocomplete`와 `syntax highlighting` 기능을 활성화 하시면 쿼리를 조금 더 편리하게 작성하실 수 있습니다.

### 4.1 Prometheus Setting

![Prometheus Setting](/assets/img/kubernetes/cilium/prometheus_setting.webp)

### 4.2 Prometheus Sample Query

![Cilium BPF Prometheus Sample Query](/assets/img/kubernetes/cilium/cilium_bpf_prometheus_query.webp)

### 4.3 Prometheus Sample Query (결과)

![Cilium BPF Prometheus Sample Query Result](/assets/img/kubernetes/cilium/cilium_bpf_prometheus_query_result.webp)

### 4.4 Prometheus Sample Query (Graph)

![Cilium BPF Prometheus Sample Query Result Graph](/assets/img/kubernetes/cilium/cilium_bpf_prometheus_query_result_graph.webp)

---

## 5. Cilium & Hubble Metrics 확인하기 (Grafana)

Grafana에서 Prometheus가 DataSource로 등록되어있는지 확인한 뒤, Explore에서 쿼리를 시험하고, 공개된 Cilium 대시보드(ID: 6658)를 Import해 확인해보도록 하겠습니다. Grafana도 위와 동일하게 `ingress`, `NodePort`혹은 `kubectl port-forward`를 사용한 방식 중 편한 방식을 사용해 접속하시면 됩니다.  

> default 계정 정보 (추가로 ID,PW를 지정하지 않았다면 아래 정보로 접속)  
> Default ID: `admin`  
> Default PW: `prom-operator`  
{: .prompt-tip}

- [Grafana Labs - Cilium Metrics](https://grafana.com/grafana/dashboards/6658-cilium-metrics/)

### 5.1 Data Source 확인

![Grafana Data Sources](/assets/img/kubernetes/cilium/cilium_grafana_data_sources.webp)

### 5.2 Explorer에서 Query 확인

![Grafana Explorer](/assets/img/kubernetes/cilium/cilium_grafana_explorer.webp)

### 5.3 Dashboard Import 하기

#### 5.3.1 Grafana Dashboard Import 클릭

![Grafana Dashboard Import Button](/assets/img/kubernetes/cilium/grafana_dashboard_import_button.webp)

#### 5.3.2 Grafana-Dashboard Import에서 Dashboard의 ID 삽입 후 Load

![Grafana Dashboard Import ID](/assets/img/kubernetes/cilium/grafana_dashboard_import_id.webp)

#### 5.3.3 Dashboard Name, Folder, Datasource 지정 후 Import

![Grafana Dashboard Import](/assets/img/kubernetes/cilium/grafana_dashboard_import.webp)

### 5.4 Dashboard Import 확인

![Grafana Imported Dashboard Check](/assets/img/kubernetes/cilium/grafana_imported_dashboard_check.webp)

---

## 6. Reference

- [Cilium Docs - Monitoring & Metrics](https://docs.cilium.io/en/stable/observability/metrics/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
