---
title: "SAP-C02 박살내기 13 - 마이그레이션 전략"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, migration, 7r, mgn, dms, sct, migration-hub, application-discovery]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-04 10:00:00 +0900
---

포트폴리오 900대를 7R로 다 분류해 놓고도 wave 1이 넘어가지 않는 상황이 있습니다. 분류 스프레드시트는 완성됐고, rehost 대상 서버에는 복제 에이전트가 깔렸고, staging area의 복제도 lag 0으로 붙어 있습니다. 그런데 컷오버 리허설에서 애플리케이션이 기동한 직후 로그인이 전부 실패합니다. 원인은 복제가 아니라 도메인 컨트롤러입니다. 옮긴 서버가 온프레미스 AD를 바라보는데 그 경로가 wave 계획 어디에도 없었습니다.

AWS의 wave planning 문서는 이 실패를 정확히 지목합니다. Active Directory 의존성은 move group을 나누는 기준으로 쓰지 않습니다. 모든 애플리케이션이 공유하는 의존성이라 어떤 wave로도 묶이지 않고, 어떤 애플리케이션을 옮기기 전에 클라우드에 도메인 컨트롤러가 먼저 서 있어야 합니다. 같은 문서가 초기 wave를 서버 10대 미만으로 잡으라고 하고, 어떤 wave도 50대를 넘기지 말라고 합니다. 이 수치들은 마이그레이션 속도를 늦추는 규칙이 아니라 컷오버가 실패했을 때 되돌릴 수 있는 크기를 정하는 규칙입니다.

SAP-C02 Domain 4가 20%를 배정한 영역이 여기입니다. 문항은 "MGN이 무엇인가"를 묻지 않고, 에이전트를 설치할 수 없는 환경에서 4시간 컷오버 윈도우를 지킬 수 있는 구성을 고르라고 합니다. DMS를 아는지가 아니라 DMS가 타깃에 stored procedure를 만들지 않는다는 사실을 아는지를 묻습니다. 서비스 이름만으로는 선지가 좁혀지지 않고, 각 도구가 하지 **못하는** 일이 답을 가릅니다.

> **TL;DR**  
> - 7R은 retire, retain, rehost, relocate, repurchase, replatform, refactor다. AWS는 large migration에 refactor를 권장하지 않는다.  
> - retire 판정 기준은 정량이다. 평균 CPU와 메모리 5% 미만이 zombie, 90일 동안 5%에서 20% 사이가 idle이다.  
> - large migration은 서버 300대 이상이다. 초기 wave는 10대 미만, 모든 wave는 50대 이하, architect 4명 팀의 rehost 처리량은 주당 최대 50대다.  
> - Active Directory는 move group 기준이 아니다. 어떤 wave보다 먼저 클라우드에 domain controller를 세운다.  
> - ADS Agentless Collector는 VMware VM만 보고 running process를 수집하지 못한다. 물리 서버와 프로세스 의존성과 Athena 내보내기는 Discovery Agent다.  
> - Migration Evaluator는 business case를 만들고 dependency mapping을 하지 않는다. 그 작업은 Migration Hub가 한다.  
> - discovery 데이터와 추적 데이터는 Migration Hub home Region 한 곳에만 저장된다. 마이그레이션 대상 Region은 자유롭다.  
> - MGN의 동시 active source server 기본 한도는 Region당 150대다. 4,000은 agentless 기준 비archived 서버 수다.  
> - MGN에는 failback이 없다. 소스로 되돌아가야 하면 DRS이고 두 에이전트를 한 서버에 함께 설치할 수 없다.  
> - DMS는 endpoint 둘 중 하나가 AWS 서비스여야 성립한다. 온프레미스에서 온프레미스로는 쓸 수 없다.  
> - DMS가 타깃에 만드는 것은 table, primary key, 경우에 따라 unique index뿐이다. 나머지는 스키마 변환 도구가 만든다.  
> - full load 전용 task는 인덱스를 없애고, full load + CDC task는 CDC 단계 전에 secondary index를 만든다. 지침이 서로 반대다.  
> - DMS CDC에는 지연 SLA가 없다. 문서가 sub-second 요구에 쓰지 말라고 명시한다.  
> - DMS 리소스는 생성 후 암호화 키를 바꿀 수 없고 비대칭 키를 지원하지 않는다.  
> - Application Migration Service는 AWS Transform MGN으로 이름이 바뀌었고 API와 복제 엔진은 유지된다.  
> - 컷오버 전에 Route 53 TTL을 300초로 낮추고, 전환을 확인한 뒤 원래 값으로 되돌린다.  
{: .prompt-info}

---

## 1. 서버 300대가 넘어가면 마이그레이션의 구조 자체가 달라진다

AWS는 서버 300대 이상을 옮기는 작업을 large migration으로 정의합니다. 이 선을 넘으면 개별 서버를 옮기는 일보다 순서를 정하고 팀을 붙이는 일이 병목이 되기 때문에, 문서가 제시하는 단계 구조도 달라집니다.

큰 흐름은 3단계입니다.

| 단계 | 하는 일 |
| :--- | :--- |
| assess | 비즈니스 케이스를 세운다. TCO 추정과 이전 근거를 만든다 |
| mobilize | landing zone을 만들고, 상세 포트폴리오 평가를 하고, 보안과 운영 모델을 세우고, 팀을 준비한다 |
| migrate and modernize | 실제로 옮긴다 |

세 번째 단계는 다시 두 개 stage로 나뉩니다. Stage 1 initialize는 1개월에서 3개월이 걸리고 runbook과 자동화를 만듭니다. Stage 2 implement는 프로젝트 범위에 따라 다르고 wave 단위로 서버를 옮깁니다. 마이그레이션 속도가 wave마다 올라가는 이유가 여기 있습니다. Stage 1에서 만든 runbook이 반복되기 때문이고, runbook 없이 첫 wave부터 대량으로 넣으면 반복할 절차 자체가 없습니다.

같은 문서가 workstream을 넷으로 나눕니다.

| workstream | 책임 |
| :--- | :--- |
| foundation | landing zone, 네트워크, 보안 기반 |
| project governance | 일정, 리스크, 보고 |
| portfolio | 메타데이터 수집, 우선순위 지정, wave planning |
| migration | 실제 이전과 컷오버 실행 |

시험에서 유용한 구분은 portfolio와 migration의 경계입니다. "어떤 애플리케이션을 언제 옮길지 정하는 일"과 "그 애플리케이션을 실제로 옮기는 일"은 다른 팀의 일이고, 앞의 것이 끝나지 않은 상태에서 뒤의 것을 시작하면 wave가 아니라 개별 작업이 됩니다.

포트폴리오 평가 자체의 타임라인도 문서에 있습니다. portfolio discovery와 초기 계획이 1주에서 5주, 우선순위 애플리케이션 평가가 6주에서 7주, portfolio 분석과 마이그레이션 계획이 8주에서 14주, continuous assessment가 15주부터 프로젝트 종료까지입니다. AWS는 이 타임라인을 indicative라고 명시하므로 절대 기준으로 외울 값은 아니지만, 평가가 몇 주 단위의 작업이라는 감각은 문항에서 "2주 안에 전체 포트폴리오를 평가하고 첫 wave를 시작한다" 같은 선지를 걸러내는 데 쓰입니다.

---

## 2. 7R은 질문 다섯 개를 순서대로 통과한 결과다

7R은 retire, retain, rehost, relocate, repurchase, replatform, refactor(re-architect) 일곱 개입니다. 이름을 외우는 것보다 어떤 질문에서 갈리는지를 잡아 두는 편이 문항에 바로 쓰입니다.

