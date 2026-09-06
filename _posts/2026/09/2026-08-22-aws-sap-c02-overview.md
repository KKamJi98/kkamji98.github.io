---
title: "AWS SAP-C02 박살내기 - 시험 구조와 4개 도메인, 7주 학습 로드맵"
date: 2026-08-22 10:00:00 +0900
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, solutions-architect, exam, roadmap]
comments: true
image:
  path: /assets/img/aws/aws.webp
---

AWS Certified Solutions Architect - Professional은 AWS 인증 체계의 Professional 등급에 속하는 솔루션 아키텍트 자격증입니다. 줄여서 SAP라고 부르고, 현재 유효한 시험 버전은 SAP-C02입니다. 180분 동안 75문항을 풀고, 1000점 만점에 750점을 넘으면 합격합니다.

AWS는 이 시험이 검증하는 것을 `advanced technical skills and experience in designing optimized AWS solutions that are based on the AWS Well-Architected Framework`라고 규정합니다. Associate 등급이 요구사항 하나에 맞는 서비스를 고르게 한다면, Professional 등급은 제약 조건 여러 개가 동시에 걸린 상태에서 여러 애플리케이션과 여러 계정을 가로지르는 설계 판단을 요구합니다. 그래서 선지 네 개가 전부 동작하는 구성으로 출제되고, 지문이 지정한 축을 따라 우선순위를 매기는 것이 실제 과제가 됩니다.

시험 구조를 먼저 정확히 아는 것이 학습 계획의 출발점입니다. 몇 문항이 채점되는지, 750점이 무엇을 뜻하는지, 부분점수가 있는지 없는지에 따라 문제 푸는 방식과 시간 배분이 달라지기 때문입니다.

> **TL;DR**  
> - 총 75문항 중 65문항이 채점되고 10문항은 채점되지 않는다. 어느 쪽인지 시험 중에 구분할 수 없다.  
> - 결과는 100-1000 scaled score로 나오고 합격선은 750이다. 도메인별 과락이 없는 compensatory 채점이라 약한 도메인을 강한 도메인으로 상쇄할 수 있다.  
> - multiple response는 정답을 **전부** 골라야 득점한다. 부분점수가 없다.  
> - 180분에 75문항이므로 문항당 2.4분이다. SAP는 지문이 길어 페이싱이 별도의 훈련 대상이다.  
> - 미응답은 오답 처리되고 추측 페널티는 없다. 빈칸을 남기는 것은 순손실이다.  
> - **SAP-C02 응시 마지막 날은 2026년 11월 16일이고, 11월 17일부터 SAP-C03으로 바뀐다.**  
{: .prompt-info}

---

## 1. AWS 인증 체계에서 SAP의 위치

AWS 인증은 다섯 갈래로 나뉩니다. 기술 등급 네 개에 더해 Business 갈래가 따로 있습니다. Business는 클라우드와 AI를 비즈니스 성과로 연결하는 전략 역량을 검증하고 기술 경험을 요구하지 않아서, 솔루션을 직접 만들지 않는 사람을 대상으로 합니다.

![AWS 자격증 등급 구조. Foundational, Associate, Professional, Specialty 네 등급과 Business 갈래로 나뉘며 같은 열이 같은 직무 축을 이룬다](/assets/img/sap-c02/aws-certification-tiers.webp)

세로가 등급이고 가로가 직무 축입니다. 맨 왼쪽 열을 보면 Solutions Architect - Associate 위에 Solutions Architect - Professional이 놓입니다. 두 상자를 잇는 화살표가 이 시리즈가 오르려는 사다리이고, 오른쪽 끝의 Developer에서 DevOps Engineer로 향하는 화살표가 그에 대응하는 다른 축입니다. Professional 등급에서 데이터 열이 비어 있는 것은 아직 그 자리에 해당하는 자격증이 없기 때문입니다.

| 등급 | 자격증 (시험 코드) |
| :--- | :--- |
| Business | AI Business Strategist (AIB-C01, 베타) |
| Foundational | Cloud Practitioner (CLF-C02)<br>AI Practitioner (AIF-C01) |
| Associate | Solutions Architect (SAA-C03)<br>Developer (DVA-C02)<br>CloudOps Engineer (SOA-C03)<br>Data Engineer (DEA-C01)<br>Machine Learning Engineer (MLA-C01, MLA-C02 베타 진행 중) |
| Professional | **Solutions Architect - Professional (SAP-C02)**<br>DevOps Engineer - Professional (DOP-C02)<br>Generative AI Developer - Professional (AIP-C01) |
| Specialty | Advanced Networking (ANS-C01, 2026-12-31 종료 예정)<br>Security (SCS-C03) |

Professional 등급은 셋이고 SAP가 그중 하나입니다. DevOps Engineer - Professional은 배포 파이프라인과 운영 자동화를 축으로 삼고, 2026년에 추가된 Generative AI Developer - Professional은 foundation model을 애플리케이션과 업무 흐름에 통합하는 일을 축으로 삼습니다. SAP는 아키텍처 설계 판단을 축으로 삼습니다.

