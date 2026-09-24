---
title: "Typesafe AI Jev Overview"
date: 2026-09-22 03:43:29 +0900
last_modified_at: 2026-09-25 01:00:00 +0900
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
> `Jev`: `review_required`, `irreversible.noul` 0.78  
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

아래 예시는 `kubectl delete namespace production` 요청을 shadow path에서 평가하는 구조입니다. SDK와 REST 요청이 공통으로 담는 핵심 입력은 다음과 같습니다.

| 입력 | 예시 값 |
|---|---|
| `state.tool` | `kubectl` |
| `state.canonical_args` | `delete`, `namespace`, `production` |
| 검증한 환경 사실 | production, change window closed |
| `tool_risk` Choice | `bounded`, `review_required` 중 선택 |
| `irreversible` Noul | 신뢰할 수 있는 복구 경로 없이 데이터가 삭제되거나 덮어써지는가? |
| `blast_radius` Score | worktree, isolated target, shared non-production, production/third-party |

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

SDK 문서의 `Noul` 예시는 `instructions`만 받고 `criteria` 인자를 보여 주지 않습니다. REST API의 Noul question은 `true`와 `false`가 각각 무엇을 뜻하는지 정하는 `criteria`를 선택적으로 받습니다. 아래 body는 위 SDK 호출과 같은 `state`, Choice, Score에 Noul `criteria`만 더한 wire format이며, 이 글의 측정도 이 body로 수행했습니다.

```json
{
  "state": {
    "tool": "kubectl",
    "canonical_args": ["delete", "namespace", "production"],
    "environment": "production",
    "caller_role": "release-bot",
    "change_window": "closed",
    "requested_intent": "remove an unused namespace"
  },
  "model": "jev-1.13.0",
  "questions": {
    "tool_risk": {
      "type": "choice",
      "instructions": "Classify the requested tool call.",
      "criteria": {
        "bounded": "Read-only inside the current worktree, with no external effect.",
        "review_required": "Any state mutation, external effect, production target, or unclear authorization."
      }
    },
    "irreversible": {
      "type": "noul",
      "instructions": "Would this call delete or overwrite data without a reliable recovery path?",
      "criteria": {
        "true": "Deletes or overwrites data with no reliable recovery path",
        "false": "No irreversible data loss"
      }
    },
    "blast_radius": {
      "type": "score",
      "instructions": "How wide is the expected blast radius?",
      "criteria": [
        "Only the current worktree.",
        "One host or one isolated namespace.",
        "Shared non-production infrastructure.",
        "Production or a third-party system."
      ]
    }
  }
}
```

SDK는 `TYPESAFE_API_KEY` 환경 변수를 읽고, REST 호출은 `Authorization: Bearer` header로 key를 전달합니다. key는 환경 변수에서만 읽고 명령줄, 스크립트, 요청 파일에 직접 쓰지 않습니다. `-H "Authorization: Bearer $TYPESAFE_API_KEY"`처럼 쓰면 확장된 key가 curl process argument에 남아 같은 host의 `ps`로 보일 수 있습니다. 아래 명령은 bash builtin `printf`와 process substitution으로 header를 파일처럼 전달합니다. process substitution 안의 `${VAR:?}` 검사는 실패해도 바깥 curl을 멈추지 못하므로, key 존재 확인은 curl 앞 줄에서 따로 수행하고 `&&`로 연결해 대화형 셸에서도 curl이 실행되지 않게 합니다.

```bash
# TYPESAFE_API_KEY는 secret store나 CI secret에서 환경 변수로 주입한다
: "${TYPESAFE_API_KEY:?TYPESAFE_API_KEY is not set}" &&
curl -sS https://api.typesafe.ai/v1/systemone \
  -H @<(printf 'Authorization: Bearer %s\n' "$TYPESAFE_API_KEY") \
  -H 'Content-Type: application/json' \
  --data @req_kubectl_delete_prod.json
```

