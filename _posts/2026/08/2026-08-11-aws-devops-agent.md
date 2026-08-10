---
title: "AWS DevOps Agent: AI 기반 인시던트 대응과 릴리스 관리 에이전트"
date: 2026-08-11 20:00:00 +0900
author: kkamji
categories: [Cloud, DevOps]
tags: [aws, devops, ai-agent, incident-response, release-management, sre, observability]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

새벽 2시, 프로덕션 환경에서 5xx 에러율이 급등한다. PagerDuty 알림이 울리고, 당번 엔지니어는 컨텍스트를 전환한 뒤 CloudWatch 대시보드, APM 트레이스, 로그, 배포 기록을 번갈아 열어본다. 인과 관계를 파악하기까지 수십 분이 소요되고, 그 사안에 사용자 영향은 누적된다. AWS는 2024년 re:Invent에서 이 문제를 자율 조사 에이전트로 접근한다. AWS DevOps Agent는 알림이 발생한 순간 자율적으로 조사를 시작하고, 근본 원인 분석과 완화 조치를 Slack이나 PagerDuty로 전달하는 "항상 대기 중인 온콜 엔지니어"를 표방한다.

이 글에서는 AWS DevOps Agent가 무엇인지, 어떤 아키텍처로 동작하는지, 어디까지 가능하고 어디에 한계가 있는지를 공식 문서와 공개된 사례를 기준으로 정리한다.

---

## 1. AWS DevOps Agent란 무엇인가

AWS DevOps Agent는 소프트웨어 변경과 프로덕션 운영을 가로지르는 AI 에이전트다. 핵심 역할은 두 가지 영역으로 나뉜다.

| 영역 | 단계 | 상태 | 핵심 기능 |
| :--- | :--- | :--- | :--- |
| **Production Operations** | 배포 이후 | 일반 available | 자율 인시던트 조사, 근본 원인 분석, 완화 조치 제안, 예방 권고 |
| **Release Management** | 배포 이전 | Preview | 코드 변경 사항의 릴리스 준비도 검토, 자율 릴리스 테스트 실행 |

Production Operations는 알림이 발생하면 사람의 개입 없이 조사를 시작한다. 2024년 re:Invent에서 preview로 발표된 이후 점진적으로 일반 available 상태로 전환 중이다. Release Management는 코드가 병합되기 전에 릴리스 준비도를 평가하고, 프로덕션과 유사한 환경에서 변경 사항에 특화된 테스트를 자율 생성 및 실행한다. 이 영역은 현재 Preview 단계다.

이 둘을 하나의 에이전트가 통합한다는 점이 핵심이다. 동일한 서비스 토폴로지 이해를 바탕으로, 배포 전에는 변경의 영향 범위를 평가하고 배포 후에는 인시던트를 조사한다.

---

## 2. 프로덕션 운영: 자율 인시던트 조사

### 2.1. 동작 방식

AWS DevOps Agent는 관측 도구에서 이벤트나 알림이 감지되면 즉시 자율 조사를 시작한다. 조사 과정은 다음 단계를 따른다.

```text
관측 도구(CloudWatch, Datadog, Splunk 등)에서 이벤트 감지
  ↓
DevOps Agent가 자율 조사 시작
  ↓
서비스 토폴로지와 의존성 맵을 활용해 영향 범위 파악
  ↓
관측 데이터 교차 분석 (지표, 로그, 트레이스, 배포 기록)
  ↓
근본 원인 식별 + 완화 조치 도출
  ↓
Slack / ServiceNow / PagerDuty로 분석 결과 자동 전달
```

이 과정에서 사람의 개입은 필요하지 않다. 알림이 Slack에 도달할 때 이미 분석 결과가 함께 표시되므로, 당번 엔지니어는 "무슨 일이 일어났는지"부터 시작하는 것이 아니라 "이 원인을 어떻게 해결할지"부터 시작할 수 있다.

### 2.2. 관측 도구 통합

DevOps Agent는 다음 관측 도구와의 built-in 통합을 제공한다.

| 도구 | 통합 방식 | 비고 |
| :--- | :--- | :--- |
| Amazon CloudWatch | AWS 네이티브 | 지표, 로그, 알람 |
| Datadog | Native integration | APM, 인프라 모니터링 |
| Dynatrace | Native integration | Davis AI 경고를 Agent 조사 자동 트리거로 전달 |
| Grafana | Native integration | Prometheus / Loki 기반 대시보드 |
| New Relic | Native integration | APM, 인프라 |
| Splunk | Native integration | 로그 중앙화, SIEM |