Specialty가 둘뿐인 것도 최근 변화입니다. Machine Learning - Specialty가 2026년 3월 31일로 종료됐고 그 자리를 Machine Learning Engineer - Associate와 Generative AI Developer - Professional이 나눠 가졌습니다. Advanced Networking - Specialty도 2026년 12월 31일에 종료되므로, 네트워크 설계 역량을 증명하려면 SAP 쪽이 남는 선택지가 됩니다.

기본 정보는 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 시험 코드 | SAP-C02 |
| 등급 | Professional |
| 응시료 | 300 USD |
| 시험 시간 | 180분 |
| 문항 수 | 75문항 (채점 65 + 비채점 10) |
| 합격 점수 | 750 / 1000 |
| 유효 기간 | 3년 |
| 사전 요구 자격증 | 없음 |
| 권장 경험 | AWS 설계 및 구현 2년 이상 |
| 응시 언어 | 영어, 일본어, 한국어, 포르투갈어(브라질), 중국어 간체, 스페인어(중남미) |

**사전 요구 자격증이 없다는 점**은 자주 오해받습니다. SAA를 취득하지 않아도 SAP에 바로 응시할 수 있습니다. AWS가 명시하는 것은 요구사항이 아니라 권장 경험이고, 그 내용은 `2 or more years of experience in using AWS services to design and implement cloud solutions`입니다.

다만 시험이 Associate 수준의 서비스 지식을 이미 갖춘 상태를 전제하고 출발한다는 점은 별개의 문제입니다. SAP 문항은 EC2가 무엇인지, S3 스토리지 클래스가 몇 종인지를 묻지 않습니다. 그것들을 아는 상태에서, 온프레미스 Active Directory를 그대로 둬야 하고 RPO는 15분이고 예산은 늘릴 수 없다는 조건이 동시에 걸렸을 때 무엇을 고를지를 묻습니다. 서비스 정의를 몰라서 틀리는 시험이 아니라 서비스 사이의 제약이 충돌하는 지점을 몰라서 틀리는 시험입니다.

유효 기간 3년이 지나면 재인증이 필요합니다. 같은 시험을 다시 보는 것 말고 두 경로가 더 있습니다. 첫째, 지정된 상위 자격증에 합격하면 하위 자격증이 3년 연장됩니다. **SAP에 합격하면 Solutions Architect - Associate와 Cloud Practitioner가 함께 3년 연장됩니다.** 짝이 정해져 있어서 아무 상위 자격증이나 아무 하위 자격증을 갱신하지는 않습니다. 둘째, AWS Skill Builder의 maintenance 과정을 이수하면 1년이 연장됩니다. 연장 기산점은 만료일이 아니라 이수한 날입니다.

---

## 2. 시험 가이드가 검증하겠다고 적어둔 것

앞에서 인용한 Exam Guide 정의문에서 결정적인 단어는 두 개입니다. `optimized`와 `Well-Architected Framework`입니다.

Well-Architected Framework는 여섯 개 pillar로 구성됩니다. operational excellence, security, reliability, performance efficiency, cost optimization, sustainability입니다. `optimized`가 붙는 순간 문제는 "동작하는 설계"를 묻지 않고 "여섯 축의 트레이드오프를 어디에서 끊었는가"를 묻게 됩니다. SAP 문항의 선지 네 개가 전부 동작하는 이유가 이것입니다. 동작 여부는 이미 걸러진 상태에서, 지문이 지정한 축을 따라 우선순위를 매기는 것이 실제 과제입니다.

같은 문단이 이어서 네 가지 능력을 명시합니다.

| Exam Guide 문구 | 실제로 요구되는 판단 |
| :--- | :--- |
| Design for organizational complexity | 계정 경계, 권한 위임, 하이브리드 연결을 조직 단위로 설계한다 |
| Design for new solutions | 백지 상태에서 컴퓨트, 데이터, 통합, 배포 방식을 고른다 |
| Continuously improve existing solutions | 이미 돌아가는 환경을 감사하고 개선 지점을 우선순위화한다 |
| Accelerate workload migration and modernization | 온프레미스 포트폴리오를 평가하고 이전 경로와 타깃 아키텍처를 정한다 |

이 네 문장이 그대로 네 개 도메인이 됩니다. 도메인 구성은 임의 분류가 아니라 시험 정의문에서 파생된 구조입니다.

대상 후보자는 `2 or more years of experience in using AWS services to design and implement cloud solutions`이고, 여기에 `architectural design that extends across multiple applications and projects within a complex organization`에 대한 전문가 수준 조언 능력이 붙습니다. 단일 애플리케이션이 아니라 여러 애플리케이션과 프로젝트를 가로지르는 설계라는 점이 SAA와 갈리는 지점입니다.

범위 밖도 명시되어 있습니다. 모바일 앱 프론트엔드 개발, 12-factor app 방법론, 운영체제 심화 지식 세 가지입니다. 커널 파라미터 튜닝이나 컨테이너 런타임 내부 동작을 파고들 필요는 없다는 뜻입니다.

