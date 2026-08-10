---
title: "AWS DevOps Agent Overview"
date: 2026-08-09 20:00:00 +0900
author: kkamji
categories: [Cloud, DevOps]
tags: [aws, devops, ai-agent, incident-response, release-management, sre, observability]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

인시던트가 발생하면 CloudWatch 지표, APM 트레이스, 로그, 배포 기록을 번갈아 확인하며 원인을 좁혀나가는 과정에 시간이 걸립니다. AWS DevOps Agent는 알림이 감지된 순간 이 조사를 자율적으로 수행하고, 근본 원인과 완화 조치를 Slack이나 PagerDuty에 정리해 전달합니다. Production Operations는 2026년 3월 31일에 GA 되었고, 코드 변경을 배포 전에 검증하는 Release Management는 Preview 단계입니다.

---

## 1. 두 가지 역할을 하나의 에이전트가 처리합니다

DevOps Agent는 배포 이후의 인시던트 조사(Production Operations)와 배포 이전의 변경 검증(Release Management)을 통합합니다. 하나의 에이전트가 동일한 서비스 토폴로지와 의존성 맵을 기반으로 동작하므로, 배포 전에는 영향 범위를 평가하고 배포 후에는 같은 맥락에서 인시던트를 조사합니다.

Production Operations는 알림 감지 즉시 사람의 개입 없이 조사를 시작합니다. 관측 도구의 지표, 로그, 트레이스, 배포 기록을 교차 분석해 근본 원인을 식별하고, 완화 조치를 Slack이나 PagerDuty로 전달합니다. Release Management는 코드가 병합되기 전에 릴리스 준비도를 평가하고, 프로덕션 유사 환경에서 변경 사항에 특화된 테스트를 자율 생성합니다.

GA 발표 시 AWS는 Preview 기간 동안 고객이 보고한 메트릭을 공유했습니다. MTTR 최대 75% 감소, 조사 속도 80% 향상, 근본 원인 정확도 94%입니다.

---

## 2. 알림이 발생하면 에이전트가 먼저 조사를 시작합니다

CloudWatch Alarm, Datadog Monitor, Dynatrace Davis AI 경고, PagerDuty 알림에서 이벤트가 감지되면 DevOps Agent는 즉시 조사를 시작합니다. 서비스 토폴로지와 의존성 맵을 활용해 영향 범위를 파악한 뒤, 관측 데이터를 교차 분석합니다. 예를 들어 CloudWatch에서 CPU 사용량 급증을 감지하고, Datadog APM 트레이스에서 특정 엔드포인트의 지연 증가를 확인한 다음, Splunk 로그에서 해당 시간대 에러 메시지를 찾는 방식으로 동작합니다.

조사가 끝나면 근본 원인과 완화 조치를 Slack 스레드, ServiceNow 티켓, PagerDuty 알림, Microsoft Teams에 자동으로 첨부합니다. 당번 엔지니어는 "무슨 일이 일어났는지"부터 시작하는 것이 아니라 "이 원인을 어떻게 해결할지"부터 시작할 수 있습니다.

GA에서는 중복 인시던트를 식별해 LINKED 상태로 묶는 Triage Agent, 조사에 필요한 코드 컨텍스트를 빌드하는 Code Indexing, 그리고 반복 작업을 자동화하는 Learned Skills와 Custom Skills가 추가되었습니다.

---

## 3. 기존 관측 도구를 대체하지 않고 상위에서 소비합니다

DevOps Agent는 다음 관측 도구와 built-in 통합을 제공합니다.

| 범주 | 도구 |
| :--- | :--- |
| 관측 (Observability) | CloudWatch, Datadog, Dynatrace, New Relic, Splunk, Grafana, Prometheus |
| CI/CD | GitHub, GitLab, Azure DevOps |
| 협업/알림 | Slack, ServiceNow, PagerDuty, Microsoft Teams |
| 프로토콜 확장 | MCP(Model Context Protocol), ACP(Agent Communication Protocol), A2A(Agent-to-Agent) |

에이전트가 이 도구들을 대체하는 것이 아니라, 각 도구가 수집한 데이터를 하나의 조사 흐름에서 교차 분석하는 상위 계층에서 동작합니다.

