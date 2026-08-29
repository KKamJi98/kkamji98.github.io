---
title: "Envoy AI Gateway 알아보기 - 데이터플레인 LLM 게이트웨이 [AI Gateway 2]"
date: 2026-08-28 02:41:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [envoy, ai-gateway, llm-gateway, kubernetes, api-gateway, study]
comments: true
image:
  path: /assets/img/ai/gateway/ai-gateway.webp
---

지난 글에서 LLM Gateway가 키, 비용, 감사를 한 지점에 모으는 관문이라고 정리했습니다. 거기 나온 LiteLLM은 애플리케이션 곁에 두는 Python 서버였습니다. 이번 글은 같은 문제를 완전히 다른 층에서 푸는 프로젝트를 봅니다. Envoy AI Gateway는 요청 경로 자체, 즉 데이터플레인에 LLM 트래픽 제어를 심는 방식입니다.

2026-08-28 기준으로 `envoyproxy/ai-gateway` 저장소와 공식 문서(버전 1.1)를 직접 확인한 내용을 정리합니다.

> **TL;DR**  
> - Envoy AI Gateway는 Envoy Gateway 위에서 동작하는 LLM 트래픽 게이트웨이. Apache-2.0  
> - 컨트롤 플레인은 Envoy Gateway, 데이터플레인은 Envoy Proxy에 AI 전용 external processor가 얹힌다  
> - 토큰 사용량 기반 rate limiting, provider 자격증명 통합, prompt caching, GenAI 관측을 프록시 층에서 처리한다  
> - LiteLLM이 앱팀 관점이라면 이쪽은 플랫폼팀 관점이다  
{: .prompt-info}

---

## 1. 두 층의 게이트웨이

![LLM gateway를 둘 수 있는 두 위치, 앱 레벨과 데이터플레인](/assets/img/ai/gateway-plane-compare.webp)

같은 "LLM 트래픽을 한 지점에서 통제한다"는 목표를 두 층에서 달성할 수 있습니다.

LiteLLM 같은 앱 레벨 게이트웨이는 애플리케이션이 SDK나 HTTP로 호출하는 Python 서비스입니다. provider 지원 폭이 넓고 앱팀이 자기 배포물 안에서 바로 쓸 수 있는 게 장점입니다.

Envoy AI Gateway는 인그레스 경로에 놓입니다. 애플리케이션은 OpenAI 호환 요청을 그냥 보내고, Envoy Proxy가 그 트래픽을 가로채 정책을 적용합니다. 확장 포인트가 Python 코드가 아니라 xDS 설정과 external processor라는 점이 근본적인 차이입니다. Kubernetes를 운영하는 팀 입장에서는 기존 인그레스와 메시 운영 지식을 그대로 재사용할 수 있는 형태입니다.

---

## 2. 아키텍처

공식 문서의 구조는 컨트롤 플레인과 데이터플레인의 분리로 요약됩니다.

- 컨트롤 플레인: Envoy Gateway가 중앙 컨트롤러입니다. AI Gateway Controller가 여기에 붙어 LLM 특화 설정을 데이터플레인에 반영합니다
- 데이터플레인: Envoy Proxy가 요청을 처리하고, 그 옆의 **AI Gateway external processor**가 요청 경로에서 AI 관련 판단을 수행합니다

Kubernetes에서는 CRD로 선언합니다. 라우팅은 `AIGatewayRoute`, provider 자격증명은 `BackendSecurityPolicy` 같은 리소스로 표현하고, Envoy Gateway가 이를 xDS로 변환해 프록시에 배포합니다. 인그레스를 Gateway API로 운영해 온 팀이라면 익숙한 패턴입니다.

---

## 3. 데이터플레인에서 하는 일

![Envoy AI Gateway의 요청 처리 흐름과 CRD](/assets/img/ai/envoy-ai-gateway-crd-flow.webp)

문서 기준 핵심 기능은 다섯 가지로 묶입니다.

**트래픽 제어.** Usage-based Rate Limiting이 이 프로젝트의 특기를 하나 꼽자면 이것입니다. 일반 API 게이트웨이의 QPS 제한과 달리, 응답에서 소비된 토큰 수를 읽어 시간창별 예산으로 제어합니다. Quota Policy로 "이 팀은 하루에 100만 토큰" 같은 정책을 프록시에서 강제합니다.

