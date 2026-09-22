---
title: "Jev - 타입과 확률로 만드는 빠른 판단 계층"
date: 2026-09-22 03:43:29 +0900
author: kkamji
categories: [AI, Development]
tags: [jev, system-one, typesafe-ai, agent, agent-harness, probabilistic-decision]
comments: true
image:
  path: /assets/img/ai/jev/jev-system-one-banner.webp
---

에이전트가 도구 호출 직전에 `kubectl delete namespace production`을 제안했을 때 JSON schema가 유효하다는 사실만으로는 실행해도 되는지 알 수 없습니다. 반대로 `git status --short`처럼 결과가 작업 트리 조회로 제한된 명령은 매번 대형 모델의 긴 추론을 붙이지 않아도 될 수 있습니다. 명령, 정규화한 인자, 대상 환경, 사용자의 의도를 한데 보고 위험도를 빠르게 분류하는 지점이 필요합니다.

Jev는 이 지점에 두는 호스팅 bounded probabilistic decision layer입니다. 상태와 타입이 정해진 질문을 전달하면 타입이 정해진 답과 확률을 받고, 그 결과를 deterministic policy가 해석합니다. **Jev는 LLM을 대체하는 생성 모델이 아니라 제한된 판단을 위한 보조 계층입니다.** 최종 실행 권한은 이 계층 밖에 남겨야 합니다.

---

## 1. 자유 텍스트 대신 판단 계약을 고정합니다

Jev 요청은 긴 대화의 다음 문장을 생성하는 인터페이스가 아닙니다. 공통 `state`에는 도구 이름, canonicalized argument, 리소스 범위, 호출자 역할, 검증한 사전 조건처럼 판단에 필요한 사실을 넣습니다. 각 question은 그 상태에 대해 어떤 종류의 답을 받아야 하는지 선언합니다. 호출자는 자연어 답변을 다시 파싱하지 않고 `choice`, `score`, `noul`과 각 primitive의 확률 필드를 policy 입력으로 사용합니다.

이 경계가 유용한 이유는 agent harness의 책임을 분리하기 때문입니다. Jev는 "이 요청이 비가역적인가", "영향 범위가 어느 구간인가", "분류 후보가 무엇인가" 같은 bounded question을 평가합니다. harness는 권한, 자원 존재 여부, 변경 창, 승인 기록, 실제 도구 실행을 담당합니다. state 안의 사용자 제공 문자열과 도구 설명은 판단 재료일 뿐 권한을 부여하는 명령이 아닙니다.

제약된 schema와 type 때문에 응답 형식이 정해져 있다는 뜻으로 `hallucination-free`라는 표현이 쓰이기도 합니다. **이는 schema 밖의 문장을 만들기 어렵다는 뜻이지, 특정 판단의 의미가 항상 옳다는 보장은 아닙니다.** 예를 들어 production namespace라는 문자열을 state에 넣었다고 해도 실제 대상이 의도한 리소스인지, 정책상 삭제가 허용되는지는 별도 검사해야 합니다.

---

## 2. Choice, Score, Noul은 같은 확률을 반환하지 않습니다

Jev의 세 primitive는 정책이 받을 값의 모양을 먼저 정합니다. Choice와 Score의 confidence를 Noul에 그대로 기대하면 threshold의 의미가 바뀝니다.

| primitive | 반환값과 확률 | 적합한 판단 |
|---|---|---|
| Choice | 유한한 option 중 하나를 `choice`로 반환하고, `probabilities`와 분포에서 유도한 `confidence`를 함께 반환 | 도구 위험 등급, 담당 queue, 검토 경로 선택 |
| Score | 순서형 level 사이의 확률 가중 위치를 `score`로 반환하고, `legend`, `probabilities`, `confidence`를 함께 반환 | 영향 범위나 증거 강도처럼 순서가 있는 등급 |
| Noul | `noul` 자체가 yes일 확률 | 비가역성, 민감정보 노출 가능성처럼 이진 사건의 확률 |

Choice의 `confidence`는 선택한 option이 맞다는 개인별 보증서가 아닙니다. Score도 점수에 대한 임의의 자기 진술 confidence가 아니라 반환 분포에서 나온 값입니다. Noul은 Boolean으로 축소하기 전에 `noul`이 yes probability라는 사실을 유지해야 합니다. 예를 들어 `irreversible.noul`에 경계값을 적용하는 것과 `risk_choice.confidence`에 경계값을 적용하는 것은 서로 다른 질문을 정책으로 옮기는 일입니다.