Grafana Mimir(Prometheus 호환) 저장 지표는 Grafana 통합으로 접근할 수 있습니다. 직접 PromQL을 실행하는 기능은 공식 문서에 명시되어 있지 않으므로, Mimir를 주요 지표 저장소로 사용하는 조직은 Grafana 통합 경유로 접근해야 합니다. AWS Athena의 S3 데이터는 CloudWatch 로그 통합으로 일부 접근할 수 있지만, Athena 쿼리 자체를 에이전트에서 직접 실행하려면 MCP 확장이 필요합니다.

Azure는 Microsoft Entra ID(구 Azure AD)를 경유해 native로 연결됩니다. 온프레미스 환경의 서비스는 MCP 서버를 통해 연결합니다. EventBridge 통합으로 조사 이벤트를 다운스트림 자동화 파이프라인으로 전송할 수 있고, Private connections 기능으로 VPC 내 private 서비스에 안전하게 연결할 수 있습니다.

---

## 4. MCP, ACP, A2A로 built-in 통합 외부를 연결합니다

Bitbucket을 소스 제어 도구로 사용하는 조직은 built-in 코드 리포지토리 통합(GitHub, GitLab, Azure DevOps)에 포함되지 않습니다. MCP(Model Context Protocol) 서버를 통해 Bitbucket 연동을 직접 구축해야 하며, 조직의 커스텀 도구, 전용 플랫폼, 자체 티켓팅 시스템과의 통합에도 같은 방식을 사용합니다.

ACP(Agent Communication Protocol)와 A2A(Agent-to-Agent)는 자체 에이전트를 안전하게 연결해 DevOps Agent의 조사 범위를 확장하는 프로토콜입니다. 조직 내부의 보안 스캐닝 에이전트를 A2A로 연결하면, 인시던트 조사 과정에서 보안 컨텍스트를 자동으로 참조할 수 있습니다.

---

## 5. 예방 권고와 자연어 SRE 인터페이스

인시던트 조사 외에도 과거 패턴을 분석해 관측성, 인프라 설정, 배포 파이프라인, 애플리케이션 복원력 네 가지 영역에서 예방 권고를 제공합니다. 권고에는 코딩 에이전트나 동료 엔지니어에게 바로 넘겨 구현할 수 있는 수준의 구체적 지시 사항인 "agent-ready spec"이 포함됩니다.

자연어 인터페이스에서는 리소스 상태 조회, 인시던트 패턴 조사, 배포 추적, 커스텀 차트 생성을 대화형으로 처리합니다. 매일 아침 데이터베이스 슬로우 쿼리를 점검하거나 최근 24시간 로그에서 이상 징후를 플래깅하는 정기 커스텀 에이전트를 설정할 수도 있습니다. 브라우저 locale 기반으로 응답 언어가 자동 번역되므로 한국어 인터페이스를 사용할 수 있습니다.

---

## 6. 릴리스 관리는 아직 Preview입니다

코드 변경이 발생하면 DevOps Agent는 코딩 표준 준수 여부, 크로스 리포지토리 의존성, 인프라 변경이 애플리케이션에 필요한 권한 범위를 벗어나는지(deterministic proof), 서비스 토폴로지 기반 영향 반경(Blast Radius)을 평가합니다. 평가 결과는 SAFE, CAUTION, BLOCK 세 단계 verdict로 제공됩니다. 이 평가를 바탕으로 위험 영역에 특화된 테스트 계획을 자율 생성하고, 사용자가 제공한 프로덕션 유사 환경에서 회귀, UX 문제, 통합 실패를 사전에 포착합니다.

이 기능은 Preview 기간 중 추가 비용 없이 사용할 수 있습니다. GA 시점과 지원 리전은 아직 확정되지 않았습니다.

---

## 7. 종량제 요금과 Support 플랜 크레딧

DevOps Agent는 종량제 요금제로 동작합니다. 에이전트가 활동하는 시간(agent-second)당 $0.0083가 부과되며, 인시던트 조사(Investigations), 릴리스 평가(Evaluations), 주문형 SRE(On-demand SRE) 세 가지 활동 유형 모두 동일한 단가를 적용합니다.

