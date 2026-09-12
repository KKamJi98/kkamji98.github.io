---
title: "LiteLLM - 배포 관측과 0 예산 키의 요청 거절 [AI Gateway 3]"
date: 2026-07-13 01:47:00 +0900
last_modified_at: 2026-09-08 00:00:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [litellm, llm-gateway, ai-gateway, kubernetes, helm, study]
comments: true
image:
  path: /assets/img/ai/gateway/litellm.webp
---

LiteLLM에서 `max_budget: 0`으로 발급한 virtual key는 지출이 `0.0`인 상태에서도 HTTP 429로 거절됐습니다. 다른 키의 mock 호출은 당시 실행 요약에 HTTP 200으로 기록됐으며, 도구 출력에서 `usage.total_tokens: 30`과 `/key/info`의 `spend: 0.0`을 확인했습니다. **성공 응답의 토큰 수와 누적 비용은 구분해서 읽어야 합니다.**

2026-08-31 홈랩 Kubernetes 실행 기록에는 mock 응답과 키 조회 결과, 0 예산 요청의 HTTP 429와 오류 본문이 남아 있습니다. 아래 내용은 키 식별자를 제거한 배포 관측 기록입니다. 당시 chart revision과 이미지 digest는 이번 대조에서 확인하지 못해 고정 버전 설치 절차로 제시하지 않습니다.

발행일 이후의 배포 관측을 반영했으며, 2026-09-08에 실행 기록과 공식 문서 및 소스를 대조해 설명을 갱신했습니다.

---

## 1. Proxy 설정과 DB에 저장하는 상태