---

## 3. SAA와 SAP의 실질적 차이

두 시험의 공식 Exam Guide를 나란히 놓으면 차이가 수치로 드러납니다.

| 항목 | SAA-C03 | SAP-C02 |
| :--- | :--- | :--- |
| 대상 경험 | 1년 이상 | 2년 이상 |
| 채점 문항 | 50 | 65 |
| 비채점 문항 | 15 | 10 |
| 총 문항 | 65 | 75 |
| 시험 시간 | 130분 | 180분 |
| 문항당 평균 시간 | 2.0분 | 2.4분 |
| 합격 점수 | 720 | 750 |
| 응시료 | 150 USD | 300 USD |

문항당 시간이 0.4분 늘어난 것보다 중요한 것은 도메인 축이 통째로 다르다는 점입니다.

| | SAA-C03 도메인 | SAP-C02 도메인 |
| :--- | :--- | :--- |
| 1 | Design Secure Architectures (30%) | Design Solutions for Organizational Complexity (26%) |
| 2 | Design Resilient Architectures (26%) | Design for New Solutions (29%) |
| 3 | Design High-Performing Architectures (24%) | Continuous Improvement for Existing Solutions (25%) |
| 4 | Design Cost-Optimized Architectures (20%) | Accelerate Workload Migration and Modernization (20%) |

SAA는 설계의 **속성**으로 도메인을 나눕니다. 보안, 복원력, 성능, 비용입니다. 각 도메인 안에서 "이 요구사항에 맞는 서비스는 무엇인가"를 묻습니다. 답은 대체로 하나의 서비스이거나 두 서비스의 조합입니다.

SAP는 설계의 **수명주기**로 도메인을 나눕니다. 조직 위에 놓기, 새로 만들기, 있는 것 고치기, 옮기기입니다. 보안과 비용과 성능은 도메인이 아니라 네 단계 전부에 걸쳐 있는 판단 기준으로 흩어집니다. 그래서 SAP 문항 하나가 IAM과 Transit Gateway와 KMS와 Cost Explorer를 동시에 건드립니다.

실질적인 결과는 세 가지입니다.

- 단일 서비스 지식만으로는 선지를 좁힐 수 없다. 서비스 사이의 제약이 충돌하는 지점을 알아야 한다
- 계정이 여러 개라는 전제가 기본값이다. SCP가 무엇을 막고 permission boundary가 무엇을 막는지 구분하지 못하면 D1 문항이 통째로 흔들린다
- "이미 이렇게 돌고 있다"로 시작하는 지문이 25%를 차지한다. 백지 설계만 연습하면 D3에서 점수가 빠진다

---

## 4. 65문항이 채점되고, 10문항은 채점되지 않습니다

Exam Guide는 채점 구조를 이렇게 규정합니다. `The exam includes 65 questions that affect your score`이고, 별도로 `The exam includes 10 unscored questions that do not affect your score`입니다. 비채점 문항은 AWS가 향후 정식 출제 후보를 평가하려고 섞어둔 것이고, 결정적으로 `The unscored questions are not identified on the exam`입니다.

시험 중에 어느 문항이 채점 대상인지 알 수 없다는 뜻입니다. 유난히 낯설거나 이상하게 좁은 문항을 만나도 그것이 비채점 문항인지 판단할 방법이 없으므로, 전부 채점된다는 가정으로 푸는 것 외에 선택지가 없습니다. 다만 시험이 끝난 뒤 "그 문항은 도저히 모르겠더라"는 기억이 남았을 때, 그중 일부는 애초에 점수에 영향이 없었을 가능성이 있다는 정도로만 의미가 있습니다.

점수는 100에서 1000 사이의 scaled score로 보고되고 합격선은 750입니다. 여기서 흔한 오해가 하나 있습니다. 750은 백분율이 아닙니다. scaled scoring은 시험 form마다 난이도가 조금씩 다른 것을 보정하기 위한 환산 모델이고, AWS는 원점수와 scaled score 사이의 환산표를 공개하지 않습니다. 따라서 **65문항 중 몇 개를 맞혀야 750이 되는지는 역산할 수 없습니다.** "75%니까 49문항"이라는 계산은 근거가 없습니다.

채점 방식은 compensatory입니다. Exam Guide 문장 그대로 `you do not need to achieve a passing score in each section. You need to pass only the overall exam`입니다. 도메인별 과락이 없습니다.

이 구조가 학습 전략에 미치는 영향은 생각보다 큽니다.

- 특정 도메인이 약해도 다른 도메인에서 상쇄할 수 있다. D4(20%, 약 13문항)를 절반만 맞혀도 D2(29%, 약 19문항)에서 만회할 여지가 있다
- 대신 **버려도 되는 도메인은 없다.** 가장 작은 D4도 13문항이고, 이를 통째로 포기하면 나머지 52문항에서 사실상 만점에 가까운 성적이 필요해진다
- 점수 리포트의 도메인별 분류표는 강점과 약점을 알려주는 참고 정보다. Exam Guide 자체가 `Use caution when you interpret section-level feedback`이라고 경고한다. 도메인당 문항 수가 적어 통계적으로 흔들리기 때문이다

