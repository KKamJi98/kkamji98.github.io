---
title: Cilium Log Monitoring with Grafana Loki + Grafana Alloy [Cilium Study 2주차]
date: 2025-07-28 10:21:35 +0900
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

1. [Vagrant와 VirtualBox로 Kubernetes 클러스터 구축하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-14-deploy-kubernetes-vagrant-virtualbox %})
2. [Flannel CNI 배포하기 [Cilium Study 1주차]]({% post_url 2025/2025-07-15-deploy-flannel-cni %})
3. [Cilium CNI 알아보기 [Cilium Study 1주차]]({% post_url 2025/2025-07-16-cilium-cni-basic %})
4. [Cilium 구성요소 & 배포하기 (kube-proxy replacement) [Cilium Study 1주차]]({% post_url 2025/2025-07-18-deploy-cilium %})
5. [Cilium Hubble 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-21-hubble-basic %})
6. [Cilium & Hubble Command Cheat Sheet [Cilium Study 2주차]]({% post_url cheat-sheet/2025-07-23-cilium-hubble-commands %})
7. [Star Wars Demo와 함께 Cilium Network Policy 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-24-hubble-demo %})
8. [Hubble Exporter와 Dynamic Exporter Configuration [Cilium Study 2주차]]({% post_url 2025/2025-07-25-hubble-exporter %})
9. [Monitoring VS Observability + SLI/SLO/SLA 알아보기 [Cilium Study 2주차]]({% post_url 2025/2025-07-26-monitoring-observability-sli-slo-sla %})
10. [Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차]]({% post_url 2025/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana %})
11. [ Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차] (현재 글)]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})


---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
