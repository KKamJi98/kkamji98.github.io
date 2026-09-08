---
title: "LLM Gateway - 키 정책, 비용 집계와 감사 [AI Gateway 1]"
date: 2026-07-09 01:17:00 +0900
last_modified_at: 2026-09-08 00:00:00 +0900
author: kkamji
categories: [AI, Infra]
tags: [llm-gateway, ai-gateway, litellm, kong, higress, portkey, api-gateway, study]
comments: true
image:
  path: /assets/img/ai/gateway/ai-gateway.webp
---

"이번 달 LLM 비용 중 마케팅팀 챗봇이 쓴 금액은 얼마인가?" 여러 팀이 OpenAI, Anthropic, Azure를 함께 쓰면 프로바이더별 사용량을 같은 팀 기준으로 묶어야 이 질문에 답할 수 있습니다. 공유한 API 키를 교체할 때 어느 애플리케이션까지 바꿔야 하는지도 알아야 합니다. LLM Gateway는 애플리케이션과 프로바이더 사이에서 호출을 중계하면서 키 정책, 비용 집계, 감사 기록을 중앙화하는 방법입니다.

2026년 8월의 조사 기록을 바탕으로 2026-09-08에 공식 문서의 기능과 라이선스 조건을 대조해 갱신했습니다. 발행일과 조사 및 갱신 시점은 구분하며, 당시의 수치에는 관측 시점을 함께 적었습니다.

---

## 1. 직접 호출에서 중앙 관리가 필요해지는 지점

애플리케이션이 LLM API를 직접 호출하는 구조도 유효합니다. 단일 프로바이더를 쓴다면 프로젝트별 키와 사용량 관리로 충분할 수 있습니다. OpenAI API 플랫폼도 프로젝트 단위 키와 권한, 사용량 관리 기능을 제공합니다. 예산 알림과 요청을 실제로 차단하는 상한은 구분해야 합니다.

관리 부담은 여러 애플리케이션이 같은 프로바이더 키를 공유하거나, 팀 구분이 프로바이더의 계정과 프로젝트 구조에 맞지 않을 때 커집니다. 키 유출 시 교체 대상을 찾기 어렵고, 여러 프로바이더의 사용량을 팀별 비용으로 환산하려면 공통 식별자와 별도 집계가 필요합니다. 비용 집계 파이프라인을 직접 만들 수도 있지만, 호출 경로에서 같은 기준을 적용하는 게이트웨이가 대안이 됩니다.

감사에도 비슷한 문제가 있습니다. 사용자, 호출 모델, 처리 결과를 각 앱이 서로 다른 형식으로 남기면 사건 하나를 추적하는 데 여러 로그를 대조해야 합니다. 중앙 로그를 쓰더라도 프롬프트와 응답을 전부 저장할 필요는 없습니다. 민감정보가 로그에 복제되지 않도록 수집 필드, 마스킹, 보존 기간과 열람 권한을 먼저 정해야 합니다.

장애 대응은 키와 비용 관리와는 다른 검증이 필요합니다. 폴백 정책을 중앙화하면 앱마다 같은 재시도 코드를 구현하는 부담을 줄일 수 있습니다. 다만 대체 모델의 응답 품질, 도구 호출 형식, 데이터 처리 지역이 달라질 수 있으므로 엔드포인트가 호환된다는 이유만으로 안전한 대체가 보장되지는 않습니다.

---

## 2. 게이트웨이의 인증과 정책 적용

애플리케이션은 게이트웨이 엔드포인트를 사용하도록 설정하고, 게이트웨이가 선택한 프로바이더로 요청을 전달합니다. LiteLLM 같은 독립 프록시도 요청 데이터 경로에 놓입니다. 특정 언어의 SDK가 필수인 구조는 아니며, 지원하는 엔드포인트를 HTTP 또는 호환 SDK로 호출할 수 있습니다.

| 관심사 | 직접 호출에서의 구현 | 게이트웨이로 중앙화할 때 |
|---|---|---|
| 키 | 앱별 프로바이더 자격증명과 교체 절차 | 앱에는 가상 키, 프로바이더 자격증명은 게이트웨이 측에서 관리 |
| 비용 | 프로바이더 프로젝트별 집계 또는 별도 비용 파이프라인 | 팀/사용자/프로젝트 식별자를 기준으로 집계하고 예산 정책 적용 |
| 감사 | 앱 로그와 공통 로그 수집기 | 요청 식별자, 모델, 정책 판정 등의 기록 형식 통일 |
| 폴백 | 앱별 재시도와 대체 모델 선택 | 재시도 횟수와 대체 경로 정책을 한 곳에서 관리 |
| 가드레일 | 앱별 검사 또는 외부 검사 서비스 | 선택한 검사와 마스킹을 공통 경로에 적용 |