이 통합은 에이전트가 해당 도구의 데이터에 접근해 교차 분석을 수행한다는 의미다. 예를 들어 CloudWatch에서 CPU 사용량 급증을 감지하고, Datadog APM 트레이스에서 특정 엔드포인트의 지연 증가를 확인한 뒤, Splunk 로그에서 해당 시간대의 에러 메시지를 교차 참조하는 방식으로 동작한다.

### 2.3. 예방 권고(Proactive Recommendations)

인시던트 조사 외에도, 과거 인시던트 패턴을 분석해 네 가지 영역에서 예방 권고를 제공한다.

- **관측성(Observability)**: 놓친 지표나 로그 경보 제안
- **인프라 최적화(Infrastructure Optimization)**: 리소스 설정, 오토스케일링 임계값 조정 제안
- **배포 파이프라인(Deployment Pipeline)**: 배포 프로세스 개선점 제안
- **애플리케이션 복원력(Application Resilience)**: 회복성 강화 방안 제안

권고에는 "agent-ready spec"이 포함된다. 이는 코딩 에이전트나 동료 엔지니어에게 바로 넘겨 구현할 수 있는 수준의 구체적 지시 사항이다. 백로그를 수동으로 관리하지 않아도, 에이전트가 지속적으로 개선점을 식별하고 전달한다.

---

## 3. 릴리스 관리: 배포 전 변경 검증 (Preview)

릴리스 관리 기능은 코드가 프로덕션에 도달하기 전에 두 가지 검증을 수행한다.

### 3.1. 릴리스 준비도 검토(Release Readiness Review)

코드 변경이 발생하면 DevOps Agent는 다음 항목을 검사한다.

- **표준 준수**: 코딩 표준, 아키텍처 가이드라인 부합 여부
- **의존성 영향**: 크로스 리포지토리 의존성 매핑으로 breaking change 사전 식별
- **접근 제어**: 인프라 변경이 Well-Architected 모범 사례를 벗어나는지 수학적 검증
- **영향 반경(Blast Radius)**: 서비스 토폴로지를 바탕으로 변경이 시스템 전체에 미치는 영향 추론

기능적 검증(Functional Verification)도 수행한다. 변경된 소프트웨어가 AWS 관리 검증 환경에서 빌드되고 정상 실행되는지 확인한다.

### 3.2. 변경 특화 테스트(Change-Specific Testing)

정적 회귀 테스트 스위트를 실행하는 것이 아니라, 릴리스 준비도 검토에서 식별된 위험 영역을 기반으로 테스트 계획을 자율 생성한다. 웹 및 API 기반 애플리케이션을 대상으로, 사용자가 제공한 프로덕션 유사 환경에서 회귀, UX 문제, 통합 실패를 사전에 포착한다.

이 기능은 **현재 Preview**이므로, 프로덕션 의사결정의 유일한 게이트로 사용하기에는 이르다. GA 시점과 지원 리전은 AWS 공식 발표를 확인해야 한다.

---

## 4. 확장 통합: MCP와 A2A

DevOps Agent는 built-in 통합 외에 두 가지 확장 경로를 제공한다.

- **MCP(Model Context Protocol) 서버**: private 또는 remote MCP 서버를 연결해 조직의 커스텀 도구, 전용 플랫폼, 자체 티켓팅 시스템과 통합한다.
- **A2A(Agent-to-Agent)**: 자체 에이전트를 안전하게 연결해 DevOps Agent의 조사 범위를 확장한다.

예를 들어 Bitbucket을 소스 제어 도구로 사용하는 조직은, built-in 통합이 없으므로 MCP 서버를 통해 Bitbucket 연동을 직접 구축해야 한다. 이는 추가 개발 작업이 필요하다는 의미다.

---

## 5. 지원 채널과 SRE 작업

### 5.1. 결과 라우팅

DevOps Agent는 조사 결과와 권고를 다음 채널로 자동 라우팅한다.

- **Slack**: 분석 결과를 스레드 또는 채널 메시지로 게시
- **ServiceNow**: 인시던트 티켓에 분석 내용 첨부
- **PagerDuty**: 알림과 함께 근본 원인 및 완화 조치 전달

### 5.2. 자연어 SRE 인터페이스

에이전트의 환경 이해를 활용해 자연어로 SRE 작업을 수행할 수 있다. 리소스 상태 조회, 인시던트 패턴 조사, 배포 추적, 예방 권고 탐색을 대화형 인터페이스에서 처리한다. 커스텀 차트와 보고서를 생성하고 저장하며 팀과 공유할 수 있다.

