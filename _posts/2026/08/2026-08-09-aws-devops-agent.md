---
title: "AWS DevOps Agent Overview"
date: 2026-08-09 20:00:00 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, devops, ai-agent, incident-response, release-management, sre, observability]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

인시던트가 발생하면 CloudWatch 지표, APM 트레이스, 로그, 배포 기록을 번갈아 확인하며 원인을 좁혀나가는 과정에 시간이 걸립니다. AWS DevOps Agent는 알림이 감지된 순간 이 조사를 자율적으로 수행하고, 근본 원인과 완화 조치를 Slack이나 PagerDuty에 정리해 전달합니다. Production Operations는 2026년 3월 31일에 GA 되었고, 코드 변경을 배포 전에 검증하는 Release Management는 Preview 단계입니다.

> **TL;DR**  
> - 알림이 감지되면 사람 개입 없이 조사를 시작해 근본 원인과 완화 조치를 Slack, PagerDuty, ServiceNow에 붙인다. Production Operations는 2026-03-31 GA, Release Management는 아직 Preview다.  
> - 기존 관측 도구를 대체하지 않고 상위에서 소비한다. **Grafana는 read-only, Datadog은 1-way**이며, Alertmanager는 네이티브 통합이 아니라 generic webhook을 거쳐야 한다.  
> - 완화 조치를 제안할 뿐 승인 없이 프로덕션 리소스를 바꾸지 않는다. EKS는 introspection만 되고 `kubectl exec`은 지원하지 않으며, Bedrock 모델은 교체할 수 없다.  
> - agent-second당 $0.0083 종량제다. 데이터는 Agent Space를 만든 리전에 저장되는데 **GA 리전 6곳에 서울(ap-northeast-2)은 없다.**  
{: .prompt-info}

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
| 관측 (Observability) | CloudWatch, Datadog, Dynatrace, New Relic, Splunk, Grafana |
| CI/CD | GitHub, GitLab, Azure DevOps |
| 협업/알림 | Slack, ServiceNow, PagerDuty, Microsoft Teams |
| AWS 서비스 | EKS, EventBridge, Private Connections |
| 프로토콜 확장 | MCP(Model Context Protocol), ACP(Agent Communication Protocol), A2A(Agent-to-Agent) |

에이전트가 이 도구들을 대체하는 것이 아니라, 각 도구가 수집한 데이터를 하나의 조사 흐름에서 교차 분석하는 상위 계층에서 동작합니다.

각 관측 도구의 통합 범위는 동일하지 않습니다. 공식 문서에서 확인한 구체적인 기능은 다음과 같습니다.

**Grafana**는 메트릭, 대시보드, 알럿 데이터를 read-only로 조회합니다. Grafana에 연결된 모든 데이터 소스(Prometheus, Loki, OpenSearch 등)에 접근할 수 있으므로, Grafana MCP 서버를 경유해 Prometheus 지표를 읽을 수 있습니다. 하지만 에이전트가 PromQL 쿼리를 직접 작성하고 실행한다는 공식 문서상 명시는 없습니다. Grafana 알럿의 Contact Points webhook을 통해 조사를 자동으로 트리거할 수도 있지만, Amazon Managed Grafana(AMG)는 webhook contact points를 지원하지 않아 이 경로를 사용할 수 없습니다. VPC 내부에만 노출된 private Grafana도 Private Connections 기능으로 연결할 수 있습니다. VPC Lattice 기반으로 동작하며, 에이전트가 VPC 내에 ENI를 프로비저닝해 Grafana에 private network path로 접근합니다. 공개 인터넷 노출이나 Internet Gateway가 불필요하고, Private Hosted Zone DNS 이름과 사설 인증서도 지원됩니다.

**Datadog**은 built-in 1-way integration으로, Datadog 모니터 알럿을 webhook으로 받아 조사를 자동 시작합니다. 조사 중에는 Datadog의 Remote MCP Server(mcp.datadoghq.com 등)를 연결해 telemetry를 introspect할 수 있습니다. Datadog API를 직접 호출하거나 DQL(Datadog Query Language) 쿼리를 실행하는 것은 Datadog MCP 서버가 제공하는 도구 범위 내에서만 가능합니다.

**EKS**는 클러스터 introspection, pod 로그, cluster events를 공식 지원합니다. Public과 Private EKS 환경 모두에서 동작하며, AWS 서비스 API를 통해 접근합니다. 단, `kubectl exec` 수준의 직접 디버깅은 지원하지 않습니다.

**Splunk**는 멀티클라우드와 온프레미스 로그를 교차 분석하는 데 사용됩니다. T-Mobile 사례에서 Splunk 통합으로 로그 교차 분석을 수행한 것이 확인됩니다.

