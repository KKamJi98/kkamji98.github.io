# Blog Refresh Backlog

이 문서는 `kkamji_scripts/blog/audit_blog_quality.py` 결과를 바탕으로 생성한 리프레시 우선순위다.
전체 글을 한 번에 고치기보다 Tier 1부터 작은 배치로 진행한다.

## Tier 1 - High impact technical refresh

- [ ] `_posts/2025/01/2025-01-15-helm-hook.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/cheat-sheet/2025-07-05-kubernetes-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-07-24-aws-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-17-irsa.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/09/2024-09-01-etcd-encrypt.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/06/2024-06-17-fqdn.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/05/2024-05-08-rbac.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-11-k8s-mysql-deploy.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/12/2023-12-13-kubernetes-cluster.md` - score 82, external links but no Reference section; add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2025/03/2025-03-15-kubernetes_monitoring_python.md` - score 88, external links but no Reference section
- [ ] `_posts/2025/10/2025-10-27-jenkins-ci-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-26-jenkins-ci-cd-env-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-10-argocd-rbac-5w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/02/2025-02-09-terraform-templatefile.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/12/2024-12-28-nginx-ingress-basic-auth.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/10/2024-10-03-harbor-docker-image-push.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/06/2024-06-07-route53-dns-record.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/05/2024-05-17-aws-summit-seoul-2024.md` - score 88, external links but no Reference section; consider adding concrete config or command examples
- [ ] `_posts/2024/06/2024-06-06-aws-domain-purchase.md` - score 88, external links but no Reference section; consider adding concrete config or command examples
- [ ] `_posts/2025/10/2025-10-13-ci-cd-study-1st-start.md` - score 88, external links but no Reference section
- [ ] `_posts/2025/07/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/12/2025-12-27-istio-fault-injection.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/01/2025-01-21-terraform-helm-provider.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/07/2025-07-26-monitoring-observability-sli-slo-sla.md` - score 94, add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2024/08/2024-08-09-fluent-bit.md` - score 94, add TL;DR callout
- [ ] `_posts/2024/07/2024-07-27-eks-secret-manager.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/07/2025-07-28-hubble-log-monitoring-with-grafana-loki.md` - score 94, add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2024/08/2024-08-10-elasticsearch.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/08/2025-08-14-cilium-cluster-mesh.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-18-argocd-cluster-management-6w.md` - score 94, add TL;DR callout; consider section-end summaries

## Tier 2 - Reference normalization

- [ ] `_posts/2023/10/2023-10-11-tcp-and-udp.md` - score 80, external links but no Reference section; long post without H2 headings
- [ ] `_posts/2025/01/2025-01-15-helm-hook.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/cheat-sheet/2025-07-05-kubernetes-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-07-24-aws-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-17-irsa.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/09/2024-09-01-etcd-encrypt.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/06/2024-06-17-fqdn.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/05/2024-05-08-rbac.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-11-k8s-mysql-deploy.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/12/2023-12-13-kubernetes-cluster.md` - score 82, external links but no Reference section; add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2023/06/2023-06-13-deep-learning-and-tensorflow.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/2023/09/2023-09-20-pxe.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/06/2023-06-26-javascript-datatype.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/09/2023-09-12-nat.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/09/2023-09-10-dhcp.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/06/2023-06-11-usb-serial-communication.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2025/03/2025-03-15-kubernetes_monitoring_python.md` - score 88, external links but no Reference section
- [ ] `_posts/2025/02/2025-02-09-terraform-templatefile.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/12/2024-12-28-nginx-ingress-basic-auth.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/10/2024-10-03-harbor-docker-image-push.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/06/2024-06-07-route53-dns-record.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/05/2024-05-17-aws-summit-seoul-2024.md` - score 88, external links but no Reference section; consider adding concrete config or command examples
- [ ] `_posts/2024/06/2024-06-06-aws-domain-purchase.md` - score 88, external links but no Reference section; consider adding concrete config or command examples
- [ ] `_posts/2025/10/2025-10-13-ci-cd-study-1st-start.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/09/2023-09-22-lvm.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/09/2023-09-14-dns.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/06/2024-06-12-priority-queue.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/01/2024-01-15-goroutine.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/09/2023-09-11-rip-ospf.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/07/2023-07-08-software-life-cycle.md` - score 88, external links but no Reference section
- [ ] `_posts/2025/04/2025-04-27-github_actions_basic.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/03/2024-03-26-stateless-vs-stateful.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/04/2024-04-01-type1-type2-virtualization.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/03/2024-03-29-virtualization.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/07/2023-07-09-git-cmp.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/09/2023-09-03-osi-7-layer-model.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/09/2023-09-13-gateway.md` - score 88, external links but no Reference section
- [ ] `_posts/2024/03/2024-03-19-zero-to-rust-book-read.md` - score 88, external links but no Reference section
- [ ] `_posts/2023/06/2023-06-11-blog.md` - score 88, external links but no Reference section

