#!/usr/bin/env python3
"""Add closing summaries to long high-impact posts.

The block is inserted before the Reference section, without changing existing
heading numbering or permalinks.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / ".hermes" / "reports" / "blog-quality-audit.csv"
REFERENCE_RE = re.compile(r"^##\s+(?:\d+[.)]?\s*)?(?:Reference|References|참고|참고 자료)\s*$", re.I | re.M)
KEYWORDS = ["kubernetes", "aws", "spring", "jvm", "terraform", "helm", "istio", "argocd", "jenkins", "cilium", "observability", "datadog"]


def impact(row: dict[str, str]) -> int:
    text = " ".join([row.get("path", ""), row.get("title", ""), row.get("categories", ""), row.get("tags", "")]).lower()
    return sum(1 for keyword in KEYWORDS if keyword in text)


def summary_block(row: dict[str, str]) -> str:
    title = row.get("title", "이 글")
    return f"""> **핵심 정리**  
> - 이 글은 `{title}`의 개념, 구성 흐름, 실습 결과를 한 번에 따라갈 수 있도록 정리한 글입니다.  
> - 다시 볼 때는 전체 명령을 처음부터 실행하기보다 환경 전제, 권한, 네트워크, 버전 차이를 먼저 확인하는 것이 좋습니다.  
> - 운영 환경에 적용할 때는 예제 값을 그대로 쓰지 말고, 조직의 보안 정책과 장애 대응 절차에 맞게 조정해야 합니다.  
{{: .prompt-tip}}

"""


def main() -> None:
    rows = list(csv.DictReader(AUDIT.open(encoding="utf-8")))
    targets = [row for row in rows if impact(row) > 0 and int(row.get("lines", "0")) >= 450]
    changed: list[str] = []
    for row in sorted(targets, key=lambda item: item["path"]):
        path = ROOT / row["path"]
        text = path.read_text(encoding="utf-8")
        if "**핵심 정리**" in text:
            continue
        matches = list(REFERENCE_RE.finditer(text))
        if not matches:
            continue
        match = matches[-1]
        new_text = text[: match.start()].rstrip() + "\n\n" + summary_block(row) + text[match.start() :]
        path.write_text(new_text, encoding="utf-8")
        changed.append(row["path"])
    print(f"targets={len(targets)} changed={len(changed)}")
    for rel in changed:
        print(rel)


if __name__ == "__main__":
    main()