가상 키는 프로바이더 키의 단순 별칭이 아닙니다. 게이트웨이는 발급된 키를 인증하고 허용 모델, 예산, rate limit 등의 정책을 확인한 뒤 선택한 백엔드의 자격증명으로 호출합니다. 발급은 사전 관리 작업이며, 애플리케이션은 이미 발급된 키로 추론 요청을 보냅니다.

팀별 키에 모델 제한과 예산, 요청 한도, 관리 API 접근 제한을 설정하면 유출 시 영향 범위를 줄일 수 있습니다. 팀에 연결되지 않은 키나 넓은 권한을 가진 키도 만들 수 있으므로 가상 키라는 형식만으로 팀 격리가 보장되지는 않습니다. 특히 LiteLLM에서는 키 소유자의 역할이 관리 경로 접근에 영향을 줄 수 있어 소유권과 허용 경로를 함께 확인해야 합니다. 키 폐기는 이후 사용을 막는 조치이며 이미 발생한 비용이나 데이터 유출을 되돌리지는 못합니다.

{% include diagrams/static/ai/llm-gateway-position.html %}

그림은 앱이 가상 키로 게이트웨이를 호출하고, 게이트웨이 측에서 프로바이더 자격증명을 관리하는 배치를 나타냅니다. 중앙 정책을 강제하려면 앱에 원본 키를 함께 배포하거나 게이트웨이를 우회하는 호출 경로를 허용하지 않는 설계도 필요합니다. 가드레일과 감사 기능은 제품 도입만으로 활성화되지 않으며, 탐지 누락과 로그 노출 위험을 별도로 검증해야 합니다.

---

## 3. 독립 LLM 프록시 - LiteLLM과 Portkey

LiteLLM은 프록시 서버로 배포하거나 Python 라이브러리로 사용할 수 있습니다. 공식 README는 100개 이상의 프로바이더를 OpenAI 형식으로 호출하는 통합 인터페이스를 설명합니다. 프로바이더 전용 옵션과 엔드포인트의 호환 범위는 실제 사용할 모델과 기능을 기준으로 확인해야 합니다.

2026년 8월 조사 당시 LiteLLM의 GitHub 스타는 약 5.7만 개로 기록했습니다. 이 수치는 당시의 관측값이며, 배포 점유율이나 운영 신뢰성을 측정한 값은 아닙니다. 아래 기능과 라이선스 조건은 2026년 9월 8일 확인한 공식 문서를 반영합니다.

LiteLLM 코어는 MIT 라이선스이며, `enterprise/` 디렉토리는 별도 Enterprise 라이선스를 따릅니다. Admin UI SSO 문서에는 v1.76.0부터 최대 5 사용자까지 무료이고 초과 시 Enterprise 라이선스가 필요하다고 명시되어 있습니다. 이 인원 기준은 관리 UI 로그인에 적용됩니다. 권한 관리는 팀과 내부 사용자 역할을 기준으로 하며, 팀을 묶는 Organizations는 Enterprise 기능으로 구분합니다.

Portkey의 `gateway` 저장소도 MIT 라이선스입니다. 라우팅, 폴백, 캐싱, 재시도 같은 프록시 기능을 제공하며, OSS Quickstart에도 로컬 로그를 보는 Gateway Console이 있습니다. OSS의 로컬 로그 콘솔과 조직 거버넌스 및 Enterprise 배포를 위한 제어면은 별도 제품 범위입니다.

Portkey 공식 README에는 인증, 서버와 도구별 접근 제어, 관측성을 제공하는 MCP Gateway도 소개되어 있습니다. 확인 시점의 README는 Enterprise 코어를 오픈소스에 통합하는 Gateway 2.0을 Pre-Release로 안내합니다. MCP 도입 시에는 제품 지원 여부와 함께 사용할 OSS 안정 릴리스에 포함된 기능을 확인해야 합니다.

LiteLLM은 공식 Helm 차트를 제공합니다. Portkey도 공식 차트가 있지만 현행 Quick Start는 Portkey가 제공하는 이미지 레지스트리 접근 정보와 `SERVICE_NAME`, `PORTKEY_CLIENT_AUTH`, `ORGANISATIONS_TO_SYNC` 설정을 요구합니다. 이 Enterprise 연동 경로와 MIT 코어의 독립 배포는 전제가 다릅니다. 어느 쪽이든 선택한 구성의 DB, 로그 저장소, 백업과 고가용성을 운영해야 합니다.

