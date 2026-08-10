---
title: "AWS DevOps Agent: 새벽 알림 없이 인시던트를 조사하는 방법"
date: 2026-08-09 20:00:00 +0900
author: kkamji
categories: [Cloud, DevOps]
tags: [aws, devops, ai-agent, incident-response, release-management, sre, observability]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

PagerDuty 알림이 울리면 당번 엔지니어는 컨텍스트를 전환한다. CloudWatch 대시보드를 열고, Datadog APM 트레이스를 뒤지고, 최근 배포 기록을 확인하면서 원인을 좁혀나간다. 이 과정에 걸리는 시간이 곧 MTTR이다. AWS DevOps Agent는 알림이 발생한 순간 이 조사를 자율적으로 수행하고, 사람이 Slack 메시지를 열었을 때 이미 근본 원인과 완화 조치가 정리되어 있는 상태를 만든다.

2024년 re:Invent에서 preview로 발표된 Production Operations 기능은 현재 일반 available 상태로 전환되었고, 코드 변경을 배포 전에 검증하는 Release Management는 Preview 단계다.

---

## 1. 두 가지 역할을 하나의 에이전트가 처리한다

DevOps Agent는 배포 이후의 인시던트 조사(Production Operations)와 배포 이전의 변경 검증(Release Management)을 통합한다. 하나의 에이전트가 동일한 서비스 토폴로지와 의존성 맵을 기반으로 동작하므로, 배포 전에는 영향 범위를 평가하고 배포 후에는 같은 맥락에서 인시던트를 조사한다.

Production Operations는 알림 감지 즉시 사람의 개입 없이 조사를 시작한다. 관측 도구의 지표, 로그, 트레이스, 배포 기록을 교차 분석해 근본 원인을 식별하고, 완화 조치를 Slack이나 PagerDuty로 전달한다. Release Management는 코드가 병합되기 전에 릴리스 준비도를 평가하고, 프로덕션 유사 환경에서 변경 사항에 특화된 테스트를 자율 생성한다.

---

## 2. 알림이 발생하면 에이전트가 먼저 조사를 시작한다

CloudWatch Alarm, Datadog Monitor, Dynatrace Davis AI 경고에서 이벤트가 감지되면 DevOps Agent는 즉시 조사를 시작한다. 서비스 토폴로지와 의존성 맵을 활용해 영향 범위를 파악한 뒤, 관측 데이터를 교차 분석한다. 예를 들어 CloudWatch에서 CPU 사용량 급증을 감지하고, Datadog APM 트레이스에서 특정 엔드포인트의 지연 증가를 확인한 다음, Splunk 로그에서 해당 시간대 에러 메시지를 찾는 방식으로 동작한다.

조사가 끝나면 근본 원인과 완화 조치를 Slack 스레드, ServiceNow 티켓, PagerDuty 알림에 자동으로 첨부한다. 당번 엔지니어는 "무슨 일이 일어났는지"부터 시작하는 것이 아니라 "이 원인을 어떻게 해결할지"부터 시작할 수 있다.

---

## 3. 기존 관측 도구를 대체하지 않고 상위에서 소비한다

DevOps Agent는 CloudWatch, Datadog, Dynatrace, Grafana, New Relic, Splunk와 built-in 통합을 제공한다. 에이전트가 이 도구들을 대체하는 것이 아니라, 각 도구가 수집한 데이터를 하나의 조사 흐름에서 교차 분석하는 상위 계층에서 동작한다.

Grafana Mimir(Prometheus 호환) 저장 지표는 Grafana 통합으로 접근할 수 있다. 직접 PromQL을 실행하는 기능은 공식 문서에 명시되어 있지 않으므로, Mimir를 주요 지표 저장소로 사용하는 조직은 Grafana 통합 경유로 접근해야 한다. AWS Athena의 S3 데이터는 CloudWatch 로그 통합으로 일부 접근할 수 있지만, Athena 쿼리 자체를 에이전트에서 직접 실행하려면 MCP 확장이 필요하다.

---

## 4. MCP와 A2A로 built-in 통합 외부를 연결한다

Bitbucket을 소스 제어 도구로 사용하는 조직은 built-in 코드 리포지토리 통합(Azure DevOps, GitHub, GitLab)에 포함되지 않는다. 이 경우 MCP(Model Context Protocol) 서버를 통해 Bitbucket 연동을 직접 구축해야 한다. MCP 서버는 private 또는 remote로 연결할 수 있으며, 조직의 커스텀 도구, 전용 플랫폼, 자체 티켓팅 시스템과의 통합에도 같은 방식을 사용한다.

A2A(Agent-to-Agent)는 자체 에이전트를 안전하게 연결해 DevOps Agent의 조사 범위를 확장하는 프로토콜이다. 예를 들어 조직 내부의 보안 스캐닝 에이전트를 A2A로 연결하면, 인시던트 조사 과정에서 보안 컨텍스트를 자동으로 참조할 수 있다.