## Tier 3 - Long-form readability pass

- [ ] `_posts/2025/12/2025-12-11-valut-vso-in-k8s-8w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-23-introduce-helm-2w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-17-introduce-container-1w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-14-cilium-cluster-mesh.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2024/11/2024-11-21-neovim.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-31-argocd-3w.md` - score 100, consider section-end summaries
- [ ] `_posts/2025/11/2025-11-18-argocd-cluster-management-6w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-25-kube-burner.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-21-argocd-applicationset-6w.md` - score 100, consider section-end summaries
- [ ] `_posts/2024/06/2024-06-24-ansible-k8s.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-14-deploy-kubernetes-vagrant-virtualbox.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-27-jenkins-ci-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-11-cilium-bgp-control-plane.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-26-jenkins-ci-cd-env-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-10-argocd-rbac-5w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-18-deploy-cilium.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-29-cilium-ipam-mode.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-24-hubble-demo.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-29-jenkins-cd-3w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-04-12-git-cheat-sheet.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-12-cilium-lb-ipam.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2023/06/2023-06-13-deep-learning-and-tensorflow.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/2026/01/2026-01-21-git-worktree.md` - score 100, consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-03-07-linux-cheat-sheet.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2024/08/2024-08-06-karpenter.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2024/06/2024-06-11-network-policy.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-21-hubble-basic.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-07-05-kubernetes-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries

## Tier 4 - TL;DR candidates

- [ ] `_posts/2025/01/2025-01-15-helm-hook.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/cheat-sheet/2025-07-05-kubernetes-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/cheat-sheet/2025-07-24-aws-cheat-sheet.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-17-irsa.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/09/2024-09-01-etcd-encrypt.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/06/2024-06-17-fqdn.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/05/2024-05-08-rbac.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2024/07/2024-07-11-k8s-mysql-deploy.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/12/2023-12-13-kubernetes-cluster.md` - score 82, external links but no Reference section; add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2023/06/2023-06-13-deep-learning-and-tensorflow.md` - score 82, external links but no Reference section; add TL;DR callout; consider section-end summaries
- [ ] `_posts/2023/09/2023-09-20-pxe.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/06/2023-06-26-javascript-datatype.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/09/2023-09-12-nat.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/09/2023-09-10-dhcp.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2023/06/2023-06-11-usb-serial-communication.md` - score 82, external links but no Reference section; add TL;DR callout
- [ ] `_posts/2025/10/2025-10-27-jenkins-ci-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-26-jenkins-ci-cd-env-3w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-10-argocd-rbac-5w.md` - score 88, add TL;DR callout; split long post into clearer H2 sections; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-27-hubble-metric-monitoring-with-prometheus-grafana.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/12/2025-12-27-istio-fault-injection.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/01/2025-01-21-terraform-helm-provider.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/07/2025-07-26-monitoring-observability-sli-slo-sla.md` - score 94, add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2024/08/2024-08-09-fluent-bit.md` - score 94, add TL;DR callout
- [ ] `_posts/2024/07/2024-07-27-eks-secret-manager.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/07/2025-07-28-hubble-log-monitoring-with-grafana-loki.md` - score 94, add TL;DR callout; consider adding concrete config or command examples
- [ ] `_posts/2024/08/2024-08-10-elasticsearch.md` - score 94, add TL;DR callout
- [ ] `_posts/2025/08/2025-08-14-cilium-cluster-mesh.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/11/2025-11-18-argocd-cluster-management-6w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-25-kube-burner.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-14-deploy-kubernetes-vagrant-virtualbox.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-11-cilium-bgp-control-plane.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-18-deploy-cilium.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-29-cilium-ipam-mode.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-24-hubble-demo.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/10/2025-10-29-jenkins-cd-3w.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-12-cilium-lb-ipam.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2024/08/2024-08-06-karpenter.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/07/2025-07-21-hubble-basic.md` - score 94, add TL;DR callout; consider section-end summaries
- [ ] `_posts/2025/08/2025-08-10-cilium-native-routing.md` - score 94, add TL;DR callout
- [ ] `_posts/2024/11/2024-11-19-lambda-log-monitoring.md` - score 94, add TL;DR callout

## Execution notes

- Use `research-deep-research` for posts with factual/version-sensitive claims.
- Use `blog-review-post` after each refresh.
- Run `kkamji_scripts/blog/pre_publish_check.sh` before commit/push.
- Avoid changing slugs unless redirects are planned.
