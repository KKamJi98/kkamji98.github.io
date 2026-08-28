---
title: "LLM Gateway 알아보기 - 키, 비용, 감사의 관문 [AI Gateway 1]"
date: 2026-08-28 01:17:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [llm-gateway, ai-gateway, litellm, kong, higress, portkey, api-gateway, study]
comments: true
image:
  path: /assets/img/ai/gateway/ai-gateway.webp
---

기업에서 LLM API를 직접 쓰기 시작하면 처음 마주치는 문제는 모델 품질이 아닙니다. OpenAI 키가 슬랙으로 공유되고, 팀마다 따로 결제한 Azure 구독이 3개 생기고, "이번 달 LLM 비용이 얼마인데 팀별로 얼마씩 쓴 거지?"라는 질문에 답할 방법이 없는 상황입니다. 이 글에서는 이 문제들을 해결하는 LLM Gateway가 무엇을 관문으로 삼는지, 그리고 2026년 현재 어떤 선택지들이 있는지를 정리합니다.

> **TL;DR**  
> - LLM Gateway는 키 관리, 비용 배분, 감사, 폴백 라우팅을 한 지점에 모은 프록시다  
> - 자체호스트 축(LiteLLM, Portkey)과 API 게이트웨이 확장 축(Kong, Higress)으로 수렴한다  
> - 2026년 기준 LLM 게이트웨이는 MCP와 에이전트 트래픽까지 흡수하는 중이다  

---

## 1. 왜 애플리케이션에서 LLM API를 직접 호출하면 안 되는가

LLM API 호출 자체는 `curl` 한 줄이면 끝납니다. 문제는 그 한 줄에 들어 있는 자격증명과 비용에서 시작됩니다.

첫 번째 문제는 키 관리입니다. 각 애플리케이션이 OpenAI나 Anthropic 키를 직접 들고 있으면, 키가 유출되었을 때 어디서 쓰는 키인지 추적하고 전부 교체해야 합니다. 팀이 열 개면 열 개의 키를 각자 로테이션하는 상황이 됩니다.

두 번째 문제는 비용 가시성입니다. LLM API는 토큰 단위로 과금되는데, 애플리케이션이 직접 호출하면 비용이 각 애플리케이션의 클라우드 계정에 흩어집니다. "마케팅팀 챗봇이 이번 달에 얼마를 썼는가"라는 질문에 표로 답하려면 각 서비스의 로그를 합산해야 합니다.

세 번째 문제는 감사입니다. 규정 준수 관점에서 "어떤 사용자가 어떤 모델에 어떤 데이터를 보냈는가"를 남겨야 할 때, 애플리케이션마다 로깅 구현이 다르면 감사 대응이 애플리케이션 수만큼 반복됩니다.

네 번째 문제는 가용성입니다. 특정 프로바이더에 장애가 나면 그 프로바이더를 직접 호출하던 서비스 전부가 영향을 받습니다. 폴백 로직을 애플리케이션마다 구현하면 똑같은 재시도 코드가 서비스 수만큼 존재하게 됩니다.

---

## 2. LLM Gateway가 하는 일

LLM Gateway는 애플리케이션과 LLM 프로바이더 사이에 놓이는 프록시입니다. 애플리케이션은 게이트웨이의 엔드포인트만 바라보고, 게이트웨이가 프로바이더 호출을 대신합니다.

| 관심사 | 게이트웨이 없이 | 게이트웨이 있을 때 |
|---|---|---|
| 키 | 앱마다 원본 키 보관 | 게이트웨이만 원본 키, 앱은 가상 키 |
| 비용 | 계정별로 흩어짐 | 팀/사용자/프로젝트별 집계와 예산 |
| 감사 | 앱별 로깅 구현 | 통일된 요청/응답 로그 |
| 폴백 | 앱별 재시도 코드 | 라우팅 정책 한 곳에서 관리 |
| 가드레일 | 앱별 구현 | PII 마스킹, 프롬프트 차단 중앙화 |

가상 키 방식이 핵심입니다. 게이트웨이가 발급한 가상 키는 게이트웨이 내부에서 실제 프로바이더 키로 치환됩니다. 애플리케이션 입장에서는 OpenAI 키가 아니라 `sk-litellm-team-a-xxx` 같은 형태의 키를 쓰게 되고, 이 키는 예산 한도와 허용 모델 목록이 붙어 있습니다. 키가 유출되면 해당 가상 키만 폐기하면 되므로 피해 범위가 한 팀으로 제한됩니다.

---

![LLM Gateway가 놓이는 위치](/assets/img/ai/llm-gateway-position.webp)

애플리케이션은 가상 키로 게이트웨이를 호출하고, 게이트웨이만 실제 프로바이더 키를 쥐고 있습니다. 예산, 감사 로그, 가드레일, 폴백 라우팅이 모두 이 한 칸에 모입니다.

---

## 3. 자체호스트 축 - LiteLLM과 Portkey

오픈소스 LLM 게이트웨이 중 가장 널리 쓰이는 것은 LiteLLM입니다. 2026년 8월 기준 GitHub 스타 약 5.7만 개로 이 분야에서 압도적이고, 릴리스 주기가 하루 단위입니다. 프록시 서버 형태로 배포하며, 100개 이상의 프로바이더를 OpenAI 호환 형식으로 호출할 수 있습니다.