---

## 5. multiple response에는 부분점수가 없습니다

문항 유형은 두 가지입니다.

| 유형 | 구성 | 득점 조건 |
| :--- | :--- | :--- |
| multiple choice | 정답 1개, 오답(distractor) 3개 | 정답 하나를 고른다 |
| multiple response | 5개 이상의 선지 중 정답 2개 이상 | **정답을 전부 골라야 득점한다** |

Exam Guide 원문은 `You must select all the correct responses to receive credit for the question`입니다. 두 개를 골라야 하는 문항에서 하나만 맞히면 0점이고, 정답 두 개를 다 골랐더라도 오답 하나를 추가로 선택하면 역시 0점입니다.

이 규칙이 기대값을 크게 바꿉니다. 5지에서 정답 2개를 고르는 경우의 수는 10가지이므로 순수 추측의 성공률은 10%입니다. multiple choice의 25%와 비교하면 절반 이하입니다.

| 상황 | 성공 확률 |
| :--- | :--- |
| multiple choice, 완전 추측 | 25% |
| multiple choice, 오답 2개 소거 | 50% |
| multiple response(5지 2답), 완전 추측 | 10% |
| multiple response(5지 2답), 후보를 3개로 좁힘 | 33% |

여기서 나오는 전략적 함의는 명확합니다. multiple response에서는 정답을 찾으려 애쓰는 것보다 **명백히 틀린 선지를 지우는 쪽이 확률을 훨씬 빠르게 끌어올립니다.** 5지를 3지로 줄이면 성공률이 10%에서 33%로 세 배 이상 오릅니다. 서비스의 하드 리밋이나 지역 제약, 지원하지 않는 조합을 근거로 소거할 수 있는 선지가 SAP 문항에는 대개 하나 이상 들어 있습니다. 그래서 이 시리즈의 각 편에서 제약 수치와 성립하지 않는 조합을 별도로 정리합니다.

---

## 6. 미응답은 오답으로 처리됩니다

Exam Guide는 `Unanswered questions are scored as incorrect. There is no penalty for guessing`이라고 명시합니다.

두 문장을 합치면 결론은 하나입니다. 빈칸으로 두면 확률 0%이고, 아무거나 찍으면 multiple choice 기준 25%입니다. 시간이 부족해 마지막 몇 문항을 못 풀게 되는 상황이 실제로 자주 발생하므로, 남은 시간이 5분 아래로 떨어지면 읽지 않은 문항이라도 전부 채우는 것이 항상 유리합니다.

시험 UI의 flag 기능을 함께 쓰는 것이 안전합니다. 확신이 서지 않는 문항에서 시간을 쓰지 말고, 일단 가장 그럴듯한 선지를 선택한 상태로 flag를 걸고 넘어갑니다. 이렇게 하면 시간이 남지 않아 돌아오지 못하더라도 그 문항은 이미 25%의 확률을 확보한 상태입니다. 선택을 비워둔 채 flag만 걸어두면 돌아오지 못했을 때 확정적으로 0점입니다.

---

## 7. 4개 도메인과 20개 task statement

도메인 가중치와 65문항 기준 환산은 다음과 같습니다. 문항 수는 가중치에서 계산한 값이고 실제 시험지의 문항 수가 정확히 이 값이라는 보장은 없습니다.

| 도메인 | 비중 | 65문항 환산 | task statement 수 |
| :--- | :--- | :--- | :--- |
| D1. Design Solutions for Organizational Complexity | 26% | 약 17문항 | 5 |
| D2. Design for New Solutions | 29% | 약 19문항 | 6 |
| D3. Continuous Improvement for Existing Solutions | 25% | 약 16문항 | 5 |
| D4. Accelerate Workload Migration and Modernization | 20% | 약 13문항 | 4 |

각 task statement 아래에는 `Knowledge of`와 `Skills in` 두 블록이 붙어 있습니다. 출제 범위를 좁힐 때 실제로 유용한 것은 `Skills in` 쪽입니다. 여기 적힌 동사가 문항이 요구하는 행위를 그대로 지정하기 때문입니다.

### 7.1. 조직 복잡성 설계 (26%)

| Task | Skills 블록이 지정하는 행위 |
| :--- | :--- |
| 1.1 Architect network connectivity strategies | 여러 VPC와 온프레미스 연결 옵션을 평가하고, 지연 요구에 맞춰 리전과 AZ를 고르고, AWS 도구로 트래픽 흐름을 추적한다 |
| 1.2 Prescribe security controls | 교차 계정 접근을 평가하고, 서드파티 IdP와 연동하고, 저장과 전송 암호화 전략을 배치하고, 보안 이벤트 알림과 감사를 중앙화한다 |
| 1.3 Design reliable and resilient architectures | RTO와 RPO에서 DR 설계를 도출하고, 자동 복구 구조를 구현하고, 백업과 복원 전략을 세운다 |
| 1.4 Design a multi-account AWS environment | 조직 요구에 맞는 계정 구조를 평가하고, 중앙 로깅과 이벤트 알림 전략을 권고하고, 거버넌스 모델을 만든다 |
| 1.5 Determine cost optimization and visibility strategies | 비용과 사용량을 도구로 모니터링하고, 비용을 사업 단위에 매핑하는 태깅 전략을 만들고, 구매 옵션이 비용과 성능에 미치는 영향을 이해한다 |