또한 정기적으로 실행되는 커스텀 에이전트를 만들 수 있다. 예를 들어 매일 아침 데이터베이스 헬스 체크(슬로우 쿼리, 파라미터 튜닝 점검)를 수행하거나, 최근 24시간 로그를 리뷰해 이상 징후를 플래깅하는 에이전트를 설정할 수 있다.

---

## 6. 요금과 Support 플랜 크레딧

AWS DevOps Agent의 요금은 연결된 AWS Support 플랜에 따라 산정된다.

| Support 플랜 | DevOps Agent 사용 크레딧 | 비고 |
| :--- | :--- | :--- |
| Business Support | Support 요금의 30% | 기본 비즈니스 지원 |
| Enterprise Support | Support 요금의 75% | TAM, IAM 컨설팅 포함 |
| Unified Operations | Support 요금의 100% | 전액 크레딧 적용 |

Enterprise Support를 사용하는 조직은 Support 요금의 75%에 해당하는 크레딧을 DevOps Agent 사용에 적용할 수 있다. Support 플랜 없이 DevOps Agent를 단독 구매하는 것은 불가능하며, 크레딧 적용 방식과 정확한 금액은 AWS 영업팀 또는 계정 관리자에게 확인해야 한다.

릴리스 관리(Preview) 기능의 요금은 아직 공식적으로 확정되지 않았다. GA 시점에 별도 안내가 예상된다.

---

## 7. 할 수 있는 것

다음은 AWS DevOps Agent가 공식적으로 지원하는 기능이다.

- **자율 인시던트 조사**: 알림 감지 즉시, 사람 개입 없이 관측 데이터를 교차 분석해 근본 원인 식별
- **완화 조치 제안**: 인시던트 해결을 위한 구체적 액션을 Slack, PagerDuty, ServiceNow에 자동 전달
- **멀티 소스 관측 통합**: CloudWatch, Datadog, Dynatrace, Grafana, New Relic, Splunk 데이터를 하나의 조사 흐름에서 교차 분석
- **예방 권고**: 과거 인시던트 패턴 분석을 통한 관측성, 인프라, 배포, 복원력 개선점 자동 식별
- **릴리스 준비도 검토**(Preview): 크로스 리포지토리 의존성, 접근 제어, 영향 반경 사전 평가
- **변경 특화 테스트**(Preview): 위험 영역 기반 테스트 자율 생성 및 실행
- **자연어 SRE 작업**: 리소스 상태 조회, 인시던트 패턴 조사, 커스텀 차트 및 보고서 생성
- **정기 커스텀 에이전트**: 일일 데이터베이스 헬스 체크, 로그 이상 탐지 등 정기 작업 자동화
- **MCP / A2A 확장**: built-in 통합에 없는 도구를 프로토콜 기반으로 연결

---

## 8. 할 수 없는 것

다음은 현재 버전의 제약이다. 일부는 GA 이후에 변경될 수 있다.

- **Bitbucket 직접 통합 불가**: Release Management의 built-in 코드 리포지토리 통합은 Azure DevOps, GitHub, GitLab만 지원한다. Bitbucket은 MCP 서버 자체 구축이 필요하다.
- **EKS pod 수준 직접 진단 미지원**: CloudWatch Container Insights를 통한 간접 분석은 가능하나, `kubectl exec`나 `kubectl describe` 수준의 직접 디버깅은 명시적으로 지원하지 않는다.
- **릴리스 관리는 Preview**: 프로덕션 게이트로 사용하기에는 검증이 더 필요하다. SLA가 보장되지 않는다.
- **AWS 생태계 종속**: DevOps Agent는 AWS 계정 내에서 동작하며, 멀티클라우드 관측 데이터는 통합 도구(Datadog, Splunk 등) 경유로만 접근한다.
- **자율 복구 실행 불가**: 완화 조치를 "제안"하지만, 사용자 명시적 승인 없이 프로덕션 리소스를 자동 변경하지 않는다. (SSM Runbook 연동 시 승인 게이트가 별도로 존재)
- **Seoul 리전 가용성 불확실**: Production Operations는 AWS 글로벌 인프라에서 동작하지만, 특정 리전의 기능 지원 여부는 AWS 계정팀에 확인해야 한다. 공식 문서에 리전별 기능 매트릭스가 명시되어 있지 않다.
- **커스텀 LLM 모델 선택 불가**: 에이전트가 사용하는 LLM은 AWS가 관리하며, 사용자가 모델을 지정하거나 교체할 수 없다.
- **구조화된 출력 제약**: 인시던트 리포트가 자유 텍스트 형식으로 전달되므로, severity 기반 자동 라우팅이나 티켓 시스템의 필드 매핑을 에이전트 출력에서 직접 수행하기 어렵다.

---

