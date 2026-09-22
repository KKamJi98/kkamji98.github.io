---
title: "Typesafe AI Jev Overview"
date: 2026-09-22 03:43:29 +0900
author: kkamji
categories: [AI, Development]
tags: [jev, system-one, typesafe-ai, agent, agent-harness, probabilistic-decision]
comments: true
image:
  path: /assets/img/ai/jev/jev-system-one-banner.webp
---

에이전트가 `kubectl delete namespace production`을 제안했다고 가정합니다. JSON schema가 유효하더라도 실제로 실행해도 되는지는 알 수 없습니다.

> **30초 예시**  
> `State`: production namespace 삭제 요청  
> `Jev`: `review_required`, 높은 비가역성 확률  
> `Policy`: 자동 실행 없이 `escalate`  
{: .prompt-tip}

반대로 `git status --short`처럼 작업 트리 조회로 제한된 명령은 대형 모델의 긴 추론 없이 좁은 판단으로 분류할 수 있습니다.

Jev는 명령, 정규화한 인자, 대상 환경, 사용자 의도를 함께 보고 typed answer와 확률을 반환하는 hosted decision layer입니다. **LLM을 대체하는 생성 모델이 아니라 제한된 판단을 위한 보조 계층입니다.** 최종 실행 권한은 deterministic policy와 harness에 남깁니다.