`Prescribe`, `Architect`, `Design`이라는 동사가 붙어 있습니다. 조직 전체에 적용되는 규칙을 처방하는 자리입니다.

### 7.2. 신규 솔루션 설계 (29%)

| Task | Skills 블록이 지정하는 행위 |
| :--- | :--- |
| 2.1 Design a deployment strategy | 배포 전략과 롤백 메커니즘을 위한 서비스를 고르고, 프로비저닝과 패치 부담을 줄이도록 managed service를 채택한다 |
| 2.2 Design a solution to ensure business continuity | DR 솔루션과 데이터 복제를 구성하고, DR 테스트를 수행하고, 다중 AZ 또는 다중 리전 백업을 자동화한다 |
| 2.3 Determine security controls based on requirements | 최소 권한 IAM을 지정하고, security group과 network ACL로 인바운드와 아웃바운드 흐름을 지정하고, 대규모 웹 애플리케이션의 공격 완화 전략을 만든다 |
| 2.4 Design a strategy to meet reliability requirements | 느슨한 결합을 구현하고, 애플리케이션과 데이터베이스 failover를 운영하고, DNS 라우팅 정책을 구현한다 |
| 2.5 Design a solution to meet performance objectives | 다양한 액세스 패턴에 맞는 대규모 아키텍처를 설계하고, 캐싱과 버퍼링과 복제로 성능 목표를 맞추고, purpose-built 서비스 선택 절차를 만든다 |
| 2.6 Determine a cost optimization strategy | 비용 효율적인 리소스로 rightsizing하고, 적절한 가격 모델을 식별하고, 데이터 전송을 모델링해 전송 비용을 줄인다 |

`Specifying`, `Developing`, `Designing`이 반복됩니다. 아직 존재하지 않는 것을 규정하는 자리입니다.

### 7.3. 기존 솔루션 지속 개선 (25%)

| Task | Skills 블록이 지정하는 행위 |
| :--- | :--- |
| 3.1 Improve overall operational excellence | 현재 배포 프로세스에서 개선 기회를 평가하고, 스택 안의 자동화 기회에 우선순위를 매기고, 장애 시나리오 훈련을 설계한다 |
| 3.2 Determine a strategy to improve security | 시크릿 관리 전략을 평가하고, 최소 권한을 감사하고, 사용자와 서비스의 추적 가능성을 검토하고, 취약점 탐지에 대한 자동 대응에 우선순위를 매기고, 교정 기법을 적용한다 |
| 3.3 Determine a strategy to improve performance | 비즈니스 요구를 측정 가능한 지표로 번역하고, 교정안을 테스트하고, 요구에 맞춰 rightsizing하고, 성능 병목을 식별한다 |
| 3.4 Determine a strategy to improve reliability | 애플리케이션 성장 추세를 이해하고, 기존 아키텍처에서 충분히 신뢰할 수 없는 영역을 판별하고, 단일 장애점을 제거한다 |
| 3.5 Identify opportunities for cost optimizations | 사용 리포트를 분석해 저사용과 과사용 리소스를 찾고, 미사용 리소스를 식별하고, 예상 사용 패턴 기반 billing alarm을 설계하고, Cost and Usage Report를 세밀하게 조사한다 |

`Evaluating`, `Auditing`, `Reviewing`, `Prioritizing`, `Employing remediation`이 핵심 동사입니다. 이미 존재하는 것을 감사하고 고치는 자리입니다. D2와 D3에 같은 서비스가 등장해도 묻는 각도가 다른 이유가 이 동사 차이입니다.

### 7.4. 마이그레이션과 모더나이제이션 가속 (20%)

| Task | Skills 블록이 지정하는 행위 |
| :--- | :--- |
| 4.1 Select workloads for potential migration | 마이그레이션 평가를 완료하고, 7R 기준으로 애플리케이션을 분류하고, TCO를 평가한다 |
| 4.2 Determine the optimal migration approach | 데이터베이스와 애플리케이션과 데이터의 전송 수단을 각각 고르고, 마이그레이션 도구에 적절한 보안 방식을 적용하고, 거버넌스 모델을 고른다 |
| 4.3 Determine a new architecture for existing workloads | 컴퓨트 플랫폼, 컨테이너 호스팅 플랫폼, 스토리지 서비스, 데이터베이스 플랫폼을 각각 고른다 |
| 4.4 Determine opportunities for modernization | 컴포넌트 디커플링 기회를 찾고, 서버리스 기회를 찾고, purpose-built 데이터베이스 기회를 찾고, 통합 서비스를 고른다 |