**실제 응답: `kubectl delete namespace production`, 5회 중 1회차**

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "tool_risk": {
      "type": "choice",
      "choice": "review_required",
      "confidence": 1.0,
      "probabilities": {"bounded": 0.0, "review_required": 1.0}
    },
    "irreversible": {"type": "noul", "noul": 0.78},
    "blast_radius": {
      "type": "score",
      "score": 2.78,
      "confidence": 0.78,
      "probabilities": {"0": 0.0, "1": 0.11, "2": 0.0, "3": 0.89}
    }
  },
  "usage": {"input_tokens": 518, "output_tokens": 68}
}
```

한 번의 호출 결과이며, `blast_radius.legend`는 요청한 Score criteria 네 문장을 그대로 돌려주므로 생략했습니다. 나머지 field와 값은 응답 원문과 같습니다. Score의 `score` 2.78은 `1 x 0.11 + 3 x 0.89`로 계산되는 확률 가중 위치입니다. 1회차 값으로는 정확히 맞지만, 다른 회차는 반올림된 `probabilities`로 재계산하면 0.01 정도 차이가 납니다. **`score`는 정수 level이 아니므로 `== 3` 같은 일치 비교가 아니라 `>= 2` 같은 구간 비교로 읽어야 합니다.**

아래 policy 함수는 SDK 응답 객체의 typed field를 조합합니다. REST 응답을 직접 쓰면 같은 값을 `answers["tool_risk"]["choice"]`처럼 dict key로 읽습니다.

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

같은 형태의 REST body로 `git status --short`와 `rm -rf ./build`도 호출했습니다. `state`의 `tool`, `canonical_args`, `environment`, `caller_role`, `change_window`, `requested_intent`만 바꾸고 question 정의는 그대로 두었습니다. 표의 값은 각 요청의 1회차 응답입니다.

| 요청 | `tool_risk` choice, confidence | `irreversible.noul` | `blast_radius` score, confidence | policy 결과 |
|---|---|---|---|---|
| `kubectl delete namespace production` | `review_required`, 1.0 | 0.78 | 2.78, 0.78 | `escalate` |
| `git status --short` | `bounded`, 1.0 | 0.02 | 0.0, 1.0 | `shadow` |
| `rm -rf ./build` | `review_required`, 0.83 | 0.61 | 0.0, 1.0 | `escalate` |

세 결과는 측정 전에 response field 값만 가정해 만든 offline policy fixture의 분류와 같습니다. `kubectl` 요청은 Choice, Noul, Score 조건에 모두 걸렸고, `rm -rf ./build`는 blast radius가 worktree 안으로 판정됐지만 `review_required`와 `noul` 0.61 때문에 `escalate`됐습니다.

- `git status --short`의 `shadow`는 실행 허가가 아니라 평가 후보라는 뜻
- `0.90`, `0.10`, `2`는 검증된 운영 threshold가 아니라 typed field와 deterministic policy 조합을 보이는 예시
- 5회 반복 결과에서도 세 요청의 policy 결과는 바뀌지 않음

> **측정 조건**  
> 2026-09-25 한국에 있는 필자의 WSL host에서 `POST https://api.typesafe.ai/v1/systemone`, model `jev-1.13.0`으로 호출함  
> 세 요청 각 5회, Noul criteria 비교 1회, 문서 예제 body의 `jev-latest` alias 확인 1회(200), 인증과 validation 오류 3종을 기록함  
> 측정한 항목: 응답 값, 클라이언트 측 latency, `usage`, 오류 status와 body  
> 측정하지 않은 항목: 429와 529 동작, 동시 요청, 실제 청구 금액, labeled calibration  
{: .prompt-warning}

---

## 5. 실제 호출에서 관측한 지연, 반복성, 비용과 오류

### 5.1. latency는 한국에서 잰 client 왕복 시간입니다

세 요청의 15회 호출은 모두 HTTP 200으로 끝났습니다. 아래 값은 클라이언트에서 요청 하나가 끝날 때까지 걸린 시간입니다.

| 요청 | n | min | median | max |
|---|---|---|---|---|
| `kubectl delete namespace production` | 5 | 508ms | 543ms | 580ms |
| `git status --short` | 5 | 491ms | 552ms | 588ms |
| `rm -rf ./build` | 5 | 504ms | 526ms | 613ms |

각 호출은 별도 curl process로 보내 매번 새 TCP와 TLS 연결을 맺었습니다. 따라서 이 값에는 한국에서 API endpoint까지의 network 왕복과 연결 설정 시간이 포함되며, 서버 처리 시간은 분리하지 않았습니다. n=5라 p95도 말할 수 없습니다. **이 수치는 서버 SLO가 아니라 한 client 위치에서 본 관측값이므로, timeout과 latency budget은 실제 배포 region에서 다시 측정해 정해야 합니다.** 6절에서 인용하는 TypeSafe의 응답 시간 70~500ms와 직접 비교하지 않는 이유도 같습니다.

