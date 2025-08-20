---
title: Cilium Cluster Mesh [Cilium Study 5주차]
date: 2025-08-14 00:05:11 +0900
author: kkamji
categories: [Kubernetes, Cilium]
tags: [kubernetes, devops, cilium, cilium-study, bgp, lb-ipam, external-traffic-policy, ecmp]
comments: true
image:
  path: /assets/img/kubernetes/cilium/cilium.webp
---

저번

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
10. [Cilium Metric Monitoring with Prometheus + Grafana [Cilium Study 2주차]]({% post_url 2025/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana %})
11. [Cilium Log Monitoring with Grafana Loki & Grafana Alloy [Cilium Study 2주차]]({% post_url 2025/2025-07-28-hubble-log-monitoring-with-grafana-loki %})
12. [IPAM 개념 및 Kubernetes Host Scope -> Cluster Scope Migration 실습 [Cilium Study 3주차]]({% post_url 2025/2025-07-29-cilium-ipam-mode %})
13. [Cilium Network Routing 이해하기 – Encapsulation과 Native Routing 비교 [Cilium Study 3주차]]({% post_url 2025/2025-08-03-cilium-routing %})
14. [Cilium Native Routing 통신 확인 및 문제 해결 – Static Route & BGP [Cilium Study 4주차]]({% post_url 2025/2025-08-10-cilium-native-routing %})
15. [Cilium BGP Control Plane [Cilium Study 5주차]]({% post_url 2025/2025-08-11-cilium-bgp-control-plane %})
16. [Cilium Service LoadBalancer BGP Advertisement & ExternalTrafficPolicy [Cilium Study 5주차]]({% post_url 2025/2025-08-12-cilium-lb-ipam %})
17. [Kind로 Kubernetes Cluster 배포하기 [Cilium Study 5주차]]({% post_url 2025/2025-08-13-kind %})
18. [Cilium Cluster Mesh [Cilium Study 5주차] (현재 글)]({% post_url 2025/2025-08-14-cilium-cluster-mesh %})



---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