**자격증명 통합.** Upstream Authentication이 gateway와 provider 사이의 인증을 담당합니다. 문서는 이 목적을 "팀과 조직에 퍼지는 자격증명 난립 방지"라고 명시합니다. provider 키가 애플리케이션 설정에 흩어지지 않고 `BackendSecurityPolicy` 한곳에 모입니다. 지난 글의 "중앙 키 볼트" 개념을 프록시 층에서 구현하는 셈입니다.

**보안 정책.** Envoy Gateway가 원래 제공하는 SecurityPolicy를 그대로 씁니다. JWT 검증, mTLS, OIDC 연동, IP allowlist가 AI 트래픽에도 동일하게 적용됩니다. AI 전용 보안 체계를 따로 익힐 필요가 없습니다.

**관측.** OpenTelemetry GenAI 시맨틱 컨벤션을 따르는 Prometheus 메트릭(토큰 사용량, latency, 모델별 성능)과 OpenInference 컨벤션의 트레이싱을 제공합니다. 모델명과 토큰 사용량이 Envoy Access Log에 붙어 나옵니다.

**provider 커버리지.** OpenAI, AWS Bedrock, Azure OpenAI, Gemini 등 주요 provider와의 연결, vendor-specific 필드 전달, provider에 관계없이 쓰는 unified `cache_control` 기반 prompt caching을 문서에서 확인했습니다.

---

## 4. LiteLLM과의 대조

2026-08-28 GitHub 실측 수치를 겁니다.

| 축 | LiteLLM | Envoy AI Gateway |
|---|---|---|
| 레이어 | 앱 레벨 Python 서버 | 데이터플레인 (C++ Envoy + external processor) |
| 배포 | Python 앱, Helm | Envoy Gateway 위 Kubernetes CRD |
| 확장 지점 | Python 콜백, 라우터 | xDS 정책, external processor |
| stars | 57,426 | 1,971 |
| 강점 | provider 지원 폭, 빠른 도입 | 인그레스 운영과 동일 축, 프록시에서 정책 강제 |

stars 격차는 29배지만 해석이 필요합니다. LiteLLM은 앱 개발자 전원이 대상 독자라 수가 크고, Envoy AI Gateway는 인프라를 운영하는 조직이 대상입니다. 후자는 Envoy 생태계의 공식 프로젝트로, Envoy가 전 세계 L7 프록시 표준 중 하나라는 점에서 운영 신뢰의 축이 다릅니다.

선택은 조직 구조의 문제에 가깝습니다. 앱팀이 자기 서비스 안에서 바로 쓸 관문이 필요하면 LiteLLM, 플랫폼팀이 인그레스에서 조직 전체 AI 트래픽을 통제하려면 Envoy AI Gateway. 둘은 경쟁이라기보다 층이 다른 조합으로도 씁니다.

---

## 5. 어디까지 확인했나

이 글의 근거는 2026-08-28 기준 공식 저장소와 문서(버전 1.1) 실측입니다. 직접 배포해서 관측한 것은 아니므로 성능 수치는 기재하지 않았습니다. v1.0.0이 2026-06-23, v1.1.0이 2026-08-21에 나온 만큼 아직 1.0 이후 첫 minor 단계라, 도입을 검토한다면 릴리스 노트 추적이 필요합니다. InferencePool 라우팅은 Envoy inference extension과의 경계가 문서에서 더 확인될 부분입니다.

한 가지는 분명합니다. 홈랩이든 회사든 이미 Envoy Gateway로 인그레스를 운영 중이라면, AI 트래픽 통제를 위해 새로운 스택을 도입할 필요 없이 같은 컨트롤 플레인 위에 CRD를 얹으면 됩니다. LLM 트래픽이 특별한 인프라를 요구하던 시대는 여기서부터 일반 HTTP 트래픽 운영에 흡수되기 시작합니다.

---

## 6. Reference

- [Envoy AI Gateway - Docs](https://aigateway.envoyproxy.io/docs/)
- [Envoy AI Gateway - Architecture](https://aigateway.envoyproxy.io/docs/concepts/architecture/)
- [Envoy AI Gateway - Capabilities](https://aigateway.envoyproxy.io/docs/capabilities/)
- [GitHub - envoyproxy/ai-gateway](https://github.com/envoyproxy/ai-gateway)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