Calibration도 개별 응답의 정답 여부를 말하지 않습니다. 비슷한 확률 구간에 속한 많은 사례를 묶었을 때 예측 확률과 실제 빈도가 얼마나 맞는지를 평가하는 집단 수준 성질입니다. **하나의 응답이 높은 confidence를 보였더라도 그 요청 하나의 정확성을 증명하지는 않습니다.** calibration을 이용하려면 배포할 task, 입력 분포, 고정한 모델 버전으로 별도의 labeled evaluation을 해야 합니다.

운영 로그에서는 raw probability 하나만 저장하기보다 question ID, option set, model ID, 실제 사후 결과를 함께 연결해야 합니다. 그래야 threshold를 올리거나 내렸을 때 어떤 위험 등급에서 false allow와 불필요한 escalation이 바뀌는지 재현할 수 있습니다. label이 늦게 확정되는 task라면 그 지연도 calibration 표본의 일부로 관리해야 하며, 아직 결과를 모르는 요청을 정답 표본으로 섞어서는 안 됩니다.

---

## 3. 공유 state는 병렬 질문을 위한 공통 사실입니다

하나의 요청에서 여러 question은 같은 state를 공유하지만 서로의 answer를 읽는 순차 단계가 아닙니다. 서비스는 이 question들을 독립적으로 처리하고 병렬화합니다. 따라서 첫 번째 Choice의 결과에 따라 두 번째 Score의 질문 의미를 바꾸려는 설계는 한 요청 안에서 성립하지 않습니다. 실제 의존성이 있으면 애플리케이션이 첫 결과를 검증하고 다음 요청의 state를 구성해야 합니다. 이 방식은 추가 지연과 실패 경로를 함께 설계해야 합니다.

입력은 text-only입니다. string, JSON, text array를 state와 question에 전달할 수 있지만 image, audio, video는 직접 입력할 수 없습니다. 문서는 English에서 가장 강한 성능을 안내하며 CJK 입력은 같은 threshold를 재사용하지 말고 자체 evaluation을 요구합니다. 도구 인자와 리소스 메타데이터가 비영어권 문자열을 포함하는 harness라면 특히 locale별 positive, negative 사례를 나누어 측정해야 합니다.

문서상 전체 context 한도는 64k tokens이며 `state`와 모든 question이 이 예산을 공유합니다. 동시에 `state + 가장 긴 단일 question`에는 32k tokens 한도가 따로 있습니다. state를 계속 붙여 넣어 긴 audit log로 만들면 관계없는 정보가 판단을 흐리는 context rot도 커집니다. 원문을 그대로 읽는 일, 정확한 산술, 개수 세기, 날짜 비교, 간접 표현 해석, 적대적 content, 서로 모순되는 기준도 공식 한계에 포함됩니다. Jev는 생성 작업도 수행하지 않습니다. **정확해야 하는 산술, 날짜, 개수 계산은 Jev에 묻지 말고 code로 처리해야 합니다.**

state를 구성할 때는 확인한 사실과 model에게 묻는 해석을 섞지 않는 편이 안전합니다. 예를 들어 namespace 존재 여부, 호출자 role, approval ID, UTC timestamp의 날짜 비교 결과는 validator가 확정한 필드로 넣습니다. 긴 command history와 자유 형식 대화는 필요한 근거만 redact하고 요약하기 전에 보존 기준을 정합니다. 단순한 truncation은 위험한 앞부분이나 마지막 인자를 잃게 할 수 있으므로, 누락이 생기면 판단을 계속하지 않고 `escalate`하는 경로가 필요합니다.

---

## 4. 버전, 비용, 한도는 threshold와 함께 기록합니다

Jev는 2026-09-15 early access로 출시됐습니다. 2026-09-22 기준 문서는 Jev 1.13과 model ID `jev-1.13.0`을 안내합니다. `jev-latest`와 `jev-preview`도 확인 시점에는 모두 그 모델을 가리켰지만 alias는 이후 이동할 수 있습니다. calibration을 바탕으로 `0.90` 같은 경계값을 배포한다면 alias가 아니라 `jev-1.13.0`을 pin하고, request log에 model ID와 question option 순서를 남겨야 합니다. Jev 1.13 문서가 별도로 다루는 jaggedness도 경계값 근처의 사례를 모델 release마다 다시 시험해야 하는 이유입니다.