**Alertmanager는 네이티브 지원 통합이 아닙니다.** 공식 문서의 지원 통합 목록에 Alertmanager가 없으며, Prometheus 자체도 Grafana의 데이터 소스로만 접근 가능합니다. Alertmanager 알럿을 트리거로 사용하려면 Generic Webhook을 통해 간접적으로 연결해야 합니다. Alertmanager의 webhook receiver를 DevOps Agent의 generic webhook endpoint로 설정하면 기술적으로 조사를 시작할 수 있지만, 공식적으로 문서화된 통합은 아닙니다.

Bitbucket, 온프레미스 서비스, 자체 티켓팅 시스템 등 built-in 통합에 포함되지 않는 도구는 MCP 서버를 통해 연결합니다. Azure는 Microsoft Entra ID(구 Azure AD)를 경유해 native로 연결되며, EventBridge 통합으로 조사 이벤트를 다운스트림 자동화 파이프라인으로 전송할 수 있고, Private Connections 기능으로 VPC 내 private 서비스에 안전하게 연결할 수 있습니다.

---

## 4. MCP, ACP, A2A로 built-in 통합 외부를 연결합니다

built-in 통합에 포함되지 않는 도구는 세 가지 프로토콜로 연결합니다.

**MCP(Model Context Protocol)** 서버는 private 또는 remote로 연결할 수 있습니다. Bitbucket 연동, 조직의 커스텀 도구, 전용 플랫폼, 자체 티켓팅 시스템과의 통합에 사용합니다. Datadog과 Grafana도 각자의 Remote MCP Server를 통해 연결되므로, MCP는 사실상 DevOps Agent의 확장 스펙 역할을 합니다.

**A2A(Agent-to-Agent)** 는 A2A v1.0 규격을 따르며, HTTP+JSON 바인딩으로 동작합니다. 단순한 정보 공유를 넘어 실제 작업을 비동기로 위임할 수 있습니다. A2A로 연결된 에이전트는 DevOps Agent에게 `investigate` 명령을 보내 5~8분간의 심층 조사를 요청하거나, `chat`으로 즉각적인 운영 질문을 할 수 있습니다. 태스크 생성, 상태 추적, 취소도 지원하며, `agent` 클라이언트 타입과 `operate` 스코프를 조합하면 자율 에이전트가 메시지 전송, 채팅 생성, 백로그 태스크 관리까지 수행할 수 있습니다. 모든 A2A 호출은 CloudTrail에 `AuthenticateAccessToken` 이벤트로 기록됩니다. AWS는 A2A 응답을 사람 검토 없이 자동 실행하지 말 것을 명시적으로 권고하고 있습니다.

**ACP(Agent Communication Protocol)** 는 A2A와 함께 자체 에이전트를 안전하게 연결하는 또 다른 프로토콜입니다.

---

## 5. 인프라 지식을 에이전트에 주입하고 예방 권고를 받습니다

DevOps Agent는 조사를 시작하기 전에 인프라 컨텍스트를 학습합니다. GA에서 추가된 Code Indexing은 연결된 코드 리포지토리를 인덱싱해 서비스 의존성 맵을 만들고, Learned Skills는 클라우드 계정, 코드, 텔레메트리를 분석해 리소스 관계와 임계 요청 경로를 자동으로 파악합니다.

사용자가 직접 지식을 주입할 수도 있습니다. Skills 기능에 Markdown 지시서(SKILL.md), 참조 문서(references/), 아키텍처 다이어그램(assets/)을 업로드하면, 에이전트가 조사 중 이를 참조합니다. 예를 들어 "우리 인프라는 EKS와 Calico 네트워킹을 사용한다", "이 서비스의 트러블슈팅 절차는 다음과 같다"를 SKILL.md로 작성해 두면, 에이전트가 매 조사마다 이 지식을 활용합니다. Skills는 UI에서 직접 작성하거나 ZIP 업로드, GitHub 리포지토리 import로 등록할 수 있습니다.

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

DevOps Agent는 완화 조치를 "제안"하지만, 사용자 명시적 승인 없이 프로덕션 리소스를 자동 변경하지 않습니다. EKS 클러스터, pod 로그, cluster events는 introspection할 수 있지만 `kubectl exec` 수준의 직접 디버깅은 지원하지 않습니다. Grafana 통합은 read-only로만 동작하며 대시보드나 알럿의 생성/수정/삭제가 불가능합니다. Datadog 통합은 1-way로 양방향이 아닙니다.

