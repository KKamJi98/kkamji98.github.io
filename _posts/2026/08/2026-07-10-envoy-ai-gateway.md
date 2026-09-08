---
title: "Envoy AI Gateway - Envoy Gateway 기반 LLM 프록시 [AI Gateway 2]"
date: 2026-07-10 02:41:00 +0900
last_modified_at: 2026-09-08 00:00:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [envoy, ai-gateway, llm-gateway, kubernetes, api-gateway, study]
comments: true
image:
  path: /assets/img/ai/gateway/ai-gateway.webp
---

출력 토큰을 포함한 최종 사용량은 응답 완료 시점에 확정됩니다. Envoy Gateway에서 HTTP 요청 수를 제한하던 설정에 토큰 예산을 넣으려면, provider 응답을 해석하고 사용량을 프록시의 정책 엔진에 전달하는 처리가 필요합니다. Envoy AI Gateway는 Envoy Gateway에 AI 전용 컨트롤러와 external processor를 결합해 이 역할을 수행합니다. Apache-2.0 라이선스의 프로젝트입니다.

발행일 이후의 2026-08-28 조사 기록을 바탕으로, 2026-09-08에 공식 `v1.1.0` 태그의 문서와 소스를 대조해 구현 설명을 갱신했습니다. 문서와 소스 조사이며 설치 및 트래픽 실행 검증은 포함하지 않습니다.

> **TL;DR**  
> Envoy Proxy가 provider 연결을 담당하고, 별도 ext-proc가 모델과 토큰 사용량을 해석한다. Kubernetes에서는 AI 전용 CRD를 기존 Gateway API 설정으로 연결하며, 토큰 제한에는 별도의 Rate Limit Service와 Redis 구성이 필요하다.  
{: .prompt-info}

---

## 1. 독립 LLM 프록시와 Envoy Gateway 통합