공식 문서의 당시 가격은 input 1 MTok당 $0.042이고 output은 무료입니다. 현재 dynamic rate limit은 초당 250,000 tokens, 분당 1,200 requests입니다. 이 값은 정적 계약값이 아니므로 admission control의 고정 상수로 두면 안 됩니다. API는 `POST /v1/systemone`이며 문서화한 주요 오류는 401, 422, 429, 529입니다. timeout, 429, 529, 예상하지 못한 인증 오류는 모두 unavailable 또는 unknown으로 취급해 policy에서 fail closed해야 합니다.

TypeSafe는 70에서 500ms의 응답 시간과 네 workflow에서 193.6배 빠르고 444.6배 저렴했다는 수치를 제시합니다. 이 두 배수는 독립 검증 결과가 아니라 **네 workflow에서 TypeSafe가 측정한 vendor benchmark**입니다. 그 benchmark의 label은 human ground truth가 아니라 GPT-6 Astra와 Claude Fable 5.1 high-thinking 응답을 평균낸 값입니다. 따라서 비용과 속도 가설을 세우는 근거는 될 수 있어도 특정 운영 task의 정답률이나 안전성을 보증하는 근거는 아닙니다.

---

## 5. 외부 평가는 빠른 좁은 판단과 task별 정확도를 함께 보여줍니다

독립 사례는 vendor 수치보다 더 구체적인 사용 조건을 보여주지만, 어느 하나도 일반 성능표는 아닙니다.

| 출처와 구성 | 관측값 | 해석 경계 |
|---|---|---|
| LangChain의 고정 weather trace 다섯 개를 각각 100회 실행 | binary oracle agreement 500/500, 평균 0.44초, 호출당 추정 $0.00035 | trace가 매우 작고 Jev service version이 기록되지 않음 |
| Archestra의 production Claude Code trace 100개, 판단 400개 | 세 judge family가 합의한 337개에서 Jev zero-shot 93%, 9-shot 95%, Sonnet 5 98%, constant baseline 79% | 합의 filter는 human ground truth와 다르며 dangerous-call refusal recall은 7/9 |
| Every의 문서 검토 | 문서 37개와 question 21개로 777 judgments를 0.7초 미만, 추정 quarter-cent에 처리 | 대다수 항목에 gold label이 없었고 synthetic passage 12개에서는 Jev가 defect 7개 중 6개, Fable 5.1은 7개를 찾음 |

Archestra 결과에는 확률을 그대로 authorization 값으로 쓰기 어려운 신호도 있습니다. 같은 payload의 probability 최대 drift는 0.17이었고, baseline noise를 뺀 뒤에도 세 option Choice의 option order를 바꾸자 약 100개 판단 중 4개가 달라졌습니다. option text와 순서는 prompt formatting이 아니라 harness의 versioned contract로 다뤄야 합니다. dangerous call을 모두 거절하지 못한 7/9 recall 역시 "높은 평균 정확도"를 실행 허가 규칙으로 바꾸지 못하게 합니다.

LangChain의 결과는 작은 고정 trace에서 latency와 반복 일치성이 좋았다는 evidence이고, Every의 결과는 대량의 문서 질문을 빠르게 처리할 가능성을 보입니다. 다만 둘 다 특정 task와 label 조건에 묶여 있습니다. **빠르고 저렴하다는 약속은 좁은 판단에서 설득력이 있지만, correctness는 입력 분포와 task에 따라 달라집니다.**

---

## 6. SDK 호출은 tool 실행과 분리한 shadow path에 둡니다

