"""Exact-source semantic wrapping. This helper never changes font sizes or artwork.

Pass the same raw Font.width/Font.wrap callbacks and physical column width in
measurement and drawing. width_budget is applied exactly once to every fit
check; pass the existing profile value (normally 1.12 regular / 1.25 bold where
already declared), not an already-divided width. Unknown include/source pairs
use the supplied legacy wrap callback unchanged at width / width_budget.

Scoped output preserves the existing space-join contract: joining nonempty
lines with one space equals joining the original whitespace-delimited words.
Explicit newlines remain hard paragraph boundaries, including blank lines.
An indivisible atom that does not fit raises CannotFit with its physical
required_width. Widen the real card/corridor and retry in BOTH passes; never
shrink the font or draw that atom beyond the column.

Advance measurements do not certify native glyph ink or actual raster QA.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Protocol

REGULAR_WIDTH_BUDGET = 1.12
BOLD_WIDTH_BUDGET = 1.25


class FontLike(Protocol):
    def width(self, text: str, size: float) -> float: ...
    def wrap(self, text: str, width: float, size: float) -> list[str]: ...


@dataclass(frozen=True)
class TypographyRepair:
    include: str
    source: str
    phrases: tuple[str, ...] = ()
    min_last_words: int = 2


# Explicit compiler source keys, not descendant/prefix matches. Phrases are
# short source-proven semantic units, never rewritten English sentences.
REPAIRS = (
    TypographyRepair('diagrams/static/ai/llm-wiki/llm-wiki-build-pipeline.html',
                     'root.0.3.0.1.2', ('search CLI', '유일한 consumer')),
    TypographyRepair('diagrams/static/ai/rag-02-chunking-strategies.html',
                     'root.0.1.0.2', ('수 있습니다.',)),
    TypographyRepair('diagrams/static/ai/rag-02-chunking-strategies.html',
                     'root.0.1.1.1.0', ('Section 1',)),
    TypographyRepair('diagrams/static/ai/rag-02-chunking-strategies.html',
                     'root.0.1.1.1.1', ('Section 2',)),
    TypographyRepair('diagrams/static/ai/rag-02-chunking-strategies.html',
                     'root.0.1.1.1.2', ('Section 3', '재귀 분할')),
    TypographyRepair('diagrams/static/aws/analytics-stack-05-query-flow.html',
                     'root.0.1.4.1.1', ('data files',)),
    TypographyRepair('diagrams/static/blockchain/bitcoin-mempool-reorg.html',
                     'root.0.3.1.1.0', ('branch를 앞섬',)),
    TypographyRepair('diagrams/static/blockchain/operator-health-ladder.html',
                     'root.0.1.4', ('peer와 별도',)),
    TypographyRepair('diagrams/static/blockchain/operator-health-ladder.html',
                     'root.0.1.6', ('보지 않음',)),
    TypographyRepair('diagrams/static/blockchain/reentrancy-cei.html',
                     'root.0.2.0.1.4', ('수 있음',)),
    TypographyRepair('diagrams/static/blockchain/reentrancy-cei.html',
                     'root.0.2.1.1.2', ('지급하지 않음',)),
    TypographyRepair('diagrams/static/blockchain/utxo-reference-structure.html',
                     'root.0.1.1', ('input으로 사용',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/argo-multi-cluster-architecture.html',
                     'root.0.1.1', ()),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/jenkins-pipeline.html',
                     'root.0.4', ('parallel test',)),
    TypographyRepair('diagrams/static/ci-cd/jenkins/jenkins-pipeline-layers.html',
                     'root.0.1.2.1.4', ('공통 코드',)),
    TypographyRepair('diagrams/static/javascript/javascript-data-type-model.html',
                     'root.0.3.0.3', ('수 있습니다.',)),
    TypographyRepair('diagrams/static/javascript/javascript-data-type-model.html',
                     'root.0.3.1.2', ('재할당만 막습니다.',)),
    TypographyRepair('diagrams/static/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.html',
                     'root.0.1.1.1', ()),
    TypographyRepair('diagrams/static/kubernetes/cilium/5w-bgp-control-plane-v2-architecture.html',
                     'root.0.2.1.3.2', ('ClusterIP route',)),
    TypographyRepair('diagrams/static/kubernetes/cilium/multi-pool.html',
                     'root.0.3.1', ('단정하지 않습니다.',)),
    TypographyRepair('diagrams/static/kubernetes/endpoint_vs_endpointslice.html',
                     'root.0.2.1.1.4.1', ('Pod-200 IP',)),
    TypographyRepair('diagrams/static/kubernetes/endpoint_vs_endpointslice.html',
                     'root.0.2.1.1.4.2', ('Pod-300 IP',)),
    TypographyRepair('diagrams/static/kubernetes/endpoint_vs_endpointslice.html',
                     'root.0.2.1.2', ()),
    TypographyRepair('diagrams/static/kubernetes/terminating-pod-troubleshooting.html',
                     'root.0.2.0.1', ('gate가 아님',)),
    TypographyRepair('diagrams/static/kubernetes/terminating-pod-troubleshooting.html',
                     'root.0.3.0', ('수 있음',)),
    TypographyRepair('diagrams/static/network/dns-recursive-resolution.html',
                     'root.0.4.1.1.0', ('referral 제공',)),
    TypographyRepair('diagrams/static/network/dns-recursive-resolution.html',
                     'root.0.4.1.1.1', ('TLD에 질의',)),
    TypographyRepair('diagrams/static/network/dns-recursive-resolution.html',
                     'root.0.4.1.1.2', ('server를 가리킴',)),
    TypographyRepair('diagrams/static/observability/datadog-rum-01-data-model.html',
                     'root.0.1.1', ('단위로 묶음',)),
    TypographyRepair('diagrams/static/sap-c02/asg-instance-lifecycle-hooks.html',
                     'root.0.1.6.0.1.6', ('즉시 종료',)),
    TypographyRepair('diagrams/static/sap-c02/aurora-global-switchover-failover.html',
                     'root.0.1.4.0.1.0', ('동기화 대기', '때만 수행')),
    TypographyRepair('diagrams/static/sap-c02/aws-backup-continuous-vs-snapshot.html',
                     'root.0.1.2.0.1.2', ('사본 불가',)),
    TypographyRepair('diagrams/static/sap-c02/aws-backup-continuous-vs-snapshot.html',
                     'root.0.1.2.1.1.2', ('표시 없음',)),
    TypographyRepair('diagrams/static/sap-c02/cloudfront-origin-failover-path.html',
                     'root.0.1.2.1.1.0', ('메서드가 아님',)),
    TypographyRepair('diagrams/static/sap-c02/cost-recommendation-sources.html',
                     'root.0.1.2.1.1.2', ('이상만 표시',)),
    TypographyRepair('diagrams/static/sap-c02/data-transfer-charge-points.html',
                     'root.0.1.2.0.1.0', ('GB 요금',)),
    TypographyRepair('diagrams/static/sap-c02/data-transfer-charge-points.html',
                     'root.0.1.2.4.1.2', ('전송은 과금',)),
    TypographyRepair('diagrams/static/sap-c02/directory-service-selection.html',
                     'root.0.1.0.3.0.1.0', ('extension 지원',)),
    TypographyRepair('diagrams/static/sap-c02/directory-service-selection.html',
                     'root.0.1.0.3.0.1.2', ('AD만 지원',)),
    TypographyRepair('diagrams/static/sap-c02/dms-schema-object-ownership.html',
                     'root.0.1.2.0.1.0', ('full load + CDC', 'CDC only')),
    TypographyRepair('diagrams/static/sap-c02/dr-verification-loop.html',
                     'root.0.2.1', ('병렬 준비',)),
    TypographyRepair('diagrams/static/sap-c02/eks-compute-option-split.html',
                     'root.0.2.2.1.1.0', ('에 넘긴다',)),
    TypographyRepair('diagrams/static/sap-c02/eks-compute-option-split.html',
                     'root.0.2.2.3.1.0', ('하드웨어에 둔다',)),
    TypographyRepair('diagrams/static/sap-c02/placement-group-boundaries.html',
                     'root.0.1.1.1.2.1', ('수 있다.',)),
    TypographyRepair('diagrams/static/sap-c02/ram-vpc-subnet-sharing.html',
                     'root.0.1.0.1.1', ('수 없다.',)),
    TypographyRepair('diagrams/static/sap-c02/rds-deployment-topologies.html',
                     'root.0.1.2.1.2.0', ('대상은 아니다.',)),
    TypographyRepair('diagrams/static/sap-c02/shared-storage-az-boundary.html',
                     'root.0.1.0.0.1.1', ('mapping 1개',)),
    TypographyRepair('diagrams/static/sap-c02/spot-interruption-signals.html',
                     'root.0.3.1.1.4', ('Terminate 불가',)),
    TypographyRepair('diagrams/static/sap-c02/sts-assume-role-cross-account.html',
                     'root.0.1.4.1.1', ('(기본 1시간)',)),
    TypographyRepair('diagrams/static/sap-c02/worm-retention-decision.html',
                     'root.0.3.0.2.1', ()),
    TypographyRepair('diagrams/static/spring/spring-24-authn-authz.html',
                     'root.0.1.1', ()),
    TypographyRepair('diagrams/static/virtualization/full-para-virtualization.html',
                     'root.0.2.1.1.0', ('guest OS',)),
    TypographyRepair('diagrams/static/blockchain/commitment-tag-compare.html',
                     'root.0.1.0.1', ('active block 수',)),
    TypographyRepair('diagrams/static/javascript/vite/vite-dev-server-on-demand-transform.html',
                     'root.0.1.1.1.1', ()),
    TypographyRepair('diagrams/static/kubernetes/horizontal-pod-autoscaling.html',
                     'root.0.1.3', ('current replicas x',)),
    TypographyRepair('diagrams/static/kubernetes/kubernetes-fqdn-resolution.html',
                     'root.0.1.1', ()),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.1', ('x + 1',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.2', ('x + 1',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.3', ('y + 1',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.4', ('y + 1',)),
    TypographyRepair('diagrams/static/sap-c02/s3-lifecycle-waterfall.html',
                     'root.0.1.0.1.0', ('128 KB',)),
    TypographyRepair('diagrams/static/sap-c02/s3-lifecycle-waterfall.html',
                     'root.0.1.0.1.4', ('128 KB',)),
    TypographyRepair('diagrams/static/sap-c02/storage-gateway-four-types.html',
                     'root.0.1.0.1.2', ('5 TiB',)),
    TypographyRepair('diagrams/static/spring/spring-10-mono-flux-backpressure.html',
                     'root.0.1.1.3', ()),
    TypographyRepair('diagrams/static/spring/spring-18-propagation.html',
                     'root.0.1.1.1.2', ()),
)
# Additional round2 repairs from the frozen real-source cases. Keep REPAIRS
# unchanged as the original 65-target/45-include contract; the existing EKS
# key receives an additive phrase, not a replacement of its earlier atoms.
ROUND2_REPAIRS = (
    TypographyRepair('diagrams/static/aws/analytics-stack-04-overview.html',
                     'root.0.1.4.0', ('S3 LOCATION 반환',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.0.1.0', ('source code를 관리',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.2.1.0.1.0', ('형상을 관리',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.2.1.0.1.4', ('image를 실행',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.2.1.1.1.2', ('Pod를 실행',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/argo-multi-cluster-architecture.html',
                     'root.0.2', ('갈라지는 대상입니다.',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/d-in-d_vs_d-out-d.html',
                     'root.0.1.1.2', ('통제가 필요합니다.',)),
    TypographyRepair('diagrams/static/ci-cd/ec2-jenkins-server-flow.html',
                     'root.0.1.2', ('executor를 할당',)),
    TypographyRepair('diagrams/static/go/goroutine-scheduling-model.html',
                     'root.0.2.3', ('work stealing',)),
    TypographyRepair('diagrams/static/go/goroutine-scheduling-model.html',
                     'root.0.2.7', ('병렬 실행',)),
    TypographyRepair('diagrams/static/jvm/jvm-02-stack-vs-heap.html',
                     'root.0.1.3', ('new Order()가', '가리키는 대상')),
    TypographyRepair('diagrams/static/jvm/jvm-10-jdk-version-gc-shift.html',
                     'root.0.1.0', ('줄어드는 관측',)),
    TypographyRepair('diagrams/static/kubernetes/cilium/cilium_l7_layer_policy.html',
                     'root.0.1.2.1.1.0.1.1', ('/v1/exhaust-port',)),
    TypographyRepair('diagrams/static/kubernetes/cilium/cluster_scope_ipam_mode.html',
                     'root.0.1.7', ('Pod IPs',)),
    TypographyRepair('diagrams/static/kubernetes/helm-hook-lifecycle.html',
                     'root.0.1.8', ('포함되지 않습니다.',)),
    TypographyRepair('diagrams/static/kubernetes/horizontal-pod-autoscaling.html',
                     'root.0.1.7', ('추가 또는 제거',)),
    TypographyRepair('diagrams/static/kubernetes/in-place-pod-resource-resize.html',
                     'root.0.2.0', ('limit을 제출합니다.',)),
    TypographyRepair('diagrams/static/kubernetes/in-place-pod-resource-resize.html',
                     'root.0.2.8', ('계속 실행됩니다.',)),
    TypographyRepair('diagrams/static/kubernetes/in-place-pod-resource-resize.html',
                     'root.0.3', ('RestartContainer가 필요합니다.',)),
    TypographyRepair('diagrams/static/network/route-selection-order.html',
                     'root.0.1.0.1.0', ('OSPF cost',)),
    TypographyRepair('diagrams/static/network/route-selection-order.html',
                     'root.0.1.0.1.4', ('처리도 반영',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.6', ('Both sides', 'data transfer', '시작 가능')),
    TypographyRepair('diagrams/static/observability/kibana-query-flow.html',
                     'root.0.1.3', ('Elasticsearch에',)),
    TypographyRepair('diagrams/static/observability/monitoring-observability-flow.html',
                     'root.0.1.4', ('세 가지 signal',)),
    TypographyRepair('diagrams/static/sap-c02/acm-certificate-issuance-paths.html',
                     'root.0.1.2.0.1.2', ('API Gateway', 'ACM 담당')),
    TypographyRepair('diagrams/static/sap-c02/acm-certificate-issuance-paths.html',
                     'root.0.1.2.1.1.2', ('사용자가 담당',)),
    TypographyRepair('diagrams/static/sap-c02/acm-certificate-issuance-paths.html',
                     'root.0.1.2.3.1.2', ('자체 배포',)),
    TypographyRepair('diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html',
                     'root.0.1.6.1.1.2.2', ('INSUFFICIENT_DATA',)),
    TypographyRepair('diagrams/static/sap-c02/dx-vif-reach-scope.html',
                     'root.0.2.4.2.1.0', ('MTU 1500 또는 8500',)),
    TypographyRepair('diagrams/static/sap-c02/eks-compute-option-split.html',
                     'root.0.2.2.1.1.0', ('AWS 에 넘긴다',)),
    TypographyRepair('diagrams/static/sap-c02/eks-compute-option-split.html',
                     'root.0.2.2.2.1.0', ('없어야 합니다.',)),
    TypographyRepair('diagrams/static/spring/spring-02-reading-order-map.html',
                     'root.0.1.0', ('bean 실행',)),
    TypographyRepair('diagrams/static/spring/spring-02-reading-order-map.html',
                     'root.0.1.8', ('빌드와 보안',)),
    TypographyRepair('diagrams/static/spring/spring-21-build-pipeline.html',
                     'root.0.1.0', ('Gradle 또는 Maven',)),
    TypographyRepair('diagrams/static/spring/spring-21-build-pipeline.html',
                     'root.0.1.8', ('archive에서 시작',)),
)
# Fresh round3 exact-source additions. Preserve the original declarations and
# algorithms; the TCP key adds its own-sequence clause alongside x + 1.
ROUND3_REPAIRS = (
    TypographyRepair('diagrams/packer-golden-image.html',
                     'root.0.1.1.4', ('머신 이미지',)),
    TypographyRepair('diagrams/packer-golden-image.html',
                     'root.0.1.1.1', ('임시 EC2 생성',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.0.1.1', ('build와 test',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html',
                     'root.0.1.2.1.1.1.0', ('Container Image',)),
    TypographyRepair('diagrams/static/jvm/jvm-02-stack-vs-heap.html',
                     'root.0.1.4', ('Order 객체',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.1', ('자신의 sequence를 보냄',)),
    TypographyRepair('diagrams/static/sap-c02/kinesis-efo-vs-shared-consumers.html',
                     'root.0.2.4.0.1.0', ('2 MB/s',)),
    TypographyRepair('diagrams/static/spring/spring-20-n-plus-1-fix.html',
                     'root.0.2', ('함께 점검합니다.',)),
)
ROUND4_REPAIRS = (
    TypographyRepair('diagrams/packer-golden-image.html',
                     'root.0.1.1.2', ('설정 저장',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/jenkins-ci-workflow.html',
                     'root.0.2.0.2.2', ('이미지 저장소',)),
    TypographyRepair('diagrams/static/ci-cd/ci-cd-study/kubernetes-gitops-loop.html',
                     'root.0.2.1.2.2', ('live state와 비교',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.4', ('ESTABLISHED로 이동',)),
    TypographyRepair('diagrams/static/observability/kibana-query-flow.html',
                     'root.0.1.6', ('검색 대상',)),
    TypographyRepair('diagrams/static/sap-c02/data-transfer-charge-points.html',
                     'root.0.1.2.3.1.2', ('전송 요금',)),
    TypographyRepair('diagrams/static/kubernetes/endpoint_vs_endpointslice.html',
                     'root.0.2.1.2', ('node metadata도',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.2', ('to client',)),
    TypographyRepair('diagrams/static/network/tcp-3-way-handshake.html',
                     'root.0.2.5', ('sequence 확인 완료',)),
)
_REPAIRS = {(r.include, r.source): r for r in REPAIRS}
for _repair in (*ROUND2_REPAIRS, *ROUND3_REPAIRS, *ROUND4_REPAIRS):
    _key = (_repair.include, _repair.source)
    _previous = _REPAIRS.get(_key)
    _REPAIRS[_key] = TypographyRepair(
        _repair.include, _repair.source,
        tuple(dict.fromkeys((*_previous.phrases, *_repair.phrases))) if _previous else _repair.phrases,
        max(_previous.min_last_words, _repair.min_last_words) if _previous else _repair.min_last_words,
    )
ALL_REPAIRS = tuple(_REPAIRS.values())


def typography_repair(include: str, source: str) -> TypographyRepair | None:
    """Exact lookup: no path normalization, ancestors or descendant opt-ins."""
    return _REPAIRS.get((include, source))


def corpus_typography_profile(include: str) -> dict[str, str]:
    """Merge before measure/draw; adds no font, size or geometry settings."""
    return {"typography_include": include} if any(r.include == include for r in ALL_REPAIRS) else {}


class CannotFit(ValueError):
    """A physical column change is required for an indivisible source atom."""
    def __init__(self, include: str, source: str, atom: str, width: float,
                 required_width: float, size: float, width_budget: float):
        self.include, self.source, self.atom = include, source, atom
        self.width, self.required_width = width, required_width
        self.size, self.width_budget = size, width_budget
        super().__init__(
            f"{include}:{source}: protected atom {atom!r} requires physical "
            f"width >= {required_width:.6f}px at size {size:g} with "
            f"budget {width_budget:g}; available {width:g}px. "
            "Widen the declared card/corridor in both measure and draw."
        )


# Apply this grammar only after an exact source opt-in. It preserves units
# with attached Korean particles/punctuation as part of the original word.
_NUMBER_UNIT = re.compile(
    r"(?<!\w)\d+(?:\.\d+)? +(?:[KMGTPE]?i?B|[km]?s|ms|Gbps)(?![A-Za-z0-9_])"
)


def _atoms(paragraph: str, repair: TypographyRepair) -> list[str]:
    paragraph = " ".join(paragraph.split())
    words = list(re.finditer(r"\S+", paragraph))
    if not words:
        return []
    spans = [match.span() for match in _NUMBER_UNIT.finditer(paragraph)]
    for phrase in repair.phrases:
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?![A-Za-z0-9_])"
        spans.extend(match.span() for match in re.finditer(pattern, paragraph))
    atoms, start = [], 0
    for i in range(1, len(words)):
        boundary = words[i].start()
        if any(left < boundary < right for left, right in spans):
            continue
        atoms.append(" ".join(word.group() for word in words[start:i]))
        start = i
    atoms.append(" ".join(word.group() for word in words[start:]))
    return atoms


def wrap_text(text: str, width: float, size: float, *, include: str,
              source: str, font: FontLike | None = None,
              measure: Callable[[str, float], float] | None = None,
              wrap: Callable[[str, float, float], list[str]] | None = None,
              width_budget: float = 1.0) -> list[str]:
    """Wrap only declared sources; callbacks consume raw, unbudgeted advances.

    The font object is optional when both callbacks are supplied. No implicit
    budget defaults override the existing per-include compiler profile.
    """
    for name, value in (("width", width), ("size", size), ("width_budget", width_budget)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    measure = measure if measure is not None else getattr(font, "width", None)
    wrap = wrap if wrap is not None else getattr(font, "wrap", None)
    repair = typography_repair(include, source)
    if repair is None:
        if wrap is None:
            raise ValueError("unscoped text requires a legacy wrap callback or font")
        return wrap(text, width / width_budget, size)
    if measure is None:
        raise ValueError("scoped text requires a raw measure callback or font")
    widths = {}

    def physical_width(value: str) -> float:
        if value not in widths:
            measured = measure(value, size) * width_budget
            if not math.isfinite(measured) or measured < 0:
                raise ValueError("measure must return a finite nonnegative width")
            widths[value] = measured
        return widths[value]

    result = []
    for paragraph in text.split("\n"):
        atoms = _atoms(paragraph, repair)
        if not atoms:
            result.append("")
            continue
        lines, line = [], []
        for atom in atoms:
            required = physical_width(atom)
            if required > width:
                raise CannotFit(include, source, atom, width, required, size, width_budget)
            candidate = " ".join(line + [atom])
            if line and physical_width(candidate) > width:
                lines.append(line)
                line = []
            line.append(atom)
        lines.append(line)
        if len(lines) >= 2 and len(" ".join(lines[-1]).split()) < repair.min_last_words:
            tail = lines[-2] + lines[-1]
            choices = []
            for split in range(1, len(tail)):
                left, right = tail[:split], tail[split:]
                if len(" ".join(right).split()) < repair.min_last_words:
                    continue
                left_width = physical_width(" ".join(left))
                right_width = physical_width(" ".join(right))
                if max(left_width, right_width) <= width:
                    choices.append((abs(left_width - right_width), split, left, right))
            if choices:
                _, _, lines[-2], lines[-1] = min(choices)
        result.extend(" ".join(parts) for parts in lines)
    return result or [""]