D4는 `Selecting`이 지배적입니다. 선택 기준을 명시적으로 갖고 있어야 답을 좁힐 수 있고, 기준 없이 서비스 목록만 외우면 선지 네 개가 전부 그럴듯해 보입니다.

---

## 8. 180분에 75문항, 페이싱을 따로 훈련해야 합니다

시험 시간은 180분이고 문항은 75개입니다. 나누면 문항당 144초, 2.4분입니다. 이 숫자가 SAP에서 특히 빡빡하게 느껴지는 이유는 지문 길이 때문입니다. SAP 문항은 요구사항, 현재 구성, 제약 조건이 각각 문단으로 붙고 선지도 길어서, 읽는 데만 1분 가까이 쓰는 문항이 흔합니다.

현실적인 배분은 이렇게 잡습니다.

| 구간 | 목표 |
| :--- | :--- |
| 문항 1-25 | 55분 이내에 통과한다. 초반에 시간을 쓰면 뒤에서 회복할 수 없다 |
| 문항 26-50 | 누적 110분 지점을 넘기지 않는다 |
| 문항 51-75 | 남은 70분으로 처리한다. 어려운 문항이 뒤에 몰려 있어도 견딜 수 있는 여유다 |
| 마지막 10분 | flag 문항 재검토와 미응답 채우기에만 쓴다 |

지문을 읽는 순서도 시간에 영향을 줍니다. 요구사항 문단부터 위에서 아래로 읽으면 마지막 문장에서야 무엇을 묻는지 알게 되고, 그 시점에 앞 내용을 다시 읽게 됩니다. 마지막 질문 문장과 최상급 한정어(`MOST cost-effective`, `LEAST operational overhead`, `MOST resilient`)를 먼저 확인하고 나서 지문으로 돌아가면 읽는 동안 필요한 정보만 추릴 수 있습니다. 같은 시나리오라도 `MOST cost-effective`와 `LEAST operational overhead`는 정답이 갈립니다. 전자는 Spot과 self-managed 쪽으로, 후자는 managed service 쪽으로 기울기 때문입니다.

한 가지 더 있습니다. AWS는 영어가 모국어가 아닌 응시자가 **영어로** 시험을 볼 때 30분을 추가로 주는 `ESL +30 MINUTES` 편의를 제공합니다. 이 편의를 받으면 210분이 되어 문항당 2.8분으로 늘어납니다. 신청은 시험 등록 전에 계정에서 한 번만 하면 이후 모든 응시에 자동 적용됩니다. 한국어로 응시하면 해당되지 않으므로, 한국어 번역 품질에 대한 부담과 30분의 추가 시간 중 어느 쪽을 택할지는 응시 전에 결정해야 합니다.

---

## 9. SAP-C02로 응시할 수 있는 기간

이 시험은 개정을 앞두고 있습니다. AWS Training and Certification 공지 기준으로 일정은 다음과 같습니다.

| 날짜 | 내용 |
| :--- | :--- |
| 2026-10-27 | SAP-C03 등록 시작 |
| 2026-11-16 또는 2026-11-17 | SAP-C02 응시 마지막 날 (아래 참고) |
| 2026-11-17 | SAP-C03 정식 응시 시작 |

마지막 날짜는 AWS 공식 페이지 두 곳이 다르게 적고 있습니다. Training and Certification 블로그의 2026년 9월 공지는 11월 16일로, 자격증 제품 페이지는 11월 17일로 안내합니다. 응시일을 11월 중순까지 미룰 계획이라면 예약 화면에서 직접 확인하시기 바랍니다.

이 글을 쓰는 2026년 9월 6일 기준으로 SAP-C02 응시 가능 기간은 71일 남았습니다. 7주 학습 계획을 오늘 시작하면 10월 하순에 응시할 수 있고, 한 번 떨어져도 재응시 여유가 남습니다. AWS 재응시 정책상 불합격 후 14일을 기다려야 하므로, 여유를 계산에 넣으려면 10월 안에 첫 응시를 잡는 편이 안전합니다.

SAP-C03에서는 AWS가 공지한 대로 생성형 AI 통합과 agentic 아키텍처, Fault Injection Service와 Resilience Hub와 Application Recovery Controller 중심의 복원력 엔지니어링, DevSecOps와 관측성, lakehouse 아키텍처, post-quantum 암호가 범위에 추가됩니다. 지금 준비 중인 내용이 통째로 무의미해지는 것은 아니지만 추가 학습이 필요하고, C03 Exam Guide가 공개되기 전까지는 정확한 도메인 구성과 가중치를 확인할 수 없습니다. C02로 끝낼 수 있으면 끝내는 편이 계획을 단순하게 만듭니다.

---

## 10. 합격선을 넘기 위한 우선순위

시험 구조에서 직접 도출되는 학습 우선순위가 있습니다.