다음 예시는 공식 Python SDK의 Choice, Noul, Score를 함께 사용해 tool-risk를 분류하는 요청 형태입니다. `state`에는 raw shell 문자열만 넣지 않고 parser가 만든 canonical argument와 환경 정보를 넣습니다. model은 calibrated threshold를 배포한 버전으로 고정하고, 이 호출 결과만으로는 도구를 실행하지 않습니다.

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
                    "bounded": "Read-only or trivially reversible inside one repository, with no external effect.",
                    "ambiguous": "The target or authorization is unclear.",
                    "irreversible": "Deletes, overwrites, publishes, or makes a persistent external change.",
                },
            ),
            "irreversible": Noul(
                instructions="Would this call cause an irreversible change?",
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

이 작업 환경에는 `TYPESAFE_API_KEY`가 없었습니다. 인증하지 않은 `POST /v1/systemone`은 `403 authentication_error`를 반환했습니다. 따라서 여기서는 직접 모델의 latency, output, billing을 주장하지 않습니다. 위 코드는 key가 있는 환경에서 shadow data를 수집할 request shape이며, 로컬에서 확인한 것은 아래처럼 response field를 조합하는 offline policy fixture입니다.

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

offline fixture에서는 `git status --short`가 `shadow`로 분류됐습니다. 이는 실행 허가가 아니라 평가 후보라는 뜻입니다. `rm -rf ./build`와 `kubectl delete namespace production`은 모두 `escalate`로 분류됐습니다. 이 fixture는 typed field와 deterministic policy 조합을 시험한 결과일 뿐 Jev의 품질 평가나 실제 tool execution 증거가 아닙니다. 위 코드의 `0.90`, `0.10`, `2`도 검증된 운영 threshold가 아니라 구조를 보여주는 예시입니다.

---

## 7. 판단 도구의 자리를 분리하면 실패 경로가 보입니다

| 수단 | 강한 지점 | Jev와의 관계 |
|---|---|---|
| deterministic code | canonical parsing, 정확한 산술, 날짜와 개수 비교 | Jev 전후에 항상 유지하는 사실 확인 계층 |
| Jev | 제한된 semantic judgment와 확률 기반 triage | shadow signal 또는 escalation 입력 |
| 일반 LLM structured output | 넓은 설명과 생성, 구조화한 응답 | schema가 있어도 semantic correctness는 별도 검증 |
| small classifier 또는 reranker | label이 충분한 고정 task의 고처리량 분류 | Jev evaluation의 비교 기준 또는 대체 후보 |
| OPA 또는 Cedar policy | 명시적인 authorization rule과 권한 판정 | 최종 권한과 deny rule을 구현하는 계층 |

여기서 Jev의 장점은 모든 policy를 대체하는 데 있지 않습니다. 기존 rule이 표현하지 못하는 좁은 의미 판단을 확률 신호로 제공하고, policy가 그 신호를 보수적으로 결합할 수 있다는 데 있습니다. 반대로 resource existence, caller entitlement, lock 보유 여부, maintenance window는 model inference 없이 결정할 수 있는 사실입니다. 이 사실을 먼저 확인하면 model에게 주는 state도 작아지고 context rot 위험도 줄어듭니다.

---

## 8. 비가역 실행은 Jev 하나로 승인하지 않습니다

비가역적이거나 blast radius가 큰 실행은 Jev만으로 authorize해서는 안 됩니다. canonicalized argument를 deterministic validator로 다시 확인하고, OPA 또는 Cedar 같은 권한 policy, 대상 환경 확인, 변경 승인, 필요하면 사람의 명시적 승인을 함께 통과시켜야 합니다. Jev가 unavailable이거나 field가 unknown이거나 schema 검증에 실패하면 `shadow`를 계속할 수 없고 `escalate`로 fail closed합니다.

초기 배포에서는 실제 호출과 병렬로 결과만 기록하는 shadow mode를 먼저 둡니다. audit에는 요청 식별자, pin한 model ID, question과 parser 및 policy version, option order, typed answer와 probability, policy result, redacted state digest, 나중에 확정된 outcome label의 참조를 남깁니다. 민감한 원문이나 credential은 복제하지 않습니다.

로그에서 가리는 것만으로 provider 전송 경계가 해결되지는 않습니다. `state`는 전송 전에 최소화하고 민감정보를 제거해야 하며, production data를 보내기 전에는 TypeSafe의 현재 retention, training use, subprocessor, data processing 조건을 별도로 확인해야 합니다. 이 조사에서는 hosted API 문서와 "customer requests or responses로 학습하지 않는다"는 제품 설명을 확인했지만, 모든 보관 조건과 계약을 검증한 것으로 확대하지 않습니다. labeled adversarial corpus에는 prompt injection, 모순된 approval 문구, 우회 표현, 길고 관계없는 state, locale별 tool argument를 포함해야 합니다. threshold는 전체 평균이 아니라 위험 등급별 false allow와 dangerous-call recall을 보고 정합니다.

shadow 결과를 실제 결과와 대조할 때도 correlation만으로 rule을 넓히면 안 됩니다. 특히 실행되지 않은 위험한 요청은 안전했는지 사후에 알기 어렵습니다. reviewer가 확정한 label, simulator 결과, 변경 기록처럼 근거의 종류를 분리하고 disagreement 사례를 별도로 보관해야 합니다. option wording, parser version, policy version 중 하나라도 바뀌면 이전 threshold의 calibration을 그대로 이식하지 않습니다.

자동 model fallback은 이 정책에 넣지 않습니다. primary Jev 요청이 실패했을 때 일반 LLM이나 다른 model이 같은 실행 결정을 대신하면 evaluation하지 않은 모델과 prompt 경로가 authorization 경계에 들어옵니다. **실패한 판단은 더 강한 자동화가 아니라 `escalate`로 처리해야 합니다.**

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