에이전트가 사용하는 LLM은 Amazon Bedrock foundation models로 AWS가 관리하며, 사용자가 모델을 지정하거나 교체할 수 없습니다. 인시던트 리포트는 자유 텍스트 형식으로 전달되므로, severity 기반 자동 라우팅이나 티켓 시스템의 필드 매핑을 에이전트 출력에서 직접 수행하기는 어렵습니다.

데이터는 Agent Space를 생성한 리전에 저장됩니다. GA 기준 지원 리전은 us-east-1, us-west-2, eu-central-1, eu-west-1, ap-southeast-2, ap-northeast-1(Tokyo) 6개입니다. Seoul(ap-northeast-2)은 포함되지 않았으므로, 한국 리전에서 데이터를 저장해야 하는 규제 요건이 있다면 현재 버전에서는 조건을 만족할 수 없습니다. 에이전트는 여러 리전의 데이터를 수집하지만, 저장과 처리는 Agent Space가 있는 리전에서 이루어집니다.

---

## 10. 프롬프트 인젝션 보호

DevOps Agent는 로그, 리소스 태그, 운영 데이터를 입력으로 소비하므로, 악성 명령이 외부 데이터에 삽입되는 prompt injection 공격에 노출될 수 있습니다. AWS는 이에 대해 4계층 방어를 공식 보안 문서에 명시하고 있습니다.

첫째, 에이전트가 사용하는 도구는 티켓과 support case 생성을 제외하고 리소스를 변경할 수 없습니다. 악성 명령이 인프라나 애플리케이션을 수정하는 것을 원천 차단합니다. 둘째, 에이전트는 primary 및 연결된 secondary AWS 계정에 할당된 역할 범위 내에서만 동작합니다. 셋째, ASL-3(AI Safety Level 3) 보호가 적용된 모델과 Amazon Bedrock Guardrails의 prompt attack filter로 prompt injection 및 jailbreak 시도를 탐지하고 차단합니다. 넷째, 에이전트의 모든 추론 단계와 행동은 journal에 기록되며, journal 항목은 기록 후 수정할 수 없습니다. 악성 행동을 숨기려는 시도를 방지합니다.

공동 책임 모델이 적용됩니다. 에이전트에 입력을 제공하는 외부 시스템에 접근할 수 있는 사용자를 신뢰할 수 있는 사용자로 제한하는 것은 고객의 책임입니다. Custom MCP 서버를 통해 임의의 도구를 추가하면 추가적인 prompt injection 기회가 발생할 수 있으므로, MCP 서버 도구에 대한 검토가 필요합니다.

---

## 11. 다중 Agent Space와 헤드리스 모드

하나의 조직에서 팀별, 계정별, 환경별로 별도의 Agent Space를 만들 수 있습니다. 각 Agent Space는 자체 구성과 권한을 가지며, 서로 엄격하게 격리됩니다. 하나의 MCP 클라이언트(IDE, CLI)에서 `agent_space_id`를 전달해 여러 Agent Space를 번갈아 호출하는 multi-Agent-Space routing도 지원합니다.

일정 주기(cadence)나 이벤트 기반으로 동작하는 커스텀 에이전트를 만들 수 있습니다. 매일 아침 데이터베이스 상태를 점검하거나 로그 이상 징후를 플래깅하는 에이전트를 설정하는 방식입니다. Headless Mode를 사용하면 웹 앱 없이 모든 기능을 MCP/A2A 엔드포인트로 호출할 수 있어, 자체 자동화 파이프라인에 DevOps Agent를 통합할 수 있습니다.

---

## 12. Reference

- [AWS DevOps Agent 공식 페이지](https://aws.amazon.com/devops-agent/)
- [AWS DevOps Agent 요금](https://aws.amazon.com/devops-agent/pricing/)
- [AWS DevOps Agent FAQ](https://aws.amazon.com/devops-agent/faqs/)
- [AWS DevOps Agent User Guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [Announcing General Availability of AWS DevOps Agent (2026-03-31)](https://aws.amazon.com/blogs/mt/announcing-general-availability-of-aws-devops-agent/)
- [AWS DevOps Agent Release Management Preview (2026-06-17)](https://aws.amazon.com/blogs/aws/aws-devops-agent-adds-release-management-capabilities-to-assess-code-changes-before-production-preview)
- [AWS Premium Support Plans](https://aws.amazon.com/premiumsupport/plans/)
- [AWS DevOps Agent Security (Prompt Injection Protection)](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security.html)
- [AWS DevOps Agent Remote Servers (MCP/A2A)](https://docs.aws.amazon.com/devopsagent/latest/userguide/accessing-devops-agent-connect-to-devops-agent-remote-servers.html)
- [AWS DevOps Agent Grafana Integration](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-grafana.html)
- [AWS DevOps Agent Datadog Integration](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-datadog.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
