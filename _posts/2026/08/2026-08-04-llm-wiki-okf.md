---
title: "LLM Wiki와 OKF - 같은 마크다운, 다른 문제 [LLM Wiki 4]"
date: 2026-08-04 03:45:00 +0900
author: kkamji
categories: [AI, Knowledge Base]
tags: [ai, llm, knowledge-base, wiki, okf, markdown, interoperability, obsidian]
comments: true
image:
  path: /assets/img/ai/llm-wiki/llm-wiki.webp
---

마크다운으로 지식 베이스를 운영하는 사례가 늘면서 그 형식을 규정하려는 시도도 나오고 있습니다. Google Cloud가 공개한 OKF(Open Knowledge Format)가 그중 하나입니다. 마크다운 파일 트리와 YAML frontmatter만으로 지식 묶음을 정의하고, 특정 LLM이나 벡터 DB, SaaS를 요구하지 않습니다. 같은 재료를 쓰기 때문에 Karpathy가 제안한 LLM Wiki의 표준화된 형태로 소개되는 경우도 있습니다.

이 글에서는 OKF 규격이 무엇을 정하고 무엇을 정하지 않는지, 어떤 문제를 풀려고 만들어졌는지를 정리합니다. 이어서 운영 중인 마크다운 위키를 이 규격에 실제로 대보고 어디가 어긋나는지, 맞출 가치가 있는지를 판단한 과정을 남깁니다.

---

## 1. OKF가 규정하는 것

OKF가 요구하는 계약은 작습니다. SPEC.md 기준으로 정리하면 다음이 전부입니다.

- 마크다운 파일 트리다. 특정 LLM, 벡터 DB, SaaS를 요구하지 않는다.
- `index.md`(디렉터리 목록)와 `log.md`(변경 이력)는 예약 파일명이다.
- 예약 파일이 아닌 문서는 YAML frontmatter를 가져야 하고, 그 안에 비어 있지 않은 `type`이 있어야 한다. **필수 필드는 이것 하나뿐이다.**
- 권장 필드는 `title`, `description`, `resource`, `tags`.
- 링크는 bundle 루트 기준 절대 경로 또는 표준 상대 경로다.
- 깨진 링크는 오류가 아니다. 소비자는 아직 작성되지 않은 지식으로 간주하고 허용해야 한다.

선택 필드는 세 묶음입니다. 출처를 적는 `sources`, 누가 언제 만들고 검증했는지 적는 `generated`와 `verified`, 수명을 적는 `status`와 `stale_after`입니다.

```yaml
---
type: concept
title: 쿠버네티스 어드미션 컨트롤
description: API 요청이 etcd에 저장되기 전 거치는 검증과 변경 단계
tags: [kubernetes, security]
sources:
  - resource: https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
    title: Kubernetes Documentation
generated:
  by: claude-opus-5
  at: 2026-08-16T10:00:00Z
status: stable
stale_after: 2027-02-01
---
```

`status`는 `draft`, `stable`, `deprecated` 셋 중 하나이고 값이 없으면 `stable`로 읽습니다. `stale_after`는 절대 날짜이며 오늘이 그 날짜 이상이면 stale입니다.

주목할 점은 규격이 형식만 정하고 나머지는 전부 생산자에게 맡긴다는 것입니다. 폴더를 어떻게 나눌지, 어떤 검색 엔진을 쓸지, 태그 체계를 어떻게 짤지, `type`에 어떤 값을 넣을지 모두 규정하지 않습니다. frontmatter에 자기만의 필드를 추가하는 것도 허용합니다.

---

## 2. v0.1에서 v0.2로 바뀐 것

현재 규격은 v0.2입니다. 초기 버전인 v0.1을 기준으로 소개한 자료가 아직 돌아다니므로, 어느 버전을 보고 있는지 확인이 필요합니다. 스펙이 밝힌 변경점은 두 군데입니다.

| 항목 | v0.1 | v0.2 |
|---|---|---|
| 생성 시각 | `timestamp` | `generated.at` |
| 출처 표기 | 본문 하단 `# Citations` 목록 | frontmatter `sources` |

본문에 있던 인용 목록이 frontmatter로 올라간 변경이 핵심입니다. 사람이 읽는 자리에서 기계가 파싱하는 자리로 옮긴 것이고, 이 방향은 마크다운 지식 베이스 전반에서 반복되는 패턴입니다.

---

## 3. 검증 도구에 대한 오해

OKF를 소개하는 글 중에 `okf-lint`라는 검증 CLI를 함께 언급하는 경우가 있습니다. 확인해 보니 공식 저장소에는 그런 도구가 없습니다. `okf` 패키지가 제공하는 진입점은 두 개입니다.

- `enrich`: BigQuery 데이터셋과 웹 소스에서 OKF bundle을 생성
- `visualize`: bundle을 인터랙티브 HTML로 렌더링