AWS Support 플랜에 가입된 조직은 크레딧을 통해 사용량을 할인받을 수 있습니다. Business Support 이상은 Support 요금의 30%, Enterprise Support는 75%, Unified Operations는 100%에 해당하는 크레딧을 매월 10일에 받습니다. 단, Support 플랜은 크레딧 혜택의 조건이지 DevOps Agent 사용 자체의 전제조건은 아닙니다. Support 플랜 없이도 종량제로 사용할 수 있으며, 신규 고객은 2개월 무료 체험과 Free Tier(10 agent spaces, 조사 20시간, 평가 15시간, 주문형 SRE 20시간)를 사용할 수 있습니다.

Release Management(Preview)는 Preview 기간 중 추가 비용 없이 사용할 수 있습니다. 에이전트가 호출하는 CloudWatch Logs Insights 등 다른 AWS 서비스 비용은 별도로 부과됩니다.

요금 부과는 2026년 4월 10일부터 시작되었습니다.

---

## 8. WGU에서 MTTR이 77% 개선된 사례

re:Invent 2024와 GA 발표에서 공개된 고객 사례 중 WGU(Western Governors University)의 결과가 구체적입니다. 191,000명의 학생을 서비스하는 Lambda 중심 환경에서 Dynatrace와 함께 사용했을 때 MTTR이 추정 2시간에서 28분으로 77% 개선되었습니다. 에이전트가 Lambda 함수 설정 오류를 내부 문서에서 발견되지 않았던 운영 지식과 연결해 식별했습니다.

United Airlines는 500개 AWS 계정, 20,000개 Lambda, Dynatrace OneAgent 38,000개 인스턴스 환경에서 다중 도구 간 블랙박스를 해소하는 데 사용했고, T-Mobile은 멀티클라우드와 온프레미스 Splunk 통합으로 로그 교차 분석을 수행했습니다. Zenchef는 해커톤 중 엔지니어 투입 없이 에이전트가 단독으로 조사를 완료해 기존 대비 약 75% 시간을 단축했습니다.

Release Management Preview의 경우 TP ICAP가 28개국 5,200명 직원의 클라우드 80% 마이그레이션 환경에서 사용했고, 24시간 규제 거래 플랫폼을 운영하는 Deriv는 SAFE/CAUTION/BLOCK verdict로 배포 리스크를 사전에 평가하고 있습니다.

---

## 9. 에이전트가 하지 못하는 것

DevOps Agent는 완화 조치를 "제안"하지만, 사용자 명시적 승인 없이 프로덕션 리소스를 자동 변경하지 않습니다. CloudWatch Container Insights를 통한 EKS 간접 분석은 가능하지만, `kubectl exec` 수준의 직접 디버깅은 공식적으로 지원하지 않습니다. 에이전트가 사용하는 LLM은 Amazon Bedrock foundation models로 AWS가 관리하며, 사용자가 모델을 지정하거나 교체할 수 없습니다. 인시던트 리포트는 자유 텍스트 형식으로 전달되므로, severity 기반 자동 라우팅이나 티켓 시스템의 필드 매핑을 에이전트 출력에서 직접 수행하기는 어렵습니다.

데이터는 Agent Space를 생성한 리전에 저장됩니다. GA 기준 지원 리전은 us-east-1, us-west-2, eu-central-1, eu-west-1, ap-southeast-2, ap-northeast-1(Tokyo) 6개입니다. Seoul(ap-northeast-2)은 포함되지 않았으므로, 한국 리전에서 데이터를 저장해야 하는 규제 요건이 있다면 현재 버전에서는 조건을 만족할 수 없습니다. 에이전트는 여러 리전의 데이터를 수집하지만, 저장과 처리는 Agent Space가 있는 리전에서 이루어집니다.

---

## 10. Reference

- [AWS DevOps Agent 공식 페이지](https://aws.amazon.com/devops-agent/)
- [AWS DevOps Agent 요금](https://aws.amazon.com/devops-agent/pricing/)
- [AWS DevOps Agent FAQ](https://aws.amazon.com/devops-agent/faqs/)
- [AWS DevOps Agent User Guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [Announcing General Availability of AWS DevOps Agent (2026-03-31)](https://aws.amazon.com/blogs/mt/announcing-general-availability-of-aws-devops-agent/)
- [AWS DevOps Agent Release Management Preview (2026-06-17)](https://aws.amazon.com/blogs/aws/aws-devops-agent-adds-release-management-capabilities-to-assess-code-changes-before-production-preview)
- [AWS Premium Support Plans](https://aws.amazon.com/premiumsupport/plans/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
