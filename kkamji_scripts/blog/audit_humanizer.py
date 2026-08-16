#!/usr/bin/env python3
"""Report AI-like public-writing artifacts in Jekyll Markdown posts.

Default mode is advisory so legacy posts can be reviewed gradually. ``--strict``
returns non-zero only for high-confidence public-writing artifacts; use it with
``--file`` before publishing a newly edited post.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

HIGH_RULES: dict[str, re.Pattern[str]] = {
    "meta-heading": re.compile(
        r"^#{1,6}\s*(?:\d+\.\s*)?(?:이 글의 범위|연재에서의 위치|학습 점검|다음 글|읽기 순서|도착 역량|글 계획 카드)"
    ),
    "meta-prose": re.compile(
        r"(?:이 글의 (?:독자|범위|목표|역할|결론)|이번 (?:글|연재)에서는|이 글은 .*?(?:다룹니다|역할)|도착 역량|의도적으로 (?:제외|상세 설명하지))"
    ),
    "roadmap-checklist": re.compile(
        r"^\s*- \[[ xX]\]|(?:연재의 각 글|이후 글에서 책임을 분리)"
    ),
    "template-wrapup": re.compile(
        r"(?:개념, 구성 흐름, 실습 결과를 한 번에 따라갈 수 있도록 정리한 글입니다|다시 볼 때는 전체 명령을 처음부터 실행하기보다|운영 환경에 적용할 때는 예제 값을 그대로 쓰지 말고)"
    ),
    # Filler emitted by the retired add_remaining_high_impact_tldr.py backfill.
    # Every bullet it produced restates the frontmatter tags or a domain platitude,
    # so a TL;DR built from it tells the reader nothing the title did not.
    "generic-tldr": re.compile(
        r"(?:주요 키워드는 .*?(?:이며|이고), 글의 예제와 명령을 따라가며 전체 흐름을 확인할 수 있습니다"
        r"|운영 관점에서는 버전, 권한, 네트워크, 보안, 장애 시 확인 지점을 함께 점검하는 것이 중요합니다"
        r"|자주 사용하는 명령과 옵션을 빠르게 찾아볼 수 있도록 정리합니다"
        r"|Cilium 기반 네트워킹, 관측, 정책 구성 흐름을 실습 중심으로 정리합니다"
        r"|Argo CD와 GitOps 운영에서 필요한 구성 요소와 권한 흐름을 정리합니다"
        r"|Jenkins 기반 CI/CD 파이프라인 구성과 Kubernetes 연동 흐름을 정리합니다"
        r"|JVM과 Spring 애플리케이션의 내부 동작과 운영 시 확인할 지점을 정리합니다"
        r"|AWS 서비스의 핵심 개념과 실제 구성 시 주의할 지점을 정리합니다"
        r"|IaC와 배포 자동화 도구를 사용할 때 필요한 구성 흐름과 주의사항을 정리합니다"
        r"|Istio 서비스 메시 구성과 트래픽 제어 관점을 실습 중심으로 정리합니다"
        r"|모니터링과 Observability 관점에서 수집, 시각화, 문제 분석 흐름을 정리합니다"
        r"|핵심 개념과 실습 흐름을 운영 관점에서 다시 확인할 수 있도록 정리합니다)"
    ),
}

ADVISORY_RULES: dict[str, re.Pattern[str]] = {
    "tldr": re.compile(r"TL;DR", re.IGNORECASE),
    "generic-signpost": re.compile(
        r"(?:이번 글에서는|다음 글에서는|살펴보겠습니다|알아보겠습니다)"
    ),
    "negative-parallel": re.compile(
        r"(?:무엇이 아닌가|단순히 .*? 아니라|항상 .*? 아닙니다)"
    ),
}


def markdown_files(args: argparse.Namespace) -> list[Path]:
    if args.file:
        return [Path(args.file)]
    root = Path(args.root)
    return sorted(root.rglob("*.md"))


def scan(path: Path) -> list[tuple[int, str, str, str]]:
    text = path.read_text(encoding="utf-8")
    front_matter = "\n".join(text.splitlines()[:12])
    # TaeJi confirmed the Cilium learning series is human-authored. Its intentional
    # prose and study markers are not evidence of automated writing. generic-tldr is
    # still checked there, because that filler was injected by a script rather than
    # written by the author.
    hand_written_series = (
        "Cilium" in front_matter
        or "Hubble" in front_matter
        or "[Cilium" in front_matter
    )
    high_rules = (
        {"generic-tldr": HIGH_RULES["generic-tldr"]}
        if hand_written_series
        else HIGH_RULES
    )
    advisory_rules: dict[str, re.Pattern[str]] = (
        {} if hand_written_series else ADVISORY_RULES
    )
    findings: list[tuple[int, str, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in high_rules.items():
            if pattern.search(line):
                findings.append((number, "HIGH", name, line.strip()))
        for name, pattern in advisory_rules.items():
            if pattern.search(line):
                findings.append((number, "ADVISORY", name, line.strip()))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="_posts", help="directory to scan")
    parser.add_argument("--file", help="one post to scan")
    parser.add_argument("--strict", action="store_true", help="fail on HIGH findings")
    args = parser.parse_args()

    files = markdown_files(args)
    if not files:
        print("No Markdown posts found.", file=sys.stderr)
        return 2

    counts: Counter[str] = Counter()
    high_count = 0
    for path in files:
        for number, severity, rule, text in scan(path):
            counts[f"{severity}:{rule}"] += 1
            if severity == "HIGH":
                high_count += 1
            print(f"{path}:{number}: {severity} {rule}: {text}")

    print(f"Scanned {len(files)} post(s).")
    for key, count in sorted(counts.items()):
        print(f"{key}={count}")

    if args.strict and high_count:
        print(
            f"Humanizer strict check failed: {high_count} high-confidence finding(s).",
            file=sys.stderr,
        )
        return 1
    if args.strict:
        print("Humanizer strict check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