LiteLLM의 엔터프라이즈 기능 구성이 특징적입니다. 저장소의 `enterprise/` 디렉토리만 별도 라이선스로 분리해 두었고, SSO는 5시트까지 무료로 제공합니다. 즉 소규모 팀은 사실상 무료로 SSO까지 쓸 수 있고, 그 이상 규모가 커지면 유료 라이선스로 넘어가는 구조입니다.

Portkey Gateway는 MIT 라이선스의 순수 오픈소스 게이트웨이입니다. 라우팅, 폴백, 캐싱, 재시도 같은 데이터 플레인 기능은 오픈소스로 제공하고, 관리 콘솔과 팀 관리 기능은 SaaS 쪽에 두는 이원 구조입니다. 코어 엔진이 가볍다는 평가가 있지만, 2026년 기준 저장소 활동이 LiteLLM에 비해 둔화된 상태입니다.

두 프로젝트 모두 Helm 차트를 제공하므로 Kubernetes에 배포하는 부담은 적습니다.

---

## 4. API 게이트웨이 확장 축 - Kong과 Higress

이미 Kong, Apigee 같은 API 게이트웨이를 운영 중인 조직은 새 게이트웨이를 도입하는 대신 기존 게이트웨이에 AI 기능을 얹는 경로를 씁니다.

Kong은 Kong AI Gateway라는 이름으로 AI 프록시 기능을 제공합니다. 기존 API 게이트웨이 자산(RBAC, OIDC 연동, rate limit, 관측성)을 그대로 쓰면서 LLM 트래픽 라우팅과 프로바이더 인증을 플러그인으로 추가하는 방식입니다. Apache 2.0 라이선스에 Helm 차트도 공식 제공됩니다.

Higress는 Alibaba에서 시작해 독립 조직(higress-group)으로 운영되는 API 게이트웨이로, AI 게이트웨이 기능을 네이티브로 내장했습니다. 멀티모델 라우팅과 토큰 단위 rate limit을 기본 제공하고, MCP 서버 호스팅 기능까지 갖추고 있습니다. Apache 2.0 라이선스로 2026년에도 활발하게 개발 중입니다.

| 구분 | LiteLLM | Portkey | Kong AI Gateway | Higress |
|---|---|---|---|---|
| 라이선스 | 커스텀(enterprise 분리) | MIT | Apache-2.0 | Apache-2.0 |
| 성격 | LLM 전용 게이트웨이 | LLM 전용 게이트웨이 | API GW + AI 플러그인 | API GW + AI 내장 |
| SSO/RBAC | 5시트 무료, 이상 유료 | SaaS 측 | 기존 GW 자산 활용 | 기본 제공 |
| MCP 지원 | 내장(MCP Gateway) | 제한적 | 플러그인 | 내장(호스팅) |
| 적합한 조직 | LLM 중심, 빠른 도입 | 가벼운 데이터 플레인 | 이미 Kong 운영 조직 | 클라우드 네이티브, MCP 병행 |

---

## 5. 2026년의 수렴 - 게이트웨이가 MCP를 흡수하는 이유

2026년 LLM 게이트웨이 시장의 가장 큰 변화는 게이트웨이가 MCP(Model Context Protocol) 트래픽을 흡수하기 시작했다는 점입니다. LiteLLM은 공식 문서에서 자신을 "LLM, MCP, and Agent gateway"로 소개하며 MCP 서버 카탈로그와 사용량 분석 기능을 내장했습니다. Higress도 MCP 서버 호스팅 기능을 제공합니다.

배경에는 에이전트 워크로드의 성장이 있습니다. 에이전트는 LLM 호출뿐 아니라 도구(MCP 서버) 호출까지 수행하는데, 이 도구 호출에도 인증, 권한, 감사, rate limit이 필요합니다. 결국 관문은 하나로 모이게 됩니다. 이 흐름에 대해서는 다음 편에서 MCP Gateway를 다루며 자세히 살펴봅니다.

---

## 6. 도입 판단 기준

LLM Gateway 도입이 필요한 조직과 그렇지 않은 조직을 나누는 기준은 규모가 아니라 "공유 인프라"의 존재 여부입니다.

- 팀이 여럿이고 LLM 예산을 배분해야 한다면 필요합니다. 비용 배분은 게이트웨이 없이는 사실상 불가능합니다.
- 규정 준수로 감사 로그가 필요하다면 필요합니다. 중앙 로그가 없으면 감사 대응이 애플리케이션 수만큼 반복됩니다.
- 개인 프로젝트나 팀 하나가 단일 프로바이더만 쓴다면 게이트웨이보다 프로바이더 네이티브 기능(예산 알림, 조직 키)으로 충분할 수 있습니다. 게이트웨이 하나가 상시 떠 있는 비용과 운영 부담이 그 가치를 넘지 않기 때문입니다.

도입 순서는 간단히 두 단계로 나눌 수 있습니다. 먼저 프록시로 배포해 키 치환과 로깅만 켜고, 그다음 예산·쿼터·폴백 정책을 단계적으로 켜는 순서가 안전합니다. 처음부터 모든 기능을 켜면 문제 발생 시 원인 분리가 어렵습니다.

---

## 7. Reference

- [LiteLLM Documentation](https://docs.litellm.ai/docs/)
- [LiteLLM GitHub Repository](https://github.com/BerriAI/litellm)
- [Portkey Gateway GitHub Repository](https://github.com/Portkey-AI/gateway)
- [Kong AI Gateway Documentation](https://developer.konghq.com/ai-gateway/)
- [Higress GitHub Repository](https://github.com/higress-group/higress)
- [OpenAI Agents SDK MCP Documentation](https://openai.github.io/openai-agents-python/mcp/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
