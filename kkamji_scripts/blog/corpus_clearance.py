"""Opt-in repairs for confirmed corpus card/frame and painted nested-frame contacts.

This is not a global layout style. The frozen manifest is the union of 76 groups
with 174 card contacts and 104 groups with 242 painted nested-group contacts in
the 391-source, 4f3e7216f221a8dd2308577541d1006ddd288aaa baseline. Three groups
occur in both classes: 177 exact group targets across 135 includes. Nested
contacts require source ancestry AND geometric containment of painted frames;
unpainted DOM wrappers, siblings and external legends are not repair evidence.

Merge corpus_clearance_profile(include) with fixed/typography profiles BEFORE
Layout.measure(), including the alarm/config custom builders. The returned dict
contains only group_insets and fresh nested dictionaries. It does not change
columns, phase flows, ratios, routing or typography budgets. A 24px authored
inset leaves 22px empty space between the existing two 2px strokes; this is a
scoped compact allowance, not the separate Jev 32px policy. Compiler density
selection must still establish that the source fits its FHD budget.

Geometry checks are source evidence, not native pixel or browser review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class BoundaryRepair:
    include: str
    group: str
    inset: int
    cards: tuple[str, ...]
    groups: tuple[str, ...]


# Exact source IDs from the baseline source audit and painted layout metadata.
# Columns: include, parent group, inset, coincident cards, coincident groups.
_REPAIR_ROWS = (
    ('diagrams/static/ai/agentic-development-workspace.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/ai/graph-system-intelligence.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1', 'root.0.1.2')),
    ('diagrams/static/ai/hermes-wsl2-agent-flow.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/ai/humanize/humanize-route-hint.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.2'), ()),
    ('diagrams/static/ai/humanize/humanize-route-hint.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/ai/llm-wiki/llm-wiki-build-pipeline.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.2'), ()),
    ('diagrams/static/ai/llm-wiki/llm-wiki-build-pipeline.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/ai/llm-wiki/llm-wiki-search-regression-gate.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/ai/rag-02-contextual-retrieval.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/ai/rag-05-cache-conflict.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/ai/rag-06-latency-eval.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/aws/analytics-stack-03-distributed-sql-mpp.html', 'root.0.1.4', 24, ('root.0.1.4.0.0.2', 'root.0.1.4.2.0.2'), ()),
    ('diagrams/static/aws/analytics-stack-04-overview.html', 'root.0.1.2', 24, ('root.0.1.2.0', 'root.0.1.2.1'), ()),
    ('diagrams/static/aws/analytics-stack-04-overview.html', 'root.0.1.4', 24, ('root.0.1.4.0', 'root.0.1.4.1'), ()),
    ('diagrams/static/aws/analytics-stack-05-query-flow.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1', 'root.0.1.4.2')),
    ('diagrams/static/aws/analytics-stack-06-catalog-federation.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/aws/analytics-stack-11-iceberg-cow-vs-mor.html', 'root.0.2.1.1', 24, ('root.0.2.1.1.0', 'root.0.2.1.1.1'), ()),
    ('diagrams/static/aws/aws-glue-partitioning-pruning-flow.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.1'), ()),
    ('diagrams/static/aws/aws-waf-challenge-token-flow.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1')),
    ('diagrams/static/aws/aws-waf-request-flow.html', 'root.0.1.6', 24, (), ('root.0.1.6.0', 'root.0.1.6.1')),
    ('diagrams/static/aws/devops-agent/devops-agent-signal-flow.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.1', 'root.0.1.2'), ()),
    ('diagrams/static/aws/devops-agent/devops-agent-signal-flow.html', 'root.0.5', 24, ('root.0.5.0', 'root.0.5.1', 'root.0.5.2'), ()),
    ('diagrams/static/aws/eks-max-pods-prefix-mode.html', 'root.0.1.1.4', 24, (), ('root.0.1.1.4.0', 'root.0.1.1.4.1')),
    ('diagrams/static/aws/eks-token-cache-flow.html', 'root.0.1.6', 24, (), ('root.0.1.6.0', 'root.0.1.6.1')),
    ('diagrams/static/aws/vpc-lattice-cross-vpc-flow.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1')),
    ('diagrams/static/blockchain/bitcoin-mempool-reorg.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/blockchain/coin-select-two-inputs.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.1'), ()),
    ('diagrams/static/blockchain/coin-select-two-inputs.html', 'root.0.3', 24, ('root.0.3.0', 'root.0.3.2'), ()),
    ('diagrams/static/blockchain/coin-select-two-inputs.html', 'root.0.5', 24, (), ('root.0.5.0', 'root.0.5.1')),
    ('diagrams/static/blockchain/hd-mnemonic-three-addresses.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/blockchain/http-200-is-not-chain-head.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/blockchain/merkle-inclusion-path.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/blockchain/merkle-inclusion-path.html', 'root.0.3', 24, ('root.0.3.0', 'root.0.3.2'), ()),
    ('diagrams/static/blockchain/operator-health-ladder.html', 'root.0.1', 24, ('root.0.1.4', 'root.0.1.6', 'root.0.1.8'), ()),
    ('diagrams/static/blockchain/receipt-finality-tags.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/blockchain/reentrancy-cei.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/blockchain/rpc-balance-is-local.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/blockchain/sign-verify-tamper.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/blockchain/solc-pin-two-hashes.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/blockchain/utxo-reference-structure.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/ci-cd/argocd-multi-cluster-flow.html', 'root.0.1.6', 24, (), ('root.0.1.6.0', 'root.0.1.6.1')),
    ('diagrams/static/ci-cd/ci-cd-study/argo-multi-cluster-architecture.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/ci-cd/ci-cd-study/argo-rollouts-architecture.html', 'root.0.1.2.1.4', 24, (), ('root.0.1.2.1.4.0', 'root.0.1.2.1.4.1')),
    ('diagrams/static/ci-cd/ci-cd-study/argo-rollouts-canary-deployment-strategies.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1', 'root.0.1.4.2', 'root.0.1.4.3')),
    ('diagrams/static/ci-cd/ci-cd-study/argocd-architecture-overview.html', 'root.0.4', 24, ('root.0.4.0', 'root.0.4.1', 'root.0.4.2', 'root.0.4.3', 'root.0.4.4'), ()),
    ('diagrams/static/ci-cd/ci-cd-study/docker-build-workflow.html', 'root.0.1.0', 24, ('root.0.1.0.1',), ('root.0.1.0.0',)),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-overview.html', 'root.0.2.0.2', 24, ('root.0.2.0.2.0',), ()),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-overview.html', 'root.0.2.1.2', 24, ('root.0.2.1.2.0', 'root.0.2.1.2.4'), ()),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html', 'root.0.2.0.2', 24, ('root.0.2.0.2.0', 'root.0.2.0.2.2'), ()),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html', 'root.0.2.1.2', 24, ('root.0.2.1.2.0', 'root.0.2.1.2.2', 'root.0.2.1.2.4'), ()),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-scripted-vs-declarative.html', 'root.0.1.0.3', 24, (), ('root.0.1.0.3.0', 'root.0.1.0.3.1')),
    ('diagrams/static/ci-cd/ci-cd-study/jenkins-scripted-vs-declarative.html', 'root.0.1.1.3', 24, (), ('root.0.1.1.3.0', 'root.0.1.1.3.1', 'root.0.1.1.3.2')),
    ('diagrams/static/ci-cd/ci-cd-study/kubernetes-architecture-overview.html', 'root.0.2.2', 24, ('root.0.2.2.0', 'root.0.2.2.1', 'root.0.2.2.2'), ()),
    ('diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html', 'root.0.2.0.2', 24, ('root.0.2.0.2.0',), ()),
    ('diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html', 'root.0.2.1.2', 24, ('root.0.2.1.2.4',), ()),
    ('diagrams/static/ci-cd/ci-cd-study/openid-connect-authorization-code-flow-simplied.html', 'root.0.2', 24, ('root.0.2.0.0',), ()),
    ('diagrams/static/ci-cd/ci-cd-study/vault-dynamic-secrets-senario.html', 'root.0.4', 24, (), ('root.0.4.0', 'root.0.4.1')),
    ('diagrams/static/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-walkthrough.html', 'root.0.1.8', 24, (), ('root.0.1.8.0', 'root.0.1.8.1', 'root.0.1.8.2')),
    ('diagrams/static/gcp/gcp-org-tree.html', 'root.0.4', 24, (), ('root.0.4.0', 'root.0.4.1')),
    ('diagrams/static/gcp/gcp-org-tree.html', 'root.0.4.0.1.2', 24, ('root.0.4.0.1.2.0', 'root.0.4.0.1.2.1'), ()),
    ('diagrams/static/gcp/gcp-wif-token-exchange-flow.html', 'root.0.5', 24, ('root.0.5.0', 'root.0.5.1'), ()),
    ('diagrams/static/git/bare-worktree-layout.html', 'root.0.2.2', 24, ('root.0.2.2.0', 'root.0.2.2.1', 'root.0.2.2.2', 'root.0.2.2.3'), ()),
    ('diagrams/static/javascript/javascript-data-type-model.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/kubernetes/cilium/2w-grafana-alloy-overview.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/kubernetes/cilium/2w-grafana-alloy-overview.html', 'root.0.7', 24, (), ('root.0.7.0', 'root.0.7.1')),
    ('diagrams/static/kubernetes/cilium/2w-grafana-loki-overview.html', 'root.0.7', 24, ('root.0.7.0', 'root.0.7.1'), ()),
    ('diagrams/static/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.html', 'root.0.1.1', 24, ('root.0.1.1.0', 'root.0.1.1.1'), ()),
    ('diagrams/static/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/kubernetes/cilium/5w-l3-announcement-over-bgp.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/kubernetes/cilium/6w-controlplane-managed.html', 'root.0.3.1.2', 24, ('root.0.3.1.2.0', 'root.0.3.1.2.1'), ()),
    ('diagrams/static/kubernetes/cilium/6w-micro-service-architecture-complexity.html', 'root.0.2.0.1', 24, ('root.0.2.0.1.0', 'root.0.2.0.1.1', 'root.0.2.0.1.2'), ()),
    ('diagrams/static/kubernetes/cilium/cilium-overview.html', 'root.0.1.1', 24, ('root.0.1.1.0.0', 'root.0.1.1.0.2', 'root.0.1.1.1', 'root.0.1.1.2'), ()),
    ('diagrams/static/kubernetes/cilium/cilium-overview.html', 'root.0.3.3', 24, ('root.0.3.3.0', 'root.0.3.3.1'), ()),
    ('diagrams/static/kubernetes/cilium/hubble-architecture.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/kubernetes/cilium/kube-proxy_replacement.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/kubernetes/cilium/kubernetes_host_scope_ipam_mode.html', 'root.0.2.6', 24, ('root.0.2.6.0', 'root.0.2.6.1'), ()),
    ('diagrams/static/kubernetes/cilium/multi-pool.html', 'root.0.2.0.1.4', 24, ('root.0.2.0.1.4.0', 'root.0.2.0.1.4.1', 'root.0.2.0.1.4.2'), ()),
    ('diagrams/static/kubernetes/endpoint_vs_endpointslice.html', 'root.0.2.1.1.4', 24, ('root.0.2.1.1.4.0', 'root.0.2.1.1.4.1', 'root.0.2.1.1.4.2'), ()),
    ('diagrams/static/kubernetes/kubernetes-rbac-binding.html', 'root.0.1.4', 24, ('root.0.1.4.0', 'root.0.1.4.1'), ()),
    ('diagrams/static/kubernetes/metrics-server-collection.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.2', 'root.0.1.4'), ()),
    ('diagrams/static/kubernetes/metrics-server-collection.html', 'root.0.3', 24, ('root.0.3.0', 'root.0.3.1'), ()),
    ('diagrams/static/kubernetes/mysql-kubernetes-deployment.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/kubernetes/nginx-basic-auth-flow.html', 'root.0.1', 24, ('root.0.1.2', 'root.0.1.4'), ()),
    ('diagrams/static/kubernetes/nginx-basic-auth-flow.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/kubernetes/probe-state-flow.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/kubernetes/terminating-pod-troubleshooting.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/kubernetes/thanos_architecture.html', 'root.0.1.6', 24, ('root.0.1.6.0', 'root.0.1.6.1'), ()),
    ('diagrams/static/kubernetes/thanos_architecture.html', 'root.0.3', 24, ('root.0.3.0', 'root.0.3.1'), ()),
    ('diagrams/static/network/dns-recursive-resolution.html', 'root.0.4', 24, ('root.0.4.0',), ('root.0.4.1',)),
    ('diagrams/static/nodejs/node-async-http-handling-flow.html', 'root.0.2.6', 24, ('root.0.2.6.0', 'root.0.2.6.1'), ()),
    ('diagrams/static/nodejs/nodejs-server-runtime-overview.html', 'root.0.1.4.2.4', 24, ('root.0.1.4.2.4.0', 'root.0.1.4.2.4.1'), ()),
    ('diagrams/static/observability/datadog-rum-01-data-model.html', 'root.0.1.4', 24, ('root.0.1.4.0', 'root.0.1.4.1', 'root.0.1.4.2', 'root.0.1.4.3', 'root.0.1.4.4'), ()),
    ('diagrams/static/project/rememberme/architecture.html', 'root.0.4', 24, ('root.0.4.0',), ('root.0.4.1',)),
    ('diagrams/static/project/weasel/about/architecture.html', 'root.0.2.1', 24, (), ('root.0.2.1.0', 'root.0.2.1.1', 'root.0.2.1.2')),
    ('diagrams/static/project/weasel/about/ci-cd.html', 'root.0.2.0.2', 24, (), ('root.0.2.0.2.0', 'root.0.2.0.2.1')),
    ('diagrams/static/project/weasel/about/workflow.html', 'root.0.1.1.1.2', 24, (), ('root.0.1.1.1.2.0', 'root.0.1.1.1.2.1')),
    ('diagrams/static/project/weasel/cicd.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/project/weasel/weasel-architecture.html', 'root.0.2.1', 24, (), ('root.0.2.1.0', 'root.0.2.1.1', 'root.0.2.1.2')),
    ('diagrams/static/project/weasel/weasel-architecture.html', 'root.0.2.3', 24, (), ('root.0.2.3.0', 'root.0.2.3.1')),
    ('diagrams/static/project/weasel/workflows.html', 'root.0.1.1.1.2', 24, ('root.0.1.1.1.2.0', 'root.0.1.1.1.2.1'), ()),
    ('diagrams/static/registry/harbor-kubernetes-architecture.html', 'root.0.2.4', 24, (), ('root.0.2.4.0', 'root.0.2.4.1')),
    ('diagrams/static/sap-c02/acm-certificate-issuance-paths.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2', 'root.0.1.2.3')),
    ('diagrams/static/sap-c02/asg-instance-lifecycle-hooks.html', 'root.0.1.6', 24, (), ('root.0.1.6.0', 'root.0.1.6.1')),
    ('diagrams/static/sap-c02/aurora-global-switchover-failover.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1')),
    ('diagrams/static/sap-c02/aws-backup-continuous-vs-snapshot.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/sap-c02/capacity-and-discount-layers.html', 'root.0.1.0', 24, ('root.0.1.0.0', 'root.0.1.0.1'), ()),
    ('diagrams/static/sap-c02/capacity-and-discount-layers.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2')),
    ('diagrams/static/sap-c02/capacity-versus-discount-matrix.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/sap-c02/capacity-versus-discount-matrix.html', 'root.0.1.4', 24, (), ('root.0.1.4.0', 'root.0.1.4.1')),
    ('diagrams/static/sap-c02/cloudfront-origin-failover-path.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html', 'root.0.1.6.0.1.2', 24, ('root.0.1.6.0.1.2.0', 'root.0.1.6.0.1.2.1'), ()),
    ('diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html', 'root.0.1.6.1.1.2', 24, ('root.0.1.6.1.1.2.0', 'root.0.1.6.1.1.2.1', 'root.0.1.6.1.1.2.2'), ()),
    ('diagrams/static/sap-c02/cloudwatch-logs-delivery-paths.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2', 'root.0.1.2.3')),
    ('diagrams/static/sap-c02/cloudwatch-logs-delivery-paths.html', 'root.0.1.2.0.1.2', 24, ('root.0.1.2.0.1.2.0', 'root.0.1.2.0.1.2.1', 'root.0.1.2.0.1.2.2', 'root.0.1.2.0.1.2.3'), ()),
    ('diagrams/static/sap-c02/config-evaluation-remediation.html', 'root.0.1.0.0.3.4', 24, (), ('root.0.1.0.0.3.4.0', 'root.0.1.0.0.3.4.1')),
    ('diagrams/static/sap-c02/config-evaluation-remediation.html', 'root.0.1.0.1.3', 24, ('root.0.1.0.1.3.0', 'root.0.1.0.1.3.2'), ()),
    ('diagrams/static/sap-c02/confused-deputy-external-id.html', 'root.0.1.0', 24, (), ('root.0.1.0.0', 'root.0.1.0.1')),
    ('diagrams/static/sap-c02/confused-deputy-external-id.html', 'root.0.1.6', 24, (), ('root.0.1.6.0', 'root.0.1.6.1')),
    ('diagrams/static/sap-c02/control-tower-landing-zone.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/sap-c02/cost-recommendation-sources.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2')),
    ('diagrams/static/sap-c02/data-transfer-charge-points.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2', 'root.0.1.2.3', 'root.0.1.2.4')),
    ('diagrams/static/sap-c02/data-transfer-online-vs-physical.html', 'root.0.1.0', 24, ('root.0.1.0.0', 'root.0.1.0.1', 'root.0.1.0.2'), ()),
    ('diagrams/static/sap-c02/data-transfer-online-vs-physical.html', 'root.0.1.8', 24, (), ('root.0.1.8.0', 'root.0.1.8.1')),
    ('diagrams/static/sap-c02/data-transfer-online-vs-physical.html', 'root.0.1.8.1.1.2', 24, ('root.0.1.8.1.1.2.0', 'root.0.1.8.1.1.2.1'), ()),
    ('diagrams/static/sap-c02/detection-to-remediation-path.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.1', 'root.0.1.2', 'root.0.1.3'), ()),
    ('diagrams/static/sap-c02/detection-to-remediation-path.html', 'root.0.5', 24, ('root.0.5.0', 'root.0.5.1'), ()),
    ('diagrams/static/sap-c02/directory-service-selection.html', 'root.0.1.0.3', 24, (), ('root.0.1.0.3.0', 'root.0.1.0.3.1')),
    ('diagrams/static/sap-c02/dms-schema-object-ownership.html', 'root.0.1.0', 24, ('root.0.1.0.0', 'root.0.1.0.1'), ()),
    ('diagrams/static/sap-c02/dms-schema-object-ownership.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1')),
    ('diagrams/static/sap-c02/dr-verification-loop.html', 'root.0.2.2', 24, (), ('root.0.2.2.0', 'root.0.2.2.1')),
    ('diagrams/static/sap-c02/dx-vif-reach-scope.html', 'root.0.2.4', 24, (), ('root.0.2.4.0', 'root.0.2.4.1', 'root.0.2.4.2')),
    ('diagrams/static/sap-c02/ec2-purchase-option-decision.html', 'root.0.2.2', 24, (), ('root.0.2.2.0', 'root.0.2.2.1')),
    ('diagrams/static/sap-c02/ec2-purchase-option-decision.html', 'root.0.2.2.0.1.2', 24, ('root.0.2.2.0.1.2.0', 'root.0.2.2.0.1.2.1'), ()),
    ('diagrams/static/sap-c02/ecs-capacity-provider-placement.html', 'root.0.2.2', 24, (), ('root.0.2.2.0', 'root.0.2.2.1')),
    ('diagrams/static/sap-c02/edge-placement-boundaries.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/sap-c02/edge-placement-boundaries.html', 'root.0.2.0.3', 24, ('root.0.2.0.3.0', 'root.0.2.0.3.1'), ()),
    ('diagrams/static/sap-c02/eks-compute-option-split.html', 'root.0.2.2', 24, (), ('root.0.2.2.0', 'root.0.2.2.1', 'root.0.2.2.2', 'root.0.2.2.3')),
    ('diagrams/static/sap-c02/eventbridge-fanout-target-limit.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/sap-c02/eventbridge-fanout-target-limit.html', 'root.0.2.1.3', 24, ('root.0.2.1.3.0', 'root.0.2.1.3.1', 'root.0.2.1.3.2'), ()),
    ('diagrams/static/sap-c02/global-accelerator-cloudfront-paths.html', 'root.0.4', 24, (), ('root.0.4.0', 'root.0.4.1')),
    ('diagrams/static/sap-c02/glue-catalog-lake-formation-access.html', 'root.0.2.8', 24, (), ('root.0.2.8.0', 'root.0.2.8.1')),
    ('diagrams/static/sap-c02/kinesis-efo-vs-shared-consumers.html', 'root.0.2.4', 24, (), ('root.0.2.4.0', 'root.0.2.4.1')),
    ('diagrams/static/sap-c02/kinesis-firehose-replay-boundary.html', 'root.0.2.6', 24, ('root.0.2.6.0', 'root.0.2.6.1'), ()),
    ('diagrams/static/sap-c02/lambda-concurrency-gates.html', 'root.0.1.0.1.2', 24, ('root.0.1.0.1.2.0', 'root.0.1.0.1.2.1'), ()),
    ('diagrams/static/sap-c02/migration-discovery-tool-ownership.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/sap-c02/migration-discovery-tool-ownership.html', 'root.0.2.2.1.2', 24, ('root.0.2.2.1.2.0', 'root.0.2.2.1.2.1'), ()),
    ('diagrams/static/sap-c02/modernization-compute-target-decision.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/sap-c02/modernization-container-hosting-boundaries.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/sap-c02/modernization-database-target-selection.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2', 'root.0.2.3')),
    ('diagrams/static/sap-c02/modernization-integration-choice-boundaries.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1', 'root.0.2.2')),
    ('diagrams/static/sap-c02/ops-event-routing.html', 'root.0.1.4', 24, ('root.0.1.4.0', 'root.0.1.4.1', 'root.0.1.4.2'), ()),
    ('diagrams/static/sap-c02/organizations-scp-hierarchy.html', 'root.0.1.2', 24, (), ('root.0.1.2.0', 'root.0.1.2.1', 'root.0.1.2.2')),
    ('diagrams/static/sap-c02/organizations-scp-hierarchy.html', 'root.0.1.2.1.1.2', 24, ('root.0.1.2.1.1.2.0', 'root.0.1.2.1.1.2.1'), ()),
    ('diagrams/static/sap-c02/placement-group-boundaries.html', 'root.0.1.1.1.2', 24, ('root.0.1.1.1.2.0', 'root.0.1.1.1.2.1'), ()),
    ('diagrams/static/sap-c02/placement-group-boundaries.html', 'root.0.1.2.1.2', 24, ('root.0.1.2.1.2.0', 'root.0.1.2.1.2.1'), ()),
    ('diagrams/static/sap-c02/ram-vpc-subnet-sharing.html', 'root.0.1.2.1.4', 24, ('root.0.1.2.1.4.0', 'root.0.1.2.1.4.1'), ()),
    ('diagrams/static/sap-c02/rds-deployment-topologies.html', 'root.0.1.1.1.2', 24, ('root.0.1.1.1.2.0', 'root.0.1.1.1.2.1'), ()),
    ('diagrams/static/sap-c02/rds-deployment-topologies.html', 'root.0.1.2.1.2', 24, ('root.0.1.2.1.2.0', 'root.0.1.2.1.2.1'), ()),
    ('diagrams/static/sap-c02/regional-failover-trigger-layers.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/sap-c02/s3-replication-scope.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/sap-c02/saml-federation-paths.html', 'root.0.1', 24, ('root.0.1.0', 'root.0.1.2', 'root.0.1.4'), ()),
    ('diagrams/static/sap-c02/saml-federation-paths.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/sap-c02/scp-iam-effective-permissions.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1', 'root.0.1.2')),
    ('diagrams/static/sap-c02/scp-iam-effective-permissions.html', 'root.0.5', 24, (), ('root.0.5.0', 'root.0.5.1')),
    ('diagrams/static/sap-c02/session-tags-abac.html', 'root.0.1', 24, (), ('root.0.1.0', 'root.0.1.1')),
    ('diagrams/static/sap-c02/session-tags-abac.html', 'root.0.5', 24, ('root.0.5.0', 'root.0.5.1'), ()),
    ('diagrams/static/sap-c02/shared-storage-az-boundary.html', 'root.0.1.0.0.1', 24, ('root.0.1.0.0.1.0', 'root.0.1.0.0.1.1'), ()),
    ('diagrams/static/sap-c02/shared-storage-az-boundary.html', 'root.0.1.1.1', 24, ('root.0.1.1.1.0', 'root.0.1.1.1.1'), ()),
    ('diagrams/static/sap-c02/spot-interruption-signals.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/sap-c02/sqs-message-lifecycle-dlq.html', 'root.0.1', 24, ('root.0.1.4', 'root.0.1.6'), ()),
    ('diagrams/static/sap-c02/sqs-message-lifecycle-dlq.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/sap-c02/stepfunctions-workflow-type-split.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1', 'root.0.3.2')),
    ('diagrams/static/sap-c02/worm-retention-decision.html', 'root.0.3', 24, (), ('root.0.3.0', 'root.0.3.1')),
    ('diagrams/static/sap-c02/worm-retention-decision.html', 'root.0.3.0.2', 24, ('root.0.3.0.2.0', 'root.0.3.0.2.1', 'root.0.3.0.2.2'), ()),
    ('diagrams/static/security/ja4/ja4-fingerprint-construction.html', 'root.0.2.2', 24, (), ('root.0.2.2.0', 'root.0.2.2.1')),
    ('diagrams/static/spring/spring-07-autoconfiguration-flow.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
    ('diagrams/static/virtualization/full-para-virtualization.html', 'root.0.2', 24, (), ('root.0.2.0', 'root.0.2.1')),
)
REPAIRS = tuple(BoundaryRepair(*row) for row in _REPAIR_ROWS)


def corpus_clearance_profile(include: str) -> dict:
    """Return only the opted-in group insets for this exact catalog identifier."""
    insets = {repair.group: repair.inset for repair in REPAIRS
              if repair.include == include}
    return {"group_insets": insets} if insets else {}


def _stroke(rect: Mapping) -> float:
    return float(rect.get("stroke_width", rect.get("stroke-width", 2)))


def stroke_clearance(parent: Mapping, child: Mapping) -> tuple[float, ...]:
    """Empty painted space on left, top, right and bottom, not center distance."""
    stroke = (_stroke(parent) + _stroke(child)) / 2
    return (
        child["x"] - parent["x"] - stroke,
        child["y"] - parent["y"] - stroke,
        parent["x"] + parent["width"] - child["x"] - child["width"] - stroke,
        parent["y"] + parent["height"] - child["y"] - child["height"] - stroke,
    )


def _descendant(child: Mapping, parent: Mapping) -> bool:
    return child["source"].startswith(parent["source"] + ".")


def _contained(child: Mapping, parent: Mapping, tolerance: float) -> bool:
    return (
        child["x"] >= parent["x"] - tolerance
        and child["y"] >= parent["y"] - tolerance
        and child["x"] + child["width"] <= parent["x"] + parent["width"] + tolerance
        and child["y"] + child["height"] <= parent["y"] + parent["height"] + tolerance
    )


def painted_boundary_contacts(
    boxes: Iterable[Mapping], groups: Iterable[Mapping], tolerance: float = 0.1,
) -> list[dict]:
    """Find ancestral, contained contacts in PAINTED rectangles only.

    Pass layout.groups, not layout.group_bounds (which includes unpainted
    wrappers). The result records both exact source IDs and actual stroke gaps.
    Noncontained external notes and nonancestral overlapping siblings are ignored.
    """
    boxes, groups = tuple(boxes), tuple(groups)
    findings = []
    for parent in groups:
        for kind, children in (("card", boxes), ("group", groups)):
            for child in children:
                if not _descendant(child, parent) or not _contained(child, parent, tolerance):
                    continue
                gaps = stroke_clearance(parent, child)
                if min(gaps) <= tolerance:
                    findings.append(dict(
                        group=parent["source"], source=child["source"],
                        kind=kind, clearance_ltrb=gaps,
                    ))
    return sorted(findings, key=lambda f: (f["group"], f["kind"], f["source"]))


def check_corpus_clearance(layout, include: str, tolerance: float = 0.1) -> list[dict]:
    """Validate selected painted boundaries and retain every evidence child ID.

    Missing frames/children are blocking, never vacuous success. Check all
    contained painted descendants of a selected boundary as well as its frozen
    evidence children, so moving an inner frame cannot conceal a new contact.
    Noncontained descendants not in the confirmed evidence are left alone; the
    independent semantic/canvas checks remain the compiler's responsibility.
    """
    repairs = [repair for repair in REPAIRS if repair.include == include]
    if not repairs:
        return []
    boxes = {box["source"]: box for box in layout.boxes}
    groups = {group["source"]: group for group in layout.groups}
    issues = []
    for repair in repairs:
        parent = groups.get(repair.group)
        if parent is None:
            issues.append(dict(code="boundary-clearance-missing-frame", group=repair.group))
            continue
        required = {(kind, key) for kind, keys in
                    (("card", repair.cards), ("group", repair.groups)) for key in keys}
        for kind, children in (("card", boxes), ("group", groups)):
            required.update((kind, key) for key, child in children.items()
                            if _descendant(child, parent) and _contained(child, parent, tolerance))
        for kind, key in sorted(required):
            child = (boxes if kind == "card" else groups).get(key)
            if child is None:
                issues.append(dict(code="boundary-clearance-missing-child",
                                   group=repair.group, source=key, kind=kind))
                continue
            gaps = stroke_clearance(parent, child)
            minimum = repair.inset - (_stroke(parent) + _stroke(child)) / 2
            if min(gaps) < minimum - tolerance:
                issues.append(dict(code="boundary-stroke-clearance",
                                   group=repair.group, source=key, kind=kind,
                                   clearance_ltrb=gaps, minimum=minimum))
    return issues
