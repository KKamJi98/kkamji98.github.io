---
title: "LiteLLM 알아보기 - 앱 레벨 LLM 게이트웨이 실습 [AI Gateway 3]"
date: 2026-08-29 01:47:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [litellm, llm-gateway, ai-gateway, kubernetes, helm, study]
comments: true
image:
  path: /assets/img/ai/gateway/litellm.webp
---

시리즈 1편에서 LLM Gateway가 키와 비용과 감사를 한 지점에 모은다고 정리했고, 2편에서 Envoy AI Gateway가 그 일을 인그레스 데이터플레인에서 처리하는 걸 봤습니다. 이번 3편은 반대쪽 축인 LiteLLM을 실제로 배포하고, virtual key 발급부터 예산 초과 거절까지 직접 확인한 기록입니다.

지난 글들이 개념 비교였다면 이번 글은 홈램 Kubernetes에 올리고 손으로 확인한 관측이 중심입니다. 2026-08-31 기준입니다.

> **TL;DR**  
> - 공식 Helm chart로 proxy + PostgreSQL + migration Job 구성을 배포한다  
> - master key는 SSM SecureString에 두고 ExternalSecret으로 주입한다  
> - virtual key에 예산을 걸면 소비 추적이 시작되고, 예산을 넘으면 429로 거절한다  
> - 앱 레벨과 데이터플레인의 선택은 결국 조직 구조의 문제다  
{: .prompt-info}

---

## 1. 배포 구조

![LiteLLM proxy의 Kubernetes 배포 구조](/assets/img/ai/litellm-architecture.webp)

LiteLLM proxy의 배포 단위는 세 가지로 묶입니다.

- litellm proxy: OpenAI 호환 요청을 받아 라우팅하고 인증하는 본체
- PostgreSQL: virtual key, 예산, 소비 기록을 저장하는 설정의 단일 진실원천
- migration Job: 배포마다 DB 스키마를 맞추는 전용 잡

DB가 설정의 단일 진실원천이라는 점이 구조적으로 중요합니다. YAML로 키를 정의하는 게 아니라 런타임에 API로 발급하면 DB에 기록되고, proxy가 그걸 읽어 판정합니다. 키 발급이 재배포 없이 이뤄지는 이유입니다.

공식 chart는 repo 안의 `helm/litellm-helm`에 있습니다. 별도 chart repository가 아니라 저장소 자체가 소스라서, 저는 홈랩 저장소에 vendoring한 뒤 설치했습니다. chart는 Bitnami PostgreSQL 14.3.1을 서브차트로 가져오고, `db.deployStandalone: true`로 함께 띄우는 구성입니다.

---

## 2. 배포 과정에서 만난 것들

매끄럽게 끝나지 않았고, 그 기록이 이 글의 절반이라고 봅니다.

**이미지 태그.** chart 기본값의 `main-v1.99.0-stable` 태그는 실제 레지스트리에 존재하지 않았습니다. Docker Hub의 태그 목록을 대조해 안정 태그 `v1.98.0`으로 내렸습니다. rc가 매일 선발행되는 프로젝트라 chart 기본값이 레지스트리를 앞서가는 상황이 언제든 벌어질 수 있습니다.

**메모리.** 512Mi limit에서 컨테이너가 OOMKilled로 반복 크래시했습니다. chart 주석의 "DB 연결 안정 상태에 약 1 CPU와 4Gi" 권고가 실제였고, 3Gi로 올리니 바로 안정됐습니다. Python 프록시 + prisma 엔진을 함께 싣는 이미지라 최소 메모리가 작지 않습니다.

**master key 주입.** 가장 시간이 걸린 부분입니다. SSM SecureString에 키를 넣고 ExternalSecret으로 클러스터에 동기화한 뒤 `envFrom`으로 주입했는데, 프록시가 계속 인증 실패를 냈습니다. 원인은 chart의 Deployment가 `PROXY_MASTER_KEY`를 자체 생성 Secret(`litellm-masterkey`)의 `secretKeyRef`로 직접 선언한다는 것이었습니다. k8s에서 명시 `env`가 `envFrom`보다 우선하므로 제 주입은 조용히 무시되고 있었습니다. chart 값의 `masterkeySecretName`과 `masterkeySecretKey`를 제 ESO Secret으로 지정해서 해결했습니다.