---

## 4. API 게이트웨이 기반 구현 - Kong과 Higress

기존 API 게이트웨이에 AI 기능을 추가하면 이미 사용하는 라우팅 설정, 배포 도구, 관측 체계를 활용할 수 있습니다. 독립 LLM 프록시와의 차이는 데이터 경로에 놓이는지 여부보다 설정 방식과 운영 통합에 있습니다. 어느 쪽이든 앱이 게이트웨이 엔드포인트를 호출하도록 구성해야 하며, 게이트웨이 배포만으로 외부 LLM 호출을 자동으로 가로채지는 않습니다.

Self-hosted Kong Gateway에서는 Services, Routes와 AI 플러그인을 조합합니다. 현재 Konnect AI Gateway 2.x 문서는 AI Models, AI Model Providers, AI MCP Servers, AI Agents 같은 엔터티를 관리하는 경로를 설명합니다. 배포 방식에 따라 설정 모델과 지원하는 MCP 모드가 다릅니다. Konnect 2.x의 설명은 9월 8일 확인한 문서 기준입니다.

`Kong/kong` OSS 코어는 Apache-2.0이지만, AI Proxy Advanced는 공식 문서에서 AI Gateway Enterprise 제공 기능으로 명시합니다. 멀티 타깃 라우팅과 로드밸런싱을 포함한 고급 AI 기능, 관리면 RBAC, 요청 인증 플러그인을 도입할 때는 배포판과 계약에 포함되는 범위를 각각 확인해야 합니다.

Higress는 Alibaba에서 시작한 Apache-2.0 API 게이트웨이입니다. 현재 공식 README는 벤더 중립 CNCF Sandbox 프로젝트로 소개하며, AI 프록시, 멀티모델 로드밸런싱과 토큰 rate limit을 설명합니다. MCP 호스팅은 플러그인 메커니즘과 OpenAPI의 MCP 서버 변환을 포함합니다. 호스팅할 서버가 이 플러그인 및 변환 방식에 맞는지 확인해야 합니다.

Higress의 OIDC 플러그인은 게이트웨이를 통과하는 요청을 인증하는 데이터면 기능입니다. 관리 콘솔 SSO와 관리자 RBAC는 사용할 콘솔 및 배포판의 로그인과 권한 모델에서 확인해야 합니다.

| 비교 대상 | LiteLLM | Portkey | Kong | Higress |
|---|---|---|---|---|
| 코드 라이선스와 제품 경계 | MIT 코어 / enterprise 별도 라이선스 | gateway 저장소 MIT / 제품 기능 포함 범위 별도 확인 | OSS 코어 Apache-2.0 / AI Proxy Advanced 등 Enterprise 기능 별도 | OSS 저장소 Apache-2.0 / 선택한 배포판 범위 확인 |
| 관리 UI SSO | v1.76.0부터 최대 5 사용자 무료, 초과 Enterprise | 조직 관리 제품의 플랜과 배포 방식 확인 | Kong Manager / Konnect와 계약 범위 확인 | 요청 OIDC와 구분, 콘솔별 확인 |
| 권한 관리 | 팀과 내부 역할, Organizations는 Enterprise | 제품의 조직/서버/도구 권한과 OSS 포함 범위 구분 | 관리면 RBAC와 요청 인증 플러그인 구분 | 데이터면 인증 플러그인과 관리 콘솔 권한 구분 |
| MCP | MCP Gateway 제공 | 제품 MCP Gateway 제공, OSS 안정 릴리스 포함 범위 별도 확인 | Konnect 엔터티 또는 self-hosted 플러그인, 모드별 차이 | 플러그인 기반 호스팅과 OpenAPI 변환 |
| 도입 시 확인할 조건 | 필요한 권한 기능과 DB 운영 | MIT 코어 배포인지 Enterprise 연동 배포인지 | 기존 운영 자산과 AI 기능 계약 | 플러그인 설정과 콘솔 권한 모델 |

표는 공식 문서의 기능과 라이선스 조건을 비교한 것입니다. 실제 도입 비용은 선택한 배포판과 계약 범위에 따라 달라집니다.

---

## 5. LLM 호출과 MCP 도구 호출의 공통 정책

LiteLLM은 MCP Gateway와 A2A Agent Gateway를 제공하고, Portkey와 Higress도 MCP 관리 기능을 설명합니다. LLM 호출 외에 도구와 에이전트 호출을 관리 대상으로 넓히는 제품들이 있습니다.