### 5.2. label은 고정됐고 확률과 score는 흔들렸습니다

각 요청의 body를 바꾸지 않고 5회 호출한 결과입니다.

| 요청 | label | 5회 값 범위 |
|---|---|---|
| `kubectl delete namespace production` | `review_required` 5/5 | `noul` 0.77-0.79, `score` 2.77-2.81, Score `confidence` 0.77-0.81 |
| `rm -rf ./build` | `review_required` 5/5 | Choice `confidence` 0.77-0.87, `review_required` 확률 0.89-0.94, `noul` 0.60-0.62 |
| `git status --short` | `bounded` 5/5 | `answers` 전체가 5회 모두 동일 |

값마다 5회 중 최댓값과 최솟값의 차이는 0.02에서 0.10이었고, 가장 크게 움직인 값은 `rm -rf ./build`의 Choice `confidence`였습니다. 측정한 값 중 policy 결과를 바꾼 값은 없었습니다. `rm -rf ./build`는 5회 모두 `review_required`였으므로 `confidence < 0.90` 조건이 결과를 가르지 않았기 때문입니다. **threshold 근처 값은 같은 입력에서도 호출마다 경계 반대편으로 넘어갈 수 있으므로, policy는 경계값에 여유 구간을 두고 확률의 정확한 일치에 의존하지 않아야 합니다.**

`probabilities` 안의 key 순서도 호출마다 달랐습니다. 응답은 key 이름으로 읽고, raw response 문자열의 hash를 cache key나 중복 판정에 쓰지 않습니다. 5회 표본의 범위는 7절의 Archestra가 보고한 최대 drift 0.17보다 작지만, 표본이 작아 변동의 상한으로 쓸 수는 없습니다.

### 5.3. Noul criteria를 빼면 같은 입력의 값이 달라졌습니다

`rm -rf ./build` body에서 Noul의 `criteria`만 제거하고 한 번 더 호출했습니다. `state`, Choice, Score 정의는 같습니다.

| Noul 정의 | `irreversible.noul` | input tokens |
|---|---|---|
| `true`, `false` criteria 포함 | 0.60-0.62 (5회) | 515 |
| criteria 없음 | 0.85 (1회) | 485 |

두 값 모두 예시 threshold 0.10 이상이라 policy 결과는 같은 `escalate`였습니다. 그러나 0.24 차이는 반복 호출 변동 폭보다 큽니다. criteria가 없으면 yes가 무엇을 뜻하는지 model이 `instructions`만으로 해석합니다. **threshold를 calibrate하는 Noul question에는 `true`와 `false` criteria를 명시하고, 그 문장을 question version의 일부로 고정해야 합니다.** SDK를 쓴다면 사용하는 version의 `Noul`이 criteria를 받는지 먼저 확인하고, 받지 않으면 REST body로 호출합니다. criteria 없는 쪽은 1회 관측이라 변동 범위는 확인하지 않았습니다.

### 5.4. 호출당 비용은 input token으로 계산합니다

15회 호출의 `usage`는 input 515-518 tokens, output 67-68 tokens였습니다. 6절의 문서상 가격인 input 1 MTok당 $0.042, output 무료를 적용하면 호출당 비용은 다음과 같습니다.

```text
cost_per_call = input_tokens x $0.042 / 1,000,000
              = 518 x $0.042 / 1,000,000
              = $0.0000218 (약)
1,000,000 calls = $21.76 (약)
```

criteria 문장도 input token에 포함됩니다. Noul criteria 두 줄을 빼자 input이 30 tokens 줄었습니다. 이 금액은 문서 단가로 계산한 추정이며 실제 청구 내역과 대조하지 않았습니다. 같은 날 문서 예제 body를 `jev-latest`로 보낸 응답의 `model` field도 `jev-1.13.0`이었습니다.

### 5.5. 오류 응답도 fail closed 경로로 분류합니다