---

## 5. 예방 권고와 자연어 SRE 인터페이스

인시던트 조사 외에도 과거 패턴을 분석해 관측성, 인프라 설정, 배포 파이프라인, 애플리케이션 복원력 네 가지 영역에서 예방 권고를 제공한다. 권고에는 코딩 에이전트나 동료 엔지니어에게 바로 넘겨 구현할 수 있는 수준의 구체적 지시 사항인 "agent-ready spec"이 포함된다.

자연어 인터페이스에서는 리소스 상태 조회, 인시던트 패턴 조사, 배포 추적, 커스텀 차트 생성을 대화형으로 처리한다. 매일 아침 데이터베이스 슬로우 쿼리를 점검하거나 최근 24시간 로그에서 이상 징후를 플래깅하는 정기 커스텀 에이전트를 설정할 수도 있다.

---

## 6. 릴리스 관리는 아직 Preview다

코드 변경이 발생하면 DevOps Agent는 코딩 표준 준수 여부, 크로스 리포지토리 의존성, 인프라 변경의 Well-Architected 부합 여부, 서비스 토폴로지 기반 영향 반경(Blast Radius)을 평가한다. 이 평가를 바탕으로 위험 영역에 특화된 테스트 계획을 자율 생성하고, 사용자가 제공한 프로덕션 유사 환경에서 회귀, UX 문제, 통합 실패를 사전에 포착한다.

이 기능은 현재 Preview이므로 프로덕션 의사결정의 유일한 게이트로 사용하기에는 이르다. GA 시점과 지원 리전은 AWS 공식 발표를 확인해야 한다.

---

## 7. 요금은 Support 플랜 크레딧으로 산정된다

DevOps Agent의 요금은 연결된 AWS Support 플랜에 따라 산정된다. Business Support는 Support 요금의 30%, Enterprise Support는 75%, Unified Operations는 100%에 해당하는 크레딧을 DevOps Agent 사용에 적용할 수 있다. Support 플랜 없이 DevOps Agent를 단독 구매하는 것은 불가능하며, 크레딧 적용 방식과 정확한 금액은 AWS 계정 관리자에게 확인해야 한다.

Release Management(Preview) 기능의 요금은 아직 공식적으로 확정되지 않았다.

---

## 8. WGU에서 MTTR이 77% 개선된 사례

re:Invent 2024에서 공개된 고객 사례 중 WGU(Western Governors University)의 결과가 구체적이다. Lambda 중심 환경에서 Dynatrace와 함께 사용했을 때 MTTR이 추정 2시간에서 28분으로 개선되었다. 에이전트가 Lambda 함수 설정 오류를 내부 문서에서 발견되지 않았던 운영 지식과 연결해 식별했다는 점에서, 단순히 지표를 읽는 것이 아니라 환경의 맥락을 활용한다는 것을 보여준다.

United Airlines는 500개 AWS 계정, 20,000개 Lambda, Dynatrace OneAgent 38,000개 인스턴스 환경에서 다중 도구 간 블랙박스를 해소하는 데 사용했고, T-Mobile은 멀티클라우드와 온프레미스 Splunk 통합으로 로그 교차 분석을 수행했다. Zenchef는 해커톤 중 엔지니어 투입 없이 에이전트가 단독으로 조사를 완료한 사례다.

---

## 9. 에이전트가 하지 못하는 것

DevOps Agent는 완화 조치를 "제안"하지만, 사용자 명시적 승인 없이 프로덕션 리소스를 자동 변경하지 않는다. CloudWatch Container Insights를 통한 EKS 간접 분석은 가능하지만, `kubectl exec` 수준의 직접 디버깅은 명시적으로 지원하지 않는다. 에이전트가 사용하는 LLM은 AWS가 관리하며, 사용자가 모델을 지정하거나 교체할 수 없다. 인시던트 리포트는 자유 텍스트 형식으로 전달되므로, severity 기반 자동 라우팅이나 티켓 시스템의 필드 매핑을 에이전트 출력에서 직접 수행하기는 어렵다.

Production Operations는 AWS 글로벌 인프라에서 동작하지만, 데이터가 다른 리전에서 처리될 수 있으므로 규제 요건이 있는 조직은 데이터 처리 리전을 계정팀에 확인해야 한다.

---

## 10. Reference

- [AWS DevOps Agent 공식 페이지](https://aws.amazon.com/devops-agent/)
- [AWS DevOps Agent User Guide](https://docs.aws.amazon.com/devopsagent/)
- [AWS DevOps Agent API Reference](https://docs.aws.amazon.com/devopsagent/latest/APIReference/)
- [AWS Premium Support Plans](https://aws.amazon.com/premiumsupport/plans/)
- [AWS re:Invent 2024 발표](https://aws.amazon.com/reinvent/)

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