## 9. 기존 관측 도구(Mimir, Datadog, Athena)와의 관계

DevOps Agent는 기존 관측 도구를 대체하지 않는다. 오히려 이 도구들이 수집한 데이터를 소비하는 상위 계층에서 동작한다.

| 관측 도구 | DevOps Agent와의 관계 |
| :--- | :--- |
| Grafana Mimir (Prometheus 호환) | Grafana 통합을 통해 Mimir 저장 지표에 접근 가능. 직접 PromQL 실행은 명시되지 않음 |
| Datadog | Native integration으로 APM, 로그, 인프라 메트릭 교차 분석 |
| AWS Athena | 간접적. CloudWatch 로그와 S3 데이터는 CloudWatch 통합으로, Athena 쿼리 자체는 MCP 확장 필요 |
| CloudFront | CloudWatch 지표/로그 통합으로 엣지 에러 분석 가능 |

다중 소스 상관 분석(예: 5xx 급증 시 Mimir 메트릭과 Datadog 트레이스, CloudFront 로그를 동시에 교차 참조)은 Datadog 통합이 가장 강력하게 지원된다. Mimir나 Athena의 경우, Grafana 통합이나 MCP 확장을 통한 간접 경로를 사용해야 한다.

---

## 10. 사례: MTTR 개선 효과

공개된 고객 사례에서 DevOps Agent의 효과를 확인할 수 있다.

| 고객 | 핵심 환경 | 효과 |
| :--- | :--- | :--- |
| United Airlines | Dynatrace 38,000 OneAgent, 500 AWS 계정, 20,000 Lambda | 다중 도구 간 블랙박스 해소. 단일 화면에서 원인 파악 |
| T-Mobile | 멀티클라우드, 온프레미스 Splunk | Splunk 통합으로 멀티클라우드 로그 교차 분석 |
| WGU (Western Governors University) | Dynatrace, Lambda 중심 | MTTR 77% 개선 (추정 2시간에서 28분). Lambda 설정 오님이 근본 원인으로 즉시 식별 |
| Zenchef | 멀티 비즈니스 유닛, API 통합 | 해커톤 중 엔지니어 투입 없이 에이전트가 단독 조사 완료 |

WGU 사례에서 주목할 점은, 에이전트가 Lambda 함수 설정 오류를 "내부 문서에서 발견되지 않았던 운영 지식"과 연결해 식별했다는 것이다. 이는 에이전트가 단순히 지표를 읽는 것이 아니라, 환경의 맥락(topology, 과거 배포, 문서)을 학습해 활용한다는 것을 보여준다.

---

## 11. 도입을 검토할 때 확인할 것

AWS DevOps Agent 도입을 실제로 검토한다면, 다음 항목을 사전에 확인해야 한다.

1. **Support 플랜과 크레딧**: 현재 Support 플랜에서 DevOps Agent 크레딧이 어떻게 적용되는지 AWS 계정팀에 확인한다.
2. **관측 도구 통합 범위**: 사용 중인 관측 도구가 built-in 통합 목록에 있는지, 없다면 MCP 확장이 가능한지 확인한다.
3. **코드 리포지토리**: Bitbucket을 사용하는 경우 Release Management 기능을 built-in으로 사용할 수 없다. MCP 서버 구축 여부를 결정해야 한다.
4. **알림 파이프라인**: 기존 CloudWatch Alarm이나 Datadog Monitor에서 SNS 또는 직접 통합으로 알림을 라우팅하는 아키텍처를 설계한다.
5. **릴리스 관리(GA) 대기**: Preview 기능에 프로덕션 의존성을 두지 않는다. Production Operations부터 먼저 도입하고, Release Management는 GA 이후 평가한다.
6. **데이터 처리 리전**: 에이전트가 관측 데이터를 처리하는 리전이 규제 요건을 만족하는지 확인한다. 공식 문서에 따르면 데이터가 "다른 리전에서 처리될 수 있다".

---

## Reference

- [AWS DevOps Agent 공식 페이지](https://aws.amazon.com/devops-agent/)
- [AWS DevOps Agent User Guide](https://docs.aws.amazon.com/devopsagent/)
- [AWS DevOps Agent API Reference](https://docs.aws.amazon.com/devopsagent/latest/APIReference/)
- [AWS Premium Support Plans](https://aws.amazon.com/premiumsupport/plans/)
- [WGU MTTR 개선 사례 (re:Invent 2024)](https://aws.amazon.com/devops-agent/)
- [United Airlines 사례](https://aws.amazon.com/devops-agent/)
- [AWS re:Invent 2024 발표](https://aws.amazon.com/reinvent/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