규격 준수 여부를 검사하는 명령은 없고, 저장소의 검증 수단은 `pytest`로 도는 자체 테스트가 전부입니다. 즉 OKF로 문서를 만들어도 그것이 규격에 맞는지 확인해 주는 공식 도구는 현재 없습니다. 검사가 필요하면 직접 만들어야 합니다.

---

## 4. Karpathy 패턴의 표준화가 아닙니다

OKF는 "Karpathy LLM Wiki에 대한 Google의 답"으로 소개되곤 합니다. 두 규격이 모두 마크다운과 frontmatter를 쓰니 그렇게 보입니다. 하지만 스펙을 읽어 보면 푸는 문제가 다릅니다.

단서는 규격에 들어 있는 필드들입니다. `resource`는 원본 자산의 정규 URI입니다. `sources[].usage_count`는 그 출처가 관측 기간 동안 몇 번 사용됐는지 세는 값입니다. Attested Computation은 검증 가능한 SQL이나 스크립트의 실행 계약을 담는 확장 타입으로, 실행 방법과 결과 영수증 형식, 판정 코드까지 규정합니다.

이것들은 노트 관심사가 아니라 **데이터 카탈로그 관심사**입니다. 실제로 Google Cloud가 밝힌 문제의식도 그쪽입니다. 데이터셋을 제공하는 쪽이 있고, 그 데이터를 제대로 쓰는 데 필요한 맥락은 따로 흩어져 있습니다. 어떤 컬럼이 실제로 무엇을 의미하는지, 어떤 쿼리가 검증됐는지, 어떤 값이 언제부터 못 믿을 값인지가 문서 도구와 메신저와 담당자 머릿속에 나뉘어 있습니다. 데이터를 받는 쪽 에이전트는 그것을 볼 수 없습니다. OKF는 그 맥락을 데이터와 함께 실어 보내기 위한 포맷입니다.

Karpathy의 LLM Wiki는 다른 문제에서 출발합니다. 모델이 같은 지식을 질의할 때마다 원문에서 다시 유추하는 낭비를 없애자는 것이고, 해법은 ingestion 시점에 한 번 컴파일해서 계속 갱신하는 것입니다. 소비자는 나 자신과 내 에이전트입니다.

| | Karpathy LLM Wiki | Google OKF |
|---|---|---|
| 푸는 문제 | 모델이 질의마다 지식을 다시 유추함 | 지식이 조직 경계를 넘지 못함 |
| 해법 | ingestion 시점 1회 컴파일 후 갱신 | 형식을 통일해 이식 가능하게 |
| 전제 소비자 | 나와 내 에이전트 | 데이터를 받는 제3자 |
| 규정 범위 | 운영 방식과 분업까지 | 파일 형식만 |

같은 마크다운으로 수렴했지만 계보가 이어지는 관계는 아닙니다. 둘 다 "에이전트가 읽을 지식을 어디에 둘 것인가"라는 같은 시대적 질문에 각자 답했다고 보는 편이 정확합니다.

---

## 5. 실제 위키를 규격에 대보면

제 위키를 OKF 기준으로 재봤습니다. `wiki/` 아래 마크다운 542개 중 예약 파일명(`index.md`, `log.md`)이 63개, 나머지 479개 중 473개가 frontmatter와 비어 있지 않은 `type`을 갖고 있었습니다. 나머지 6개는 원문 스냅샷과 스키마 문서라 애초에 대상이 아닙니다.

어긋나는 지점은 둘뿐이었습니다.

**첫째, index 파일의 frontmatter입니다.** OKF는 index 파일에 frontmatter를 두지 않습니다. 유일한 예외가 bundle 루트 `index.md`의 `okf_version` 선언입니다. 제 위키는 62개 index 중 61개가 frontmatter를 갖고 있습니다. 자체 스키마가 index도 일반 노트처럼 취급하기 때문입니다.

**둘째, 위키링크입니다.** Obsidian의 `[[page-name]]`은 OKF의 표준 마크다운 링크가 아닙니다. 511개 문서가 이 문법을 씁니다. Obsidian 그래프 뷰와 커밋 훅의 링크 검사가 모두 이 문법 위에 서 있습니다.

반대로 OKF에 없는데 제 위키에 있는 것도 있었습니다. 주장의 확신도를 기록하는 `confidence`, 출처 등급을 나누는 `source_status`, 문서 사이 관계에 종류를 붙이는 `relations`, 원문 변조를 잡는 `sha256`, 두 문서가 충돌할 때 세우는 `contested` 플래그입니다. OKF는 생산자가 정의한 필드를 허용하므로 이것들을 버릴 필요는 없습니다.

---

## 6. 채택하지 않기로 한 이유