{% include diagrams/static/ai/litellm-architecture.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/litellm-architecture--39ece6e6e8007745.png" %}

LiteLLM Proxy는 클라이언트와 LLM provider 사이에서 OpenAI 호환 HTTP 요청을 받는 독립 프록시입니다. 클라이언트는 Gateway endpoint와 발급된 키를 사용해 HTTP 또는 호환 SDK로 호출합니다.

그림에서 요청을 중계하는 Proxy와 배포 및 상태 관리 구성 요소를 구분했습니다. 당시 선택한 chart 구성에는 LiteLLM Proxy, PostgreSQL, DB 스키마를 준비하는 migration Job이 있었습니다. migration Job은 chart 설정에 따라 배포 시점에 실행합니다. 추론 요청은 Proxy가 처리합니다.

PostgreSQL은 API로 발급한 virtual key, 예산, 소비 기록 등 관리 상태를 영속화합니다. 모델 목록과 라우터 설정은 YAML로 정의할 수 있고, 환경변수와 Secret도 구성에 참여합니다. 모델을 DB에 저장할지는 `store_model_in_db` 같은 설정에 따라 달라집니다. 키는 Proxy 재배포 없이 API로 발급할 수 있습니다. 상태를 읽고 갱신하는 시점은 Proxy의 캐시와 동기화 방식에 따라 달라집니다.

공식 chart 소스 경로는 `helm/litellm-helm`입니다. 공식 배포 문서는 `oci://ghcr.io/berriai/litellm-helm`을 통한 Helm 설치도 안내합니다. 이 배포에서는 홈랩 저장소에 chart를 vendoring해 사용했습니다. Reference의 고정 revision은 설정과 주석을 대조한 근거이며, 당시 vendoring한 chart commit을 뜻하지 않습니다.

당시 `db.deployStandalone: true`로 PostgreSQL을 함께 배포했습니다. 의존성의 `14.3.1`은 Bitnami `postgresql` 서브차트 버전이며 PostgreSQL 서버 버전이 아닙니다. 실제 DB 서버 버전은 이번 대조에서 확인하지 못했습니다.

---

## 2. 이미지 조회 실패와 메모리 제한

2026-08-31 기록에는 GHCR의 `main-v1.99.0-stable` 이미지 조회에 실패해 `litellm/litellm:v1.98.0`을 사용한 것으로 남아 있습니다. 조회 실패의 원인은 당시 오류 응답과 배포 기록을 추가 대조해야 합니다. 이 이미지 선택은 당시 관측이며 현재 권장 버전은 아닙니다.

배포 중 `OOMKilled`가 발생했고 메모리 limit을 `3Gi`로 높인 뒤 기동이 안정됐다는 기록이 있습니다. 실패 당시 Pod의 limit은 이번 대조에서 확정하지 못했습니다. 기동 성공만으로 `3Gi`를 제품의 최소 메모리나 장기 운영 안정성 기준으로 사용할 수는 없으며, **운영 부하에 맞춘 별도 측정이 필요합니다**.

Reference에 고정한 chart 소스의 주석은 DB 연결과 트래픽을 고려해 worker당 약 1 CPU와 4Gi를 권고합니다. 리소스 산정에는 이 권고와 운영 부하 측정을 함께 사용해야 합니다. 이번 OOM의 구체적인 원인은 추가 진단이 필요합니다.

---

## 3. master key가 envFrom 값으로 바뀌지 않은 이유

SSM SecureString에 저장한 master key를 ExternalSecret으로 Kubernetes Secret에 동기화하고 `envFrom`으로 주입했지만 인증 실패가 계속됐습니다. 당시 chart의 Deployment는 `PROXY_MASTER_KEY`를 자체 생성 Secret의 `secretKeyRef`로 명시적으로 선언하고 있었습니다.

Kubernetes에서 같은 이름의 환경변수가 겹치면 명시적인 `env` 값이 `envFrom`보다 우선합니다. 따라서 Secret 동기화가 성공해도 Proxy가 기대한 값을 사용하는 것은 아니었습니다. chart의 `masterkeySecretName`과 `masterkeySecretKey`를 ESO가 생성한 Secret의 이름과 데이터 키에 맞추어 해결했습니다. **확인해야 할 대상은 Secret 존재 여부뿐 아니라 Deployment가 실제로 참조하는 Secret과 키 이름입니다.**

**ESO가 Secret을 갱신해도 이미 실행 중인 컨테이너의 환경변수는 자동으로 바뀌지 않습니다.** 당시에는 Secret 갱신 후 rollout restart로 새 값을 반영했습니다. 이는 환경변수로 주입하는 방식의 특성이며 Secret volume이나 애플리케이션의 동적 재로딩 동작과는 구별해야 합니다.

---

## 4. virtual key 발급과 mock 응답

{% include diagrams/static/ai/litellm-virtual-key-flow.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/litellm-virtual-key-flow--4701f8019d165145.png" %}

관리자는 master key로 `/key/generate`를 호출해 키를 발급하고, 클라이언트는 발급된 virtual key로 추론을 요청합니다. master key는 관리 경로에서만 사용하도록 분리합니다. 그림의 키 발급은 사전 관리 작업이고, 발급된 키를 검증하는 추론 경로는 별도입니다. 이 경로에서 성공한 mock 호출은 아래의 사용량 및 키 조회 결과로, 0 예산 키의 거절은 5절의 오류 응답으로 구분해 확인했습니다.

당시 키 발급에 사용한 요청 본문은 다음과 같습니다. 발급 응답 원문과 키 값은 포함하지 않습니다.

```json
{
  "key_alias": "blog-test-key",
  "max_budget": 0.5,
  "budget_duration": "1h"
}
```

발급된 키로 `/v1/chat/completions`의 mock 모델을 호출했습니다. 모델에는 `mock_response`를 설정했습니다. 다음은 실행 기록에서 키 식별자를 제거한 관측 요약입니다.

- 추론 요청: 당시 실행 요약의 HTTP 200, 도구 출력의 응답 문구 `Mock reply from litellm lab.`
- 응답 usage: `total_tokens: 30`
- `/key/info` 조회: `spend: 0.0`

mock 응답의 토큰 수는 LiteLLM이 반환한 모의 사용량입니다. 이 호출로 mock 응답과 키 조회 동작을 확인했습니다. `spend: 0.0`은 양수 비용 집계의 증거가 아니므로 실제 비용 추적은 유료 provider 호출의 spend 증가와 청구액을 대조해 검증해야 합니다.

---

## 5. 0 예산 키의 경계값 거절

`max_budget: 0`인 키를 별도로 발급하고 같은 mock 모델을 호출했을 때는 HTTP 429가 기록됐습니다. 당시 도구 출력에는 HTTP status와 오류 본문 앞부분이 있습니다. 아래는 키 식별자를 마스킹한 관측 요약이며 전체 HTTP 헤더 덤프는 아닙니다.

```text
HTTP status: 429
message: Budget has been exceeded! [키 식별자 생략] Current cost: 0.0, Max budget: 0.0
type: budget_exceeded
param: null
code: "429"
```

`v1.98.0`의 키 예산 검사 소스는 유한 예산에 대해 `spend >= max_budget`을 검사합니다. 지출 `0.0`과 예산 `0.0`이 같은 경우도 거절 조건에 포함됩니다. **이번 결과는 비용 누적에 따른 초과가 아닌 개별 키의 0 예산 경계값 거절에 해당합니다.**

키 예산 검사와 팀 예산 검사는 별도입니다. 당시 실험은 개별 키를 대상으로 했으며 팀 생성과 `team_id` 연결, 여러 키의 예산 합산은 시험하지 않았습니다. 소스에서는 인증 단계의 예산 검사를 확인할 수 있지만, provider 수신 로그나 네트워크 trace를 통한 upstream 미수신 여부는 이번 실험의 관측 범위 밖입니다.

**양수 예산의 비용 통제를 검증하려면 요청 허용, 요청별 비용과 누적 spend 증가, 후속 요청 거절을 같은 실험에서 연결해야 합니다.** 동시 요청에 따른 초과 사용량과 비용 반영 지연도 함께 측정해야 실제 운영 상한을 정할 수 있습니다.

---

## 6. Reference

- [LiteLLM Docs - Deployment](https://docs.litellm.ai/docs/proxy/deploy)
- [LiteLLM Docs - Proxy Configuration](https://docs.litellm.ai/docs/proxy/configs)
- [LiteLLM Docs - Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [LiteLLM Docs - Cost Tracking](https://docs.litellm.ai/docs/proxy/cost_tracking)
- [LiteLLM Chart - Dependencies, fixed revision](https://github.com/BerriAI/litellm/blob/168a0055a244acdcf97c330c52e085ab40b1424c/helm/litellm-helm/Chart.yaml#L33-L37)
- [LiteLLM Chart - Worker resources, fixed revision](https://github.com/BerriAI/litellm/blob/168a0055a244acdcf97c330c52e085ab40b1424c/helm/litellm-helm/values.yaml#L184-L197)
- [LiteLLM Chart - Master key environment, fixed revision](https://github.com/BerriAI/litellm/blob/168a0055a244acdcf97c330c52e085ab40b1424c/helm/litellm-helm/templates/deployment.yaml#L120-L124)
- [LiteLLM v1.98.0 - Key budget checks](https://github.com/BerriAI/litellm/blob/v1.98.0/litellm/proxy/auth/auth_checks.py#L3917-L3933)
- [Kubernetes API - Container env and envFrom](https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/pod-v1/#environment-variables)
- [Kubernetes Docs - Secret environment variables](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/#define-container-environment-variables-using-secret-data)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
