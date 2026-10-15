"""Semantic wrapping regressions; no source, artwork or native pixels are written."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fhd_svg as compiler
from corpus_typography import ALL_REPAIRS, REPAIRS, ROUND2_REPAIRS

ROOT = Path(__file__).resolve().parents[3]
LIFECYCLE = "diagrams/static/sap-c02/s3-lifecycle-waterfall.html"
STANDARD_IA = "root.0.1.0.1.4"


@pytest.fixture(scope="module")
def font():
    return compiler.Font(ROOT / compiler.FONT)


def test_minimum_billable_numeric_unit_is_kept_on_one_line(font):
    text = "최소 30일, 최소 과금 128 KB"
    width = font.width("최소 30일, 최소 과금 128", 22) + 0.01
    baseline = font.wrap(text, width, 22)
    assert baseline[-1] == "KB"  # Prove the actual compiler failure first.
    from corpus_typography import wrap_text
    lines = wrap_text(text, width, 22, include=LIFECYCLE,
                      source=STANDARD_IA, font=font)
    assert any("128 KB" in line for line in lines), lines
    assert " ".join(lines) == text


def test_last_two_lines_rebalance_instead_of_leaving_a_word_widow():
    from corpus_typography import wrap_text
    lines = wrap_text("one two three four", 13, 22,
                      include=LIFECYCLE, source=STANDARD_IA,
                      measure=lambda text, size: len(text))
    assert lines == ["one two", "three four"]
    assert " ".join(lines) == "one two three four"


@pytest.mark.parametrize("include,source,text,phrase,width", [
    ("diagrams/static/sap-c02/storage-gateway-four-types.html", "root.0.1.0.1.2",
     "file share 하나가 버킷 하나, 파일 최대 5 TiB", "5 TiB", 29),
    ("diagrams/static/network/tcp-3-way-handshake.html", "root.0.2.1",
     "server가 x + 1을 확인하고 자신의 sequence를 보냄", "x + 1을", 12),
    ("diagrams/static/network/tcp-3-way-handshake.html", "root.0.2.3",
     "client가 y + 1을 ACK", "y + 1을", 11),
    ("diagrams/static/sap-c02/dms-schema-object-ownership.html", "root.0.1.2.0.1.0",
     "full load, full load + CDC, CDC only", "CDC only", 17),
    ("diagrams/static/ai/rag-02-chunking-strategies.html", "root.0.1.1.1.2",
     "Section 3", "Section 3", 8),
])
def test_declared_units_operators_quantifiers_and_names_are_atomic(
        include, source, text, phrase, width):
    from corpus_typography import wrap_text, CannotFit
    if len(phrase) > width:
        with pytest.raises(CannotFit):
            wrap_text(text, width, 22, include=include, source=source,
                      measure=lambda value, size: len(value))
    else:
        if include == "diagrams/static/network/tcp-3-way-handshake.html" and source == "root.0.2.1":
            # The fresh own-sequence clause is also indivisible. Preserve the
            # original 12-unit failure and retry only at its explicit width.
            with pytest.raises(CannotFit) as exc:
                wrap_text(text, width, 22, include=include, source=source,
                          measure=lambda value, size: len(value))
            assert exc.value.atom == "자신의 sequence를 보냄"
            assert exc.value.required_width == len(exc.value.atom)
            width = exc.value.required_width
        lines = wrap_text(text, width, 22, include=include, source=source,
                          measure=lambda value, size: len(value))
        assert any(phrase in line for line in lines), lines
        assert " ".join(lines) == text
        assert all(len(line) <= width for line in lines)


@pytest.mark.parametrize("include,source,token", [
    ("diagrams/static/spring/spring-18-propagation.html", "root.0.1.1.1.2", "(REQUIRES_NEW)"),
    ("diagrams/static/spring/spring-10-mono-flux-backpressure.html", "root.0.1.1.3", "downstream으로"),
    ("diagrams/static/kubernetes/horizontal-pod-autoscaling.html", "root.0.1.3", "current/target"),
    ("diagrams/static/spring/spring-24-authn-authz.html", "root.0.1.1", "SecurityContext의"),
    ("diagrams/static/ci-cd/ci-cd-study/argo-multi-cluster-architecture.html", "root.0.1.1", "자격증명으로"),
    ("diagrams/static/javascript/vite/vite-dev-server-on-demand-transform.html", "root.0.1.1.1.1", "dependency만"),
    ("diagrams/static/kubernetes/kubernetes-fqdn-resolution.html", "root.0.1.1", "web-service.apps.svc.cluster.local"),
    ("diagrams/static/sap-c02/worm-retention-decision.html", "root.0.3.0.2.1", "s3:BypassGovernanceRetention과"),
])
def test_technical_identifiers_and_attached_particles_fail_instead_of_fragmenting(
        font, include, source, token):
    from corpus_typography import CannotFit, wrap_text
    budget = 1.25
    required = font.width(token, 28) * budget
    with pytest.raises(CannotFit) as exc:
        wrap_text(token, required - 0.01, 28, include=include, source=source,
                  font=font, width_budget=budget)
    assert exc.value.atom == token
    assert exc.value.required_width == pytest.approx(required)
    assert exc.value.source == source
    assert exc.value.include == include
    assert "Widen" in str(exc.value)
    # Explicit, caller-owned physical width fallback. The helper never widens
    # a column silently and never retries at a smaller font.
    assert wrap_text(token, required + 0.01, 28, include=include, source=source,
                     font=font, width_budget=budget) == [token]


def source(include):
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    return next(e for e in compiler.Parse(original).root.descendants()
                if e.tag == "figure" and "sd" in e.classes)


def test_exact_source_scope_is_frozen():
    import hashlib
    pairs = [(r.include, r.source) for r in REPAIRS]
    assert len(pairs) == len(set(pairs)) == 65
    assert len({include for include, _ in pairs}) == 45
    assert hashlib.sha256("\n".join(i + "|" + s for i, s in pairs).encode()).hexdigest() == 'eb27d1484d4b23d12cf023f184ef47ad31c299249954823139b783163f1d67d0'


@pytest.mark.parametrize("repair", ALL_REPAIRS, ids=lambda r: r.include + ":" + r.source)
def test_every_declared_source_and_phrase_still_exists(repair):
    figure = source(repair.include)
    elements = {e.key: e for e in [figure, *figure.descendants()]}
    assert repair.source in elements
    element = elements[repair.source]
    assert compiler.Layout(None, 28, 22).kind(element) in {"node", "edge", "text"}
    for phrase in repair.phrases:
        assert phrase in element.text(), (repair.include, repair.source, phrase)
        assert len(phrase.split()) <= 4  # No entire prose paragraphs as atoms.


@pytest.mark.parametrize("include,key", [
    ("_includes/" + LIFECYCLE, STANDARD_IA),
    ("/" + LIFECYCLE, STANDARD_IA),
    (LIFECYCLE.upper(), STANDARD_IA),
    (LIFECYCLE, "root.0.1.0.1"),
    (LIFECYCLE, STANDARD_IA + ".0"),
    (LIFECYCLE, STANDARD_IA + " "),
    (LIFECYCLE, "root.0.1.0.1.40"),
    ("diagrams/static/unknown.html", STANDARD_IA),
])
def test_unknown_or_malformed_identifiers_delegate_without_normalization(include, key):
    from corpus_typography import typography_repair, wrap_text
    calls = []
    sentinel = ["legacy result"]

    def legacy(text, width, size):
        calls.append((text, width, size))
        return sentinel

    assert typography_repair(include, key) is None
    assert wrap_text("unaltered\ninput", 112, 22, include=include, source=key,
                     wrap=legacy, width_budget=1.12) is sentinel
    assert calls == [("unaltered\ninput", 112 / 1.12, 22)]


def test_profile_adds_only_an_exact_include_marker_and_is_copy_isolated():
    from corpus_typography import corpus_typography_profile
    first = corpus_typography_profile(LIFECYCLE)
    assert first == {"typography_include": LIFECYCLE}
    first["typography_include"] = "broken"
    assert corpus_typography_profile(LIFECYCLE) == {"typography_include": LIFECYCLE}
    assert corpus_typography_profile("_includes/" + LIFECYCLE) == {}
    assert corpus_typography_profile("diagrams/static/unknown.html") == {}


@pytest.mark.parametrize("budget", [1.0, 1.12, 1.25])
def test_rebalance_preserves_the_same_physical_width_budget(budget):
    from corpus_typography import wrap_text
    measured_sizes = []

    def measure(value, size):
        measured_sizes.append(size)
        return len(value)

    lines = wrap_text("one two three four", 13 * budget, 22,
                      include=LIFECYCLE, source=STANDARD_IA,
                      measure=measure, width_budget=budget)
    assert lines == ["one two", "three four"]
    assert all(len(line) * budget <= 13 * budget for line in lines)
    assert set(measured_sizes) == {22}


def test_rebalance_changes_only_the_last_two_lines():
    from corpus_typography import wrap_text
    lines = wrap_text("zero zero zero one two three four", 13, 22,
                      include=LIFECYCLE, source=STANDARD_IA,
                      measure=lambda value, size: len(value))
    assert lines == ["zero zero", "zero one two", "three four"]
    assert " ".join(lines) == "zero zero zero one two three four"


def test_unavoidable_single_word_line_remains_honest_not_oversize():
    from corpus_typography import wrap_text
    assert wrap_text("alpha beta", 5, 22, include=LIFECYCLE, source=STANDARD_IA,
                     measure=lambda value, size: len(value)) == ["alpha", "beta"]


def test_hard_paragraph_breaks_and_blank_lines_are_preserved():
    from corpus_typography import wrap_text
    text = "  not  only\t128 KB  \n\nno generation\n"
    lines = wrap_text(text, 11, 22, include=LIFECYCLE, source=STANDARD_IA,
                      measure=lambda value, size: len(value))
    assert lines == ["not only", "128 KB", "", "no", "generation", ""]
    assert " ".join(line for line in lines if line) == " ".join(text.split())
    assert wrap_text("", 11, 22, include=LIFECYCLE, source=STANDARD_IA,
                     measure=lambda value, size: len(value)) == [""]


def test_numeric_unit_with_particle_and_punctuation_is_atomic():
    from corpus_typography import CannotFit, wrap_text
    with pytest.raises(CannotFit) as exc:
        wrap_text("최소 128 KB까지, 유지", 8, 22,
                  include=LIFECYCLE, source=STANDARD_IA,
                  measure=lambda value, size: len(value))
    assert exc.value.atom == "128 KB까지,"


def test_phrase_matching_does_not_confuse_section_three_with_thirty():
    from corpus_typography import wrap_text
    include = "diagrams/static/ai/rag-02-chunking-strategies.html"
    lines = wrap_text("Section 30", 8, 22, include=include, source="root.0.1.1.1.2",
                      measure=lambda value, size: len(value))
    assert lines == ["Section", "30"]


@pytest.mark.parametrize("argument,value", [
    ("width", 0), ("width", -1), ("width", float("nan")),
    ("size", 0), ("size", float("inf")),
    ("width_budget", 0), ("width_budget", float("nan")),
])
def test_invalid_dimensions_fail_before_wrapping(argument, value):
    from corpus_typography import wrap_text
    kwargs = dict(width=100, size=22, width_budget=1.12)
    kwargs[argument] = value
    with pytest.raises(ValueError, match=argument):
        wrap_text("text", kwargs["width"], kwargs["size"],
                  width_budget=kwargs["width_budget"],
                  include=LIFECYCLE, source=STANDARD_IA,
                  measure=lambda text, size: len(text))


@pytest.mark.parametrize("measured", [float("nan"), float("inf"), -1])
def test_invalid_measurements_never_produce_an_overflow_line(measured):
    from corpus_typography import wrap_text
    with pytest.raises(ValueError, match="finite nonnegative"):
        wrap_text("text", 100, 22, include=LIFECYCLE, source=STANDARD_IA,
                  measure=lambda text, size: measured)


def test_measurement_and_legacy_callbacks_are_required_only_for_their_own_path():
    from corpus_typography import wrap_text
    with pytest.raises(ValueError, match="raw measure"):
        wrap_text("text", 100, 22, include=LIFECYCLE, source=STANDARD_IA)
    with pytest.raises(ValueError, match="legacy wrap"):
        wrap_text("text", 100, 22, include="unknown", source=STANDARD_IA)


def test_compiler_measure_and_draw_use_the_scoped_wrap_policy(font):
    # Intentionally RED until the parent integrates the helper into every
    # Layout.wrap call site with the same include/key/budget in both passes.
    from corpus_typography import corpus_typography_profile, wrap_text
    figure = source(LIFECYCLE)
    element = next(e for e in figure.descendants() if e.key == STANDARD_IA)
    profile = {"regular_width_budget": 1.12, "bold_width_budget": 1.25,
               **corpus_typography_profile(LIFECYCLE)}
    layout = compiler.Layout(font, 28, 22, padding=24, profile=profile)
    text_width = (font.width("최소 30일, 최소 과금 128", 22) + 0.01) * 1.12
    width = text_width + 48
    expected = wrap_text("최소 30일, 최소 과금 128 KB", text_width, 22,
                         include=LIFECYCLE, source=STANDARD_IA, font=font,
                         width_budget=1.12)
    head, detail = layout.lines(element, width)
    assert detail == expected
    height = 48 + len(head) * 28 * 1.3 + len(expected) * 22 * 1.35 + 12
    assert layout.measure(element, width) == pytest.approx(height)
    layout.draw(element, 64, 64, width)
    emitted = [t["text"] for t in layout.texts
               if t["source"] == STANDARD_IA and not t["label"]]
    assert emitted == expected


@pytest.mark.parametrize("repair", ALL_REPAIRS, ids=lambda r: r.include + ":" + r.source)
def test_actual_source_text_sweep_preserves_content_atoms_and_budget(font, repair):
    from corpus_typography import CannotFit, wrap_text
    figure = source(repair.include)
    element = next(e for e in figure.descendants() if e.key == repair.source)
    legacy = compiler.Layout(font, 28, 22)
    head, detail = legacy.lines(element, 1000000)
    label = legacy.kind(element) == "node" or bool(element.classes & compiler.HEAD_CLASSES)
    runs = [(" ".join(head), 28 if label else 22, 1.25 if label else 1.12)]
    if detail:
        runs.append((" ".join(detail), 22, 1.12))
    for text, size, budget in runs:
        for width in (60, 96, 144, 200, 276, 400, 600):
            try:
                lines = wrap_text(text, width, size, include=repair.include,
                                  source=repair.source, font=font, width_budget=budget)
            except CannotFit as exc:
                assert exc.required_width > width
                assert exc.required_width == pytest.approx(font.width(exc.atom, size) * budget)
                assert exc.atom in text
                continue
            assert " ".join(lines) == " ".join(text.split())
            assert all(font.width(line, size) * budget <= width for line in lines)
            # Deterministic equal inputs are the contract for measure and draw.
            assert wrap_text(text, width, size, include=repair.include,
                             source=repair.source, measure=font.width,
                             wrap=font.wrap, width_budget=budget) == lines
            for phrase in repair.phrases:
                if phrase in text:
                    assert any(phrase in line for line in lines), (text, phrase, lines)


# Round2 pixel findings, frozen at exact include/source and source_fragment SHA.
# Widths/sizes/budgets and baseline lines are real parent Layout observations.
ROUND2_SOURCES = {
    30: ('diagrams/static/aws/analytics-stack-04-overview.html', '727bb1154c2bf766d390e87d4d9fa3256c6a0db6c0678d9dbbea0cb807647df3'),
    96: ('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html', '18d5af48faecbdfcc99dea6d504e3239bc862da05dbe15bacffabdaba79893cb'),
    98: ('diagrams/static/ci-cd/ci-cd-study/argo-multi-cluster-architecture.html', '23e8d11a2f18cc35bd0849cc5a65f499ed2fddefd5f9070af623d2ab632ffe44'),
    106: ('diagrams/static/ci-cd/ci-cd-study/d-in-d_vs_d-out-d.html', '4d295af2736b510030828690060f4413b0171a882d0982f16f23f2d25589cca9'),
    131: ('diagrams/static/ci-cd/ec2-jenkins-server-flow.html', 'ff62e2b7d5a22725af54c82e724183d6a4f4b3c61a5341c8024b2ed79ffb8170'),
    148: ('diagrams/static/go/goroutine-scheduling-model.html', '4a6d23b2382bab7894589cceb991dc1bacee4473c1563cc976042133785f4ad6'),
    156: ('diagrams/static/jvm/jvm-02-stack-vs-heap.html', '1a277e1ecb5f3a6ca77c59bb183534f0433186aa892667a44a9e6d906b9fc3d4'),
    164: ('diagrams/static/jvm/jvm-10-jdk-version-gc-shift.html', '775c50132acc1b1e4d8a9ad7021a16a6fa2a6f544df1bd6dbbf4e16d97f80967'),
    188: ('diagrams/static/kubernetes/cilium/cilium_l7_layer_policy.html', '77d11d57c5c9d378ccd7ecd135ad316ea5ed8f97e06190d5b384cb0ef4f5522b'),
    190: ('diagrams/static/kubernetes/cilium/cluster_scope_ipam_mode.html', '0d52cd58f3d48228341e4200f809551c0a45040d12dfff7753f3509b182a83a5'),
    214: ('diagrams/static/kubernetes/helm-hook-lifecycle.html', '3426735afb51e0ac771925d63dd93aed5172e3fe2564335b636295c5b589aef0'),
    215: ('diagrams/static/kubernetes/horizontal-pod-autoscaling.html', '7702d771f180aa6cc8499b3aff9cce38cbe337011b34e13c08fc9b292e163f0f'),
    217: ('diagrams/static/kubernetes/in-place-pod-resource-resize.html', '6646d7502d388037c2a198e225993667c7c4ec85157c046df1689074ec551b2d'),
    243: ('diagrams/static/network/route-selection-order.html', '336c3fd06a418e5ae8df89b83e6684948a2579d974fac90a6c3f7305d5eb4059'),
    245: ('diagrams/static/network/tcp-3-way-handshake.html', '7d209360182d4ac16bd773a529d36638ff2f82d8a1f1a1fff846527ec8d9c315'),
    257: ('diagrams/static/observability/kibana-query-flow.html', 'caed263f79a867653c96ef1040436c896487185e8d80ac58b2ea2a88b57b8bd3'),
    260: ('diagrams/static/observability/monitoring-observability-flow.html', 'ccbf624968663a6a330aa87809a3e01792e8c381a8618316b84215b5d35f70bd'),
    276: ('diagrams/static/sap-c02/acm-certificate-issuance-paths.html', '48df1ad027701730b4ea02e2bbf01be39c0dc4f278cceb9ebeb5d7147de8f68c'),
    283: ('diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html', 'e6e097213b34181bc7fc9e77794dc07a97ce59ab3fc54512413455347c29754a'),
    300: ('diagrams/static/sap-c02/dx-vif-reach-scope.html', 'a9099b8c28412e0dcf86b40b62e8cb910118728e9e1d545b6d1fdaf1f2804fc2'),
    305: ('diagrams/static/sap-c02/eks-compute-option-split.html', '37d535c869969632802c753c1bdff345cb0ff20cce3f60ece3fc0888c96fce48'),
    364: ('diagrams/static/spring/spring-02-reading-order-map.html', '9eb31370001a2cf22030ccfa02d7d620866e73c2181a0418d68bf449361b9623'),
    383: ('diagrams/static/spring/spring-21-build-pipeline.html', 'db5bb7a98ff874a036853069531d5420470952ae0a4f3acfc4b3e1b3f3fa33e7'),
}
ROUND2_CASES = (
    (30, 'root.0.1.4.0', '엔진에 schema와 S3 LOCATION 반환', ('S3 LOCATION 반환',), 312.0, 22, 1, False, ('엔진에 schema와 S3 LOCATION', '반환')),
    (96, 'root.0.1.0.1.0', '애플리케이션 source code를 관리', ('source code를 관리',), 244.0, 18, 1.12, False, ('애플리케이션 source code를', '관리')),
    (96, 'root.0.1.2.1.0.1.0', 'Kubernetes Manifest와 배포 형상을 관리', ('형상을 관리',), 308.0, 18, 1.12, False, ('Kubernetes Manifest와 배포 형상을', '관리')),
    (96, 'root.0.1.2.1.0.1.4', 'Manifest를 적용하고 실제 image를 실행', ('image를 실행',), 308.0, 18, 1.12, False, ('Manifest를 적용하고 실제 image를', '실행')),
    (96, 'root.0.1.2.1.1.1.2', 'Registry에서 image를 가져와 Pod를 실행', ('Pod를 실행',), 308.0, 18, 1.12, False, ('Registry에서 image를 가져와 Pod를', '실행')),
    (98, 'root.0.2', 'kind-mgmt의 Argo CD에 대상 Cluster credential을 등록한 뒤, 각 Application의 destination을 kind-prd 또는 kind-dev로 지정합니다. 두 경로는 순서가 아니라 중앙 관리에서 갈라지는 대상입니다.', ('갈라지는 대상입니다.',), 1792, 20, 1.12, False, ('kind-mgmt의 Argo CD에 대상 Cluster credential을 등록한 뒤, 각 Application의 destination을 kind-prd 또는 kind-dev로 지정합니다. 두 경로는 순서가 아니라 중앙 관리에서 갈라지는', '대상입니다.')),
    (106, 'root.0.1.1.2', '중첩 daemon은 없지만 socket 접근이 호스트 Docker 권한으로 이어지므로 접근 통제가 필요합니다.', ('통제가 필요합니다.',), 846.0, 20, 1.12, False, ('중첩 daemon은 없지만 socket 접근이 호스트 Docker 권한으로 이어지므로 접근 통제가', '필요합니다.')),
    (131, 'root.0.1.2', 'controller가 queue를 관리하고 executor를 할당', ('executor를 할당',), 432.0, 22, 1, False, ('controller가 queue를 관리하고 executor를', '할당')),
    (148, 'root.0.2.3', 'G, M, P와 work stealing', ('work stealing',), 155.194, 22, 1, False, ('G, M, P와 work', 'stealing')),
    (148, 'root.0.2.7', 'GOMAXPROCS 범위 안에서 병렬 실행', ('병렬 실행',), 155.194, 22, 1, False, ('GOMAXPROCS', '범위 안에서 병렬', '실행')),
    (156, 'root.0.1.3', 'new Order()가 가리키는 대상', ('new Order()가', '가리키는 대상'), 136, 22, 1.12, False, ('new', 'Order()가', '가리키는', '대상')),
    (164, 'root.0.1.0', '같은 workload에서 collection 시간이 줄어드는 관측', ('줄어드는 관측',), 432.0, 22, 1, False, ('같은 workload에서 collection 시간이 줄어드는', '관측')),
    (188, 'root.0.1.2.1.1.0.1.1', 'HTTP PUT /v1/exhaust-port', ('/v1/exhaust-port',), 145.5, 20, 1.12, False, ('HTTP PUT', '/v1/exhaust-', 'port')),
    (190, 'root.0.1.7', 'allocate Pod IPs', ('Pod IPs',), 144.94112, 22, 1.12, False, ('allocate Pod', 'IPs')),
    (214, 'root.0.1.8', 'hook resource는 release resource에 포함되지 않습니다.', ('포함되지 않습니다.',), 432.0, 22, 1, False, ('hook resource는 release resource에 포함되지', '않습니다.')),
    (215, 'root.0.1.7', 'replica 추가 또는 제거', ('추가 또는 제거',), 136, 18, 1, False, ('replica 추가 또는', '제거')),
    (217, 'root.0.2.0', 'resize subresource에 새 request와 limit을 제출합니다.', ('limit을 제출합니다.',), 429.71999999999997, 22, 1, False, ('resize subresource에 새 request와 limit을', '제출합니다.')),
    (217, 'root.0.2.8', '같은 Pod 이름, node, IP에서 container가 계속 실행됩니다.', ('계속 실행됩니다.',), 429.71999999999997, 22, 1, False, ('같은 Pod 이름, node, IP에서 container가 계속', '실행됩니다.')),
    (217, 'root.0.3', 'RestartContainer 정책이면 container를 재시작해 적용하되 Pod는 재생성하지 않습니다. v1.33에서 memory limit 감소에는 memory의 resizePolicy[*].restartPolicy: RestartContainer가 필요합니다.', ('RestartContainer가 필요합니다.',), 1792, 22, 1, False, ('RestartContainer 정책이면 container를 재시작해 적용하되 Pod는 재생성하지 않습니다. v1.33에서 memory limit 감소에는 memory의 resizePolicy[*].restartPolicy: RestartContainer가', '필요합니다.')),
    (243, 'root.0.1.0.1.0', '같은 protocol 안의 후보 비교: RIP hop 수, OSPF cost', ('OSPF cost',), 266.0, 22, 1.12, False, ('같은 protocol 안의 후보', '비교: RIP hop 수, OSPF', 'cost')),
    (243, 'root.0.1.0.1.4', 'prefix별 next hop을 설치하며 동등 경로 처리도 반영', ('처리도 반영',), 266.0, 22, 1.12, False, ('prefix별 next hop을', '설치하며 동등 경로 처리도', '반영')),
    (245, 'root.0.2.6', '양방향 data transfer 시작 가능', ('Both sides', 'data transfer', '시작 가능'), 276.0, 22, 1, False, ('양방향 data transfer 시작', '가능')),
    (257, 'root.0.1.3', 'Elasticsearch에 query 전송', ('Elasticsearch에',), 143.02800000000002, 22, 1, False, ('Elasticsearch', '에 query 전송')),
    (260, 'root.0.1.4', 'alert에 미리 쓰지 않은 질문을 위한 세 가지 signal', ('세 가지 signal',), 432.0, 22, 1, False, ('alert에 미리 쓰지 않은 질문을 위한 세 가지', 'signal')),
    (276, 'root.0.1.2.0.1.2', 'CloudFront는 us-east-1 인증서 필요, 갱신과 재바인딩은 ACM 담당', ('API Gateway', 'ACM 담당'), 267.0, 20, 1, False, ('CloudFront는 us-east-1 인증서', '필요, 갱신과 재바인딩은 ACM', '담당')),
    (276, 'root.0.1.2.1.1.2', 'passphrase로 암호화된 key를 export하고 재배포는 사용자가 담당', ('사용자가 담당',), 267.0, 20, 1, False, ('passphrase로 암호화된 key를', 'export하고 재배포는 사용자가', '담당')),
    (276, 'root.0.1.2.3.1.2', '사설 인증서를 export해 자체 배포', ('자체 배포',), 267.0, 20, 1, False, ('사설 인증서를 export해 자체', '배포')),
    (283, 'root.0.1.6.1.1.2.2', 'INSUFFICIENT_DATA', ('INSUFFICIENT_DATA',), 213.33333333333334, 22, 1.25, True, ('INSUFFICIENT_', 'DATA')),
    (300, 'root.0.2.4.2.1.0', 'dedicated당 4개, MTU 1500 또는 8500', ('MTU 1500 또는 8500',), 201.33333333333334, 14, 1, False, ('dedicated당 4개, MTU 1500 또는', '8500')),
    (305, 'root.0.2.2.1.1.0', '노드 운영을 AWS 에 넘긴다', ('AWS 에 넘긴다',), 201.33333333333334, 16, 1.25, True, ('노드 운영을 AWS', '에 넘긴다')),
    (305, 'root.0.2.2.2.1.0', 'DaemonSet과 privileged container가 필요 없어야 합니다.', ('없어야 합니다.',), 201.33333333333334, 14, 1.12, False, ('DaemonSet과 privileged', 'container가 필요 없어야', '합니다.')),
    (364, 'root.0.1.0', 'HTTP 도착, container dispatch, bean 실행', ('bean 실행',), 432.0, 22, 1.12, False, ('HTTP 도착, container dispatch, bean', '실행')),
    (364, 'root.0.1.8', 'Series 5 (optional): 빌드와 보안', ('빌드와 보안',), 432.0, 28, 1.25, True, ('Series 5 (optional): 빌드와', '보안')),
    (383, 'root.0.1.0', 'src/main/java와 build file, Gradle 또는 Maven', ('Gradle 또는 Maven',), 432.0, 22, 1.12, False, ('src/main/java와 build file, Gradle 또는', 'Maven')),
    (383, 'root.0.1.8', '앱과 모든 의존성을 하나의 archive에서 시작', ('archive에서 시작',), 432.0, 22, 1.12, False, ('앱과 모든 의존성을 하나의 archive에서', '시작')),
)


@pytest.mark.parametrize("case", ROUND2_CASES, ids=lambda c: f"round2-{c[0]}:{c[1]}")
def test_round2_exact_real_wrap_repair_or_explicit_width_blocker(font, monkeypatch, case):
    import hashlib
    from corpus_typography import CannotFit, wrap_text
    index, key, text, phrases, width, size, budget, label, baseline_lines = case
    include, source_hash = ROUND2_SOURCES[index]
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    assert hashlib.sha256(original.encode()).hexdigest() == source_hash
    figure = source(include)
    element = next(e for e in figure.descendants() if e.key == key)
    head, detail = compiler.Layout(font, 28, 22).lines(element, 1000000)
    actual_parts = [" ".join(head)] + ([" ".join(detail)] if detail else [])
    assert text in actual_parts  # Never manufacture a prose run from a whole node.
    import corpus_typography as policy
    with monkeypatch.context() as legacy:
        legacy.setattr(policy, "_REPAIRS", {(r.include, r.source): r for r in REPAIRS})
        assert tuple(wrap_text(text, width, size, include=include, source=key,
                               font=font, width_budget=budget)) == baseline_lines
    present = [phrase for phrase in phrases if phrase in text]
    assert present
    required = max(font.width(phrase, size) * budget for phrase in present)
    if required > width:
        with pytest.raises(CannotFit) as exc:
            wrap_text(text, width, size, include=include, source=key,
                      font=font, width_budget=budget)
        assert exc.value.atom in text
        assert exc.value.required_width == pytest.approx(font.width(exc.value.atom, size) * budget)
        assert exc.value.width == width
        width = exc.value.required_width + 0.01  # Explicit caller-owned fallback only.
    lines = wrap_text(text, width, size, include=include, source=key,
                      font=font, width_budget=budget)
    assert " ".join(lines) == " ".join(text.split())
    assert all(font.width(line, size) * budget <= width for line in lines)
    for phrase in present:
        assert any(phrase in line for line in lines), (include, key, phrase, lines)
    assert (len(lines) == 1 or len(lines[-1].split()) >= 2
            or lines[-1] in [p for p in present if len(p.split()) == 1])


def test_round2_repair_sources_and_phrases_are_exact_and_bounded():
    from corpus_typography import typography_repair
    for index, key, text, phrases, *_ in ROUND2_CASES:
        include, _ = ROUND2_SOURCES[index]
        repair = typography_repair(include, key)
        assert repair is not None
        assert repair.min_last_words == 2
        element = next(e for e in source(include).descendants() if e.key == key)
        assert compiler.Layout(None, 28, 22).kind(element) in {"node", "edge", "text"}
        for phrase in phrases:
            assert phrase in element.text()
            assert phrase in repair.phrases
            assert len(phrase.split()) <= 4
        assert typography_repair(include, key + ".999") is None


def test_round2_scoped_unicode_is_not_nfkc_rewritten(font):
    from corpus_typography import wrap_text
    include, _ = ROUND2_SOURCES[30]
    text = "ＡＷＳ ① e\u0301 ＫＢ 반환"
    lines = wrap_text(text, 1000, 22, include=include, source="root.0.1.4.0", font=font)
    assert " ".join(lines) == text


def test_round2_unspecified_source_keeps_legacy_word_split(font):
    from corpus_typography import wrap_text
    include, _ = ROUND2_SOURCES[257]
    text = "Elasticsearch에 query 전송"
    width = 143.02800000000002
    assert wrap_text(text, width, 22, include=include, source="root.0.1.7", font=font) == font.wrap(text, width, 22)


ROUND2_DENSITIES = {
    30: (28, 22, 24, 24),
    96: (20, 18, 16, 16),
    98: (24, 20, 20, 20),
    106: (24, 20, 20, 20),
    131: (28, 22, 24, 24),
    148: (28, 22, 24, 24),
    156: (28, 22, 24, 24),
    164: (28, 22, 24, 24),
    188: (24, 20, 20, 20),
    190: (28, 22, 24, 24),
    214: (28, 22, 24, 24),
    215: (20, 18, 16, 16),
    217: (28, 22, 24, 24),
    243: (28, 22, 24, 24),
    245: (28, 22, 24, 24),
    257: (28, 22, 24, 24),
    260: (28, 22, 24, 24),
    276: (24, 20, 20, 20),
    283: (22, 18, 16, 16),
    300: (16, 14, 10, 10),
    305: (16, 14, 10, 10),
    364: (28, 22, 24, 24),
    383: (28, 22, 24, 24),
}
ROUND2_WIDTH_BLOCKERS = {156, 188, 257, 283}


def test_round2_additive_scope_is_frozen_and_preserves_original_phrases():
    import hashlib
    from corpus_typography import typography_repair
    pairs = [(r.include, r.source) for r in ROUND2_REPAIRS]
    assert len(pairs) == len(set(pairs)) == 35
    assert len({i for i, _ in pairs}) == 23
    assert hashlib.sha256("\n".join(i + "|" + s for i, s in pairs).encode()).hexdigest() == "ee3519c6069747d89a8367a41ff9b14cad957fef96648ffc2ee58ab3e2057863"
    old_pairs = {(r.include, r.source) for r in (*REPAIRS, *ROUND2_REPAIRS)}
    assert len(old_pairs) == 99
    assert {(r.include, r.source) for r in ALL_REPAIRS
            if (r.include, r.source) in old_pairs} == old_pairs
    for repair in REPAIRS:
        merged = typography_repair(repair.include, repair.source)
        assert merged is not None
        assert set(repair.phrases) <= set(merged.phrases)


@pytest.mark.parametrize("index", ROUND2_SOURCES)
def test_round2_full_source_in_memory_at_frozen_parent_density(font, index):
    import json
    from corpus_typography import CannotFit, corpus_typography_profile
    include, _ = ROUND2_SOURCES[index]
    figure = source(include)
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    font_budgets = json.loads((ROOT / "kkamji_scripts/blog/static_png/fhd-font-budgets.json").read_text())["sources"]
    profile = {**compiler.FIXED_LAYOUT_PROFILES.get(include, {}),
               **font_budgets.get(include, {}), **corpus_typography_profile(include)}
    for key, value in compiler.corpus_flow_balance_profile(include).items():
        if isinstance(value, dict):
            profile[key] = {**profile.get(key, {}), **value}
        else:
            profile[key] = list(dict.fromkeys([*profile.get(key, []), *value]))
    clearance = compiler.corpus_clearance_profile(include)
    if clearance:
        current = profile.get("group_insets", {})
        profile["group_insets"] = {**current, **{k: max(v, current.get(k, 0))
                                                   for k, v in clearance["group_insets"].items()}}
    label, detail, gap, padding = ROUND2_DENSITIES[index]
    assert label >= 16 and detail >= 14
    layout = compiler.Layout(font, label, detail, gap, padding, profile)
    assert layout.profile["typography_include"] == include
    try:
        measured = layout.measure(figure, compiler.WIDTH - 128)
        assert measured <= compiler.HEIGHT - 128
        layout.draw(figure, 64, 64 + (compiler.HEIGHT - 128 - measured) / 2,
                    compiler.WIDTH - 128)
        layout.resolve_boundary_edges(figure)
    except CannotFit as exc:
        if index == 245 and exc.source == "root.0.2.1":
            # Round3 adds this exact clause; the frozen round2 corridor is too
            # narrow. Assert the physical blocker, never treat this as geometry.
            assert exc.atom == "자신의 sequence를 보냄"
            assert exc.size == detail == 22
            assert exc.width_budget == 1
            assert exc.required_width == pytest.approx(font.width(exc.atom, 22))
            assert exc.required_width > exc.width
            return
        assert index in ROUND2_WIDTH_BLOCKERS, str(exc)
        assert exc.source in {case[1] for case in ROUND2_CASES if case[0] == index}
        assert exc.required_width > exc.width
        assert exc.size in {label, detail}
        return  # Explicit unresolved physical width, not a native/geometry PASS.
    compiler.manual_relation_fixes(layout, figure, include)
    compiler.complete_group_boundaries(layout)
    compiler.complete_relation_labels(layout)
    assert compiler.visible_text_coverage(layout, original) == []
    assert compiler.semantic_check(layout, figure) == []
    for case in ROUND2_CASES:
        if case[0] != index:
            continue
        _, key, text, phrases, *_ = case
        emitted = [t["text"] for t in layout.texts if t["source"] == key]
        for phrase in phrases:
            if phrase in text:
                assert any(phrase in line for line in emitted), (index, key, phrase, emitted)

# Fresh round3 findings only. Native SVG identity is evidence metadata, not a
# promise that live artwork is unchanged. source_fragment and complete prose
# runs are re-read; widths, sizes, budgets and old rows are frozen native inputs.
# Packer uses its original icon-adjusted 332px detail column and 120px caption
# (144px corridor minus two 12px insets), at the original unbudgeted 22px font.
ROUND3_SOURCES = {
    1: ('diagrams/packer-golden-image.html', '2bea76dd7d41f6bbf14cf609813fdf6934ea38254e44e2d6bf2f90463ee2904f', 'bcde26bd0fae9cac6b120abbdcec48b3eaa6f86719f4f74a4406364bf14a48e8'),
    96: ('diagrams/static/ci-cd/ci-cd-study/application-deploy-model-in-kubernetes.html', '18d5af48faecbdfcc99dea6d504e3239bc862da05dbe15bacffabdaba79893cb', 'd71522647f0c6eee20298c69c579ad72cb93fa9e841c42d070258edcea3ab455'),
    156: ('diagrams/static/jvm/jvm-02-stack-vs-heap.html', '1a277e1ecb5f3a6ca77c59bb183534f0433186aa892667a44a9e6d906b9fc3d4', '28ea238aa8e0c4204a54cd1dafc5605972f4147698437c09ee28968af3330fcf'),
    245: ('diagrams/static/network/tcp-3-way-handshake.html', '7d209360182d4ac16bd773a529d36638ff2f82d8a1f1a1fff846527ec8d9c315', '2e4e08fcf5f3c8775d2e4a0ccb72fc0780646984e1840c8749fef45ff78d62da'),
    311: ('diagrams/static/sap-c02/kinesis-efo-vs-shared-consumers.html', '163efbbc7dab1b22a2d9260098a4c00a64c8aa44184be6d9d7003969b84025b2', 'ed9a6e77a627d61398a193a9d367f89c0e4d349c7d71da34e9abae70510010c5'),
    382: ('diagrams/static/spring/spring-20-n-plus-1-fix.html', '56eb6cc66c95b8c918364bcf3bd371dd959a80929e167277cddd1d32336b635d', '04e7542f9d842baf0859b52e32b5439a3998309115861959247ad1333a346063'),
}
ROUND3_CASES = (
    (1, 'root.0.1.1.4', '설치 결과를 담은 재사용 가능한 머신 이미지', ('머신 이미지',), 332.0, 22, 1, ('설치 결과를 담은 재사용 가능한 머신', '이미지')),
    (1, 'root.0.1.1.1', 'Builder가 임시 EC2 생성', ('임시 EC2 생성',), 120, 22, 1, ('Builder가', '임시 EC2', '생성')),
    (96, 'root.0.1.0.1.1', 'code build와 test', ('build와 test',), 136, 18, 1.12, ('code build와', 'test')),
    (96, 'root.0.1.2.1.1.1.0', 'CI가 push한 versioned Container Image', ('Container Image',), 308.0, 18, 1.12, ('CI가 push한 versioned Container', 'Image')),
    (156, 'root.0.1.4', '여러 thread가 접근할 수 있는 Order 객체', ('Order 객체',), 408.0, 22, 1.12, ('여러 thread가 접근할 수 있는 Order', '객체')),
    (245, 'root.0.2.1', 'server가 x + 1을 확인하고 자신의 sequence를 보냄', ('자신의 sequence를 보냄',), 136, 22, 1, ('server가', 'x + 1을', '확인하고', '자신의', 'sequence를', '보냄')),
    (311, 'root.0.2.4.0.1.0', 'GetRecords pull, 샤드당 2 MB/s 총량을 모든 컨슈머가 나눕니다.', ('2 MB/s',), 282.0, 20, 1.12, ('GetRecords pull, 샤드당 2', 'MB/s 총량을 모든 컨슈머가', '나눕니다.')),
    (382, 'root.0.2', 'EntityGraph는 같은 fetch plan을 선언하고, DTO projection은 엔티티 자체를 로드하지 않는 선택지입니다. 컬렉션 JOIN FETCH와 paging은 결과 행과 메모리 사용량을 함께 점검합니다.', ('함께 점검합니다.',), 1792, 22, 1.12, ('EntityGraph는 같은 fetch plan을 선언하고, DTO projection은 엔티티 자체를 로드하지 않는 선택지입니다. 컬렉션 JOIN FETCH와 paging은 결과 행과 메모리 사용량을 함께', '점검합니다.')),
)


@pytest.mark.parametrize("index", ROUND3_SOURCES)
def test_round3_real_frozen_runs_preserve_phrase_or_require_geometry(font, monkeypatch, index):
    import hashlib
    from corpus_typography import CannotFit, wrap_text
    import corpus_typography as policy
    include, source_sha, _ = ROUND3_SOURCES[index]
    original = compiler.source_fragment((ROOT / "_includes" / include).read_text())
    assert hashlib.sha256(original.encode()).hexdigest() == source_sha
    elements = {e.key: e for e in source(include).descendants()}
    prior_pairs = {(r.include, r.source) for r in (*REPAIRS, *ROUND2_REPAIRS)}
    prior = {}
    for repair in (*REPAIRS, *ROUND2_REPAIRS):
        old = prior.get((repair.include, repair.source))
        prior[repair.include, repair.source] = policy.TypographyRepair(
            repair.include, repair.source,
            tuple(dict.fromkeys((*old.phrases, *repair.phrases))) if old else repair.phrases,
            max(old.min_last_words, repair.min_last_words) if old else repair.min_last_words)
    assert len(prior_pairs) == len(prior) == 99
    for case in ROUND3_CASES:
        if case[0] != index:
            continue
        _, key, text, phrases, width, size, budget, baseline = case
        element = elements[key]
        head, detail = compiler.Layout(font, 28, 22).lines(element, 1000000)
        assert text in [" ".join(head), " ".join(detail)]
        with monkeypatch.context() as legacy:
            legacy.setattr(policy, "_REPAIRS", prior)
            assert tuple(wrap_text(text, width, size, include=include, source=key,
                                   font=font, width_budget=budget)) == baseline
        required = max(font.width(phrase, size) * budget for phrase in phrases)
        if required > width:
            with pytest.raises(CannotFit) as exc:
                wrap_text(text, width, size, include=include, source=key,
                          font=font, width_budget=budget)
            assert exc.value.atom in phrases
            assert (exc.value.include, exc.value.source, exc.value.size,
                    exc.value.width_budget, exc.value.width) == (include, key, size, budget, width)
            assert exc.value.required_width == pytest.approx(required)
            width = required + 0.01  # Explicit local caller-owned corridor fallback.
        lines = wrap_text(text, width, size, include=include, source=key,
                          font=font, width_budget=budget)
        assert " ".join(lines) == text
        assert len(lines[-1].split()) >= 2
        assert all(font.width(line, size) * budget <= width for line in lines)
        for phrase in phrases:
            assert any(phrase in line for line in lines), (index, key, phrase, lines)
        layout = compiler.Layout(font, 28, size, profile={
            "regular_width_budget": budget, **policy.corpus_typography_profile(include)})
        assert layout.wrap(text, width, size, source=key) == lines
        if index == 245:
            # Preserve the server's own initial sequence and the x + 1 ACK.
            assert any("x + 1을" in line for line in lines)
            assert 2 <= len(lines) <= 4
            assert "SYN, ACK: server to client" in original
            assert "server seq = y, ack = x + 1" in original


def test_round3_additive_exact_scope_preserves_all_previous_declarations():
    from corpus_typography import ROUND3_REPAIRS, ROUND4_REPAIRS, typography_repair
    pairs = [(r.include, r.source) for r in ROUND3_REPAIRS]
    expected = {(ROUND3_SOURCES[c[0]][0], c[1]) for c in ROUND3_CASES}
    assert len(pairs) == len(set(pairs)) == 8
    assert set(pairs) == expected
    assert len({i for i, _ in pairs}) == 6
    assert len(ALL_REPAIRS) == 112
    assert len({r.include for r in ALL_REPAIRS}) == 69
    assert len(ROUND4_REPAIRS) == 9
    for repair in (*REPAIRS, *ROUND2_REPAIRS, *ROUND3_REPAIRS, *ROUND4_REPAIRS):
        merged = typography_repair(repair.include, repair.source)
        assert merged is not None
        assert set(repair.phrases) <= set(merged.phrases)
        assert merged.min_last_words == 2
    for index, key, _, phrases, *_ in ROUND3_CASES:
        include = ROUND3_SOURCES[index][0]
        repair = typography_repair(include, key)
        assert repair is not None
        assert set(phrases) <= set(repair.phrases)
        assert all(len(p.split()) <= 4 for p in repair.phrases)
        assert typography_repair(include, key + ".999") is None
    tcp = typography_repair(ROUND3_SOURCES[245][0], "root.0.2.1")
    assert tcp is not None
    assert "x + 1" in tcp.phrases


def test_round3_unscoped_inputs_remain_byte_identical_and_no_nfkc(font):
    from corpus_typography import corpus_typography_profile, typography_repair, wrap_text
    text = "  ＡＷＳ\t① e\u0301 ＫＢ\n2 MB/s  "
    for index, (include, _, _) in ROUND3_SOURCES.items():
        assert corpus_typography_profile(include) == {"typography_include": include}
        calls, sentinel = [], ["unchanged legacy result"]
        def legacy(value, width, size):
            calls.append((value, width, size))
            return sentinel
        assert typography_repair(include, "root.999") is None
        assert wrap_text(text, 112, 22, include=include, source="root.999",
                         wrap=legacy, width_budget=1.12) is sentinel
        assert calls == [(text, 112 / 1.12, 22)]
        key = next(c[1] for c in ROUND3_CASES if c[0] == index)
        assert wrap_text(text, 1000, 22, include=include, source=key,
                         font=font) == ["ＡＷＳ ① e\u0301 ＫＢ", "2 MB/s"]