충돌이 두 개뿐이니 맞추려면 맞출 수 있었습니다. 변환 스크립트를 짜서 위키링크를 표준 링크로 바꾸고 index의 frontmatter를 걷어내면 규격에 맞는 사본이 나옵니다.

그런데 그 사본을 누가 읽는지를 따져보니 답이 없었습니다.

제 위키의 소비자는 저와 제 에이전트뿐입니다. 이들은 이미 스키마 문서와 검색 스크립트로 위키를 잘 읽고 있습니다. 넘겨줄 제3자가 없는 상태에서 542개 문서의 두 번째 사본을 만드는 빌드 단계를 세우면, 갱신되지 않은 사본이 남았을 때 "이게 최신인가"를 매번 판단해야 하는 부담만 생깁니다. 규격에 맞추는 비용보다 이 부담이 큽니다.

게다가 규격 자체가 아직 작습니다. 필수 필드가 하나뿐이고 공식 검증 도구도 없습니다. 나중에 실제로 지식을 넘겨줄 일이 생겼을 때 맞춰도 비용이 거의 같습니다. 지금 미리 맞춰서 얻는 이득이 없습니다.

이 판단은 규격의 품질과 무관합니다. 조직 간에 데이터와 맥락을 함께 주고받아야 하는 상황이라면 OKF는 합리적인 선택입니다. 다만 그 상황에 있지 않다면, 형식이 비슷해 보인다는 이유로 개인 위키를 규격에 맞출 이유는 없습니다.

---

## 7. 그래도 하나는 가져왔습니다

규격을 읽다가 제 스키마에 빠진 것을 하나 발견했습니다. `stale_after`입니다.

제 위키에는 문서마다 `confidence`가 붙어 있습니다. 내가 이 주장을 얼마나 확신하는지를 기록합니다. `updated`도 있습니다. 언제 마지막으로 고쳤는지를 기록합니다. 그런데 **언제까지 믿어도 되는지**를 기록하는 필드는 없었습니다.

1편에서 일반 위키의 한계를 이야기하며 이렇게 썼습니다. LLM은 오래된 문서와 최신 문서를 구분하지 못한 채 둘 다 사실로 답하므로 갱신 시점과 신뢰도가 기계적으로 표시되어야 한다고요. 주장은 해놓고 정작 만료를 표현하는 필드는 만들지 않았던 셈입니다.

`updated: 2026-03-01`은 3월에 고쳤다는 사실만 알려줍니다. 그 문서가 지금도 유효한지는 알려주지 않습니다. 개념 설명이라면 3월 것이어도 멀쩡하고, 요금표라면 이미 틀렸을 수 있습니다. 둘을 같은 신호로 다루면 에이전트는 구분하지 못합니다.

그래서 스키마에 선택 필드로 추가했습니다.

```yaml
stale_after: 2026-11-01
```

붙이는 대상은 만료가 예정된 주장으로 한정했습니다. 요금과 가격, 제품 버전과 지원 종료일, 벤더 정책과 쿼터, 시점이 박힌 조사 결과 같은 것들입니다. 개념 설명이나 원리, 회고처럼 시간이 지나도 틀려지지 않는 문서에는 붙이지 않습니다. 전부에 붙이면 만료 알림이 소음이 되어 아무도 보지 않게 됩니다.

기존 문서에 소급해서 넣지도 않았습니다. 실제로 만료 시점을 판단할 수 있는 신규 문서와 재검토하는 문서부터 적용합니다. 확인하지 않은 날짜를 일괄로 채워 넣으면 그 필드 자체를 믿을 수 없게 됩니다.

중요한 것은 lint가 이 필드를 실제로 검사하게 만드는 일입니다. 선언만 해두고 아무도 보지 않으면 장식입니다. 기존 검사 스크립트에 만료 문서를 모으는 로직을 붙였습니다.

```python
raw_stale = note.frontmatter.get("stale_after")
if raw_stale is not None:
    try:
        expires = date.fromisoformat(str(raw_stale))
    except ValueError:
        metadata.append({"path": note.relative, "issue": "invalid_stale_after"})
    else:
        if today >= expires:
            stale.append({"path": note.relative, "stale_after": expires.isoformat()})
```

만료 판정은 삭제 신호가 아니라 재확인 신호로 다룹니다. 확인해서 값이 그대로면 `stale_after`만 미루고 `updated`를 갱신합니다. 값이 바뀌었으면 본문을 고칩니다. 어느 쪽이든 문서가 조용히 썩는 것보다 낫습니다.

규격 하나를 통째로 채택하는 것과, 그 규격에서 내게 없는 것 하나를 가져오는 것은 다른 일입니다. 후자가 대개 더 실용적입니다.

---

## 8. Reference

- [Open Knowledge Format - SPEC.md](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [Open Knowledge Format - README](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/README.md)
- [Google Cloud Blog - How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)
- [Karpathy - LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
