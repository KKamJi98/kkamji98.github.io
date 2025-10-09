---
title: Kubernetes 리소스 모니터링 (3) - Prometheus & Grafana 연동
date: 2024-11-09 23:18:20 +0900
author: kkamji
categories: [Monitoring & Observability, Metric]
tags: [kubernetes, monitoring, observability, prometheus, node-exporter, push-gateway, grafana, dashboard, slack, data-source]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/observability/grafana/grafana.webp
---

이번 시간에는 **Prometheus**에서 수집한 지표를 **Grafana**를 사용해 시각화 하는 방법에 대해 알아보도록 하겠습니다.

### 관련 글

1. [Kubernetes 리소스 모니터링 (1) - Prometheus]({% post_url 2024/2024-11-07-prometheus %})
2. [Kubernetes 리소스 모니터링 (2) - Grafana]({% post_url 2024/2024-11-08-grafana %})
3. [Kubernetes 리소스 모니터링 (3) - Prometheus & Grafana 연동 (현재 글)]({% post_url 2024/2024-11-09-prometheus-grafana %})
4. [Kubernetes 리소스 모니터링 (4) - Prometheus & Thanos 연동]({% post_url 2025/2025-06-21-thanos-deploy %})

---

## 1. Data Source 추가

> 이전에 변경한 비밀번호를 사용해 **Grafana**에 접속한 뒤, 메인 화면에 보이는 DATA SOURCES에서 **Add your first data source**를 클릭합니다.
{: .prompt-tip}

![Add Data Source](/assets/img/observability/grafana/grafana_add_data_source.webp)

> **Prometheus** 메트릭을 Data Source로 사용할 예정이니 **Prometheus**를 클릭합니다.
{: .prompt-tip}

![Add Data Source Prometheus](/assets/img/observability/grafana/grafana_add_data_source_prometheus.webp)

> Kubernetes FQDN을 통해 Prometheus 도메인 이름을 추가하여 설정합니다.  
> (namespace: `monitoring`, service: `prometheus-server`)  
> FQDN: `http://prometheus-server.monitoring.svc.cluster.local:9090`  
{: .prompt-tip}

![Input Prometheus Server URL](/assets/img/observability/grafana/grafana_input_prometheus_server_url.webp)

> Authentication과 TLS 세팅 등의 설정이 필요한 경우 설정해 준 뒤 페이지 하단의 Save & test를 눌러 접속이 가능한지 확인합니다.
{: .prompt-tip}

![Grafana Prometheus Connection Test](/assets/img/observability/grafana/grafana_prometheus_connection_test.webp)

---

## 2. Data Source 확인 및 Import DashBoard

> 좌측 상단의 메뉴를 클릭 한 뒤, Connections > Data sources에 들어가 prometheus를 확인합니다.
{: .prompt-tip}

![Grafana Check Prometheus Data Source](/assets/img/observability/grafana/grafana_check_prometheus_data_source.webp)

> 좌측 상단의 Dashboards 메뉴에서, Create dashboard를 클릭합니다.
{: .prompt-tip}

![Grafana Create Dashboard](/assets/img/observability/grafana/grafana_create_dashboard.webp)

> Import dashboard를 클릭하고 Import Dashboard에 마음에 드는 URL이나 ID를 입력한 뒤, Load 버튼을 클릭합니다.
>
> <https://grafana.com/grafana/dashboards/>  
> 위의 사이트에서 대시보드를 찾아볼 수 있습니다.
{: .prompt-tip}

![Grafana Click Import Dashboard](/assets/img/observability/grafana/grafana_click_import_dashboard.webp)

![Grafana Insert Dashboard Number](/assets/img/observability/grafana/grafana_insert_dashboard_number.webp)

> Data Source가 방금 추가한 Prometheus로 되어있는지 확인한 뒤, Import 버튼을 클릭합니다.
{: .prompt-tip}

![Grafana Import Dashboard](/assets/img/observability/grafana/grafana_import_dashboard.webp)

---

## 3. Grafana DashBoard 확인

> 추가한 Dashboard를 통해 Prometheus를 통해 수집된 Kubernetes 리소스를 확인할 수 있습니다.
{: .prompt-tip}

![Grafana DashBoard](/assets/img/observability/grafana/grafana_dashboard.webp)

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