에이전트의 도구 호출에는 누가 어느 서버의 어떤 도구를 실행할 수 있는지 판단하는 권한 정책과 감사 기록이 필요합니다. 공통 관문을 두면 인증과 관측 체계를 함께 운영할 수 있지만, 모델 접근 권한이 도구 실행 권한을 자동으로 부여해서는 안 됩니다. 데이터 변경을 수행하는 도구에는 별도 승인이나 더 좁은 권한 정책이 필요할 수 있습니다.

LLM과 MCP의 관문을 합칠지는 도구의 신뢰 경계, 운영 주체, 장애 영향 범위로 결정합니다. 이 조건이 다르면 관문을 나누고 감사 식별자만 연결할 수 있습니다.

---

## 6. 중앙화의 이익과 추가 운영 비용

도입 여부는 팀 수만으로 결정되지 않습니다. 프로바이더의 프로젝트 기능과 기존 로그 체계로 필요한 정책을 구현할 수 있는지, 여러 프로바이더에 같은 기준을 적용하는 비용이 얼마나 드는지를 먼저 비교해야 합니다.

| 운영 조건 | 판단 |
|---|---|
| 단일 프로바이더의 프로젝트와 팀 구분이 일치 | 네이티브 키, 사용량 집계와 예산 알림부터 검토 |
| 여러 프로바이더에 공통 팀 예산과 키 정책이 필요 | 게이트웨이 중앙화와 별도 집계 파이프라인의 구현 비용 비교 |
| 사용자별 감사와 데이터 취급 제한이 필요 | 로그 필드, 마스킹, 보존과 열람 권한 설계 후 중앙 적용 검토 |
| 게이트웨이 장애가 여러 앱에 전파 | 복제본, 의존 저장소 가용성과 복구 절차를 운영 비용에 포함 |

게이트웨이 비용에는 상시 실행 자원뿐 아니라 로그 저장, DB와 백업, 상용 기능 계약, 업그레이드 검증이 포함됩니다. 비용 집계가 가능하다는 것과 청구액이 자동으로 줄어든다는 것은 다릅니다. 집계 단가와 실제 프로바이더 청구의 차이, 재시도에서 발생하는 추가 사용량도 확인해야 합니다.

도입할 때는 제한된 호출부터 인증과 최소 권한, 필요한 메타데이터 기록을 검증한 뒤 예산과 폴백 정책을 추가하는 편이 원인 분리에 유리합니다. 예산 차단은 동시 요청과 사용량 반영 시점을 포함해 시험해야 하고, 폴백은 대체 모델의 품질과 데이터 취급 조건까지 확인해야 합니다. 공통 정책을 한 번에 바꿀 수 있다는 이점만큼 잘못된 정책이 여러 앱에 동시에 영향을 주는 위험도 커집니다.

---

## 7. Reference

- [LiteLLM - GitHub README](https://github.com/BerriAI/litellm)
- [LiteLLM - Core License](https://github.com/BerriAI/litellm/blob/main/LICENSE)
- [LiteLLM - Enterprise License](https://github.com/BerriAI/litellm/blob/main/enterprise/LICENSE.md)
- [LiteLLM - Admin UI SSO](https://docs.litellm.ai/docs/proxy/admin_ui_sso)
- [LiteLLM - Role-based Access Controls](https://docs.litellm.ai/docs/proxy/access_control)
- [LiteLLM - Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [LiteLLM - Official Helm Chart](https://github.com/BerriAI/litellm/tree/main/helm/litellm-helm)
- [Portkey - Gateway README and MCP Gateway](https://github.com/Portkey-AI/gateway)
- [Portkey - Gateway License](https://github.com/Portkey-AI/gateway/blob/main/LICENSE)
- [Portkey - Gateway Helm Chart](https://github.com/Portkey-AI/helm/blob/main/charts/portkey-gateway/README.md)
- [Kong - OSS License](https://github.com/Kong/kong/blob/master/LICENSE)
- [Kong - AI Gateway](https://developer.konghq.com/ai-gateway/)
- [Kong - AI Proxy Advanced](https://developer.konghq.com/plugins/ai-proxy-advanced/)
- [Kong - Self-hosted AI Gateway](https://developer.konghq.com/ai-gateway/configure-on-prem/)
- [Higress - GitHub README](https://github.com/higress-group/higress)
- [Higress - License](https://github.com/higress-group/higress/blob/main/LICENSE)
- [Higress - OIDC Authentication Plugin](https://github.com/higress-group/higress/blob/main/plugins/wasm-go/extensions/oidc/README_EN.md)
- [OpenAI - Managing Projects in the API Platform](https://help.openai.com/en/articles/9186755-managing-your-work-in-the-api-platform-with-projects)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
