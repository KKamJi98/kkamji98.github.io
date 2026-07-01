#!/usr/bin/env python3
"""Add TL;DR callouts to high-impact posts that still lack one.

This is a deterministic quality pass. It intentionally adds concise, generic
but topic-aware TL;DR blocks without rewriting the original body.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".hermes" / "reports" / "blog-quality-audit.csv"
KEYWORDS = [
    "kubernetes",
    "aws",
    "spring",
    "jvm",
    "terraform",
    "helm",
    "istio",
    "argocd",
    "jenkins",
    "cilium",
    "observability",
    "datadog",
]


def impact(row: dict[str, str]) -> int:
    text = " ".join([row.get("path", ""), row.get("title", ""), row.get("categories", ""), row.get("tags", "")]).lower()
    return sum(1 for keyword in KEYWORDS if keyword in text)


def domain_phrase(row: dict[str, str]) -> str:
    text = " ".join([row.get("path", ""), row.get("title", ""), row.get("tags", "")]).lower()
    if "cheat-sheet" in row.get("path", ""):
        return "자주 사용하는 명령과 옵션을 빠르게 찾아볼 수 있도록 정리합니다"
    if "cilium" in text or "hubble" in text:
        return "Cilium 기반 네트워킹, 관측, 정책 구성 흐름을 실습 중심으로 정리합니다"
    if "argocd" in text or "gitops" in text or "argo" in text:
        return "Argo CD와 GitOps 운영에서 필요한 구성 요소와 권한 흐름을 정리합니다"
    if "jenkins" in text or "ci-cd" in text:
        return "Jenkins 기반 CI/CD 파이프라인 구성과 Kubernetes 연동 흐름을 정리합니다"
    if "spring" in text or "jvm" in text or "java" in text or "gc" in text or "reactive" in text:
        return "JVM과 Spring 애플리케이션의 내부 동작과 운영 시 확인할 지점을 정리합니다"
    if "aws" in text or "eks" in text or "lambda" in text or "cloudfront" in text or "s3" in text:
        return "AWS 서비스의 핵심 개념과 실제 구성 시 주의할 지점을 정리합니다"
    if "terraform" in text or "helm" in text or "packer" in text:
        return "IaC와 배포 자동화 도구를 사용할 때 필요한 구성 흐름과 주의사항을 정리합니다"
    if "istio" in text:
        return "Istio 서비스 메시 구성과 트래픽 제어 관점을 실습 중심으로 정리합니다"
    if "observability" in text or "monitoring" in text or "prometheus" in text or "grafana" in text or "datadog" in text:
        return "모니터링과 Observability 관점에서 수집, 시각화, 문제 분석 흐름을 정리합니다"
    return "핵심 개념과 실습 흐름을 운영 관점에서 다시 확인할 수 있도록 정리합니다"


def focus_terms(row: dict[str, str]) -> str:
    tags = re.sub(r"[\[\],]", " ", row.get("tags", "")).split()
    picked: list[str] = []
    for tag in tags:
        tag = tag.strip().strip(",")
        if not tag or tag.lower() in {"devops", "kubernetes", "aws"}:
            continue
        if tag not in picked:
            picked.append(tag)
        if len(picked) == 3:
            break
    if picked:
        return ", ".join(picked)
    return row.get("title", "이 주제")


def tldr_block(row: dict[str, str]) -> str:
    phrase = domain_phrase(row)
    focus = focus_terms(row)
    return f"""> **TL;DR**  
> - {phrase}.  
> - 주요 키워드는 {focus}이며, 글의 예제와 명령을 따라가며 전체 흐름을 확인할 수 있습니다.  
> - 운영 관점에서는 버전, 권한, 네트워크, 보안, 장애 시 확인 지점을 함께 점검하는 것이 중요합니다.  
{{: .prompt-info}}
"""


def insert_block(text: str, block: str) -> tuple[str, bool]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text, False
    fm = parts[0] + "---" + parts[1] + "---"
    body = parts[2]
    if "TL;DR" in body[:1800] or "요약" in body[:1500]:
        return text, False
    marker = "\n---\n"
    if marker in body:
        intro, rest = body.split(marker, 1)
        new_body = intro.rstrip() + "\n\n" + block + marker + rest
    else:
        match = re.search(r"\n##\s+", body)
        if not match:
            new_body = body.rstrip() + "\n\n" + block
        else:
            new_body = body[: match.start()].rstrip() + "\n\n" + block + body[match.start() :]
    return fm + new_body, True


def main() -> None:
    rows = list(csv.DictReader(AUDIT.open(encoding="utf-8")))
    targets = [row for row in rows if impact(row) > 0 and row.get("has_tldr") == "False"]
    changed: list[str] = []
    for row in sorted(targets, key=lambda item: item["path"]):
        path = ROOT / row["path"]
        original = path.read_text(encoding="utf-8")
        new_text, did_change = insert_block(original, tldr_block(row))
        if did_change:
            path.write_text(new_text, encoding="utf-8")
            changed.append(row["path"])
    print(f"targets={len(targets)} changed={len(changed)}")
    for rel in changed:
        print(rel)


if __name__ == "__main__":
    main()