{% include diagrams/static/ai/jev-decision-pipeline.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/jev-decision-pipeline--730424ce5bbc600e.png" %}

---

## 1. Jev는 실행 권한이 아닌 판단 신호를 반환합니다

Jev는 긴 대화의 다음 문장을 생성하는 인터페이스가 아닙니다. 공통 `state`에는 도구 이름, canonicalized argument, 리소스 범위, 호출자 역할, 검증한 사전 조건처럼 판단에 필요한 사실을 넣습니다. 각 question은 그 상태에서 받을 answer의 종류를 선언합니다.

| 계층 | 맡는 일 | 실행 권한 |
|---|---|---|
| deterministic validator | canonical parsing, 자원 존재 여부, 날짜와 개수 같은 사실 확인 | 부여하지 않음 |
| Jev | 비가역성, 영향 범위, 분류 후보 같은 bounded question에 확률 신호 제공 | 부여하지 않음 |
| policy와 harness | threshold, 권한, 승인, 변경 창을 결합하고 실제 도구 호출 결정 | 이 계층에서만 검토 |

harness는 자연어 answer를 다시 파싱하지 않습니다. `choice`, `score`, `noul`과 primitive별 확률 필드를 policy 입력으로 사용합니다. `state` 안의 사용자 제공 문자열과 도구 설명은 판단 재료일 뿐, 권한을 부여하는 명령이 아닙니다.

제약된 schema와 type 때문에 `hallucination-free`라는 표현을 쓰기도 합니다. 그러나 schema는 응답의 형태를 제한할 뿐입니다.

> **schema 밖 문장을 만들기 어렵다는 것과 판단의 의미가 항상 옳다는 것은 다릅니다.**  
> `production` namespace라는 문자열을 넣어도 실제 대상이 의도한 리소스인지, 정책상 삭제가 허용되는지는 별도 검사해야 합니다.  
{: .prompt-warning}

---

## 2. Choice, Score, Noul은 서로 다른 질문에 답합니다

세 primitive는 policy가 받을 값의 모양을 먼저 정합니다. Choice나 Score의 `confidence`를 Noul에 그대로 적용하면 threshold가 가리키는 사건 자체가 달라집니다.

{% include diagrams/static/ai/jev-primitives.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/jev-primitives--8f4879260bec067c.png" %}

| primitive | 반환하는 typed answer | 적합한 판단 |
|---|---|---|
| Choice | 유한한 option의 `choice`, `probabilities`, 분포에서 유도한 `confidence` | 도구 위험 등급, 담당 queue, 검토 경로 |
| Score | 순서형 level의 확률 가중 위치인 `score`, `legend`, `probabilities`, `confidence` | 영향 범위, 증거 강도처럼 순서가 있는 등급 |
| Noul | `noul` 자체가 yes일 확률 | 비가역성, 민감정보 노출 가능성 같은 이진 사건 |

정책에서 읽는 방식도 구분해야 합니다.

- Choice의 `confidence`는 선택한 option이 맞다는 개별 요청의 보증서가 아님
- Score의 `confidence`는 임의의 자기 진술이 아니라 반환 분포에서 나온 값
- Noul은 Boolean으로 줄이기 전에 `noul`이 yes probability라는 사실을 유지
- `irreversible.noul`과 `risk_choice.confidence`에 같은 경계값을 적용하는 일은 서로 다른 질문을 정책으로 옮기는 일

Calibration은 한 응답의 정답 여부가 아니라, 비슷한 확률 구간에 속한 많은 사례의 예측 확률과 실제 빈도가 얼마나 맞는지 보는 집단 수준 성질입니다. **높은 `confidence` 하나가 그 요청의 정확성을 증명하지는 않습니다.**

Calibration을 활용하려면 배포할 task, 입력 분포, 고정한 model version으로 labeled evaluation을 따로 수행해야 합니다. 운영 로그에는 raw probability 하나만 저장하기보다 다음 연결을 남깁니다.

- question ID, option set, model ID, 실제 사후 결과
- threshold 변경 전후의 false allow와 불필요한 escalation
- 늦게 확정되는 label의 지연 상태. 결과를 아직 모르는 요청은 정답 표본에 넣지 않음

---

## 3. state는 검증된 공통 사실로 작게 유지합니다

같은 요청의 여러 question은 하나의 `state`를 공유하지만, 서로의 answer를 읽는 순차 단계가 아닙니다. 서비스는 question을 독립적으로 처리하고 병렬화합니다.

| 한 요청에서 가능한 구성 | 한 요청에서 성립하지 않는 구성 |
|---|---|
| 같은 state로 Choice, Score, Noul을 병렬 평가 | 첫 Choice answer로 두 번째 Score question의 의미를 변경 |
| 여러 독립 판단을 한 policy 입력으로 수집 | 앞 answer를 사실처럼 넣어 뒤 answer를 재평가 |

실제 의존성이 있으면 애플리케이션이 첫 결과를 검증한 뒤, 다음 요청의 `state`를 새로 구성해야 합니다. 이 경로에는 추가 지연과 실패 처리도 함께 설계해야 합니다.

| 입력과 한도 | 확인할 점 |
|---|---|
| 입력 형식 | string, JSON, text array를 `state`와 question에 전달. image, audio, video 직접 입력은 지원하지 않음 |
| 언어 | 문서는 English에서 가장 강한 성능을 안내. CJK 입력은 같은 threshold를 재사용하지 않고 자체 evaluation 필요 |
| 전체 context | `state`와 모든 question이 합쳐서 64k tokens |
| 단일 question 경계 | `state`와 가장 긴 단일 question이 합쳐서 32k tokens |

긴 audit log를 `state`에 계속 붙이면 관계없는 정보가 판단을 흐리는 context rot도 커집니다. 공식 한계에는 원문을 그대로 읽는 일, 정확한 산술, 개수 세기, 날짜 비교, 간접 표현 해석, 적대적 content, 서로 모순되는 기준이 포함됩니다. Jev는 생성 작업도 수행하지 않습니다. **정확해야 하는 산술, 날짜, 개수 계산은 Jev에 묻지 말고 code로 처리해야 합니다.**

`state`에는 확인한 사실과 model에게 묻는 해석을 섞지 않는 편이 안전합니다.

- validator가 확정한 namespace 존재 여부, caller role, approval ID, UTC timestamp의 날짜 비교 결과를 사실 필드로 넣음
- 긴 command history와 자유 형식 대화는 필요한 근거만 redact하고, 요약 전 보존 기준을 정함
- truncation으로 위험한 앞부분이나 마지막 인자가 사라지면 판단을 계속하지 않고 `escalate`함

---

## 4. 요청과 typed answer를 policy 입력으로 연결합니다

아래 예시는 `kubectl delete namespace production` 요청을 shadow path에서 평가하는 구조입니다. REST wire format을 재현하지 않고, SDK가 받을 핵심 입력만 먼저 요약합니다.

| 입력 | 예시 값 |
|---|---|
| `state.tool` | `kubectl` |
| `state.canonical_args` | `delete`, `namespace`, `production` |
| 검증한 환경 사실 | production, change window closed |
| `tool_risk` Choice | `bounded`, `review_required` 중 선택 |
| `irreversible` Noul | 신뢰할 수 있는 복구 경로 없이 데이터가 삭제되거나 덮어써지는가? |
| `blast_radius` Score | worktree, isolated target, shared non-production, production/third-party |

**응답 예시: 실제 API에서 관측한 값이 아닌 illustrative policy input**

```json
{
  "tool_risk": {
    "choice": "review_required",
    "confidence": 0.96
  },
  "irreversible": {
    "noul": 0.98
  },
  "blast_radius": {
    "score": 3,
    "confidence": 0.90
  }
}
```

응답 예시는 `answers` map으로 정규화한 값입니다. primitive의 전체 응답에는 앞 절에서 설명한 `probabilities`와 Score의 `legend`도 포함됩니다. 수치는 실제 호출 결과가 아니며, policy가 typed field를 어떻게 읽는지 보이기 위한 예시입니다.

다음 공식 Python SDK 예시는 Choice, Noul, Score를 함께 사용합니다. `state`에는 raw shell 문자열만 넣지 않고 parser가 만든 canonical argument와 환경 정보를 넣습니다. model은 calibrated threshold를 배포한 version으로 고정하며, **이 호출 결과만으로는 도구를 실행하지 않습니다.**

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

state = {
    "tool": "kubectl",
    "canonical_args": ["delete", "namespace", "production"],
    "environment": "production",
    "caller_role": "release-bot",
    "change_window": "closed",
    "requested_intent": "remove an unused namespace",
}

with TypeSafeClient(model="jev-1.13.0") as client:
    response = client.system_one(
        state=state,
        questions={
            "tool_risk": Choice(
                instructions="Classify the requested tool call.",
                criteria={
                    "bounded": "Read-only inside the current worktree, with no external effect.",
                    "review_required": "Any state mutation, external effect, production target, or unclear authorization.",
                },
            ),
            "irreversible": Noul(
                instructions="Would this call delete or overwrite data without a reliable recovery path?",
            ),
            "blast_radius": Score(
                instructions="How wide is the expected blast radius?",
                criteria=[
                    "Only the current worktree.",
                    "One host or one isolated namespace.",
                    "Shared non-production infrastructure.",
                    "Production or a third-party system.",
                ],
            ),
        },
    )

answers = {
    "tool_risk": response.choices["tool_risk"],
    "irreversible": response.nouls["irreversible"],
    "blast_radius": response.scores["blast_radius"],
}
```

> **로컬 환경 확인**  
> 이 작업 환경에는 `TYPESAFE_API_KEY`가 없었습니다. 인증하지 않은 `POST /v1/systemone`은 `403 authentication_error`를 반환했습니다.  
{: .prompt-warning}

따라서 여기서는 직접 모델의 latency, output, billing을 주장하지 않습니다. 위 SDK 호출은 key가 있는 환경에서 shadow data를 수집할 request shape입니다. 로컬에서 확인한 것은 response field를 조합하는 offline policy fixture입니다.

```python
def shadow_or_escalate(answers):
    risk = answers["tool_risk"]
    irreversible = answers["irreversible"]
    blast_radius = answers["blast_radius"]

    if (
        risk.choice != "bounded"
        or risk.confidence < 0.90
        or irreversible.noul >= 0.10
        or blast_radius.score >= 2
        or blast_radius.confidence < 0.90
    ):
        return "escalate"
    return "shadow"
```

offline fixture에서는 다음처럼 분류됐습니다.

- `git status --short`는 `shadow`. 실행 허가가 아니라 평가 후보라는 뜻
- `rm -rf ./build`와 `kubectl delete namespace production`은 `escalate`
- `0.90`, `0.10`, `2`는 검증된 운영 threshold가 아니라 typed field와 deterministic policy 조합을 보이는 예시

---

## 5. model ID, 요금, 한도도 판단 계약의 일부입니다

Jev는 2026-09-15 early access로 출시됐습니다. 2026-09-22 기준 문서는 Jev 1.13과 model ID `jev-1.13.0`을 안내합니다.

| 항목 | 당시 문서상 값 | 운영에서 할 일 |
|---|---|---|
| alias | `jev-latest`, `jev-preview`도 확인 시점에는 `jev-1.13.0`을 가리킴 | alias는 이동할 수 있으므로 calibrated threshold에는 pin한 model ID 기록 |
| 가격 | input 1 MTok당 $0.042, output 무료 | 비용 추정 시 문서 갱신 여부 확인 |
| dynamic rate limit | 초당 250,000 tokens, 분당 1,200 requests | admission control의 고정 상수로 사용하지 않음 |
| API와 오류 | `POST /v1/systemone`, 문서화한 주요 오류는 401, 422, 429, 529 | timeout, 429, 529, 예상하지 못한 인증 오류는 unavailable 또는 unknown으로 취급하고 fail closed |

`0.90` 같은 경계값을 배포한다면 alias가 아니라 `jev-1.13.0`을 pin하고, request log에 model ID와 question option 순서를 남겨야 합니다. Jev 1.13 문서가 별도로 다루는 jaggedness도 경계값 근처 사례를 model release마다 다시 시험해야 하는 이유입니다.

| TypeSafe가 제시한 수치 | 해석 경계 |
|---|---|
| 응답 시간 70~500ms | 네 workflow에서 측정한 값 |
| 193.6배 빠름, 444.6배 저렴함 | 독립 검증이 아닌 TypeSafe vendor benchmark |
| benchmark label | human ground truth가 아니라 GPT-6 Astra와 Claude Fable 5.1 high-thinking 응답의 평균 |

**이 vendor benchmark는 비용과 속도 가설의 근거는 될 수 있어도, 특정 운영 task의 정답률이나 안전성을 보증하지는 않습니다.**

---

## 6. 외부 평가는 빠른 좁은 판단의 조건을 보여줍니다

독립 사례는 vendor 수치보다 구체적인 사용 조건을 제공하지만, 어느 하나도 일반 성능표는 아닙니다.

| 출처와 구성 | 관측값 | 해석 경계 |
|---|---|---|
| LangChain의 고정 weather trace 다섯 개를 각각 100회 실행 | binary oracle agreement 500/500, 평균 0.44초, 호출당 추정 $0.00035 | trace가 매우 작고 Jev service version이 기록되지 않음 |
| Archestra의 production Claude Code trace 100개, 판단 400개 | 세 judge family가 합의한 337개에서 Jev zero-shot 93%, 9-shot 95%, Sonnet 5 98%, constant baseline 79% | 합의 filter는 human ground truth와 다르며 dangerous-call refusal recall은 7/9 |
| Every의 문서 검토 | 문서 37개와 question 21개로 777 judgments를 0.7초 미만, 추정 quarter-cent에 처리 | 대다수 항목에 gold label이 없었고 synthetic passage 12개에서는 Jev가 defect 7개 중 6개, Fable 5.1은 7개를 찾음 |

Archestra의 결과는 확률을 authorization 값으로 그대로 쓰기 어려운 신호도 남깁니다.

- 같은 payload의 probability 최대 drift는 0.17
- baseline noise를 뺀 뒤에도 세 option Choice의 option order를 바꾸자 약 100개 판단 중 4개가 달라짐
- dangerous call을 모두 거절하지 못한 refusal recall은 7/9

이 신호 때문에 높은 평균 정확도를 실행 허가 규칙으로 바꿀 수는 없습니다. option text와 순서는 prompt formatting이 아니라 harness의 versioned contract로 다뤄야 합니다. LangChain 결과는 작은 고정 trace에서 latency와 반복 일치성이 좋았다는 evidence이고, Every 결과는 대량 문서 질문을 빠르게 처리할 가능성을 보입니다. **빠르고 저렴하다는 약속은 좁은 판단에서 설득력이 있지만 correctness는 입력 분포와 task에 따라 달라집니다.**

---

## 7. Jev는 사실 확인과 authorization 사이의 좁은 판단 계층입니다

| 수단 | 강한 지점 | Jev와의 관계 |
|---|---|---|
| deterministic code | canonical parsing, 정확한 산술, 날짜와 개수 비교 | Jev 전후에 유지하는 사실 확인 계층 |
| Jev | 제한된 semantic judgment와 확률 기반 triage | shadow signal 또는 escalation 입력 |
| 일반 LLM structured output | 넓은 설명과 생성, 구조화한 응답 | schema가 있어도 semantic correctness는 별도 검증 |
| small classifier 또는 reranker | label이 충분한 고정 task의 고처리량 분류 | Jev evaluation의 비교 기준 또는 대체 후보 |
| OPA 또는 Cedar policy | 명시적인 authorization rule과 권한 판정 | 최종 권한과 deny rule을 구현하는 계층 |

Jev의 장점은 모든 policy를 대체하는 데 있지 않습니다. 기존 rule이 표현하지 못하는 좁은 의미 판단을 확률 신호로 제공하고, policy가 그 신호를 보수적으로 결합할 수 있다는 데 있습니다.

resource existence, caller entitlement, lock 보유 여부, maintenance window는 model inference 없이 결정할 수 있는 사실입니다. 이를 먼저 확인하면 model에 전달하는 `state`가 작아지고 context rot 위험도 줄어듭니다.

---

## 8. 비가역 실행은 Jev 하나로 승인하지 않습니다

> **비가역적이거나 blast radius가 큰 실행은 Jev만으로 authorize해서는 안 됩니다.**  
> canonicalized argument 재검증, authorization policy, 대상 환경 확인, 변경 승인, 필요하면 사람의 명시적 승인을 함께 통과시킵니다.  
{: .prompt-danger}

| 조건 | 처리 |
|---|---|
| Jev unavailable, unknown field, schema validation 실패 | `escalate`로 fail closed |
| 초기 연동 | 실제 호출과 병렬로 판단 결과만 기록하는 shadow mode |
| provider 전송 전 | `state` 최소화와 민감정보 제거, retention, training use, subprocessor, data processing 조건 확인 |
| shadow audit | 요청 ID, pin한 model ID, question/parser/policy version, option order, typed answer와 probability, policy result, redacted state digest, eventual outcome label 참조 |
| adversarial evaluation | prompt injection, 모순된 approval 문구, 우회 표현, 관계없는 긴 state, locale별 tool argument 포함 |
| model, option wording, parser, policy 변경 | 이전 threshold를 재사용하지 않고 calibration 재평가 |

TypeSafe 문서에서는 `customer requests or responses`로 학습하지 않는다고 설명합니다. 이 문장만으로 모든 보관 조건과 계약까지 검증됐다고 확대하지 않습니다. 실행되지 않은 위험 요청의 실제 결과는 알기 어려우므로 reviewer label, simulator 결과, 변경 기록을 분리하고 disagreement 사례를 보존합니다. threshold는 전체 평균보다 위험 등급별 false allow와 dangerous-call recall을 기준으로 조정합니다.

자동 model fallback은 이 정책에 넣지 않습니다. primary Jev 요청이 실패했을 때 일반 LLM이나 다른 model이 같은 실행 결정을 대신하면 evaluation하지 않은 model과 prompt 경로가 authorization 경계에 들어옵니다. **실패한 판단은 더 강한 자동화가 아니라 `escalate`로 처리해야 합니다.**

---

## 9. Reference

- [TypeSafe AI - Introducing System One Models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [TypeSafe AI Docs - System One](https://docs.typesafe.ai/concepts/system-one)
- [TypeSafe AI Docs - Models and aliases](https://docs.typesafe.ai/models)
- [TypeSafe AI Docs - Choice, Score, and Noul primitives](https://docs.typesafe.ai/primitives)
- [TypeSafe AI Docs - System One API](https://docs.typesafe.ai/api)
- [TypeSafe AI Docs - Confidence](https://docs.typesafe.ai/confidence)
- [TypeSafe AI Docs - Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [TypeSafe AI Docs - Python SDK](https://docs.typesafe.ai/sdk/python)
- [TypeSafe AI - Workflow evals](https://evals.typesafe.ai/)
- [LangChain Blog - Jev-as-a-Judge for Agent Evals](https://langchain.com/blog/jev-agent-evals-langsmith)
- [Daniel G. Shea - Jev evaluator reproducible source tree](https://github.com/danielgshea/jev-as-a-judge/tree/adfea74905f721ea2594e22804c8c8edf1693163)
- [Archestra - Jev on 100 real agent calls](https://archestra.ai/blog/we-tested-jev-on-100-real-agent-calls)
- [Every - Jev document judgment experiments](https://every.to/also-true-for-humans/mini-vibe-check-typesafe-s-jev-judged-everything-i-ve-written-in-0-7-seconds)
- [LangChain Docs - TypeSafe integrations](https://docs.langchain.com/oss/python/integrations/providers/typesafe)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