{% include diagrams/static/sap-c02/migration-7r-decision-tree.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/migration-7r-decision-tree--e128c530d52a2433.png" %}

그림은 포트폴리오 평가 결과에서 출발해 질문 다섯 개를 통과하는 동안 일곱 개의 결과가 하나씩 떨어져 나가는 구조를 담았습니다. 각 질문 상자의 부제에 그 질문을 판정하는 근거가 적혀 있고, 마지막 질문에서 갈라진 세 결과는 옮기면서 무엇을 바꾸는지가 서로 다릅니다. refactor로 가는 경로가 점선인 것은 AWS가 대규모 마이그레이션에서 이 전략을 권장하지 않기 때문입니다.

AWS가 large migration에서 흔한 전략으로 지목하는 것은 rehost, replatform, relocate, retire 넷입니다. refactor를 권장하지 않는 이유는 명시적입니다. 마이그레이션을 하면서 모더나이제이션을 동시에 하기 때문입니다. 옮기는 작업과 다시 쓰는 작업을 한 wave 안에 넣으면 컷오버 실패의 원인을 분리할 수 없습니다.

일곱 전략의 판정 기준을 표로 정리하면 이렇습니다.

| 전략 | 판정 기준 | AWS 문서의 예시와 도구 |
| :--- | :--- | :--- |
| retire | 쓰이지 않는다 | 평균 CPU와 메모리 5% 미만, 90일 inbound connection 없음 |
| retain | 클라우드 등가물이 없거나 옮길 수 없다 | mainframe, mid-range, non-x86 Unix, IBM AS/400, Oracle Solaris, 데이터 residency 규제, SaaS 버전 출시 대기 |
| repurchase | 상용 제품이 같은 기능을 준다 | drop and shop. 라이선스에서 SaaS로, 벤더 최신 버전 또는 서드파티 등가물로 교체 |
| relocate | 이동 단위가 서버가 아니라 플랫폼이다 | 온프레미스 플랫폼에서 그 플랫폼의 클라우드 버전으로. 인스턴스나 객체를 다른 VPC, Region, 계정으로 |
| rehost | 아무것도 바꾸지 않는다 | lift and shift. MGN, AWS Cloud Migration Factory Solution, VM Import/Export |
| replatform | 옮기면서 플랫폼만 바꾼다 | lift, tinker, and shift. SQL Server를 RDS for SQL Server로, Graviton 전환, Windows에서 Linux로, App2Container |
| refactor | 코드를 다시 쓴다 | 컴플라이언스 때문에 일부 테이블만 온프레미스에 남기고 데이터베이스를 분리하는 경우 |

마지막 줄이 시험에서 자주 나오는 판정입니다. 데이터베이스를 쪼개는 작업이 왜 replatform이 아니라 refactor인지 묻는 문항이 있고, 근거는 AWS 문서가 refactor 사유로 든 예시 자체입니다. 보안과 컴플라이언스 때문에 고객 정보나 환자 진단 같은 일부 테이블을 온프레미스에 남겨야 해서 데이터베이스를 분리해야 하는 경우가 refactor로 분류돼 있습니다. 데이터 모델이 바뀌면 그것을 읽는 애플리케이션 코드가 바뀌기 때문입니다.

---

## 3. retire와 retain은 정량 기준으로 갈린다

두 전략 모두 "옮기지 않는다"는 결론이지만 이유가 반대입니다. retire는 쓰이지 않아서 옮기지 않는 것이고, retain은 옮길 수 없어서 남기는 것입니다.

retire 후보 판정에 AWS가 제시하는 수치는 세 개입니다.

| 분류 | 기준 |
| :--- | :--- |
| zombie application | 평균 CPU와 메모리 사용률이 5% 미만 |
| idle application | 90일 동안 평균 CPU와 메모리 사용률이 5%에서 20% 사이 |
| 연결 없음 | 최근 90일간 inbound connection이 없다 |

원문은 90일이라는 기간을 idle 쪽에만 붙이고 zombie 쪽에는 기간을 명시하지 않습니다. 문항에서 수치가 나오면 5%가 경계선이고, 5% 미만을 idle로 부르거나 5%에서 20%를 zombie로 부르는 선지가 함정으로 들어옵니다. 두 분류 모두 retire 후보라는 결론은 같으므로 분류명 자체를 묻지 않으면 답이 갈리지 않습니다.

retain 사유는 성격이 다릅니다.

- mainframe, mid-range, non-x86 Unix 애플리케이션. AWS가 드는 예시가 IBM AS/400과 Oracle Solaris다
- 클라우드에 등가물이 없는 특수 하드웨어 의존
- 데이터 residency 규제
- 벤더의 SaaS 버전 출시를 기다리는 중

AS/400이 지문에 나오면 대응하는 EC2 인스턴스 패밀리가 없으므로 rehost와 replatform이 동시에 탈락합니다. 재작성 예산이 승인되지 않았다는 조건이 붙으면 refactor도 탈락하고 retain만 남습니다. 이 조합은 SAP-C02가 즐겨 쓰는 형태입니다.

---

## 4. rehost와 replatform과 relocate가 갈리는 두 축

셋 다 코드를 다시 쓰지 않는 전략이라 선지에서 자주 함께 나옵니다. 갈리는 축은 두 개입니다. OS와 애플리케이션이 그대로인가, 그리고 이동 단위가 서버인가 플랫폼인가.

| 축 | rehost | replatform | relocate |
| :--- | :--- | :--- | :--- |
| 정의 | 변경 없이 그대로 옮긴다 | 옮기면서 일부 최적화 | 플랫폼 단위로 옮긴다 |
| 아키텍처 변경 | 없다 | 일부 있다 | 없다 |
| 이동 단위 | 서버 | 서버 또는 컴포넌트 | 플랫폼, 또는 인스턴스와 객체의 소속 |
| 대표 예 | 물리와 가상 서버를 EC2로 | SQL Server를 RDS for SQL Server로 | 온프레미스 플랫폼에서 그 플랫폼의 클라우드 버전으로, RDS DB 인스턴스를 다른 VPC나 계정으로 |
| 도구 | MGN, Cloud Migration Factory, VM Import/Export | RDS, 컨테이너화, App2Container | 플랫폼 자체 이전 수단 |

relocate가 가장 빠른 전략인 이유가 문서에 적혀 있습니다. 새 하드웨어를 사지 않고, 애플리케이션을 다시 쓰지 않고, 기존 운영을 바꾸지 않고, 아키텍처에 영향을 주지 않기 때문입니다. 문항에서 "다수 서버를 한 번에, 아키텍처 변경 없이, 가장 짧은 기간에"라는 조건이 붙으면 relocate가 후보로 올라옵니다.

여기서 흔한 오답이 물리 서버를 EC2로 옮기는 것을 relocate로 부르는 것입니다. 그것은 rehost입니다. relocate는 플랫폼 단위 이동이거나 인스턴스와 객체를 다른 VPC, 다른 Region, 다른 계정으로 옮기는 것입니다.

replatform의 예시로 문서가 드는 것은 온프레미스 SQL Server를 Amazon RDS for SQL Server로 옮기는 것, Graviton 프로세서로 전환하는 것, Windows에서 Linux로 전환하며 .NET Framework를 .NET Core로 포팅하는 것, 코드 변경 없이 VM을 컨테이너로 옮기는 것입니다. 마지막 항목이 판정을 헷갈리게 만드는데, 컨테이너화가 코드 변경을 수반하지 않으면 replatform이고 서비스 분해를 수반하면 refactor입니다.

---

## 5. repurchase는 구매로 끝나지 않는다

repurchase는 drop and shop입니다. 전통 라이선스에서 SaaS로 이동하거나, 벤더의 최신 버전이나 서드파티 등가물로 교체하거나, 직접 만든 애플리케이션을 SaaS로 대체하는 경우입니다.

문서가 구매 후 절차를 따로 나열한다는 점이 시험 관점에서 중요합니다.

- 사용자 교육
- 데이터 이전
- 인증 서비스 통합. 문서가 Microsoft Active Directory를 예로 든다
- 네트워킹 구성

"SaaS로 바꾸면 마이그레이션 작업이 사라진다"는 서술이 성립하지 않는 근거입니다. 데이터 이전과 신원 통합은 남고, 특히 인증 통합은 앞에서 본 도메인 컨트롤러 선행 조건과 같은 종류의 작업입니다.

가상 데스크톱과 애플리케이션 스트리밍도 repurchase로 분류되는 사례입니다. 온프레미스 VDI 환경을 Amazon WorkSpaces로 바꾸거나 개별 애플리케이션 배포를 AppStream 2.0으로 바꾸면 서버를 옮기는 대신 서비스를 구독하는 형태가 됩니다. 이때도 사용자 디렉터리 연동과 데이터 이전은 그대로 남습니다.

---

## 6. TCO 근거를 만드는 도구와 인벤토리를 만드는 도구는 다르다

이사회에 낼 숫자를 만드는 일과 move group을 만드는 일은 다른 도구가 맡습니다. 문항이 "CFO가 승인 전에 비용을 보고받으려 한다"로 시작하면 답이 좁혀집니다.

{% include diagrams/static/sap-c02/migration-discovery-tool-ownership.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/migration-discovery-tool-ownership--a9adf2cd902f3463.png" %}

그림은 같은 온프레미스 자산을 대상으로 세 가지 수집 경로가 각각 어떤 산출물에 도달하는지를 담았습니다. 각 수집 도구 상자의 부제에 배포 단위와 수집 주기와 대상 제약이 적혀 있고, 산출물 쪽 상자에는 그 산출물을 만들 수 있는 도구가 무엇인지가 함께 적혀 있습니다. Migration Evaluator에서 나가는 선과 Discovery Agent에서 나가는 선이 서로 다른 상자에 도착하는 것이 이 그림의 요점입니다.

**Migration Evaluator**의 수집 방식은 네트워크 안에 Windows Server VM 한 대를 띄우는 것입니다. WMI, SNMP, VMware vSphere, T-SQL 같은 표준 프로토콜을 쓰고 하이퍼바이저나 개별 서버에 에이전트를 설치하지 않습니다. 대상은 블록 스토리지가 붙은 x86 아키텍처 서버입니다. collector를 배포하지 않고 기존 인벤토리와 사용률을 flat file로 제출하는 경로도 있습니다.

business case 산출물에 들어가는 것은 이렇습니다.

- EBS와 EC2와 OS 라이선스 비용 추정
- Microsoft SQL Server 라이선스 분석
- BYOL 모델링
- 비즈니스 기능별 애플리케이션 그룹핑
- 중국 본토를 제외한 모든 퍼블릭 AWS 리전의 비용 모델링

**Migration Evaluator는 application dependency mapping을 하지 않습니다.** FAQ가 그 작업을 AWS Migration Hub에서 한다고 명시합니다. "의존성 맵이 필요하다"는 요구가 지문에 있으면 Migration Evaluator는 답이 아닙니다.

세 도구의 역할을 나란히 놓으면 이렇게 됩니다.

| 축 | Migration Evaluator | Application Discovery Service | Migration Hub |
| :--- | :--- | :--- | :--- |
| 목적 | TCO와 business case | 서버와 DB 인벤토리, 사용률, 네트워크 의존성 | 마이그레이션 상태 추적 단일 창구 |
| 수집 수단 | Windows Server VM 1대, WMI와 SNMP와 vSphere와 T-SQL | Agentless Collector, Discovery Agent, file-based import | 자체 수집 없음. 도구가 보내는 상태를 받는다 |
| 산출물 | 라이선스 포함 비용 추정, 애플리케이션 그룹핑 | 사용률 데이터, TCP 연결, 프로세스 목록 | 서버 그룹핑, 애플리케이션별 진행률 |
| dependency mapping | 하지 않는다 | 데이터를 제공한다 | 시각화를 수행한다 |

---

## 7. Application Discovery Service 두 방식이 수집하지 못하는 것

ADS의 discovery 방식은 세 가지입니다. vCenter에 OVA로 배포하는 Agentless Collector, 서버마다 설치하는 Discovery Agent, 그리고 Migration Hub template을 쓰는 file-based import입니다.

수집 주기부터 다릅니다.

| 방식 | 수집 주기 |
| :--- | :--- |
| Agentless Collector | 약 60분 |
| Discovery Agent | 약 15초 |
| Migration Hub template과 RVTools export | 단일 스냅샷 |

두 방식이 갈리는 지점은 두 개입니다.

| 축 | Agentless Collector | Discovery Agent |
| :--- | :--- | :--- |
| 배포 단위 | vCenter당 OVA 1개 | 서버마다 설치 |
| 물리 서버 | 지원하지 않는다 | 지원한다 |
| running process | 수집하지 못한다 | 수집한다 |
| time series 사용률 내보내기 | 불가 | 가능 |
| network data의 Athena와 CSV 내보내기 | 불가 | 가능 |
| 데이터베이스 메타데이터 | Oracle, SQL Server, MySQL, PostgreSQL 수집 | 수집하지 않는다 |
| TCP network connection 수집 | 지원 | 지원 |
| Migration Hub 시각화 | 지원 | 지원 |

Agentless Collector가 running process를 수집하지 못하는 이유는 VM 내부를 들여다볼 수 없기 때문입니다. 프로세스 수준 의존성 맵이 필요하면 에이전트를 깔아야 하고, 물리 서버가 섞여 있어도 마찬가지입니다. 반대로 데이터베이스 메타데이터는 Agentless Collector만 수집합니다. 데이터베이스와 분석 모듈이 Microsoft Active Directory의 LDAP로 OS와 DB와 분석 서버 정보를 모으고, 주기적으로 CPU와 메모리와 디스크 용량 실사용량을 쿼리하며, 스키마 복잡도와 중복도 함께 수집합니다.

두 방식을 섞어 쓰는 구성이 실제로는 흔합니다. VMware VM은 Agentless Collector로 넓게 훑고, 프로세스 의존성이 필요한 핵심 애플리케이션 서버와 물리 서버에만 Discovery Agent를 설치하는 형태입니다. 다만 문항이 "전체 자산의 시계열 사용률을 Athena로 분석한다"처럼 조건을 걸면 그 범위 전체에 에이전트가 필요합니다.

---

## 8. home Region을 정하지 않으면 discovery가 시작되지 않는다

ADS와 Migration Hub는 home Region 개념을 공유합니다. 모든 discovery 데이터는 Migration Hub home Region 한 곳에 저장되고, discovery를 시작하기 전에 home Region을 반드시 먼저 설정해야 합니다. agent와 connector와 import는 선택한 home Region에서만 쓸 수 있습니다.

Migration Hub 쪽 규칙도 같은 형태입니다. home Region에 저장되는 것은 migration tracking data뿐이고, 실제 마이그레이션 대상 Region은 사용하는 도구가 지원하는 어떤 Region이든 될 수 있습니다. 콘솔이나 SDK나 CLI에서 write action을 하려면 home Region을 먼저 선택해야 합니다.

여기서 나오는 오답 선지가 "Region마다 Migration Hub를 두고 각각 추적한다"입니다. 추적 데이터는 한 곳에만 저장되므로 성립하지 않습니다. 반대 방향의 오해도 있습니다. home Region이 하나라고 해서 대상 Region까지 하나로 묶이지는 않습니다.

현재 Migration Hub 문서가 상태 업데이트를 받는다고 명시하는 도구는 두 개입니다. Application Migration Service와 AWS DMS입니다. "Snowball 작업 진행률을 Migration Hub에서 본다" 같은 선지는 이 목록에 없습니다.

Migration Hub와 Application Discovery Service는 2025-11-07부터 신규 고객을 받지 않습니다. 기존 고객은 진행 중인 discovery 프로젝트를 계속 쓸 수 있고, AWS는 그 프로젝트의 lifecycle을 통상 4개월로 봅니다. 대안으로 제시되는 것은 AWS Transform입니다. Exam Guide v1.2의 in-scope 목록에는 두 서비스가 그대로 있으므로 시험 준비 관점에서는 정상적으로 다루고, 신규 계정에서 콘솔을 열어 보려다 막히는 상황만 기억하면 됩니다.

---

## 9. move group과 wave를 만드는 규칙에는 수치가 있다

move group은 함께 옮겨야 하는 서버 또는 애플리케이션 묶음이고, wave는 하나 이상의 move group으로 구성됩니다. 그래서 순서는 move group을 먼저 만들고 그것을 wave로 묶는 방향입니다.

move group을 나누는 규칙으로 문서가 드는 예시는 이렇습니다.

- 같은 데이터베이스를 공유하는 애플리케이션
- 같은 애플리케이션 owner
- 같은 patch window

**Microsoft Active Directory 의존성은 move group 기준으로 쓰지 않습니다.** 모든 애플리케이션의 공통 의존성이라 그것으로 묶으면 전체가 하나의 group이 되기 때문이고, 문서의 지침은 어떤 애플리케이션을 옮기기 전에 클라우드에 domain controller를 먼저 세우라는 것입니다.

wave 크기에 대한 정량 기준은 네 개입니다.

| 기준 | 값 |
| :--- | :--- |
| 미리 계획하는 wave 수 | 최소 4개에서 5개 앞까지 |
| 초기 wave(1번에서 5번) 크기 | 서버 10대 미만 |
| wave 전체 상한 | 서버 50대 |
| rehost 패턴의 표준 처리량 | architect 4명 팀이 1주에 최대 50대 |

마지막 줄이 앞의 세 줄을 설명합니다. 팀 하나의 주간 처리량이 50대이므로 wave 상한 50대는 한 주에 소화 가능한 크기를 뜻하고, 초기 wave를 10대 미만으로 잡는 것은 runbook이 아직 검증되지 않은 구간이기 때문입니다. 서버 1,000대를 12개월에 옮긴다는 지문이 나오면 팀 하나로는 부족하다는 계산이 바로 나옵니다.

wave sizing 판단 축은 서버 수만이 아닙니다.

| 축 | 판단 |
| :--- | :--- |
| network bandwidth | wave 크기가 대역폭을 초과하면 안 된다 |
| 스토리지 크기 | 100GB 애플리케이션을 2TB보다 먼저 |
| 환경 | dev와 test를 prod보다 먼저 |
| 사용자 수 | 사용자 10명 규모를 10,000명 규모보다 먼저 |

wave plan 산출물에는 서버와 애플리케이션과 데이터베이스 목록, 시작일, 컷오버 일시가 들어갑니다. 메타데이터는 양쪽을 다 모읍니다. 소스 쪽에서 서버명과 OS를, 타깃 쪽에서 서브넷과 보안 그룹과 AWS 계정을 수집합니다. 타깃 메타데이터가 wave plan에 들어간다는 것은 landing zone이 그 시점에 이미 서 있어야 한다는 뜻입니다.

---

## 10. wave보다 먼저 서 있어야 하는 것들

앞 절의 마지막 문장이 이 절의 주제입니다. wave 계획서에 타깃 서브넷과 보안 그룹과 계정 ID를 적으려면 그것들이 이미 존재해야 합니다.

{% include diagrams/static/sap-c02/migration-wave-prerequisites.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/migration-wave-prerequisites--2d08a785a028ef61.png" %}

그림은 wave 계획과 실행 사이에 놓인 선행 조건들을 담았습니다. 왼쪽 세 상자는 wave 하나의 내용물이 아니라 모든 wave의 공통 전제이고, DNS TTL 인하 상자는 wave 실행 자체가 아니라 컷오버 윈도우에 붙습니다. 오른쪽 끝 컷오버 상자의 부제에 그 윈도우 안에서 순서대로 일어나는 동작이 적혀 있습니다.

**landing zone.** mobilize 단계의 산출물입니다. 계정 구조, 네트워크, 가드레일, 로깅이 여기 들어갑니다. 조직 구조와 Control Tower 구성 자체는 [멀티 계정 거버넌스 편](/posts/aws-sap-c02-multi-account-governance/)에서 다뤘고, 여기서는 wave plan이 참조할 타깃 메타데이터의 출처로만 봅니다.

**domain controller.** 앞에서 본 대로 어떤 wave보다 먼저입니다. 어떤 디렉터리 옵션을 고를지는 뒤의 신원 절에서 다룹니다.

**회선.** 복제 트래픽이 지나갈 경로입니다. 마이그레이션 기간에만 대역폭이 필요한 경우 Direct Connect hosted connection이 후보가 되는데, 조달 방식에 제약이 있습니다. hosted connection은 콘솔에서 요청할 수 없고 파트너가 만들어 준 것을 사용자가 accept해야 쓸 수 있습니다. 속도 변경도 파트너만 할 수 있습니다. 포트 속도는 50Mbps, 100Mbps, 200Mbps, 300Mbps, 400Mbps, 500Mbps, 1Gbps, 2Gbps, 5Gbps, 10Gbps, 25Gbps입니다. 1Gbps 이상은 특정 요건을 충족한 파트너만 만들 수 있고, 25Gbps는 100Gbps 포트가 있는 로케이션에서만 가능합니다.

hosted connection에는 traffic policing이 적용됩니다. 설정된 최대 속도를 넘는 트래픽은 폐기되고, 그래서 버스트 트래픽의 실효 처리량이 비버스트보다 낮아질 수 있습니다. "500Mbps hosted connection에 순간적으로 1Gbps를 밀어 넣어 초기 복제를 앞당긴다"는 계획이 성립하지 않는 근거입니다.

**DNS TTL.** 컷오버 절차의 일부지만 준비는 며칠 전에 합니다. Route 53 문서의 지침은 이미 사용 중인 도메인이나 서브도메인의 설정을 바꿀 때 먼저 300초 같은 짧은 값으로 TTL을 낮추고, 새 설정이 맞다고 확인한 뒤에 값을 다시 올리라는 것입니다. 순서가 뒤집힌 선지가 자주 나옵니다. 컷오버가 끝난 뒤에 TTL을 낮추면 이미 캐시된 응답은 기존 TTL이 만료될 때까지 그대로 유지되므로 전환 시간을 줄이지 못합니다.

---

## 11. MGN의 복제 경로는 staging area에서 두 갈래로 나뉜다

Application Migration Service는 2026년 6월 AWS Transform MGN으로 이름이 바뀌었고 API와 복제 엔진은 유지됩니다. 물리와 가상과 클라우드 서버를 대상으로 연속 블록 레벨 복제를 수행하는 rehost 도구입니다. 컷오버 윈도우는 통상 분 단위입니다. 동작은 replication, launch, post-launch 세 종류의 템플릿으로 제어하고, 서버를 application으로 묶고 application을 wave로 묶어 대량 조작합니다. wave 개념이 도구 안에도 있다는 점이 앞 절의 wave plan과 맞물립니다.

{% include diagrams/static/sap-c02/mgn-replication-cutover-flow.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/mgn-replication-cutover-flow--20ab45c43e220a42.png" %}

그림은 소스 쪽, staging area subnet, 타깃 VPC 세 경계를 각각 상자로 감싸고 그 사이를 지나는 복제 경로를 담았습니다. agentless 경로는 점선으로 따로 표시했고, staging 볼륨에서 갈라지는 두 인스턴스는 목적이 다릅니다. 각 상자의 부제에 인스턴스 타입과 볼륨 비율과 스냅샷 유지 개수가 적혀 있습니다.

staging area의 구성 수치는 그대로 시험 재료입니다.

| 항목 | 값 |
| :--- | :--- |
| replication server 인스턴스 타입 | t3.small |
| 볼륨 대 replication server 비율 | 통상 15대 1 |
| replication server의 IP | 고정할 수 없다. MGN이 자동으로 최신 AMI로 교체한다 |
| staging 볼륨 | 소스 볼륨마다 같은 크기의 EBS 볼륨 1개 |
| 스냅샷 유지 | 디스크당 5개에서 7개 수준. 증분 스냅샷이고 쓰이지 않으면 자동 삭제된다 |

현재 AWS Transform MGN은 target storage type으로 Amazon EBS(default)와 FSx for NetApp ONTAP을 지원합니다. 위 표와 그림의 staging volume 수치는 기본 EBS 경로를 기준으로 하며, ONTAP을 선택하면 FSx storage secret ARN과 iSCSI용 security group 같은 별도 설정이 필요합니다. 2026년 8월 release notes에서 ONTAP target이 generally available로 전환됐습니다.

스냅샷 개수는 같은 FAQ 페이지 안에서 한 항목이 5개에서 6개, 다른 항목이 5개에서 7개로 적혀 있습니다. 정확한 수를 묻는 문항은 나오지 않는다고 보는 편이 안전하고, "증분 스냅샷을 소수 개 유지해 launch 지연을 줄인다"는 성질만 기억하면 됩니다.

복제 트래픽 자체의 성질도 정리해 둡니다.

| 항목 | 값 |
| :--- | :--- |
| 복제 포트 | TCP 1500 |
| staging 보안 그룹 | 0.0.0.0:1500 inbound가 자동으로 열린다. 제한은 ACL과 네트워크 통제로 한다 |
| 커스텀 DNS 사용 시 | replication과 conversion 서버의 outbound에 TCP 53 추가 |
| 암호화 | 전송 중 데이터 전부 암호화 |
| 압축 | LZ4. 데이터 종류에 따라 60%에서 70% |
| 일관성 | crash consistent. 서버가 내려가기 직전 상태를 확보한다 |

staging 보안 그룹이 0.0.0.0:1500을 자동으로 여는 동작은 보안 검토에서 자주 걸립니다. MGN 쪽에서 이 규칙을 좁히는 설정을 주지 않으므로, 통제는 서브넷 NACL과 라우팅으로 합니다. 복제 트래픽을 인터넷으로 내보내지 않아야 하면 staging 서브넷을 프라이빗으로 두고 Direct Connect private VIF나 VPN으로 경로를 고정합니다.

2026-08-15부터 MGN의 replication과 conversion 서버는 Amazon Linux 2023을 씁니다. Amazon Linux 2가 2026-06-30에 지원 종료되기 때문입니다. AL2023은 패키지 저장소용 S3 버킷 의존성이 새로 생기므로, Route 53 DNS Firewall 차단 목록이나 제한적인 S3 gateway endpoint policy를 쓰는 환경에서는 `arn:aws:s3:::al2023-repos-{region}-de612dc2/*` 허용을 추가해야 합니다. 복제가 갑자기 붙지 않는 원인으로 시험보다 실무에서 더 자주 만나는 항목입니다.

디스크 구성에 대한 규칙도 있습니다. MGN은 LVM과 RAID 구성을 그대로 지원하고, SAN처럼 블록 디바이스로 보이는 디스크는 로컬 디스크처럼 투명하게 복제합니다. 반면 NFS share처럼 네트워크 마운트된 NAS는 복제되지 않습니다. 그 데이터를 옮기려면 실제 NFS 서버에 에이전트를 설치해야 합니다.

---

## 12. MGN 워크플로 12단계에서 되돌릴 수 있는 지점

MGN의 마이그레이션 워크플로는 12단계입니다. 순서를 외우는 것보다 어느 지점까지 되돌릴 수 있는지를 잡아 두는 편이 문항에 쓰입니다.

1. 대상 Region 초기화
2. 에이전트 설치. agentless면 vCenter Client 설치
3. initial sync 완료 대기
4. test instance 기동
5. 인수 테스트 후 test instance 종료와 삭제
6. post-launch action 구성
7. 컷오버 윈도우 대기
8. lag 0 확인
9. 소스 서비스 정지
10. cutover instance 기동
11. 성공 확인 후 finalize cutover
12. source server archive

4번에서 5번은 몇 번이든 반복할 수 있습니다. test instance를 띄우고 지워도 복제는 계속 돌고 있고 소스는 그대로 서비스합니다. 되돌릴 수 없는 선이 9번입니다. 소스 서비스를 정지한 뒤부터는 사용자 트래픽이 어디에도 도달하지 않는 구간이 시작되고, 이 구간의 길이가 컷오버 다운타임입니다.

11번 finalize cutover를 건너뛰면 복제 리소스가 정리되지 않고 서버 상태도 컷오버 완료로 표시되지 않습니다. "test instance를 그대로 운영으로 쓴다"는 선지는 여기서 걸립니다. test instance는 인수 테스트용이고 컷오버는 cutover instance 기동과 finalize로 완결됩니다.

post-launch action은 6번 자리에 있습니다. 스크립트 경로를 소스 서버에 미리 만들어 두는 방식입니다.

| 항목 | Linux | Windows |
| :--- | :--- | :--- |
| 경로 | `/boot/post_launch` | `C:\Program Files (x86)\AWS Replication Agent\post_launch\` |
| 파일 조건 | 실행 권한이 있는 파일 | `.exe`, `.cmd`, `.bat` |
| 실행 주체 | root | Local System |

PowerShell 스크립트는 자동 실행되지 않으므로 `.cmd`로 감싸야 합니다. 에이전트 설정 디렉터리 아래에 두는 구조라서, 스크립트를 타깃 인스턴스에 올려 두는 방식으로는 동작하지 않습니다.

---

## 13. agent 기반과 agentless가 갈리는 지점은 컷오버 윈도우다

agentless 복제는 vCenter에 MGN vCenter Client를 설치해 스냅샷 기반으로 동작합니다. 회사 정책상 서버마다 에이전트를 설치할 수 없을 때 쓰는 경로입니다.

메커니즘은 snapshot shipping입니다. VMware 스냅샷을 뜨고, 임시 replication agent가 VMware Changed Block Tracking으로 변경 블록 위치를 찾고, Virtual Disk Development Kit로 읽어 타깃 계정으로 보냅니다. 첫 회는 initial sync로 디스크 전량을 보내고 이후는 CBT 변경분만 보냅니다. 각 회가 성공하면 타깃 계정에 consistent snapshot group이 생기고 이것으로 test와 cutover 인스턴스를 기동합니다. 문서는 이 과정을 계속 시작하고 감시하는 형태로만 기술하고 고정 주기를 수치로 제시하지 않습니다.

**AWS는 가능하면 agent 기반을 권장합니다.** 근거가 명시돼 있습니다. agent 기반만 CDP(Continuous Data Protection)를 지원하고 컷오버 윈도우가 가장 짧습니다. agentless는 스냅샷 사이의 간격만큼 데이터가 뒤처지므로 컷오버 윈도우가 길어집니다. 문항에서 "에이전트를 설치할 수 없다"와 "컷오버 다운타임을 최소화해야 한다"가 동시에 요구되면 그 조합 자체가 성립하지 않는 선지가 됩니다. 반대로 "컷오버 윈도우가 애플리케이션당 4시간까지 허용된다"처럼 여유가 명시되면 agentless가 답이 됩니다.

agentless의 환경 제약도 좁습니다.

| 항목 | 제약 |
| :--- | :--- |
| 지원 가상화 | vCenter 6.7, 7.0, 8.0만. 그 외 가상화 환경은 지원하지 않는다 |
| 물리 서버 | 대상이 아니다 |
| vCenter Client 설치 대상 | 64bit Linux만. Ubuntu 18.x 이상 22.04까지, Amazon Linux 2, RHEL 8.x |
| 전용 VM | 최소 1대를 client 전용으로 잡는다 |
| IPv6-only 소스 환경 | 동작하지 않는다 |
| 소스 OS 지원 범위 | agent 기반과 동일한 Windows와 Linux |
| Region 범위 | MGN이 지원하는 전 Region |
| CloudEndure Migration | 쓸 수 없다. MGN 전용 기능이다 |

VMware 쪽 제약도 네 가지가 명시돼 있습니다. VMC on AWS에서 오는 마이그레이션은 agentless와 agent 기반 둘 다 지원합니다. vMotion, Storage vMotion, DRS, Storage DRS는 부분 지원이고, 복제 run이 끝난 뒤 다음 run 시작 전의 이동만 지원합니다. 이때도 대상 ESXi host와 datastore와 datacenter와 VM에 대한 vCenter 계정 권한이 필요합니다. 복제 run이 진행 중일 때의 이동은 지원하지 않습니다. Cross vCenter vMotion은 MGN과 함께 쓸 수 없고, VMware Virtual Volumes 마이그레이션은 AWS가 지원하지 않습니다.

---

## 14. MGN 쿼터가 대규모 wave의 상한을 정한다

MGN의 서비스 쿼터 기본값은 일곱 개입니다.

| 항목 | 기본값 |
| :--- | :--- |
| Region당 동시 진행 job | 20개 |
| 동시 복제 가능한 active source server | 150대 |
| 비archived source server | 4,000대(agentless 기준) |
| 단일 job의 최대 서버 | 200대 |
| 전체 활성 job의 최대 서버 | 200대 |
| 계정과 Region당 총 서버 | 50,000대 |
| source server당 동시 job | 1개 |

시험에서 답을 가르는 값은 **동시 복제 active source server 150대**입니다. 4,000이나 50,000 같은 큰 수가 함께 제시되면 그쪽을 동시 복제 한도로 착각하기 쉬운데, 4,000은 agentless 기준 비archived 서버 수이고 50,000은 계정과 Region당 총 서버 수입니다. 150대를 넘겨야 하면 Support에 상향을 요청합니다.

이 값이 앞의 wave 규칙과 맞물립니다. wave 상한 50대는 팀 처리량에서 나온 값이고, 동시 active 150대는 도구 쪽 한도입니다. 두 값이 다르므로 "쿼터가 150이니 wave에 150대를 넣는다"는 계산은 나오지 않습니다. 여러 wave의 복제가 겹쳐 도는 구간에서 합계가 150을 넘지 않는지 확인하는 용도입니다.

요금 쪽에서 기억할 것은 두 가지입니다. AWS Transform MGN 사용 자체는 90일 무료지만, free period 중에도 복제를 위해 MGN이 프로비저닝한 AWS 인프라 요금은 발생합니다. test와 cutover 인스턴스의 EC2와 EBS도 별도로 과금됩니다.

---

## 15. MGN과 DRS는 같은 복제 기술 위에서 종료 상태가 다르다

AWS Elastic Disaster Recovery와 MGN은 같은 블록 레벨 복제 기술을 공유합니다. 둘 다 staging area로 복제하고, 차이는 무엇을 기동하고 그 다음에 무엇이 남는지입니다.

| 축 | MGN | DRS |
| :--- | :--- | :--- |
| 목적 | 일회성 rehost 컷오버 | 상시 DR 준비와 복구 |
| 기동 대상 | test instance, cutover instance | recovery instance |
| failback | 없다 | 있다. 소스 환경 복구 후 되돌린다 |
| 시점 복구 | 최신 상태 기준 컷오버 | point in time 선택 가능 |
| 종료 상태 | source server archive | 상시 복제 유지 |

**failback이 답을 가릅니다.** "컷오버 후 일정 기간 동안 언제든 온프레미스로 되돌릴 수 있어야 하고, 되돌리는 동안 클라우드에서 발생한 변경이 소스에 반영되어야 한다"는 요구가 지문에 나오면 MGN이 아니라 DRS입니다. MGN 문서 자체가 DRS가 지원하는 기능이 MGN에 없을 때는 DRS를 마이그레이션에 써도 된다고 명시합니다.

두 에이전트를 한 서버에 동시에 설치할 수 없다는 제약도 함께 나옵니다. DRS 에이전트를 설치하려면 MGN 에이전트를 먼저 제거해야 합니다. "이전과 DR 준비를 한 번에 한다"는 선지가 성립하지 않는 근거입니다.

DRS 자체는 저비용 스토리지와 최소 컴퓨트로 staging area를 유지하고, 최신 상태 또는 과거 시점으로 recovery instance를 분 단위로 기동하며, 비파괴 drill과 failback을 지원합니다. DR 전략 설계와 RTO와 RPO 계산은 마이그레이션 문항의 소재가 아니므로, 여기서는 MGN과 구분되는 축만 봅니다. 문서의 표현은 recovery instance를 분 단위로 기동한다는 것뿐이고 초 단위 RPO 수치는 제시하지 않으므로, 특정 RPO 값을 근거로 선지를 고르지 않습니다.

---

## 16. DMS가 성립하는 유일한 요건

AWS DMS 사용의 요건은 하나입니다. **endpoint 둘 중 하나가 AWS 서비스 위에 있어야 합니다.** 온프레미스 DB에서 다른 온프레미스 DB로는 DMS를 쓸 수 없습니다. 이 한 줄이 선지 하나를 바로 지웁니다.

마이그레이션 구성 요소는 다섯 개입니다.

| 구성 요소 | 역할 |
| :--- | :--- |
| database discovery | DMS Fleet Advisor |
| 자동 스키마 변환 | DMS Schema Conversion |
| replication instance | 관리형 EC2 인스턴스 |
| source와 target endpoint | 연결 정보 |
| replication task | 실제 이전 작업 |

replication instance는 관리형 EC2 인스턴스이고 인스턴스 클래스에 따라 데이터 스토리지가 50GB 또는 100GB로 붙습니다. 모든 스토리지는 GP2 SSD입니다. Multi-AZ를 켜면 다른 AZ에 동기 복제 standby가 생기고 그만큼 성능 오버헤드가 발생합니다. 이 오버헤드가 마이그레이션 기간에만 존재하는 비용이라는 점이 판단 재료가 됩니다.

DMS 소스로 지원되는 온프레미스와 EC2 엔진은 Oracle, SQL Server, MySQL, MariaDB, PostgreSQL, MongoDB, SAP ASE, IBM Db2 LUW, IBM Db2 for z/OS입니다. SQL Server는 Express 에디션을 지원하지 않고 Web 에디션은 full load만 지원합니다. 서드파티 관리형 서비스도 소스가 됩니다. Azure SQL Database, Azure PostgreSQL과 MySQL Flexible Server, Google Cloud for MySQL과 PostgreSQL, OCI MySQL Heatwave가 목록에 있습니다. 다른 클라우드에서 AWS로 오는 데이터베이스 이전 문항에서 DMS가 답이 되는 근거입니다.

---

## 17. DMS는 타깃에 무엇을 만들고 무엇을 만들지 않는가

heterogeneous 마이그레이션 문항이 갈리는 지점이 여기입니다. **DMS가 타깃에 만드는 것은 table과 primary key, 그리고 경우에 따라 unique index뿐입니다.**

{% include diagrams/static/sap-c02/dms-schema-object-ownership.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/dms-schema-object-ownership--06440de1083954c6.png" %}

그림은 같은 소스 데이터베이스에 두 도구가 붙었을 때 타깃에 생기는 오브젝트가 어떻게 나뉘는지를 담았습니다. 가운데 두 상자가 각 도구의 역할이고, 그 오른쪽 두 상자에 각 도구가 실제로 만드는 오브젝트 목록이 들어 있습니다. Secrets Manager 상자는 migration project가 자격증명을 어디에서 읽는지를 표시한 것입니다.

DMS가 만들지 않는 것은 이렇습니다.

- secondary index
- foreign key
- user account
- sequence
- stored procedure
- trigger
- view

전체 스키마와 코드 오브젝트 변환이 필요하면 DMS Schema Conversion이나 AWS SCT가 필요합니다. "DMS task 하나로 스키마와 데이터를 모두 옮긴다"는 선지가 성립하지 않는 이유이고, stored procedure 400개가 지문에 등장하면 변환 도구가 확정됩니다.

---

## 18. migration type 세 가지와 뒤집히는 인덱스 지침

DMS의 migration type은 세 가지입니다.

| 타입 | 동작 | 전제 |
| :--- | :--- | :--- |
| Full load | 기존 데이터만 옮긴다 | 전체 복사 시간만큼 outage를 허용할 수 있다 |
| Full load + CDC | 전체 적재 중 변경을 캡처해 이후 적용한다 | outage를 최소화해야 한다 |
| CDC only | 변경분만 옮긴다 | bulk load를 다른 수단으로 이미 마쳤다 |

target table preparation mode는 Do nothing, Drop tables on target, Truncate 세 가지입니다.

성능 지침이 타입에 따라 반대 방향이라는 점이 함정입니다.

| 대상 | full load 전용 task | full load + CDC task |
| :--- | :--- | :--- |
| primary key index | 제거하거나 생성을 미룬다 | 유지한다 |
| secondary index | 제거하거나 생성을 미룬다 | **CDC 단계 전에 만든다** |
| 참조 무결성 제약 | 제거하거나 생성을 미룬다 | 컷오버 시점에 켠다 |
| DML trigger | 제거하거나 생성을 미룬다 | 컷오버 직전에 켠다 |

full load + CDC에서 secondary index를 미리 만들어야 하는 이유는 DMS가 logical replication을 쓰기 때문입니다. 인덱스가 없으면 CDC 적용 단계에서 매 변경마다 full table scan이 발생합니다. 반대로 full load 전용 task에서는 적재 중 인덱스 유지 비용이 그대로 지연이 되므로 제거가 맞습니다. "full load 속도를 높이려고 타깃에 인덱스와 foreign key를 미리 만들어 둔다"는 선지는 방향이 반대입니다.

나머지 튜닝 항목도 함께 정리합니다.

| 항목 | 값과 동작 |
| :--- | :--- |
| full load 병렬 테이블 수 | 기본 8개. `MaxFullLoadSubTasks`로 조정하며 작은 인스턴스에서는 줄이는 편이 낫다 |
| Limited LOB mode | 기본값. 기본 크기 제한 32KB이고 초과분은 잘린다 |
| Full LOB mode | 크기 무관 전체 이전. 느리다 |
| Inline LOB mode | `FullLobMode`가 true일 때만 사용. `InlineLobMaxSize` 범위 1KB에서 102400KB, 기본값 0 |
| batch optimized apply | 트랜잭션을 묶어 효율을 높이지만 거의 항상 참조 무결성 제약을 위반한다 |
| RDS 타깃 | 컷오버 준비 전까지 백업과 Multi-AZ를 끄는 것이 권장 |
| RDS가 아닌 타깃 | 컷오버까지 로깅을 끈다 |
| full load 중 failover | single AZ든 Multi-AZ든 host 교체가 일어나면 full load task가 실패한다 |

LOB 처리는 데이터가 조용히 잘리는 경로라 실무와 시험 양쪽에서 자주 나옵니다. 기본값인 Limited LOB mode를 그대로 두면 32KB를 넘는 LOB은 잘린 채 타깃에 들어갑니다. `InlineLobMaxSize`를 32KB보다 크게 잡으면 메모리 압박이 생길 수 있다는 경고도 함께 있습니다.

batch optimized apply와 참조 무결성의 관계는 순서 문제입니다. 이 옵션을 켜면 제약 위반이 사실상 항상 발생하므로, 마이그레이션 중에는 제약을 꺼 두고 컷오버 과정에서 다시 켭니다. full load 중 failover가 task를 실패시킨다는 항목은 완료되지 않은 테이블에 대해 실패 지점부터 재시작해야 한다는 뜻이고, 그래서 마이그레이션 중 Multi-AZ를 끄는 권장이 성능만이 아니라 실패 확률 관점에서도 성립합니다.

data validation을 지원하는 엔진은 Oracle, PostgreSQL, MySQL, MariaDB, SQL Server, Aurora MySQL, Aurora PostgreSQL, IBM Db2 LUW, Amazon Redshift입니다. premigration assessment 기능도 있어서 task를 돌리기 전에 실패 가능 요소를 미리 찾습니다.

---

## 19. DMS CDC를 쓰면 안 되는 용도

DMS CDC는 실시간 복제가 아닙니다. **CDC 지연에 대한 SLA가 없습니다.** 문서는 sub-second 또는 보장된 저지연이 필요한 용도에 DMS CDC를 쓰지 말라고 명시하고, 대안으로 네이티브 DB 복제나 전용 스트리밍을 지목합니다.

이 문장이 문항에서 어떻게 쓰이는지가 중요합니다. "금융 거래를 두 시스템 사이에서 sub-second로 동기화한다"는 요구가 나오면 DMS CDC 선지는 그럴듯해 보여도 탈락합니다. 반대로 "컷오버 다운타임을 15분 이내로 줄인다"는 요구는 CDC가 정확히 해결하는 문제입니다. 전자는 정상 운영 상태의 지연 요구이고 후자는 전환 시점의 outage 요구라서, 같은 CDC라도 답이 갈립니다.

---

## 20. DMS Serverless가 못 하는 것

DMS Serverless는 용량 산정을 DMS에 맡기는 형태입니다. DCU(DMS capacity unit) 하나가 RAM 2GB이고, `MinCapacityUnits`와 `MaxCapacityUnits` 사이에서 DMS가 용량을 자동 산정하고 스케일합니다.

동작 제약이 여러 개 있습니다.

| 항목 | 동작 |
| :--- | :--- |
| full load 진행 중 | scale down하지 못한다 |
| 초기 스토리지 | 100GB |
| 스토리지 확장 | 15분마다 사용률을 확인하고 90%를 넘으면 늘린다. 스케일링 사이에 cooling period가 없다 |
| 48시간 안에 시작되지 않은 replication | 재개할 수 없다. DMS가 리소스를 deprovision한다 |
| 한 번 시작한 뒤 | `start-replication-type`을 `resume-processing`으로 재개해야 하고 새로 시작할 수 없다 |
| deprovisioned 상태 | 테이블 메타데이터와 통계가 사라진다 |

기능 제약이 선지를 가릅니다.

- view를 지원하지 않는다
- custom CDC start point 설정을 지원하지 않는다
- Db2 endpoint에 SSL 연결을 지원하지 않는다
- 관리용 public IP가 없다
- S3, Kinesis, Secrets Manager, DynamoDB, Redshift, OpenSearch Service를 쓰려면 VPC endpoint가 필요하다

엔진 지원 범위도 표준 DMS보다 좁습니다. Serverless 소스는 MongoDB, DocumentDB, SQL Server, PostgreSQL 호환, MySQL 호환, MariaDB, Oracle, S3, IBM Db2입니다. 타깃은 SQL Server, PostgreSQL, MySQL 호환, Oracle, S3, Redshift, DynamoDB, Kinesis Data Streams, MSK, OpenSearch Service, DocumentDB, Neptune입니다.

**SAP ASE가 소스 목록에 없습니다.** 지문에 SAP ASE가 등장하면 Serverless 선지가 전부 탈락하고 provisioned replication instance가 답이 됩니다. view 이전이 요구되거나 custom CDC start point가 필요한 경우도 같은 결론입니다.

| 축 | provisioned replication instance | Serverless replication |
| :--- | :--- | :--- |
| 용량 지정 | 인스턴스 클래스 선택 | Min과 Max DCU 지정. DCU 1개는 RAM 2GB |
| 엔진 지원 범위 | 넓다 | 좁다. 표준이 지원하는 모든 엔진을 지원하지 않는다 |
| view | 지원 | 지원하지 않는다 |
| custom CDC start point | 지원 | 지원하지 않는다 |
| 스토리지 | 클래스별 50GB 또는 100GB, GP2 | 초기 100GB, 90%에서 자동 확장 |
| 유휴 후 재개 | 인스턴스가 살아 있다 | 48시간 미시작이면 deprovision되어 재개 불가 |
| full load 중 축소 | 해당 없음 | 불가 |

---

## 21. SCT와 DMS Schema Conversion 중 무엇을 고를 것인가

DMS Schema Conversion은 AWS SCT의 변환 엔진 위에 만든 완전관리형 웹 기반 기능입니다. 데이터가 아니라 스키마만 변환하고, 데이터 이전은 DMS의 데이터 마이그레이션 기능으로 따로 합니다. 현재 변환은 rules-based engine을 기본으로 하며, 완전히 변환되지 않는 객체에는 generative AI 보조 변환을 사용할 수 있습니다.

리소스 모델이 세 종류입니다.

| 리소스 | 내용 |
| :--- | :--- |
| instance profile | 네트워크와 보안 설정 |
| data provider | 소스 또는 타깃 연결 정보 |
| migration project | data provider 두 개와 instance profile, 그리고 자격증명을 담은 Secrets Manager secret |

DB 자격증명이 Secrets Manager에 들어간다는 점이 마이그레이션 도구 보안 문항의 재료가 됩니다. 자격증명을 프로젝트 설정에 평문으로 넣는 구성은 이 모델에서 나오지 않습니다.

타깃이 아직 없어도 virtual target으로 변환을 진행하고 나중에 실제 타깃을 붙일 수 있습니다. 변환 결과는 타깃에 바로 적용하거나 SQL 스크립트로 S3에 내보낼 수 있습니다. 타깃에 없는 소스 기능은 extension pack으로 일부 에뮬레이션합니다.

지원 변환 경로는 11개입니다.

| 소스 | 타깃 |
| :--- | :--- |
| Oracle | Aurora PostgreSQL과 RDS PostgreSQL, Aurora MySQL과 RDS MySQL, Redshift |
| SQL Server | PostgreSQL 계열, MySQL 계열 |
| PostgreSQL | MySQL 계열 |
| MySQL | PostgreSQL 계열 |
| Db2 LUW | PostgreSQL 계열 |
| Db2 for z/OS | PostgreSQL 계열, RDS for Db2 |
| SAP ASE | PostgreSQL 계열 |

Db2 for z/OS 경로는 콘솔에 없고 API나 CLI로만 씁니다. 그리고 **AWS SCT는 DMS Schema Conversion보다 더 많은 소스와 타깃 데이터베이스를 지원합니다.** 이 문장을 DMS 문서가 직접 명시하므로, 변환 경로가 위 11개 밖이면 데스크톱 SCT를 쓴다는 판단이 성립합니다.

| 축 | AWS SCT(데스크톱) | DMS Schema Conversion |
| :--- | :--- | :--- |
| 설치 | 데스크톱 클라이언트 | 설치 없음. 콘솔과 API |
| 지원 DB 범위 | 더 넓다 | 11개 변환 경로 |
| 리소스 모델 | 로컬 프로젝트 | instance profile, data provider, migration project |
| 자격증명 | 로컬 프로젝트 설정 | Secrets Manager |
| 데이터 이전 | 하지 않는다 | 하지 않는다. DMS 데이터 마이그레이션이 담당한다 |

반대 방향의 함정도 있습니다. 소스와 타깃이 같은 엔진이면 스키마 이전에 변환 도구를 쓰지 말라는 것이 문서 권고입니다. 네이티브 도구를 씁니다. Oracle SQL Developer, MySQL Workbench, pgAdmin 4가 문서가 드는 예시입니다. MySQL에서 RDS MySQL로 가는 동종 이전에 DMS Schema Conversion을 붙이는 선지는 그럴듯하지만 권고에 어긋납니다.

---

## 22. 마이그레이션 도구 자체의 보안 경계

Exam Guide Task 4.2의 skill 하나가 마이그레이션 도구에 적절한 보안 방법을 적용하는 것입니다. 도구가 데이터를 대량으로 읽고 쓰는 경로라서 통제 지점이 따로 있습니다.

DMS 쪽 통제는 네 가지입니다.

| 항목 | 동작 |
| :--- | :--- |
| 암호화 대상 | replication instance의 스토리지와 endpoint connection information |
| 키 요건 | KMS 대칭 키만. 비대칭 키는 지원하지 않는다 |
| 키 변경 | **리소스를 만든 뒤에는 암호화 키를 바꿀 수 없다** |
| 기본 키 | `aws/dms` |

키를 나중에 바꿀 수 없다는 제약이 설계 순서를 정합니다. 규제 요건상 customer managed key가 필요하면 replication instance를 만들기 전에 결정해야 하고, 이미 만들었으면 새로 만들어 옮기는 것 외에 방법이 없습니다.

네트워크 쪽은 이렇습니다. endpoint 연결은 SSL과 TLS를 지원합니다. replication instance는 항상 VPC 안에 생성되고, 보안 그룹은 소스와 타깃 DB 포트로의 egress를 최소한 허용해야 합니다. 비RDBMS 엔진에 대해서는 VPC endpoint를 지원하지 않습니다.

운영 절차에도 정해진 순서가 있습니다. endpoint 비밀번호를 바꾸려면 task를 먼저 stop하고, DB에서 비밀번호를 바꾸고, endpoint를 modify한 뒤 task를 restart 또는 resume합니다. 순서를 바꾸면 task가 실패한 상태로 남습니다.

MGN 쪽 통제 지점은 앞에서 본 staging 서브넷과 보안 그룹입니다. 0.0.0.0:1500 inbound가 자동으로 열리므로 NACL과 라우팅으로 좁히고, 복제 트래픽을 인터넷으로 내보내지 않아야 하면 프라이빗 서브넷과 private VIF 또는 VPN으로 경로를 고정합니다. staging 볼륨과 스냅샷도 EBS 암호화 대상이므로 계정 기본 암호화 설정이 그대로 적용됩니다.

---

## 23. 컷오버 다운타임을 줄이는 절차는 도구마다 다르다

같은 "다운타임 최소화" 요구라도 서버 이전과 데이터베이스 이전의 답이 다릅니다.

**서버 이전.** MGN 연속 복제를 계속 돌려 두고, 컷오버 윈도우에서 lag 0을 확인한 뒤 소스 서비스를 정지하고 cutover instance를 기동합니다. 다운타임은 9번 단계에서 10번 단계 사이의 길이입니다. 여기에 DNS 전환 시간이 더해지므로 TTL을 미리 낮춰 둡니다.

**데이터베이스 이전.** full load + CDC로 steady state에 도달시킨 뒤 애플리케이션을 전환합니다. 다운타임은 애플리케이션을 멈추고 마지막 변경분이 적용되기를 기다린 다음 새 endpoint로 전환하는 구간입니다. 이때 마이그레이션 중 꺼 두었던 것들을 되돌리는 순서가 따라옵니다. 참조 무결성 제약과 DML trigger를 켜고, RDS 타깃이면 백업과 Multi-AZ를 다시 켭니다.

컷오버 절차에서 순서가 뒤집히면 안 되는 항목을 모아 두면 이렇습니다.

| 항목 | 올바른 순서 |
| :--- | :--- |
| Route 53 TTL | 전환 전에 300초로 낮추고 확인 후 원래 값으로 올린다 |
| replication lag | 소스 서비스 정지 전에 0을 확인한다 |
| DML trigger | 컷오버 직전에 켠다 |
| 참조 무결성 제약 | 컷오버 과정에서 켠다 |
| RDS 백업과 Multi-AZ | 컷오버 준비가 될 때까지 꺼 두고 이후에 켠다 |
| finalize cutover | cutover instance 성공 확인 후에 실행한다 |

TTL을 사후에 낮추는 선지가 매번 등장하는 이유는 그럴듯하기 때문입니다. 캐시를 무효화한다는 표현이 붙어 있으면 더 그렇습니다. 이미 리졸버에 들어간 응답은 기존 TTL이 만료될 때까지 살아 있으므로, 사후 인하는 다음 전환을 준비하는 효과만 있습니다.

---

## 24. 마이그레이션 중 신원을 어디에 둘 것인가

앞에서 domain controller가 wave보다 먼저 서야 한다고 했는데, 그 domain controller를 무엇으로 세울지는 세 가지 선택지가 있습니다.

| 축 | AWS Managed Microsoft AD | AD Connector | Simple AD |
| :--- | :--- | :--- | :--- |
| 실체 | 실제 Windows Server AD | 온프레미스 AD로의 프록시 | Samba 4 기반 디렉터리 |
| 사용자 저장 | AWS에 존재한다 | 저장하지 않는다. 온프레미스에만 있다 | AWS에 존재한다 |
| trust | 지원 | 해당 없음. 원본이 온프레미스다 | 지원하지 않는다 |
| 스키마 확장, LDAPS | 지원 | 해당 없음 | 지원하지 않는다 |
| MFA | 지원 | RADIUS 연동 | 지원하지 않는다 |
| RDS for SQL Server | 지원 | 호환되지 않는다 | 호환되지 않는다 |
| 규모 | Standard 약 30,000 오브젝트, Enterprise 약 500,000 | 온프레미스 규모에 종속 | 소규모 |

AWS Managed Microsoft AD의 규모 수치는 AWS가 근사치라고 명시합니다. Standard Edition은 직원 5,000명 이하 조직 기준으로 디렉터리 오브젝트 약 30,000개, Enterprise Edition은 약 500,000개입니다. 12만 오브젝트가 지문에 나오면 Enterprise입니다.

AD Connector는 디렉터리 동기화나 federation 인프라 없이 로그인 요청을 온프레미스 DC로 전달하는 프록시입니다. 서비스 계정 하나만 추가하면 되고, seamless domain join으로 EC2 Windows 인스턴스를 온프레미스 도메인에 조인할 수 있습니다.

Simple AD는 Samba 4 기반이라 지원하지 않는 것이 많습니다. MFA, trust relationship, DNS dynamic update, 스키마 확장, LDAPS, PowerShell AD cmdlet, FSMO role transfer가 전부 미지원입니다.

답이 갈리는 축은 두 개입니다.

1. **온프레미스 AD를 계속 source of truth로 남기는가.** 남긴다면 AD Connector이거나 Managed Microsoft AD와의 trust입니다. 사용자 계정 자체를 클라우드에 복제하지 않아야 한다는 조건이 붙으면 이 방향입니다.
2. **RDS for SQL Server의 Windows 인증이 필요한가.** 현재 RDS for SQL Server는 AWS Managed Microsoft AD 또는 self-managed Microsoft AD 직접 연동을 지원합니다. AD Connector와 Simple AD는 둘 다 호환되지 않습니다.

두 조건이 함께 나오는 문항이 실제로 자주 출제됩니다. 온프레미스 AD를 유지하면서 RDS for SQL Server를 쓰는 한 가지 방법은 Managed Microsoft AD를 만들고 온프레미스 AD와 forest trust를 맺는 구성입니다. 사용자 계정은 온프레미스에 남고 인증만 위임됩니다. self-managed AD 직접 연동 조건을 충족한다면 이 방법을 선택할 수도 있습니다.

---

## 25. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**포트폴리오 평가와 wave**

| 항목 | 값 |
| :--- | :--- |
| large migration의 정의 | 서버 300대 이상 |
| zombie application | 평균 CPU와 메모리 사용률 5% 미만 |
| idle application | 90일 동안 평균 사용률 5%에서 20% |
| retire 후보의 연결 기준 | 최근 90일간 inbound connection 없음 |
| 미리 계획하는 wave 수 | 최소 4개에서 5개 앞까지 |
| 초기 wave(1번에서 5번) | 서버 10대 미만 |
| wave 전체 상한 | 서버 50대 |
| rehost 표준 처리량 | architect 4명 팀이 1주에 최대 50대 |
| migrate and modernize Stage 1 | 1개월에서 3개월 |
| portfolio assessment 타임라인 | discovery 1주에서 5주, 우선순위 평가 6주에서 7주, 분석과 계획 8주에서 14주, continuous assessment 15주부터. AWS가 indicative로 명시 |

**Application Discovery Service와 Migration Hub**

| 항목 | 값 |
| :--- | :--- |
| Agentless Collector 수집 주기 | 약 60분 |
| Discovery Agent 수집 주기 | 약 15초 |
| Migration Hub template과 RVTools export | 단일 스냅샷 |
| Agentless Collector 대상 | VMware VM만. 물리 서버 미지원 |
| Agentless Collector가 수집하는 DB | Oracle, SQL Server, MySQL, PostgreSQL |
| discovery 데이터 저장 위치 | Migration Hub home Region 한 곳 |
| Migration Hub 상태 업데이트를 받는 도구 | Application Migration Service, AWS DMS |
| 신규 고객 접수 | Migration Hub와 ADS 모두 2025-11-07부터 중단 |

**MGN**

| 항목 | 값 |
| :--- | :--- |
| Region당 동시 진행 job | 20개 |
| 동시 복제 active source server | 150대. 초과 시 Support 요청 |
| 비archived source server | 4,000대(agentless 기준) |
| 단일 job 최대 서버 | 200대 |
| 전체 활성 job 최대 서버 | 200대 |
| 계정과 Region당 총 서버 | 50,000대 |
| source server당 동시 job | 1개 |
| replication server 타입 | t3.small |
| 볼륨 대 replication server 비율 | 통상 15대 1 |
| 스냅샷 유지 | 디스크당 5개에서 7개 수준 |
| 복제 포트 | TCP 1500 |
| 커스텀 DNS 시 추가 포트 | outbound TCP 53 |
| 압축률 | LZ4 기준 60%에서 70% |
| 일관성 | crash consistent |
| agentless 지원 vCenter | 6.7, 7.0, 8.0 |
| vCenter Client 설치 OS | Ubuntu 18.x에서 22.04, Amazon Linux 2, RHEL 8.x. 64bit Linux만 |
| AL2023 전환 | 2026-08-15부터. `arn:aws:s3:::al2023-repos-{region}-de612dc2/*` 허용 필요 |
| MGN 사용료 무료 기간 | 90일. 복제와 test 및 cutover에 쓰는 AWS 인프라 요금은 별도 |

**DMS**

| 항목 | 값 |
| :--- | :--- |
| 성립 요건 | endpoint 둘 중 하나가 AWS 서비스 |
| replication instance 스토리지 | 클래스에 따라 50GB 또는 100GB, 전부 GP2 SSD |
| full load 병렬 테이블 수 | 기본 8개. `MaxFullLoadSubTasks` |
| Limited LOB mode 기본 크기 | 32KB. 초과분은 잘린다 |
| `InlineLobMaxSize` | 1KB에서 102400KB, 기본값 0 |
| DMS가 만드는 오브젝트 | table, primary key, 경우에 따라 unique index |
| CDC 지연 SLA | 없다 |
| KMS 키 | 대칭 키만. 생성 후 변경 불가. 기본 키 `aws/dms` |
| SQL Server 소스 | Express 미지원, Web 에디션은 full load만 |
| DCU 1개 | RAM 2GB |
| Serverless 초기 스토리지 | 100GB. 15분마다 확인하고 90% 초과 시 확장 |
| Serverless 재개 한도 | 48시간 안에 시작하지 않으면 deprovision |
| DMS Schema Conversion 변환 경로 | 11개 |

**마이그레이션 실행 경로**

| 항목 | 값 |
| :--- | :--- |
| Direct Connect hosted connection 포트 속도 | 50Mbps에서 25Gbps. 1Gbps 이상은 요건 충족 파트너만, 25Gbps는 100Gbps 포트 로케이션만 |
| hosted connection 생성 주체 | 파트너가 만들고 사용자가 accept한다. 콘솔 요청 불가 |
| hosted connection traffic policing | 설정 최대 속도 초과분은 폐기된다 |
| Route 53 TTL 절차 | 변경 전에 300초로 인하, 확인 후 원복 |
| AWS Managed Microsoft AD Standard | 약 30,000 디렉터리 오브젝트 |
| AWS Managed Microsoft AD Enterprise | 약 500,000 디렉터리 오브젝트 |

---

## 26. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| retire 대 retain | retire는 쓰이지 않아서 버리는 것이고 retain은 옮길 수 없어서 남기는 것이다. 사용률 수치가 나오면 retire, 플랫폼 등가물 부재가 나오면 retain이다 |
| zombie 대 idle | 5% 미만이 zombie이고 5%에서 20%가 idle이다. 둘 다 retire 후보라 결론은 같지만 분류명을 바꿔 놓은 선지가 나온다 |
| rehost 대 relocate | rehost는 서버 단위로 EC2에 올린다. relocate는 플랫폼 단위 이동이거나 인스턴스와 객체를 다른 VPC, Region, 계정으로 옮기는 것이다 |
| replatform 대 refactor | 코드를 다시 쓰지 않으면 replatform이다. 데이터 모델 분리처럼 코드 변경을 수반하면 refactor다 |
| repurchase 대 replatform | repurchase는 제품을 바꾼다. replatform은 같은 애플리케이션을 관리형 플랫폼에 올린다 |
| Migration Evaluator 대 ADS | Evaluator는 business case와 라이선스 비용을 만들고 dependency mapping을 하지 않는다. ADS는 사용률과 프로세스와 TCP 연결을 수집한다 |
| ADS 대 Migration Hub | ADS는 수집하고 Migration Hub는 추적하고 시각화한다. Hub는 자체 수집을 하지 않는다 |
| Agentless Collector 대 Discovery Agent | 물리 서버가 섞여 있거나 프로세스 수준 의존성이 필요하면 Agent다. 데이터베이스 메타데이터는 반대로 Collector만 수집한다 |
| MGN agent 기반 대 agentless | agent 기반만 CDP를 지원해 컷오버 윈도우가 가장 짧다. agentless는 게스트 OS에 설치할 수 없을 때의 경로이고 vCenter 6.7과 7.0과 8.0만 지원한다 |
| MGN 대 DRS | 종료 상태가 다르다. MGN은 archive로 끝나고 DRS는 상시 복제를 유지한다. failback과 point in time 복구는 DRS에만 있다 |
| MGN 대 VM Import/Export | MGN은 연속 증분 복제라 컷오버 윈도우가 분 단위다. VM Import/Export는 이미지를 만들어 올리는 일회성 경로라 증분이 없다 |
| test instance 대 cutover instance | test는 몇 번이든 띄우고 지울 수 있고 소스는 계속 서비스한다. cutover는 소스 정지 이후에 기동하고 finalize로 이어진다 |
| DMS 대 네이티브 DB 도구 | 소스와 타깃이 같은 엔진이면 네이티브 도구가 권고다. 엔진이 다르면 DMS와 변환 도구 조합이다 |
| DMS 대 DMS Schema Conversion | DMS는 데이터와 table과 primary key를 옮긴다. 나머지 스키마 오브젝트는 변환 도구가 만든다 |
| AWS SCT 대 DMS Schema Conversion | 변환 경로가 11개 안에 있으면 관리형 기능이고, 밖이면 데스크톱 SCT다 |
| full load 대 full load + CDC | outage를 허용할 수 있으면 full load다. 인덱스 지침이 서로 반대라는 점이 함께 나온다 |
| CDC only 대 full load + CDC | CDC only는 bulk load를 다른 수단으로 이미 마쳤음을 전제한다. 타깃이 비어 있으면 성립하지 않는다 |
| provisioned 대 DMS Serverless | 엔진 조합이 Serverless 범위 밖이거나 view와 custom CDC start point가 필요하면 provisioned다 |
| DMS CDC 대 네이티브 복제 | sub-second 지연 보장이 요구되면 DMS CDC가 아니다. 컷오버 다운타임 단축이 요구면 DMS CDC다 |
| Managed Microsoft AD 대 AD Connector | 사용자 계정을 AWS에 두는지가 갈린다. RDS for SQL Server는 AWS Managed Microsoft AD 또는 self-managed Microsoft AD 직접 연동을 지원하고 AD Connector는 호환되지 않는다 |
| AD Connector 대 Simple AD | AD Connector는 온프레미스 AD가 이미 있을 때 그 계정을 그대로 쓰는 프록시다. Simple AD는 온프레미스 AD 없이 저규모 디렉터리가 필요할 때이고 trust를 지원하지 않는다 |
| Direct Connect hosted 대 dedicated | hosted connection은 파트너가 만들고 사용자가 accept하며 콘솔에서 요청할 수 없다. traffic policing이 적용된다 |
| move group 대 wave | move group은 함께 옮겨야 하는 묶음이고 wave는 하나 이상의 move group으로 구성된다. AD 의존성은 move group 기준이 아니다 |

---

## 27. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| 온프레미스 Oracle에서 온프레미스 PostgreSQL로 DMS를 쓴다 | endpoint 둘 중 하나가 AWS 서비스여야 한다 |
| DMS 하나로 heterogeneous 마이그레이션의 스키마까지 전부 옮긴다 | DMS는 table, primary key, 일부 unique index만 만든다. 나머지는 변환 도구가 필요하다 |
| SAP ASE 소스를 DMS Serverless로 옮긴다 | Serverless 소스 목록에 SAP ASE가 없다 |
| DMS Serverless로 view를 이전한다 | Serverless는 view를 지원하지 않는다. custom CDC start point도 지원하지 않는다 |
| MGN으로 마이그레이션한 뒤 문제가 생기면 소스로 failback한다 | failback은 DRS의 기능이고 MGN에는 없다 |
| 한 서버에 MGN 에이전트와 DRS 에이전트를 함께 설치해 이전과 DR을 동시에 준비한다 | 동시에 설치할 수 없다. 한쪽을 제거해야 다른 쪽이 설치된다 |
| 에이전트 설치가 금지된 환경에서 agentless로 무중단에 가까운 컷오버를 보장한다 | agentless는 스냅샷 기반이라 CDP가 없다. 가장 짧은 컷오버 윈도우가 필요하면 agent 기반이다 |
| test instance를 그대로 운영으로 전환하고 finalize cutover를 건너뛴다 | 컷오버는 cutover instance 기동과 finalize로 완결된다. 건너뛰면 복제 리소스가 정리되지 않는다 |
| replication server에 Elastic IP를 붙여 복제 경로를 고정한다 | replication server의 IP는 고정할 수 없고 MGN이 자동으로 교체한다 |
| NFS로 마운트된 NAS 데이터도 MGN이 함께 복제한다 | 네트워크 마운트는 복제되지 않는다. 실제 NFS 서버에 에이전트를 설치해야 한다 |
| MGN post-launch 스크립트를 타깃 인스턴스에 올려 둔다 | 스크립트 경로는 소스 서버에 만든다. Linux는 `/boot/post_launch`, Windows는 에이전트 설치 경로 아래다 |
| PowerShell 스크립트를 post-launch action으로 그대로 등록한다 | 자동 실행되지 않는다. `.cmd`로 감싸야 한다 |
| MGN으로 한 Region에서 4,000대를 동시 복제한다 | 동시 active source server 기본 한도는 150대다. 4,000은 agentless 기준 비archived 서버 수다 |
| 물리 서버가 섞인 데이터센터를 ADS Agentless Collector 하나로 전부 discovery한다 | Agentless Collector는 VMware VM만 지원한다 |
| 프로세스 수준 의존성 맵이 필요한데 Agentless Collector로 충분하다고 본다 | VM 내부를 보지 못해 running process를 수집하지 못한다 |
| Discovery Agent로 데이터베이스 스키마 복잡도를 수집한다 | 데이터베이스 메타데이터는 Agentless Collector의 데이터베이스와 분석 모듈이 수집한다 |
| dependency mapping이 필요해서 Migration Evaluator를 도입한다 | FAQ가 그 작업을 Migration Hub에서 한다고 명시한다. Evaluator의 산출물은 business case다 |
| Migration Hub를 여러 Region에 두고 Region별 진행 상황을 각각 추적한다 | 추적 데이터는 home Region 한 곳에만 저장된다 |
| home Region이 하나이므로 마이그레이션 대상 Region도 하나로 묶인다 | 대상 Region은 도구가 지원하는 어떤 Region이든 될 수 있다 |
| discovery를 먼저 시작하고 home Region은 나중에 정한다 | discovery를 시작하기 전에 home Region을 반드시 설정해야 한다 |
| 평균 사용률 5%에서 20% 사이 서버를 zombie로 분류해 retire한다 | 5% 미만이 zombie이고 5%에서 20%가 idle이다 |
| 물리 서버를 EC2로 옮기는 것을 relocate로 분류한다 | rehost다. relocate는 플랫폼 단위 이동이거나 소속 변경이다 |
| AS/400 애플리케이션을 replatform으로 분류해 RDS로 옮긴다 | non-x86 mid-range는 retain 사유다. 클라우드 등가물이 없다 |
| 첫 wave에 서버 200대를 넣어 속도를 확보한다 | 초기 wave는 10대 미만, 모든 wave는 50대 이하다. 팀 하나의 주당 처리량도 최대 50대다 |
| Active Directory 의존성을 move group 기준으로 삼아 AD 서버와 애플리케이션을 같은 wave에 넣는다 | AD는 공통 의존성이라 기준에서 제외하고, 어떤 wave보다 먼저 domain controller를 세운다 |
| wave 크기를 서버 수만으로 정한다 | 네트워크 대역폭, 스토리지 크기, 환경, 사용자 수가 함께 판단 축이다 |
| full load 속도를 높이려고 타깃에 secondary index와 foreign key를 미리 만들어 둔다 | full load 전용 task는 인덱스와 제약과 DML trigger를 제거하거나 생성을 미룬다 |
| full load + CDC에서도 secondary index를 나중에 만든다 | CDC 단계 전에 만들어야 한다. 없으면 logical replication이 full table scan을 유발한다 |
| batch optimized apply를 켜고 참조 무결성 제약도 유지한다 | 거의 항상 제약을 위반한다. 마이그레이션 중에는 끄고 컷오버에서 켠다 |
| Limited LOB mode 기본값으로 두면 모든 LOB이 그대로 이전된다 | 기본 32KB를 넘는 LOB은 잘린다 |
| DMS 리소스 생성 후 규제 요건 때문에 KMS 키를 customer managed key로 교체한다 | 생성 후에는 암호화 키를 바꿀 수 없다. 비대칭 키도 쓸 수 없다 |
| 비밀번호만 DB에서 바꾸면 DMS task가 자동으로 따라간다 | task를 stop하고 비밀번호를 바꾸고 endpoint를 modify한 뒤 restart 또는 resume해야 한다 |
| 금융 거래 동기화에 DMS CDC를 써서 sub-second 지연을 보장한다 | CDC 지연에 SLA가 없고 문서가 그 용도를 금지한다 |
| homogeneous 마이그레이션의 스키마 이전에 DMS Schema Conversion을 쓴다 | 같은 엔진이면 네이티브 도구를 쓰라는 것이 문서 권고다 |
| 변환 경로가 목록에 없어도 DMS Schema Conversion으로 처리한다 | AWS SCT가 더 넓은 소스와 타깃을 지원한다. 11개 밖이면 SCT다 |
| 컷오버가 끝난 뒤 Route 53 레코드의 TTL을 낮춘다 | 이미 캐시된 응답은 기존 TTL이 만료될 때까지 유지된다. 인하는 변경 전에 한다 |
| alias 레코드로 바꾸면 TTL과 무관하게 즉시 전환된다 | alias 레코드도 캐싱 대상이고 대상 리소스에 따른 TTL을 따른다 |
| Simple AD로 온프레미스 AD와 trust를 맺어 신원을 통합한다 | Simple AD는 trust relationship을 지원하지 않는다 |
| AD Connector로 RDS for SQL Server의 Windows 인증을 구성한다 | AD Connector는 RDS SQL Server와 호환되지 않는다 |
| Managed Microsoft AD Standard Edition으로 12만 오브젝트를 담는다 | Standard는 약 30,000 오브젝트 규모다. 12만이면 Enterprise다 |
| 500Mbps hosted connection에 순간적으로 1Gbps를 밀어 넣어 초기 복제를 앞당긴다 | traffic policing이 적용되어 설정 최대 속도 초과분은 폐기된다 |
| hosted connection을 콘솔에서 직접 만들어 마이그레이션 기간에만 쓴다 | 파트너가 만들어야 하고 사용자는 accept만 한다. 속도 변경도 파트너의 몫이다 |
| SaaS로 repurchase하면 마이그레이션 작업이 사라진다 | 교육, 데이터 이전, 인증 서비스 통합, 네트워킹 구성이 남는다 |

---

## 28. 예상 문제 10문항

**Q1.** 제조 기업이 18개월 뒤 데이터센터 임대 계약 종료를 앞두고 포트폴리오 평가를 마쳤습니다. 애플리케이션 A는 IBM AS/400에서 도는 생산 관리 시스템이고 벤더가 x86 포팅 경로를 제공하지 않습니다. 애플리케이션 B는 최근 90일 평균 CPU 3%, 메모리 4%이고 같은 기간 inbound connection이 0건입니다. 재작성 예산은 승인되지 않았습니다. 두 애플리케이션에 대한 MOST appropriate 7R 전략 조합은 무엇입니까?

- A. A는 rehost, B는 relocate
- B. A는 refactor, B는 rehost
- C. A는 retain, B는 retire
- D. A는 replatform, B는 retain

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

AWS는 mainframe, mid-range, non-x86 Unix 애플리케이션을 retain 사유로 명시하고 IBM AS/400을 그 예시로 듭니다. 애플리케이션 B는 90일 평균 CPU와 메모리 사용률이 5% 미만이라 zombie application 기준에 들어가고, 최근 90일 inbound connection이 없는 것도 retire 후보 기준입니다.

- A가 틀린 이유: rehost는 x86 가상 또는 물리 서버를 그대로 EC2로 옮기는 전략이고 AS/400에는 대응하는 인스턴스 패밀리가 없다. relocate는 플랫폼 단위 이동이거나 인스턴스와 객체를 다른 VPC, Region, 계정으로 옮기는 것이라 사용되지 않는 서버를 정리하는 전략이 아니다.
- B가 틀린 이유: refactor는 코드 재작성을 수반하는데 재작성 예산이 승인되지 않았다. AWS는 대규모 마이그레이션에 refactor를 권장하지 않는다.
- D가 틀린 이유: replatform은 옮기면서 일부 최적화를 하는 전략이라 클라우드 등가물이 없는 AS/400에 적용되지 않는다. B를 retain하면 사용되지 않는 서버의 비용이 그대로 남는다.

</details>

**Q2.** 금융사가 서버 1,100대를 12개월에 걸쳐 마이그레이션합니다. 주 전략은 rehost이고 architect 4명으로 구성된 migration 팀 하나가 실행합니다. 모든 애플리케이션이 온프레미스 Active Directory 인증에 의존합니다. 첫 wave 계획으로 MOST appropriate한 것은 무엇입니까?

- A. 어떤 wave보다 먼저 클라우드에 domain controller를 세우고, wave 1은 서버 10대 미만의 비운영 애플리케이션으로 구성한다
- B. Active Directory 의존성을 move group 기준으로 삼아 같은 도메인을 쓰는 서버를 wave당 300대씩 묶는다
- C. wave 크기를 네트워크 대역폭이 아니라 애플리케이션 owner 수로 정하고 wave 1에 50대를 넣는다
- D. 첫 wave에 domain controller와 그것에 의존하는 애플리케이션 200대를 함께 넣어 인증 경로를 한 번에 검증한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

AWS wave planning 지침은 초기 wave(1번에서 5번)를 서버 10대 미만으로 잡고, 어떤 wave도 서버 50대를 넘기지 않으며, architect 4명 팀이 rehost 기준 주당 최대 50대를 처리한다고 봅니다. Active Directory는 모든 애플리케이션의 공통 의존성이므로 move group 기준에서 제외하고, 어떤 애플리케이션을 옮기기 전에 클라우드에 domain controller를 먼저 세우라고 문서가 명시합니다.

- B가 틀린 이유: AD 의존성은 공통 의존성이라 move group 기준으로 쓰지 않는다. wave당 300대도 상한을 크게 넘는다.
- C가 틀린 이유: wave sizing 축에 network bandwidth가 포함되고 wave 크기가 대역폭을 초과하면 안 된다. wave 1에 50대는 초기 wave 기준인 10대 미만에도 어긋난다.
- D가 틀린 이유: 200대는 초기 wave 10대 미만 기준과 wave 상한 50대를 모두 초과하고, AD를 wave에 포함시키는 것 자체가 지침에 어긋난다.

</details>

**Q3.** 소매 기업 CFO가 온프레미스 VMware 환경 900대의 AWS 이전 비용을 이사회 승인 전에 보고받으려 합니다. 보안팀은 게스트 OS에 어떤 에이전트도 설치할 수 없다고 통보했습니다. 추정에는 Windows Server와 SQL Server 라이선스 비용과 BYOL 시나리오가 포함되어야 합니다. MOST appropriate 접근은 무엇입니까?

- A. AWS Pricing Calculator에 vCenter 인벤토리를 수동 입력해 견적을 만든다
- B. AWS Compute Optimizer로 rightsizing 권고를 받아 비용을 추정한다
- C. Application Discovery Service Discovery Agent를 배포해 사용률을 수집하고 Migration Hub에서 비용을 산출한다
- D. AWS Migration Evaluator의 collector를 배포해 business case를 만든다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

Migration Evaluator는 네트워크 안에 Windows Server VM 한 대를 띄우고 WMI, SNMP, VMware vSphere, T-SQL 같은 표준 프로토콜로 수집하며 하이퍼바이저나 개별 서버에 에이전트를 설치하지 않습니다. business case 산출물에 EC2와 EBS와 OS 라이선스 비용 추정, Microsoft SQL Server 라이선스 분석, BYOL 모델링이 포함됩니다.

- A가 틀린 이유: Pricing Calculator는 사용자가 입력한 사양으로 견적을 계산할 뿐 실사용률 기반 rightsizing이나 SQL Server 라이선스 분석을 제공하지 않는다.
- B가 틀린 이유: Compute Optimizer는 이미 AWS에서 도는 리소스의 rightsizing 권고를 만드는 서비스라 온프레미스 인벤토리와 라이선스 분석 대상이 아니다.
- C가 틀린 이유: Discovery Agent는 서버마다 게스트 OS에 설치해야 해서 보안 제약을 위반한다. Migration Hub는 비용 산출 도구가 아니라 마이그레이션 진행 추적과 의존성 시각화 도구다.

</details>

**Q4.** 데이터센터에 VMware VM 400대와 물리 서버 60대가 섞여 있습니다. 마이그레이션 팀은 애플리케이션 사이 통신을 프로세스 수준까지 파악해 move group을 만들어야 하고, 90일치 시계열 사용률 데이터를 Athena로 분석하려 합니다. MOST appropriate discovery 구성은 무엇입니까?

- A. Agentless Collector를 배포하고 물리 서버는 RVTools export로 import한다
- B. 모든 VM과 물리 서버에 Application Discovery Service Discovery Agent를 설치한다
- C. vCenter에 Application Discovery Service Agentless Collector만 배포한다
- D. Migration Hub import template으로 전체 인벤토리를 한 번에 올린다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Discovery Agent는 물리 서버와 VM을 모두 지원하고 약 15초 주기로 수집하며 running process를 수집합니다. time series utilization data 내보내기와 network data의 Athena 및 CSV 내보내기도 Discovery Agent만 지원합니다.

- A가 틀린 이유: RVTools export는 VMware 대상의 단일 스냅샷 import라 물리 서버의 프로세스 수준 의존성과 시계열 사용률을 제공하지 않는다.
- C가 틀린 이유: Agentless Collector는 VMware VM만 지원해 물리 서버 60대를 커버하지 못하고, VM 내부를 보지 못해 running process를 수집하지 못한다.
- D가 틀린 이유: Migration Hub import template은 단일 스냅샷이며 프로세스 정보와 시계열 사용률 데이터가 없다.

</details>

**Q5.** 리테일 기업이 온프레미스 물리 서버 120대를 EC2로 옮깁니다. 감사 요건상 컷오버 후 60일 동안 언제든 온프레미스로 되돌릴 수 있어야 하고, 되돌리는 동안 클라우드에서 발생한 변경이 소스 서버에 반영되어야 합니다. MOST appropriate 서비스 선택은 무엇입니까?

- A. AWS Elastic Disaster Recovery로 이전하고 failback을 준비한다
- B. MGN으로 이전하고 AWS Backup의 cross-account 복원으로 되돌린다
- C. AWS Application Migration Service로 이전하고 source server를 archive하지 않는다
- D. 같은 서버에 MGN 에이전트와 DRS 에이전트를 함께 설치해 이전과 failback을 동시에 준비한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

MGN과 DRS는 같은 블록 레벨 복제 기술을 공유하지만 failback은 DRS에만 있습니다. MGN 문서는 DRS가 지원하는 기능이 MGN에 없을 때 DRS를 마이그레이션에 사용해도 된다고 명시합니다.

- B가 틀린 이유: AWS Backup은 지원 대상 리소스의 백업과 복원을 다루고 온프레미스 물리 서버로 향하는 역방향 연속 복제를 제공하지 않는다.
- C가 틀린 이유: MGN에는 failback 기능이 없다. source server를 archive하지 않는 것은 서버 레코드를 목록에 남길 뿐 클라우드 변경을 온프레미스로 되돌리지 못한다.
- D가 틀린 이유: 같은 서버에 두 에이전트를 동시에 설치할 수 없다. DRS 에이전트를 설치하려면 MGN 에이전트를 먼저 제거해야 한다.

</details>

**Q6.** 보험사 보안 정책이 운영 중인 게스트 OS에 신규 소프트웨어를 설치하는 것을 금지합니다. 대상은 vCenter 7.0에서 도는 VM 300대이고, 복제 트래픽은 인터넷을 경유하면 안 되며 기존 Direct Connect private VIF만 써야 합니다. 컷오버 윈도우는 애플리케이션당 4시간까지 허용됩니다. MOST appropriate 구성은 무엇입니까?

- A. 각 VM에 AWS Replication Agent를 설치하고 replication server에 Elastic IP를 붙여 복제 경로를 고정한다
- B. 각 VM에 DRS 에이전트를 설치해 연속 복제한 뒤 recovery instance로 컷오버한다
- C. MGN vCenter Client를 배포해 agentless 스냅샷 복제를 수행하고, staging area subnet으로 가는 경로를 Direct Connect private VIF로 라우팅한다
- D. VM Import/Export로 각 VM의 OVA를 내보내 S3에 올린 뒤 AMI로 변환한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

MGN의 agentless 복제는 vCenter에 MGN vCenter Client를 설치해 스냅샷 기반으로 동작하며, 회사 정책상 서버마다 에이전트를 설치할 수 없을 때 쓰는 경로입니다. AWS가 agent 기반을 권장하는 이유는 CDP를 지원해 컷오버 윈도우가 가장 짧기 때문인데, 여기서는 4시간 윈도우가 허용되므로 agentless의 스냅샷 주기를 감당할 수 있습니다.

- A가 틀린 이유: 게스트 OS에 에이전트를 설치하는 것 자체가 정책 위반이고, replication server에 Elastic IP를 붙이면 private VIF만 쓰라는 요건과 어긋나는 public 경로가 생긴다. MGN은 replication server의 IP 고정을 지원하지도 않는다.
- B가 틀린 이유: DRS 에이전트도 게스트 OS에 설치해야 하므로 같은 정책에 걸린다.
- D가 틀린 이유: VM Import/Export는 VM을 정지하고 이미지를 내보내 업로드하는 일회성 경로라 증분 복제가 없다. 300대 규모에서 컷오버 윈도우 안에 끝낼 수 없다.

</details>

**Q7.** Oracle 11g 데이터베이스를 Aurora PostgreSQL로 옮깁니다. 스키마에는 stored procedure 400개, trigger, secondary index, foreign key가 있습니다. 데이터 크기는 4TB이고 컷오버 다운타임은 15분 이내여야 합니다. MOST appropriate 조합은 무엇입니까?

- A. DMS Schema Conversion으로 변환한 뒤 full load only task로 이전하고 컷오버 시점에 애플리케이션을 정지한다
- B. DMS Schema Conversion으로 스키마와 코드 오브젝트를 변환해 타깃에 적용한 뒤, DMS full load + CDC로 데이터를 이전하고 CDC 단계 전에 secondary index를 생성한다
- C. DMS full load + CDC task 하나로 스키마와 데이터를 모두 이전한다
- D. Oracle Data Pump로 스키마와 데이터를 내보내 S3에 올린 뒤 DMS CDC only task로 변경분을 따라잡는다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

DMS는 타깃에 table, primary key, 경우에 따라 unique index만 만들고 secondary index, foreign key, sequence, stored procedure, trigger, view는 만들지 않습니다. 전체 스키마와 코드 오브젝트 변환에는 DMS Schema Conversion이 필요합니다. full load + CDC task는 CDC 단계 전에 secondary index를 만들어야 하는데, DMS가 logical replication을 쓰기 때문에 인덱스가 없으면 full table scan이 발생합니다.

- A가 틀린 이유: full load only는 4TB 적재가 끝날 때까지 소스를 정지해야 하므로 15분 다운타임 제약을 만족하지 못한다.
- C가 틀린 이유: DMS 단독으로는 stored procedure와 trigger 같은 코드 오브젝트를 이전하지 못한다.
- D가 틀린 이유: Oracle Data Pump는 동종 엔진 사이의 도구라 Oracle에서 PostgreSQL로 가는 heterogeneous 변환을 하지 못한다. CDC only는 다른 수단으로 타깃이 이미 동일 데이터로 채워졌음을 전제한다.

</details>

**Q8.** SAP ASE에서 Aurora MySQL로 2TB를 옮깁니다. 팀은 replication instance 용량을 직접 관리하고 싶지 않아 DMS Serverless를 우선 검토했습니다. 소스 스키마에는 애플리케이션이 의존하는 view 12개가 있고 이것도 함께 이전되어야 합니다. MOST appropriate 접근은 무엇입니까?

- A. Aurora MySQL에 SAP ASE용 federated 엔진을 붙여 소스를 직접 조회한다
- B. DMS Serverless replication을 만들고 최소 2 DCU, 최대 16 DCU로 설정한다
- C. DMS Serverless로 데이터만 옮기고 view는 타깃에서 수동으로 다시 만든다
- D. provisioned replication instance로 DMS task를 구성하고 view는 DMS Schema Conversion 또는 AWS SCT로 변환한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: D**

DMS Serverless의 지원 소스 목록에는 SAP ASE가 없고, Serverless는 view를 지원하지 않으며 custom CDC start point 설정도 지원하지 않습니다. 엔진 조합이 Serverless 범위 밖이면 provisioned replication instance가 정답이 됩니다. view는 DMS 자체가 만들지 않으므로 스키마 변환 도구가 필요합니다.

- A가 틀린 이유: Aurora MySQL은 SAP ASE를 대상으로 하는 federated 엔진을 제공하지 않는다.
- B가 틀린 이유: SAP ASE는 DMS Serverless 소스로 지원되지 않아 replication을 만들 수 없다.
- C가 틀린 이유: 같은 이유로 Serverless 구성 자체가 성립하지 않는다.

</details>

**Q9.** 온프레미스 Active Directory를 계속 신원의 source of truth로 유지해야 합니다. 마이그레이션 대상 중 하나는 Windows 인증을 쓰는 SQL Server 데이터베이스이고 이것을 RDS for SQL Server로 replatform합니다. 사용자 계정은 클라우드에 복제되지 않고 온프레미스에만 존재해야 합니다. MOST appropriate 구성은 무엇입니까?

- A. AWS Managed Microsoft AD를 만들고 온프레미스 AD와 forest trust를 맺은 뒤 RDS for SQL Server를 이 디렉터리에 조인한다
- B. IAM Identity Center에 온프레미스 AD를 external identity provider로 연결하고 RDS 인증에 사용한다
- C. AD Connector를 만들어 RDS for SQL Server에 연결한다
- D. Simple AD를 만들고 온프레미스 AD와 trust를 맺는다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

AWS Managed Microsoft AD는 실제 Windows Server Active Directory이고 온프레미스 AD와 trust를 맺을 수 있으며 RDS for SQL Server를 지원합니다. trust를 쓰면 사용자 계정은 온프레미스에 남고 인증만 위임됩니다.

- B가 틀린 이유: IAM Identity Center는 AWS 액세스 포털과 애플리케이션 SSO를 담당하고, RDS for SQL Server의 Windows 인증에 필요한 도메인 조인을 제공하지 않는다.
- C가 틀린 이유: AD Connector는 RDS for SQL Server와 호환되지 않는다고 문서가 명시한다.
- D가 틀린 이유: Simple AD는 Samba 4 기반이라 trust relationship을 지원하지 않고 RDS for SQL Server와도 호환되지 않는다.

</details>

**Q10.** MGN으로 복제 중인 애플리케이션 서버 40대를 토요일 새벽 2시간 윈도우에 컷오버합니다. 서비스의 public DNS 레코드는 Route 53에 있고 현재 TTL은 86400초입니다. 다운타임을 최소화하기 위해 취해야 할 조치 두 가지는 무엇입니까? (2개 선택)

- A. test instance를 그대로 운영으로 전환하고 finalize cutover 단계를 건너뛴다
- B. 컷오버 며칠 전에 대상 레코드의 TTL을 300초 같은 짧은 값으로 낮추고, 전환이 확인된 뒤 원래 값으로 올린다
- C. 컷오버 직전에 MGN failback을 구성해 롤백 경로를 만든다
- D. 컷오버가 끝난 직후 TTL을 300초로 낮춰 캐시된 응답을 무효화한다
- E. 컷오버 윈도우에서 replication lag이 0인지 확인한 뒤 소스 서버의 서비스를 정지하고 cutover instance를 기동한다
- F. 레코드를 alias 레코드로 바꾸면 TTL과 무관하게 즉시 전환되므로 TTL은 그대로 둔다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B, E**

Route 53 문서는 이미 사용 중인 도메인이나 서브도메인의 설정을 바꿀 때 먼저 300초 같은 짧은 값으로 TTL을 낮추고, 새 설정이 맞다고 확인한 뒤 값을 다시 올리라고 명시합니다. MGN 워크플로는 컷오버 윈도우에서 lag이 0인지 확인하고, 소스 서비스를 정지한 뒤 cutover instance를 기동하고, 성공을 확인한 다음 finalize cutover와 source server archive로 끝납니다.

- A가 틀린 이유: test instance는 인수 테스트용이며 컷오버 절차는 cutover instance 기동과 finalize cutover로 완결된다. finalize를 건너뛰면 복제 리소스가 정리되지 않고 서버 상태도 컷오버 완료로 표시되지 않는다.
- C가 틀린 이유: failback은 DRS의 기능이고 MGN에는 없다.
- D가 틀린 이유: 이미 리졸버에 캐시된 응답은 기존 TTL이 만료될 때까지 유지되므로 사후에 TTL을 낮춰도 진행 중인 컷오버의 전환 시간을 줄이지 못한다.
- F가 틀린 이유: alias 레코드도 리졸버 캐싱의 대상이며 대상 리소스에 따라 정해진 TTL을 따른다. 레코드 타입 변경이 전파를 즉시로 만들지 않는다.

</details>

---

## 29. Reference

- [AWS Prescriptive Guidance - Migration strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/large-migration-guide/migration-strategies.html)
- [AWS Prescriptive Guidance - Guide for AWS large migrations](https://docs.aws.amazon.com/prescriptive-guidance/latest/large-migration-guide/introduction.html)
- [AWS Prescriptive Guidance - Phases of a large migration](https://docs.aws.amazon.com/prescriptive-guidance/latest/large-migration-guide/phases.html)
- [AWS Prescriptive Guidance - Wave planning](https://docs.aws.amazon.com/prescriptive-guidance/latest/large-migration-portfolio-playbook/wave-planning.html)
- [AWS Prescriptive Guidance - Implement wave planning](https://docs.aws.amazon.com/prescriptive-guidance/latest/large-migration-portfolio-playbook/implement-wave-planning.html)
- [AWS Prescriptive Guidance - Application portfolio assessment guide](https://docs.aws.amazon.com/prescriptive-guidance/latest/application-portfolio-assessment-guide/introduction.html)
- [AWS Application Discovery Service - What is AWS Application Discovery Service?](https://docs.aws.amazon.com/application-discovery/latest/userguide/what-is-appdiscovery.html)
- [AWS Application Discovery Service - Availability change](https://docs.aws.amazon.com/application-discovery/latest/userguide/application-discovery-service-availability-change.html)
- [AWS Migration Hub - What is AWS Migration Hub?](https://docs.aws.amazon.com/migrationhub/latest/ug/whatishub.html)
- [AWS Migration Hub - Availability change](https://docs.aws.amazon.com/migrationhub/latest/ug/migrationhub-availability-change.html)
- [AWS Migration Evaluator - FAQs](https://aws.amazon.com/migration-evaluator/faqs/)
- [AWS Application Migration Service - What is Application Migration Service?](https://docs.aws.amazon.com/mgn/latest/ug/what-is-application-migration-service.html)
- [AWS Application Migration Service - General questions FAQ](https://docs.aws.amazon.com/mgn/latest/ug/General-Questions-FAQ.html)
- [AWS Application Migration Service - Replication related FAQ](https://docs.aws.amazon.com/mgn/latest/ug/Replication-Related-FAQ.html)
- [AWS Application Migration Service - Agentless replication](https://docs.aws.amazon.com/mgn/latest/ug/agentless-mgn.html)
- [AWS Application Migration Service - Agentless replication related FAQ](https://docs.aws.amazon.com/mgn/latest/ug/Agentless-Replication-Related-FAQ.html)
- [AWS Application Migration Service - vCenter Client overview](https://docs.aws.amazon.com/mgn/latest/ug/installing-vcenter-overview-mgn.html)
- [AWS Application Migration Service - vCenter Client requirements](https://docs.aws.amazon.com/mgn/latest/ug/installing-vcenter-reques-mgn.html)
- [AWS Application Migration Service - Migration workflow](https://docs.aws.amazon.com/mgn/latest/ug/migration-workflow-gs.html)
- [AWS Application Migration Service - Pricing](https://aws.amazon.com/application-migration-service/pricing/)
- [AWS Transform MGN - Adding source servers](https://docs.aws.amazon.com/mgn/latest/ug/adding-servers.html)
- [AWS Transform MGN - Release notes](https://docs.aws.amazon.com/mgn/latest/ug/mgn-release-notes.html)
- [AWS Transform MGN - Replication template reference](https://docs.aws.amazon.com/mgn/latest/ug/replication-server-settings.html)
- [AWS Elastic Disaster Recovery - What is Elastic Disaster Recovery?](https://docs.aws.amazon.com/drs/latest/userguide/what-is-drs.html)
- [AWS DMS - What is AWS Database Migration Service?](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Introduction.html)
- [AWS DMS - High-level view of AWS DMS](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Introduction.HighLevelView.html)
- [AWS DMS - Components of AWS DMS](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Introduction.Components.html)
- [AWS DMS - Sources for AWS DMS](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Introduction.Sources.html)
- [AWS DMS - Best practices](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_BestPractices.html)
- [AWS DMS - Security](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Security.html)
- [AWS DMS Serverless - Components](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Serverless.Components.html)
- [AWS DMS Serverless - Limitations](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Serverless.Limitations.html)
- [AWS DMS - Schema conversion](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_SchemaConversion.html)
- [AWS Schema Conversion Tool - What is AWS SCT?](https://docs.aws.amazon.com/SchemaConversionTool/latest/userguide/CHAP_Welcome.html)
- [AWS Direct Connect - Hosted connections](https://docs.aws.amazon.com/directconnect/latest/UserGuide/hosted_connection.html)
- [Amazon Route 53 - Values that you specify when you create or edit records](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-values-basic.html)
- [AWS Directory Service - What is AWS Directory Service?](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/what_is.html)
- [Amazon RDS for SQL Server - Working with self-managed Active Directory](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_SQLServer_SelfManagedActiveDirectory.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