**문항 수가 곧 투자 우선순위입니다.** D2가 약 19문항으로 가장 크고 D4가 약 13문항으로 가장 작습니다. 그런데 D4는 서비스 목록이 짧고 판단 기준이 명시적이어서 투입 시간 대비 회수가 좋은 편입니다. 7R 분류 기준, 전송량과 기간으로 전송 수단을 고르는 계산, 컴퓨트와 데이터베이스 타깃 결정 트리 정도면 상당 부분이 커버됩니다. 반대로 D1은 문항 수는 17개인데 IAM 정책 평가 로직과 하이브리드 네트워크 토폴로지가 걸려 있어 가장 많은 시간을 요구합니다.

**공통 지식 집합을 먼저 세우면 여러 도메인이 같이 올라갑니다.** RTO와 RPO에서 출발하는 DR 판단은 Task 1.3과 2.2와 3.4에 동시에 걸려 있습니다. 세 task를 합치면 문항 수가 적지 않은데, 한 번 정리하면 셋을 함께 커버합니다. 비용 도구도 마찬가지로 Task 1.5와 2.6과 3.5에 걸쳐 있습니다.

**약점을 방치해도 되는 범위가 있습니다.** compensatory 채점이므로 특정 task에서 점수가 빠져도 총점으로 넘길 수 있습니다. 다만 도메인 하나를 통째로 비우는 것은 다릅니다. 가장 작은 D4를 전부 놓치면 나머지 52문항에서 거의 완벽해야 하는데, 지문이 긴 시험에서 그 정도 정확도를 유지하는 것은 현실적이지 않습니다.

**모의고사는 지식 점검이 아니라 페이싱 점검입니다.** 문항당 2.4분을 지키는 감각은 문제를 푼다고 생기지 않고, 시간을 재고 75문항을 연속으로 푸는 훈련에서 생깁니다. AWS Skill Builder의 공식 practice question set과 official practice exam은 실제 시험의 문항 스타일과 길이에 가장 가까운 기준점이므로, 서드파티 문제집보다 먼저 한 번 풀어 난이도 감각을 보정하는 편이 좋습니다.

---

## 11. 시리즈 15편이 다루는 범위

Overview 뒤로 15편이 이어지고, 20개 task statement 전부에 담당 편을 배정했습니다. 주제마다 설명을 소유하는 편을 하나로 고정해서 같은 서비스를 여러 편에서 반복 설명하지 않습니다.

| 편 | 주제 | 주 도메인 | 다루는 범위 |
| :--- | :--- | :--- | :--- |
| 1 | [멀티 계정 거버넌스](/posts/aws-sap-c02-multi-account-governance/) | D1 | Organizations, SCP와 RCP, Control Tower, IAM Identity Center, RAM, StackSets, 조직 단위 비용 배분 |
| 2 | [IAM 심화와 페더레이션](/posts/aws-sap-c02-iam-federation/) | D1 | 정책 평가 로직, permission boundary, STS, SAML과 OIDC, Directory Service, Access Analyzer |
| 3 | [하이브리드 네트워크](/posts/aws-sap-c02-hybrid-networking/) | D1 | VPC 설계, Transit Gateway, Direct Connect, VPN, PrivateLink, 전이 라우팅, 흐름 진단 도구 |
| 4 | [DNS와 글로벌 트래픽](/posts/aws-sap-c02-dns-global-traffic/) | D1 | Route 53 라우팅 정책, Resolver 하이브리드 DNS, Global Accelerator, CloudFront |
| 5 | [컴퓨트 선택과 확장](/posts/aws-sap-c02-compute-scaling/) | D2 | 인스턴스 패밀리, 구매 옵션 6종, Placement Group, ASG 정책, Spot |
| 6 | [컨테이너와 서버리스](/posts/aws-sap-c02-container-serverless/) | D2 | ECS, EKS, Fargate, ECR, Lambda 제약, ELB, API Gateway, 배포와 롤백 단위 |
| 7 | [데이터 계층 선택](/posts/aws-sap-c02-data-layer-selection/) | D2 | RDS와 Aurora, DynamoDB, ElastiCache, S3 클래스, EBS와 EFS와 FSx, OpenSearch |
| 8 | [디커플링과 데이터 파이프라인](/posts/aws-sap-c02-decoupling-data-pipeline/) | D2 | SQS, SNS, EventBridge, Kinesis, Step Functions, Glue, Athena, Redshift |
| 9 | [보안 심화](/posts/aws-sap-c02-security-deep-dive/) | D3 | KMS와 CloudHSM, Secrets Manager, ACM, WAF와 Shield, GuardDuty와 Security Hub, 자동 교정 |
| 10 | [가용성과 재해복구](/posts/aws-sap-c02-availability-dr/) | D3 | RTO와 RPO, DR 전략 4종, AWS Backup, 복제 수단별 RPO, ARC, 장애 주입 |
| 11 | [관측성과 운영 자동화](/posts/aws-sap-c02-observability-operations/) | D3 | CloudWatch, CloudTrail, X-Ray, Config, Systems Manager, IaC와 배포 전략 |
| 12 | [비용 최적화](/posts/aws-sap-c02-cost-optimization/) | D3 | 태그와 Cost Categories, Cost Explorer와 CUR, Budgets, Savings Plans 커버리지, 데이터 전송 과금 |
| 13 | [마이그레이션 전략](/posts/aws-sap-c02-migration-strategy/) | D4 | 7R, 포트폴리오 평가, MGN, DMS와 SCT, 컷오버 실행 경로 |
| 14 | [데이터 전송과 하이브리드 엣지](/posts/aws-sap-c02-data-transfer-hybrid-edge/) | D4 | DataSync, Transfer Family, Storage Gateway, Outposts, Wavelength, Local Zones |
| 15 | [모더나이제이션 패턴](/posts/aws-sap-c02-modernization-patterns/) | D4 | 컴퓨트와 컨테이너와 데이터베이스 타깃 결정, strangler fig, 디커플링 판단 |