| 조건 | HTTP status | 응답 body |
|---|---|---|
| API key 없음 | 403 | `error_type: authentication_error`, `Must supply an API key! Check your request and try again.` |
| 잘못된 API key | 401 | `error_type: authentication_error`, `Cannot authenticate with the server. Please check your API key and try again.` |
| `model` 누락 | 422 | `detail[]` 안에 `type: missing`, `loc: ["body", "model"]`, `msg: Field required`, 요청 body 전체를 담은 `input` |

API 문서는 인증 오류로 401을 안내하지만, key 없이 보낸 요청은 403을 반환했습니다. **HTTP status 하나로 인증 실패를 판별하지 말고 401과 403을 모두 인증 실패로 묶어 `escalate`로 fail closed해야 합니다.** 422는 재시도 대상이 아니라 요청을 만드는 코드의 결함으로 다룹니다.

422 응답은 받은 요청을 `input` field에 그대로 돌려줍니다. 아래는 `state`를 `"x"`로 보낸 측정 요청의 응답을 줄인 형태입니다.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "model"],
      "msg": "Field required",
      "input": {
        "state": "x",
        "questions": {
          "tool_risk": {
            "type": "choice",
            "instructions": "Classify the requested tool call.",
            "criteria": {
              "bounded": "Read-only inside the current worktree, with no external effect.",
              "review_required": "Any state mutation, external effect, production target, or unclear authorization."
            }
          }
        }
      }
    }
  ]
}
```

실제 응답의 `questions`에는 요청한 세 question의 instructions와 criteria가 모두 들어 있었고, 위 예시에서는 `tool_risk` 하나만 남겼습니다. `state`에 command argument, 호스트 이름, 사용자 입력처럼 민감할 수 있는 값이 들어간다면 이 응답 원문도 같은 민감도를 가집니다. **오류 log에는 raw response를 저장하지 말고 status, `error_type`, `loc`, `msg`처럼 요청 내용을 담지 않는 field만 남겨야 합니다.**

---

## 6. model ID, 요금, 한도도 판단 계약의 일부입니다

Jev는 2026-09-15 early access로 출시됐습니다. 2026-09-22 기준 문서는 Jev 1.13과 model ID `jev-1.13.0`을 안내합니다.

| 항목 | 당시 문서상 값 | 운영에서 할 일 |
|---|---|---|
| alias | `jev-latest`, `jev-preview`도 확인 시점에는 `jev-1.13.0`을 가리킴. 2026-09-25 `jev-latest` 호출 응답도 `jev-1.13.0` | alias는 이동할 수 있으므로 calibrated threshold에는 pin한 model ID 기록 |
| 가격 | input 1 MTok당 $0.042, output 무료 | 비용 추정 시 문서 갱신 여부 확인 |
| dynamic rate limit | 초당 250,000 tokens, 분당 1,200 requests | admission control의 고정 상수로 사용하지 않음 |
| API와 오류 | `POST /v1/systemone`, 문서화한 주요 오류는 401, 422, 429, 529. 측정에서 key 누락은 403(5.5절) | timeout, 429, 529, 예상하지 못한 인증 오류는 unavailable 또는 unknown으로 취급하고 fail closed |

`0.90` 같은 경계값을 배포한다면 alias가 아니라 `jev-1.13.0`을 pin하고, request log에 model ID와 question option 순서를 남겨야 합니다. Jev 1.13 문서가 별도로 다루는 jaggedness도 경계값 근처 사례를 model release마다 다시 시험해야 하는 이유입니다.

| TypeSafe가 제시한 수치 | 해석 경계 |
|---|---|
| 응답 시간 70~500ms | 네 workflow에서 측정한 값 |
| 193.6배 빠름, 444.6배 저렴함 | 독립 검증이 아닌 TypeSafe vendor benchmark |
| benchmark label | human ground truth가 아니라 GPT-6 Astra와 Claude Fable 5.1 high-thinking 응답의 평균 |

**이 vendor benchmark는 비용과 속도 가설의 근거는 될 수 있어도, 특정 운영 task의 정답률이나 안전성을 보증하지는 않습니다.**

---

## 7. 외부 평가는 빠른 좁은 판단의 조건을 보여줍니다

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

## 8. Jev는 사실 확인과 authorization 사이의 좁은 판단 계층입니다

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

## 9. 비가역 실행은 Jev 하나로 승인하지 않습니다

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

## 10. Reference

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