{% include diagrams/static/ai/gateway-plane-compare.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/gateway-plane-compare--20e9628c05c336d6.png" %}

LiteLLM Proxy와 Envoy AI Gateway는 모두 애플리케이션과 provider 사이에서 실제 요청을 중계합니다. 구현 방식과 설정 체계, 함께 운영하는 구성 요소가 다릅니다.

LiteLLM Proxy는 Python 기반의 독립 LLM 프록시입니다. 클라이언트는 OpenAI 호환 HTTP 또는 SDK로 호출할 수 있습니다. Envoy AI Gateway는 Envoy Gateway의 라우팅과 정책 체계에 AI 요청 처리를 결합합니다. Kubernetes에서 Gateway API를 운영해 온 팀은 기존 리소스 관리 방식을 재사용할 수 있습니다.

어느 쪽이든 클라이언트가 Gateway endpoint를 사용하도록 설정해야 요청이 게이트웨이를 거칩니다. Kubernetes ingress는 대표적인 배포 형태이며, 프로젝트에는 standalone `aigw` 실행 형태도 있습니다. 아래 sidecar와 CRD 설명은 공식 Kubernetes 배포 구조를 기준으로 합니다.

| 비교 항목 | LiteLLM Proxy | Envoy AI Gateway |
|---|---|---|
| 요청 처리 | Python 기반 독립 LLM 프록시 | Envoy Proxy와 Go ext-proc의 협업 |
| 클라이언트 연결 | OpenAI 호환 HTTP/SDK로 Proxy endpoint 호출 | 지원 API의 HTTP/SDK로 Gateway endpoint 호출 |
| 주요 설정 체계 | Proxy 설정과 관리 API | AI Gateway CRD와 Envoy Gateway 정책 |
| Kubernetes 운영 | Proxy 배포 및 사용하는 기능의 저장소 관리 | 두 controller의 연동, sidecar, 필요한 제한 및 관측 인프라 관리 |

독립 프록시의 설정과 관리 API를 사용할지, 기존 Envoy Gateway 정책 체계에 AI 처리를 통합할지를 운영 구성과 함께 비교해야 합니다. 두 프록시를 연속 배치한다면 인증과 사용량 집계의 책임을 나누어 중복 처리를 피해야 합니다.

2026-08-28 조사 기록의 GitHub stars는 LiteLLM **57,426**, Envoy AI Gateway **1,971**입니다. 당시 수집 스냅샷은 이번 대조에서 확인하지 못해 역사적 참고값으로 남깁니다. 도입 판단에는 위 표의 운영 구성과 필요한 기능을 사용합니다.

---

## 2. 설정 경로와 요청 경로

{% include diagrams/static/ai/envoy-ai-gateway-crd-flow.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/ai/envoy-ai-gateway-crd-flow--6bebf1f69f10a5d3.png" %}

컨트롤 플레인은 Envoy Gateway와 AI Gateway controller가 함께 구성합니다. AI Gateway controller는 `AIGatewayRoute`, `AIServiceBackend`, `BackendSecurityPolicy` 같은 AI 전용 리소스를 감시하고 `HTTPRoute`, `HTTPRouteFilter` 및 ext-proc 설정 Secret을 생성하거나 갱신합니다. Envoy Gateway는 생성된 리소스를 Envoy 설정으로 변환합니다. 이 과정에서 AI Gateway의 extension server가 xDS 설정을 보완하고, 최종 설정은 Envoy Gateway가 Proxy에 배포합니다.

요청을 provider로 전달하는 프로세스는 **Envoy Proxy**입니다. C++ Envoy Proxy와 Go로 작성된 **AI Gateway external processor(ext-proc)**는 별도 프로세스입니다. 공식 Kubernetes 배포에서는 admission webhook을 통해 ext-proc가 같은 Envoy Proxy Pod의 sidecar로 주입되며, 두 프로세스는 로컬 Unix Domain Socket(UDS)으로 통신합니다.

클라이언트 요청은 Envoy Proxy가 받고, Proxy가 필요한 처리 단계에서 ext-proc에 요청과 응답 처리를 맡깁니다. ext-proc는 모델 추출, provider 형식 변환, 토큰 사용량 추출 등을 수행하고 그 결과를 Proxy에 돌려줍니다. 실제 upstream HTTP 연결은 Proxy가 담당합니다. `AIGatewayRoute`나 `BackendSecurityPolicy`는 설정 객체이지, 요청이 통과하는 네트워크 홉이 아닙니다.

기존 Envoy Gateway 설치에는 AI Gateway controller, extension server 연동, admission webhook과 ext-proc sidecar를 추가합니다. 토큰 제한이나 quota를 사용하려면 Rate Limit Service와 Redis를 구성하고 Envoy Gateway의 rate limiting도 활성화해야 합니다.

릴리즈 발행일은 v1.0.0이 **2026-06-23 UTC**, v1.1.0이 **2026-08-21 UTC**입니다. v1.0의 안정 API는 `AIGatewayRoute`, `AIServiceBackend`, `BackendSecurityPolicy`, `GatewayConfig`, `MCPRoute`의 `v1beta1`입니다. `QuotaPolicy` 등 다른 API의 안정성은 개별 버전으로 확인해야 합니다. v1.1은 v1.0에서 CRD migration을 요구하지 않지만 Helm controller의 security context 기본값 변경은 확인해야 합니다.

v1.1 릴리즈의 의존 버전은 Envoy Gateway v1.8.1, Envoy Proxy v1.38.1, Gateway API v1.5.1, Gateway API Inference Extension v1.0.2입니다. 기존 설치를 재사용할 때는 이 의존 버전과의 호환성을 확인하고 추가 controller 및 sidecar의 운영 비용을 반영해야 합니다.

---

## 3. 응답 토큰 제한과 모델별 quota

### 3.1. Usage-based Rate Limiting

Usage-based Rate Limiting은 응답의 토큰 사용량을 Envoy Gateway의 global rate limit에 연결합니다. `AIGatewayRoute.spec.llmRequestCosts`에서 입력, 출력, 전체 토큰 또는 CEL로 계산한 비용을 dynamic metadata로 정의하고, `BackendTrafficPolicy`가 그 metadata를 응답 비용으로 사용하도록 설정합니다. 일반적인 QPS 제한과 달리 응답에서 계산한 토큰 수도 제한 단위가 될 수 있습니다.

요청을 받을 때는 이미 집계된 사용량으로 허용 여부를 판단하고, 허용된 요청의 응답이 완료되면 사용량을 차감합니다. v1.1 문서는 스트리밍 요청도 마지막 사용량을 확인한 뒤 반영하며, 이미 허용한 스트림이 한도를 넘겼다고 중간에 끊지는 않는다고 설명합니다. 후속 요청을 `429 Too Many Requests`로 거절하는 제어이므로, 요청 전에 최종 비용을 예약하는 정밀한 선불 상한과는 다릅니다.

### 3.2. QuotaPolicy

`QuotaPolicy`는 `AIServiceBackend`에 부착하는 모델별 토큰 예산 정책입니다. 완료된 요청의 사용량을 기본 `total_tokens` 또는 CEL 비용식으로 계산하고, 관련 quota가 소진되면 후속 요청을 거절합니다. Usage-based Rate Limiting과 설정 API는 다르지만, 두 기능 모두 응답 토큰을 사용하며 rate limit 인프라를 활용합니다.

v1.1에서는 다음 조건이 정책의 강제 범위를 결정합니다.

| 설정 | v1.1에서 확인할 동작 |
|---|---|
| `perModelQuotas[].modelName` | route의 해당 backendRef에 지정한 `modelNameOverride`와 일치해야 적용 |
| `bucketRules[].clientSelectors` | 현재는 header 조건만 반영 |
| `mode: Shared` | 일치하는 모든 bucket rule과 default bucket에 사용량을 반영하되, 관련 bucket 중 하나라도 잔여량이 있으면 허용 |
| `serviceQuota` | API 필드는 존재하지만 태그 소스에 enforcement 미구현 TODO가 남아 있음 |
| `bucketRules[].shadowMode` | quota 검사와 집계는 하되 초과 결과로 요청을 거절하지 않음 |
| API 버전 | `QuotaPolicy`는 `v1alpha1`이며 core `v1beta1` 안정성 보장과 구별 |

특히 `Shared`는 팀 bucket과 전체 bucket 중 하나가 소진되면 무조건 차단하는 계층형 hard cap이 아닙니다. 팀별로 나누려면 인증 결과와 연결된 식별 헤더 및 bucket rule을 설계해야 합니다. 클라이언트가 임의로 넣은 팀 ID를 신뢰하면 다른 팀의 bucket을 선택할 수 있으므로, 신뢰된 인증 단계에서 값을 검증하거나 덮어쓰는 경계가 필요합니다.

토큰 집계는 금액 정산과도 다릅니다. 모델별 단가와 캐시 과금 조건을 반영하지 않은 토큰 한도만으로 조직 전체 청구 금액을 보장할 수는 없습니다. 동시 요청에서의 초과량이나 Rate Limit Service 및 Redis 장애 시 허용 여부는 이 조사에서 실행 검증하지 않았습니다.

---

## 4. Provider 연결과 prompt cache의 지원 범위

공식 provider 지원표는 지원 여부를 **API schema 변환**과 **upstream 인증**으로 나눕니다. 전자는 `AIServiceBackend.spec.schema`, 후자는 `BackendSecurityPolicy`로 설정합니다. OpenAI, AWS Bedrock, Azure OpenAI, Google 계열 provider에 연결할 수 있다는 사실이 모든 endpoint와 vendor-specific 필드를 같은 방식으로 처리한다는 보장은 아닙니다.

예를 들어 v1.1 지원표의 Google Gemini on AI Studio는 OpenAI 호환 endpoint를 사용합니다. Google Vertex AI는 별도의 `GCPVertexAI` schema를 사용하고, Vertex AI의 Claude는 `GCPAnthropic`으로 구분합니다. 배포할 모델의 endpoint, 요청 형식과 인증 조합을 지원표 및 해당 provider 가이드에서 함께 확인해야 합니다.

### 4.1. 캐시는 Gateway가 아니라 provider가 유지

v1.1의 unified `cache_control` API 지원표는 다음 Claude 백엔드를 명시합니다.

| 백엔드 | API schema | Gateway의 처리 |
|---|---|---|
| Anthropic Direct | `Anthropic` | native `cache_control` 사용 |
| GCP Vertex AI의 Claude | `GCPAnthropic` | provider가 요구하는 형식으로 변환 |
| AWS Bedrock의 Claude | `AWSBedrockAnthropic` | provider가 요구하는 형식으로 변환 |

요청 content block 등에 `cache_control: {"type": "ephemeral"}`을 지정하면 Gateway가 이를 전달하거나 변환합니다. **캐시는 provider별로 유지됩니다.** 이 기능은 Gateway 내부의 범용 응답 캐시나 semantic cache가 아니며, 서로 다른 provider가 동일한 캐시 저장소를 공유하는 것도 아닙니다.

이 표의 범위는 Gateway의 unified API입니다. OpenAI, Azure OpenAI, Gemini 등 provider 자체의 캐시 지원과 최소 입력 길이, TTL 및 과금은 선택한 모델의 provider 문서에서 확인해야 합니다.

---

## 5. 클라이언트 인증과 provider 자격증명

클라이언트를 인증하는 정책과 provider에 제시할 자격증명은 서로 다른 신뢰 경계에 있습니다.

| 목적 | 사용하는 리소스 |
|---|---|
| 클라이언트 JWT, OIDC, IP 접근 제어 | Envoy Gateway `SecurityPolicy` |
| 클라이언트 mTLS | Gateway HTTPS/TLS listener와 `ClientTrafficPolicy.spec.tls.clientValidation` |
| provider 인증 방식과 자격증명 참조 | AI Gateway `BackendSecurityPolicy` |
| 장기 API 키 저장 | Kubernetes Secret |

AI Gateway 문서는 Envoy Gateway 보안 정책을 Gateway 또는 생성된 HTTPRoute에 연결하는 방식을 안내합니다. 정책 종류별 `targetRefs`를 확인해 연결하고, 클라이언트 mTLS는 위 표의 listener와 `ClientTrafficPolicy`로 구성합니다.

`BackendSecurityPolicy`는 인증 방식과 자격증명 참조를 중앙 관리합니다. 장기 API 키는 Kubernetes Secret에 저장하고, 지원되는 AWS, Azure, GCP 인증 방식에서는 cloud identity 기반 단기 자격증명을 사용할 수 있습니다. controller는 처리 규칙과 자격증명을 담은 ext-proc 설정 Secret도 관리하므로, 원본 키 Secret뿐 아니라 생성된 Secret에 대한 RBAC, 저장 암호화와 회전 운영도 고려해야 합니다.

v1.1의 `credentialOverride`는 신뢰된 필터가 요청마다 upstream 자격증명을 제공하는 기능입니다. dynamic metadata 또는 요청 헤더 중 하나를 소스로 선택하며, 릴리즈는 dynamic metadata를 권장합니다. 요청 헤더를 사용한다면 클라이언트 입력을 그대로 신뢰하지 않도록 해야 합니다. `fallbackToConfigured` 기본값은 `true`이므로, override가 없는 요청을 정적 자격증명으로 처리할지까지 의도에 맞게 설정해야 합니다.

---

## 6. 관측 데이터의 생성과 노출

Envoy AI Gateway는 토큰 사용량, 최초 토큰까지의 시간과 토큰 사이 지연 등을 Prometheus 메트릭으로 제공합니다. 운영 access log의 필드는 별도 출력 설정으로 선택합니다.

모델명과 사용량을 Envoy access log에 기록하려면 `AIGatewayRoute.spec.llmRequestCosts`로 사용량 metadata를 정의하고, `EnvoyProxy.spec.telemetry.accessLog`의 출력 형식에서 이를 참조해야 합니다. 공식 예제는 요청 모델을 `X-AI-EG-MODEL` 헤더에서, 응답 모델과 토큰 값을 `io.envoy.ai_gateway` dynamic metadata에서 추출합니다. 구성한 EnvoyProxy를 Gateway 또는 GatewayClass에 연결하는 작업도 필요합니다.

트레이싱은 OpenTelemetry collector endpoint를 설정해 활성화합니다. v1.1의 기본 semantic convention은 OpenInference이며, ext-proc에 `AI_GATEWAY_TRACING_SEMCONV=gen_ai`를 지정하면 OpenTelemetry GenAI 속성을 선택할 수 있습니다. span 이름과 속성 이름이 달라지므로 전환할 때는 대시보드와 알림의 쿼리도 확인해야 합니다.

민감 정보 수집의 기본값도 다릅니다. OpenInference는 기본적으로 요청과 응답 내용을 포함할 수 있으므로 `OPENINFERENCE_HIDE_INPUTS`, `OPENINFERENCE_HIDE_OUTPUTS` 등으로 수집 범위를 정해야 합니다. `gen_ai`는 메시지 내용 수집이 opt-in이며 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`로 활성화합니다. `OPENINFERENCE_HIDE_*` 설정은 `gen_ai`에는 적용되지 않습니다. convention 선택만 바꾸고 기존 redaction 설정이 그대로 유효하다고 가정하면 안 됩니다.

---

## 7. InferencePool의 endpoint 선택과 AI 처리

2026-08-28 조사에서는 InferencePool 라우팅과 inference extension의 경계를 추가 확인할 대상으로 남겼습니다. 2026-09-08에 v1.1 태그 문서를 재확인한 결과, `HTTPRoute + InferencePool`과 `AIGatewayRoute + InferencePool` 경로가 각각 문서화되어 있습니다.

InferencePool은 추론 endpoint 집합을 선언하고, Gateway API Inference Extension의 Endpoint Picker Provider(EPP)가 endpoint 선택을 담당합니다. EPP와 AI Gateway ext-proc는 별도 역할입니다. HTTPRoute 경로에서는 Envoy가 EPP에 endpoint 선택을 요청합니다. AIGatewayRoute 경로에서는 여기에 모델 추출, 요청 및 응답 변환, 사용량 metadata 생성 같은 AI Gateway 처리가 결합됩니다.

이를 사용하려면 Inference Extension CRD, Envoy Gateway의 InferencePool 지원 설정과 Endpoint Picker 배포가 필요합니다. EPP의 endpoint 선택과 ext-proc의 AI 요청 처리를 구분하면 모델 라우팅 문제와 추론 서버 선택 문제를 각각 추적할 수 있습니다.

---

## 8. Reference

- [Envoy AI Gateway v1.1 - License](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/LICENSE)
- [Envoy AI Gateway v1.1 - Standalone Entrypoint](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/cmd/aigw/main.go)
- [Envoy AI Gateway - v1.0.0 Release](https://github.com/envoyproxy/ai-gateway/releases/tag/v1.0.0)
- [Envoy AI Gateway - v1.1.0 Release](https://github.com/envoyproxy/ai-gateway/releases/tag/v1.1.0)
- [Envoy AI Gateway v1.1 - Control Plane](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/concepts/architecture/control-plane.md)
- [Envoy AI Gateway v1.1 - Go External Processor](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/cmd/extproc/main.go)
- [Envoy AI Gateway v1.1 - Usage-based Rate Limiting](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/traffic/usage-based-ratelimiting.md)
- [Envoy AI Gateway v1.1 - Quota Policy](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/traffic/quota-policy.md)
- [Envoy AI Gateway v1.1 - QuotaPolicy API Source](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/api/v1alpha1/quota_policy.go)
- [Envoy AI Gateway v1.1 - Supported Providers](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/llm-integrations/supported-providers.md)
- [Envoy AI Gateway v1.1 - Prompt Caching](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/llm-integrations/prompt-caching.md)
- [Envoy AI Gateway v1.1 - Upstream Authentication](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/security/upstream-auth.mdx)
- [Envoy AI Gateway v1.1 - Security Policy Attachment](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/security/index.md)
- [Envoy Gateway v1.8.1 - External Client Mutual TLS](https://github.com/envoyproxy/gateway/blob/v1.8.1/site/content/en/latest/tasks/security/mutual-tls.md)
- [Envoy AI Gateway v1.1 - Access Logs](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/observability/accesslogs.md)
- [Envoy AI Gateway v1.1 - Distributed Tracing](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/observability/tracing.md)
- [Envoy AI Gateway v1.1 - InferencePool Support](https://github.com/envoyproxy/ai-gateway/blob/v1.1.0/site/versioned_docs/version-1.1/capabilities/inference/inferencepool-support.md)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