ESO가 Secret을 갱신해도 이미 띄운 pod의 환경변수는 바뀌지 않는다는 점도 확인했습니다. Secret 갱신 후에는 rollout restart가 필요합니다.

---

## 3. virtual key와 예산

![virtual key 발급부터 예산 거절까지의 흐름](/assets/img/ai/litellm-virtual-key-flow.webp)

master key로 `/key/generate`를 호출해 virtual key를 발급합니다. 실제 호출에 쓴 요청과 응답은 다음과 같습니다.

```json
{
  "key_alias": "blog-test-key",
  "max_budget": 0.5,
  "budget_duration": "1h"
}
```

발급된 키로 `/v1/chat/completions`를 호출하면 proxy가 키를 검증하고, 소비를 집계하기 시작합니다. 이번 랩에서는 실비용이 없도록 chart 설정에 `mock_response`를 지정한 mock 모델을 두고 호출했습니다. 응답은 200이었고 usage에 total_tokens 30개가 기록됐습니다. `/key/info`로 보면 이 키의 spend가 추적되기 시작한 것을 확인할 수 있습니다.

예산 거절이 이 구조의 핵심 관측입니다. `max_budget: 0`인 키를 하나 더 발급한 뒤 같은 호출을 하면:

```json
{"error": {"message": "Budget has been exceeded! Key=zero-budget-key (sk-...) Current cost: 0.0, Max budget: 0.0", "type": "budget_exceeded", "code": "429"}}
```

HTTP 429와 함께 거절됩니다. 요청이 provider에 도달하기 전에 게이트에서 막힌다는 것이 직접 관측됩니다. 1편에서 설명한 "팀별 예산을 관문에서 강제한다"가 실제로는 이 한 줄의 에러로 구현돼 있는 셈입니다.

---

## 4. 세 계층으로 본 시리즈 정리

지난 두 편과 이번 편을 하나의 표로 묶습니다.

| 축 | 개념 (1편) | Envoy AI Gateway (2편) | LiteLLM (3편) |
|---|---|---|---|
| 위치 | 관문 개념 | 인그레스 데이터플레인 | 애플리케이션 곁 |
| 구현 | 해당 없음 | C++ Envoy + external processor | Python proxy + PostgreSQL |
| 설정 | 해당 없음 | Kubernetes CRD | DB가 진실원천, API로 발급 |
| 강점 | 관문의 필요성 설명 | 인그레스 운영과 동일 축 | 빠른 도입, 풍부한 기능 |
| 확인 방식 | 문서 대조 | 문서 대조 | 직접 배포 후 관측 |

세 편을 통해 같은 문제에 대한 답이 층마다 다르게 존재한다는 게 보입니다. 트래픽이 조직 인그레스를 통과하는 지점에서 통제할 것인가, 애플리케이션이 호출하는 서비스 지점에서 통제할 것인가. 전자가 플랫폼팀의 언어라면 후자는 앱팀의 언어입니다. 저는 두 축 모두 실재하는 문제이고, 조직의 운영 주체가 어디냐가 선택을 결정한다고 봅니다.

개인 홈랩 기준으로는 LiteLLM이 실용적입니다. Envoy Gateway 인그레스는 이미 있지만, AI 트래픽 통제를 인그레스 레이어에 넣을 만큼 호출 주체가 많지 않습니다. 키 관리와 예산이 목적이라면 proxy 하나면 충분합니다.

---

## 5. Reference

- [LiteLLM Docs](https://docs.litellm.ai/docs/)
- [GitHub - BerriAI/litellm](https://github.com/BerriAI/litellm)
- [LiteLLM Helm chart](https://github.com/BerriAI/litellm/tree/main/helm/litellm-helm)
- [LiteLLM Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