각 편은 개념 설명에서 끝나지 않고 세 가지를 추가로 담습니다. 시험에서 답을 가르는 하드 리밋과 동작 제약, 헷갈리는 서비스 짝의 비교표, 그리고 그럴듯하지만 서비스 제약 때문에 성립하지 않는 조합입니다. 마지막에 오리지널 시나리오 10문항과 해설을 붙여서, 정답 근거와 오답 세 개가 각각 어떤 제약 때문에 틀렸는지까지 확인할 수 있게 합니다.

---

## 12. 7주 학습 로드맵

2026년 9월 7일부터 10월 25일까지 7주입니다. 도메인 가중치에 맞춰 D1과 D2에 4주, D3와 D4에 2주, 마지막 1주를 복습과 페이싱 훈련에 배정했습니다.

| 주차 | 기간 | 학습 범위 | 해당 편 |
| :--- | :--- | :--- | :--- |
| 1 | 09-07 - 09-13 | 멀티 계정 거버넌스, IAM과 페더레이션 | 1, 2 |
| 2 | 09-14 - 09-20 | 하이브리드 네트워크, DNS와 글로벌 트래픽 | 3, 4 |
| 3 | 09-21 - 09-27 | 컴퓨트 선택과 확장, 컨테이너와 서버리스 | 5, 6 |
| 4 | 09-28 - 10-04 | 데이터 계층 선택, 디커플링과 데이터 파이프라인 | 7, 8 |
| 5 | 10-05 - 10-11 | 보안 심화, 가용성과 재해복구, 관측성과 운영 자동화 | 9, 10, 11 |
| 6 | 10-12 - 10-18 | 비용 최적화, 마이그레이션 3편 | 12, 13, 14, 15 |
| 7 | 10-19 - 10-25 | 모의고사 2회, 오답 정리, 페이싱 훈련 | 신규 학습 없음 |

주차별로 지켜야 할 기준이 두 가지 있습니다.

- 한 주가 끝날 때 그 주에 다룬 편의 예상 문제를 시간을 재고 푼다. 정답률보다 문항당 소요 시간을 먼저 본다
- 6주차가 끝나면 전 범위 모의고사를 한 번 돌린다. 7주차에 약점을 보강할 시간을 남기려면 여기서 약점이 드러나야 한다

7주차 이후에도 시간이 남습니다. 10월 25일 시점에 SAP-C02 응시 가능 기간이 22일 남으므로, 첫 응시에서 불합격하더라도 14일 대기 후 재응시할 여유가 있습니다.

---

## 13. Reference

- [AWS Certification - AWS Certified Solutions Architect Professional](https://aws.amazon.com/certification/certified-solutions-architect-professional/)
- [AWS Certification - Exam Guide SAP-C02](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-professional-02/solutions-architect-professional-02.html)
- [AWS Certification - Exam Guide SAA-C03](https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/solutions-architect-associate-03.html)
- [AWS Certification - AWS Certified Solutions Architect Associate](https://aws.amazon.com/certification/certified-solutions-architect-associate/)
- [AWS Certification - Exam Guides Index](https://docs.aws.amazon.com/aws-certification/latest/examguides/aws-certification-exam-guides.html)
- [AWS Certification - Recertification](https://aws.amazon.com/certification/recertification/)
- [AWS Training and Certification Blog - AWS Expands AI Certification Portfolio](https://aws.amazon.com/blogs/training-and-certification/big-news-aws-expands-ai-certification-portfolio-and-updates-security-certification/)
- [AWS Well-Architected Framework - The Pillars of the Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html)
- [AWS Training and Certification Blog - Certification Updates September 2026](https://aws.amazon.com/blogs/training-and-certification/september-2026-new-offerings/)
- [AWS Certification - Coming Soon](https://aws.amazon.com/certification/coming-soon/)
- [AWS Certification Policies - Before Testing](https://aws.amazon.com/certification/policies/before-testing/)
- [AWS Certification Policies - After Testing](https://aws.amazon.com/certification/policies/after-testing/)
- [AWS Skill Builder - Exam Prep](https://skillbuilder.aws/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
