---
title: "SAP-C02 박살내기 11 - 관측성과 운영 자동화"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, cloudwatch, cloudtrail, x-ray, systems-manager, cloudformation, codedeploy, observability]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-09-02 10:00:00 +0900
---

야간 배치를 돌리는 인스턴스가 멎었는데 붙여 둔 EC2 recover action이 실행되지 않은 적이 있습니다. 알람 이력을 열어 보면 알람은 ALARM으로 가지 않았고 INSUFFICIENT_DATA에 머물러 있습니다. 임계값도 evaluation periods도 그대로였고, 바뀐 것은 인스턴스가 멎으면서 메트릭 자체가 끊겼다는 사실뿐입니다.

여기서 답을 가르는 것은 임계값이 아니라 결측 데이터 처리 설정입니다. 기본값은 `missing`이고, evaluation range의 데이터포인트가 전부 없으면 알람은 INSUFFICIENT_DATA로 갑니다. `breaching`으로 두었다면 같은 상황에서 ALARM으로 갔을 것이고, `notBreaching`으로 두었다면 OK에 머물렀을 것입니다. 세 값 모두 임계값과 무관하게 결과를 바꿉니다.

SAP-C02 Domain 3은 이 층에서 문항을 냅니다. 지문은 서비스 이름을 묻지 않고, 이미 돌아가는 환경에서 신호가 왜 안 잡히는지, 잡힌 신호를 어디까지 사람 손 없이 교정으로 이을 수 있는지, 그 교정과 배포가 실패했을 때 되돌리는 경로가 무엇인지를 묻습니다. CloudWatch와 Config와 Systems Manager와 CodeDeploy는 각자 할 수 있는 일과 구조적으로 못 하는 일이 따로 있고, 선지는 대개 그 못 하는 쪽에 놓입니다.

> **TL;DR**  
> - 알람의 결측 처리 기본값은 `missing`이다. 데이터가 전부 없으면 INSUFFICIENT_DATA로 간다.  
> - 결측 처리 설정은 실제 데이터포인트가 evaluation periods보다 적을 때만 개입한다. 충분하면 아예 쓰이지 않는다.  
> - composite alarm은 SNS와 OpsItem은 만들지만 EC2 action과 Auto Scaling action을 실행하지 못한다.  
> - 로그 그룹당 subscription filter는 5개이고 조정할 수 없다. 그 이상 팬아웃하려면 스트림 하나로 모은다.  
> - S3 export는 데이터가 export 가능해지기까지 최대 12시간이 걸리고 계정당 동시 task가 1개다. 실시간 조건이면 탈락한다.  
> - cross-account observability는 Region 내부에서만 동작하고 sink는 계정당 리전당 1개다.  
> - Application Signals는 서비스와 SLO 중심이고 Transaction Search는 `aws/spans`의 span 속성을 검색한다. RUM은 실제 사용자 세션, Container Insights는 컨테이너 성능 로그를 본다.  
> - CloudTrail Event history는 90일이고 management event만 담는다. data event 조사는 trail이나 Lake가 필요하다.  
> - Config proactive rule은 평가만 한다. 차단도 교정도 하지 않는다. aggregator는 read-only다.  
> - X-Ray sampling은 parent-based다. 하위 서비스에만 rule을 걸면 적용되지 않는다.  
> - Patch Manager의 준수 기준은 사용자가 정의한 patch baseline이고, OS 메이저 버전 업그레이드는 지원하지 않는다.  
> - `DeletionPolicy`는 리소스 교체 경로에 적용되지 않는다. 그 자리를 `UpdateReplacePolicy`가 맡는다.  
> - NLB 뒤의 ECS blue/green은 `ECSAllAtOnce`만 지원한다. canary와 linear가 없다.  
> - Incident Manager는 response plan으로 응답자와 Automation runbook을 시작한다. Change Manager는 2025-11-07부터 신규 고객에게 열리지 않는다.  
{: .prompt-info}

---

## 1. 메트릭의 해상도와 보존 기간이 조회 가능한 질문을 정한다

CloudWatch 메트릭은 발행 시점에 해상도가 정해지고, 그 해상도가 나중에 물을 수 있는 질문의 범위를 제한합니다. 표준 해상도는 1분 granularity이고 고해상도는 1초 granularity입니다. AWS 서비스가 스스로 발행하는 메트릭은 기본이 표준 해상도이고, 고해상도는 커스텀 메트릭에서 선택합니다.

보존 기간은 period마다 다르고, 짧은 period 데이터는 기간이 지나면 더 긴 period로 집계돼 남습니다.

| period | 보존 기간 |
| :--- | :--- |
| 60초 미만(고해상도) | 3시간 |
| 60초 | 15일 |
| 300초 | 63일 |
| 3,600초 | 455일(15개월) |

이 표가 문항이 되는 방식은 이렇습니다. "6개월 전의 1분 단위 메트릭으로 용량 추이를 분석한다"는 요구는 성립하지 않습니다. 15일이 지난 시점에 1분 데이터는 이미 없고 남아 있는 것은 5분과 1시간으로 집계된 값입니다. 장기 분석이 요구되면 메트릭을 별도 저장소로 내보내는 설계가 답이 되고, 그 수단이 뒤에서 볼 metric stream입니다.

메트릭 자체의 성격도 몇 가지 확인해 둘 값이 있습니다.

- 메트릭은 삭제할 수 없다. 신규 데이터가 15개월간 없으면 자동으로 만료한다.
- 메트릭은 생성된 Region 안에만 존재한다. 리전을 가로지르는 조회는 별도 설계가 필요하다.
- 메트릭당 dimension은 최대 30개다.
- 커스텀 메트릭은 dimension을 가로질러 자동 집계되지 않는다. 발행하지 않은 dimension 조합으로는 통계를 조회할 수 없다.

마지막 항목이 실무와 시험에서 함께 걸리는 지점입니다. `Service`와 `AvailabilityZone` 두 dimension을 붙여 발행했다면 `Service`만으로 묶은 값은 존재하지 않습니다. 그 값이 필요하면 `Service`만 붙인 데이터포인트를 별도로 발행해야 합니다.

`PutMetricData`의 타임스탬프에도 창이 있습니다. 과거 2주, 미래 2시간까지 허용합니다. 다만 허용된다는 것과 알람이 동작한다는 것은 다릅니다. 알람은 현재 UTC 기준으로 평가하므로 하루 전 타임스탬프를 지금 올리면 알람은 INSUFFICIENT_DATA로 가거나 평가가 지연됩니다. "야간 배치가 집계한 값을 아침에 올려 알람을 건다"는 구성이 실패하는 이유입니다.

percentile 통계에도 조건이 있습니다. 메트릭 값에 음수가 하나라도 있으면 percentile을 쓸 수 없습니다. statistic set으로 발행한 데이터는 SampleCount가 1이거나, Min과 Max가 같고 Sum이 Min에 SampleCount를 곱한 값인 경우에만 percentile을 얻습니다. 지연 시간 p99를 SLI로 쓰겠다는 설계에서 값을 statistic set으로 압축해 올리면 원하는 통계가 나오지 않습니다.

---

## 2. 알람이 상태를 정하는 순서와 결측 처리가 개입하는 지점

알람은 threshold를 넘었는지만 보는 장치가 아니라, 데이터포인트를 모으고 개수를 세고 부족분을 채워 넣는 절차입니다. 도입부의 상황이 이 절차의 마지막 단계에서 갈렸습니다.

{% include diagrams/static/sap-c02/cloudwatch-alarm-missing-data.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/cloudwatch-alarm-missing-data--a27a61fb5a3388c3.png" %}

그림은 메트릭 데이터포인트에서 출발해 evaluation range 수집, 데이터포인트 개수 판정, 상태 결정, action 실행까지를 한 줄기로 놓은 배치입니다. 가운데의 개수 판정 상자에서 경로가 둘로 갈리고, 한쪽은 M out of N 판정으로, 다른 한쪽은 결측 처리 설정으로 이어집니다. 오른쪽의 세 상자가 알람이 도달할 수 있는 상태이고, 그중 ALARM에서만 action 상자로 선이 이어집니다. 상자 안의 부제도 함께 읽을 값입니다. 결측 처리 상자에는 기본값과 예외 네임스페이스가, M out of N 상자에는 premature alarm 회피 로직이, action 상자에는 Auto Scaling action의 반복 실행 예외가 적혀 있습니다.

순서를 문장으로 옮기면 이렇습니다.

1. **evaluation range 수집.** 알람은 evaluation periods보다 넓은 범위에서 데이터포인트를 가져온다.
2. **개수 판정.** 실제 데이터포인트 수가 evaluation periods 이상이면 결측 처리 설정은 아예 쓰이지 않고 무시된다.
3. **부족분 채우기.** 데이터가 모자랄 때만 결측 처리 설정이 개입한다.
4. **M out of N 판정.** datapoints to alarm 개수만큼 breaching이면 ALARM으로 간다.
5. **action 실행.** 상태가 바뀔 때만 실행한다.

2번이 자주 오해되는 지점입니다. 결측 처리를 `breaching`으로 두었다고 해서 데이터가 정상으로 들어오는 동안 알람이 더 민감해지지는 않습니다. 그 설정은 데이터가 실제로 모자랄 때만 쓰입니다.

결측 처리 값은 네 가지입니다.

| 값 | 동작 |
| :--- | :--- |
| `missing` | 기본값. evaluation range의 데이터가 전부 없으면 INSUFFICIENT_DATA로 간다 |
| `notBreaching` | 결측을 임계 이내로 취급한다. 데이터가 없어도 OK에 머문다 |
| `breaching` | 결측을 임계 초과로 취급한다. 데이터가 끊기면 ALARM으로 간다 |
| `ignore` | 직전 상태를 그대로 유지한다 |

기본값이 `missing`인 데 예외가 하나 있습니다. `AWS/DynamoDB` 네임스페이스 메트릭의 알람만 기본이 `ignore`입니다. 그리고 EC2 stop, terminate, reboot, recover action을 붙인 알람에 대해서는 결측을 `missing`으로 두라고 문서가 권고합니다. 인스턴스가 이미 멈춰 메트릭이 끊긴 상황에서 복구 action이 반복 실행되는 것을 막기 위해서입니다.

M out of N 알람에도 예외 로직이 붙습니다. datapoints to alarm을 5개 중 3개로 두었다면 breaching이 3개 미만일 때는 ALARM으로 가지 않는다고 생각하기 쉽지만, premature alarm 회피 로직이 그 판단을 뒤집습니다. **evaluation range 안에서 가장 오래된 breaching 데이터포인트가 datapoints to alarm 값만큼 오래됐고 그 이후가 전부 breaching이나 missing이면, 실제 breaching 개수가 M에 못 미쳐도 ALARM으로 갑니다.**

action 실행 규칙도 시험 재료입니다.

- 알람은 **상태가 바뀔 때만** action을 실행한다.
- 예외는 Auto Scaling action이다. 새 상태를 유지하는 동안 분당 1회 계속 실행한다.
- 알람 이력은 30일 보존한다.
- 알람 evaluation period 상한은 period가 3,600초 이상이면 7일, 그보다 짧으면 1일이다(period와 evaluation periods의 곱 기준).
- 계정당 알람 개수 제한은 없다.

이 예외가 실제 설계를 가릅니다. Lambda를 알람 action으로 붙여 스케일링을 흉내 내면, 부하가 지속되는 동안 추가 확장이 일어나지 않습니다. 상태 전이가 한 번 일어난 뒤에는 다시 실행되지 않기 때문입니다. 반복 실행이 필요한 자리는 Auto Scaling policy입니다.

**composite alarm의 제약**이 여기에 이어집니다. composite alarm은 여러 알람의 논리 조합으로 상태를 정하고 알람 폭풍을 줄이는 장치이지만, 실행할 수 있는 action이 제한됩니다.

| composite alarm이 할 수 있는 것 | 할 수 없는 것 |
| :--- | :--- |
| SNS 알림 | EC2 action |
| investigation 생성 | Auto Scaling action |
| OpsItem 생성 | cross-account composite alarm |
| incident 생성 | |

"세 메트릭이 동시에 임계를 넘을 때만 확장한다"는 요구를 composite alarm으로 구현하려 하면 여기서 막힙니다. AND 조건을 유지하면서 Auto Scaling을 트리거하는 표준 해법은 metric math로 세 메트릭을 하나의 식으로 결합한 뒤 그 위에 metric alarm을 세우는 것입니다.

cross-account 알람에도 지원되지 않는 함수가 있습니다. `ANOMALY_DETECTION_BAND`, `INSIGHT_RULE`, `SERVICE_QUOTA` 세 metric math 함수는 cross-account 알람에서 쓸 수 없습니다.

**anomaly detection**은 임계값을 사람이 정하기 어려운 메트릭에 쓰는 대안입니다.

- 모델은 **최대 2주** 과거 데이터로 학습한다.
- 시간별, 일별, 주별 계절성과 추세를 반영한다.
- 모델은 메트릭과 statistic 조합마다 별도로 만들어진다.
- 배포 구간처럼 학습에서 빼고 싶은 기간을 지정할 수 있다.

배포 직후의 비정상 구간을 제외 기간으로 지정하는 기능이 실무와 문항 모두에서 등장합니다. 이상 구간을 학습에 넣으면 그 패턴이 정상 범위로 들어가 이후 같은 사고를 감지하지 못하기 때문입니다.

---

## 3. 커스텀 메트릭을 만드는 세 경로는 권한과 원본 접근성에서 갈린다

애플리케이션 지표를 CloudWatch 메트릭으로 만드는 경로는 세 가지이고, 선택 기준은 기능이 아니라 필요한 권한과 원본 로그에 다시 접근할 수 있는지 여부입니다.

| 경로 | 필요 권한 | 원본 로그 | 특징 |
| :--- | :--- | :--- | :--- |
| `PutMetricData` | `cloudwatch:PutMetricData` | 없다 | 메트릭만 만든다. API 호출을 코드에 넣어야 한다 |
| EMF(embedded metric format) | `logs:PutLogEvents` | 남는다 | 로그 이벤트 안에 메트릭을 embed한다 |
| metric filter | 없음(로그 그룹에 설정) | 남는다 | 이미 들어온 로그에서 패턴을 센다 |

**EMF는 `cloudwatch:PutMetricData` 권한이 필요 없습니다.** 로그를 쓰는 권한만으로 커스텀 메트릭이 생성되고, 같은 로그 이벤트가 CloudWatch Logs에 그대로 남아 Logs Insights로 파고들 수 있습니다. 메트릭에서 이상을 발견한 뒤 그 시점의 원본 이벤트를 바로 열어 보는 흐름이 여기서 나옵니다.

대신 두 가지 함정이 따라옵니다. 전달 보장이 at-least-once라 중복 값이 생길 수 있고, **고카디널리티 dimension을 넣으면 조합마다 커스텀 메트릭이 생성돼 과금이 폭증합니다.** requestId나 사용자 ID를 dimension으로 올리는 구성이 대표적인 사고입니다. 그런 축으로 분석해야 한다면 dimension이 아니라 뒤에서 볼 Contributor Insights가 자리입니다.

metric filter는 로그를 발행하는 코드를 고칠 수 없을 때의 경로입니다. 애플리케이션이 이미 특정 문자열을 찍고 있고 그 발생 횟수를 메트릭으로 만들어야 한다면, 코드 변경 없이 로그 그룹 쪽에서 처리합니다. 로그 그룹당 metric filter는 100개이고 이 값은 조정할 수 없습니다.

---

## 4. metric stream과 cross-account observability가 각각 넘기는 경계

메트릭을 CloudWatch 밖으로 내보내거나, 다른 계정의 메트릭을 한자리에서 보는 방법이 각각 따로 있습니다. 둘은 이름이 비슷하게 들리지만 넘는 경계가 다릅니다.

**metric stream**은 계정 밖으로 나가는 경로입니다.

- Firehose 경유 또는 S3 quick setup으로 near-real-time push한다.
- 출력 포맷은 JSON, OpenTelemetry 1.0.0, OpenTelemetry 0.7.0 세 가지다.
- 스트림당 필터는 최대 1,000개이고 include와 exclude를 섞을 수 없다.
- 계정당 스트림 개수 제한은 없다.
- 기본 포함 통계는 Minimum, Maximum, SampleCount, Sum이다.

"서드파티 SaaS 모니터링으로 전체 메트릭을 상시 전달한다"는 요구에서 `GetMetricData` 폴링과 metric stream이 갈립니다. 폴링은 API 호출 수와 지연이 메트릭 수에 비례해 늘고, `GetMetricData` 요청 자체가 계정당 리전당 500 requests per second 쿼터를 씁니다. metric stream은 push 방식이라 이 축을 없애고, 스트림 개수 제한이 없다는 점이 대량 전달 설계를 가능하게 합니다.

**cross-account observability**는 계정 경계를 넘는 조회 경로입니다. monitoring account에 sink를 두고 source account가 link를 만드는 구조입니다.

| 항목 | 값 |
| :--- | :--- |
| monitoring account 하나가 연결하는 source account | 최대 100,000개 |
| source account 하나가 공유하는 monitoring account | 최대 5개 |
| sink | 계정당 리전당 1개 |
| 공유 가능한 telemetry | 메트릭, 로그 그룹, X-Ray trace, Application Signals의 service와 SLO, Application Insights 애플리케이션, Internet Monitor |
| 범위 | Region 내부 |

문항이 파고드는 지점은 두 가지입니다.

**첫째, 링크는 Region 내부에서 동작합니다.** monitoring account에서 다른 리전의 source account 데이터를 이 기능으로 볼 수 없습니다. 3개 리전에 흩어진 로그를 한 번에 검색해야 한다는 지문이 나오면 cross-account observability는 답이 되지 못하고, subscription filter로 중앙 스트림에 모으는 설계가 답입니다.

**둘째, 공유 범위는 양쪽 선택의 교집합입니다.** source account가 monitoring account보다 **많은** telemetry 유형을 선택하면 링크 생성 자체가 실패하고, **적게** 선택하면 링크는 만들어지되 양쪽에서 함께 선택된 유형만 넘어옵니다. 메트릭만 보이고 로그와 trace가 안 보이는 증상은 source 쪽 설정이 좁을 때 나옵니다. 그리고 링크 해제는 source account에서만 합니다.

monitoring account로 지정된 계정에서는 여러 source account의 로그 그룹을 **하나의 Logs Insights 쿼리로 가로질러** 조회할 수 있습니다. 이 점이 기존의 cross-account cross-Region 대시보드와 갈리는 지점입니다. 대시보드 쪽은 콘솔에서 여러 계정과 리전의 위젯을 한 화면에 모아 보는 기능이고, Logs Insights를 계정 가로질러 실행하지는 못합니다.

---

## 5. 로그가 로그 그룹을 떠나는 경로는 네 가지다

CloudWatch Logs에 들어온 로그를 다른 곳에서 쓰려면 로그 그룹 밖으로 꺼내야 하고, 경로마다 지연과 개수 제한이 다릅니다. 이 표가 D3 문항에서 가장 자주 답을 가릅니다.

{% include diagrams/static/sap-c02/cloudwatch-logs-delivery-paths.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/cloudwatch-logs-delivery-paths--82e978a9f00e1319.png" %}

그림은 왼쪽의 로그 그룹 하나에서 네 갈래가 나가는 배치입니다. 위쪽 갈래인 subscription filter에서 다시 네 개의 대상 서비스로 부챗살처럼 퍼지고, 아래쪽으로 metric filter, S3 export task, Logs Insights 쿼리가 차례로 놓입니다. export 경로만 점선인 이유가 상자 안에 적혀 있습니다. 이 경로는 실시간 흐름이 아니라 데이터가 준비될 때까지 기다리는 배치 작업입니다.

**subscription filter**가 실시간 경로입니다.

- 로그 그룹당 **5개**이고 조정할 수 없다.
- 대상은 Kinesis Data Streams, Lambda, Data Firehose, OpenSearch Service **네 가지**다.
- 전달 payload는 base64 인코딩 후 gzip 압축된다.
- throttle된 전달은 최대 **24시간** 재시도하고 그 뒤에는 폐기한다.

5개 제한이 그대로 문항이 됩니다. 여섯 번째 팀이 같은 로그 그룹을 구독하려 하면 실패하고, 이 값은 Service Quotas 증설 대상이 아닙니다. 해법은 하나의 subscription filter로 Kinesis Data Streams에 보내고 소비자들을 그 스트림 위에 두는 것입니다. Kinesis Data Streams는 여러 소비자가 같은 데이터를 독립적으로 읽으므로 로그 사본이 늘지 않습니다.

교차 계정 교차 리전 구독에는 별도 규칙이 있습니다. **log group과 destination은 같은 리전에 있어야 하지만, destination이 가리키는 실제 리소스는 다른 리전에 둘 수 있습니다.** 따라서 소스 리전마다 destination을 하나씩 만들고 그 destination들이 모두 중앙 계정의 같은 스트림을 가리키게 하면, 여러 리전의 로그를 단일 파이프라인으로 모을 수 있습니다. 이 구조를 모르면 "리전마다 별도 수집 스택이 필요하다"는 오답 선지를 고르게 됩니다.

**S3 export task**는 실시간 경로가 아닙니다.

- 로그 데이터가 export 가능해지기까지 **최대 12시간** 걸린다.
- export task는 **24시간** 뒤 timeout한다.
- 계정당 동시 실행 가능한 export task는 **1개**이고 조정할 수 없다.
- 대상 버킷은 AES-256과 SSE-KMS까지 지원하고 DSSE-KMS는 지원하지 않는다.
- AWS 문서가 **상시 아카이빙 용도로 정기 export를 권하지 않고** subscription을 권한다.

"매시간 export를 돌려 준실시간에 가깝게 만든다"는 선지는 동시 task 1개와 12시간 준비 시간 두 가지 이유로 성립하지 않습니다.

**Logs Insights**의 쿼터도 확인해 둡니다.

| 항목 | 값 |
| :--- | :--- |
| Logs Insights QL 동시 쿼리 | 계정당 100개(대시보드에 얹은 쿼리 포함) |
| OpenSearch PPL과 SQL 동시 쿼리 | 15개 |
| 쿼리 timeout | 60분 |
| 쿼리 결과 조회 가능 기간 | 7일 |
| 조회 대상 | 로그 그룹 생성 시각 이후 타임스탬프, 2018-11-05 이후 수집분 |
| Live Tail | 계정당 동시 세션 15개, 세션당 로그 그룹 10개 |

로그 그룹 생성 시각 이전 타임스탬프의 이벤트는 Logs Insights로 조회할 수 없다는 조건이 실무에서 걸립니다. 과거 데이터를 새 로그 그룹으로 옮겨 넣어도 그 이벤트들은 쿼리에 잡히지 않습니다.

나머지 CloudWatch Logs 쿼터도 함께 봅니다.

| 항목 | 값 |
| :--- | :--- |
| 로그 이벤트 최대 크기 | 1,024 KB |
| `PutLogEvents` 배치 최대 크기 | 1 MB |
| `PutLogEvents` 호출 한도 | 기본 5,000 TPS(조정 가능) |
| 계정당 로그 그룹 | 기본 1,000,000개 |
| resource policy | Region당 10개 |

---

## 6. 고카디널리티 축과 외형 관측은 Contributor Insights와 canary가 나눠 맡는다

메트릭 dimension으로 다룰 수 없는 축이 있습니다. 어떤 IP가, 어떤 URL이, 어떤 테넌트가 문제를 만들고 있는지는 값의 가짓수가 너무 많아 dimension으로 발행할 수 없습니다. 그 자리가 **Contributor Insights**입니다.

- 로그 데이터를 실시간으로 분석해 상위 기여자와 고유 기여자 수를 시계열로 만든다.
- rule은 직접 작성하거나 AWS가 제공하는 sample rule과 built-in rule을 쓴다.
- 계정당 리전당 rule은 **기본 100개**이고 증설할 수 있다.
- monitoring account에서 여러 source account의 로그 그룹을 하나의 rule로 분석할 수 있다.
- rule에 매칭되는 **로그 이벤트 발생 건수 기준으로 과금**한다.
- rule이 참조하는 숫자 값이 -1e9에서 1e9 밖이면 그 로그 항목을 건너뛴다.

EMF의 dimension 폭증 함정과 짝을 이룹니다. 사용자 ID별 요청 수를 알고 싶다는 요구에 dimension을 늘리면 커스텀 메트릭이 조합 수만큼 만들어지지만, Contributor Insights는 로그 필드를 그대로 읽어 상위 기여자만 시계열로 만듭니다.

**Synthetics canary**는 반대편입니다. 안에서 수집한 신호가 아니라 밖에서 두드려 본 결과입니다.

- 계정 안에 Lambda 함수를 만들어 스크립트를 실행한다(Node.js, Python, Java).
- 최소 실행 주기는 **1분**이고 cron과 rate 표현식을 쓴다.
- 메트릭은 `CloudWatchSynthetics` 네임스페이스에 `CanaryName` dimension으로 발행된다.
- `executeStep()`이나 `executeHttpStep()`을 쓰면 `StepName` dimension이 추가된다.
- VPC 안에서 실행할 수 있다.
- 계정당 canary 개수는 us-east-1이 300개, 대부분의 다른 리전은 500개이고 증설할 수 있다.

`StepName` dimension이 실무에서 유용한 이유는 실패 지점을 단계 단위로 좁혀 주기 때문입니다. 로그인, 검색, 결제 세 단계를 하나의 canary로 묶어 두면 어느 단계에서 끊겼는지가 메트릭으로 바로 드러납니다.

트래픽이 없는 시간대에 장애를 감지해야 한다는 요구가 지문에 있으면 canary가 답입니다. 실제 요청이 없으면 애플리케이션 메트릭도 없고, 그 상태에서는 알람이 INSUFFICIENT_DATA에 머물 뿐 아무것도 알려주지 않습니다.

**Application Signals와 Transaction Search**는 분산 서비스의 상태와 한 건의 거래를 서로 다른 관점에서 연결합니다. Application Signals는 애플리케이션에서 call volume, availability, latency, fault, error를 자동 수집하고 서비스와 의존성 topology와 SLO 상태를 함께 보여줍니다. Java, Python, Node.js, .NET을 지원하며 EKS, ECS, EC2에서 검증된 경로입니다. 서비스 이름을 직접 지정해야 하는 실행 환경도 있으므로 에이전트를 설치했다는 사실만으로 topology가 완성된다고 가정하면 안 됩니다.

Transaction Search를 켜면 X-Ray로 보낸 trace의 span이 `aws/spans` 로그 그룹에 구조화된 로그로 들어옵니다. 이 경로는 100퍼센트 span을 저장해 고객 ID나 주문 번호 같은 속성으로 거래를 검색하고, Logs Insights의 anomaly와 pattern 분석이나 metric filter도 같은 원본에 적용하게 합니다. X-Ray로 trace를 보내지 않는 환경은 ADOT, CloudWatch agent, 또는 OpenTelemetry를 사용하는 Application Signals 경로로 시작할 수 있습니다. X-Ray sampling으로 일부 trace만 남기는 것과 Transaction Search에서 span 원본을 검색하는 것은 서로 다른 계층입니다.

**CloudWatch RUM**은 서버가 아니라 실제 웹과 모바일 사용자의 세션에서 page load, client-side error, 화면 로드, 네트워크 오류와 같은 신호를 near-real-time으로 수집합니다. app monitor가 생성한 client snippet이 세션의 수집 비율을 적용하고, RUM 원본은 기본 30일 뒤 삭제됩니다. 장기 보존이 필요하면 CloudWatch Logs로 사본을 보내고 로그 그룹 보존 기간을 별도로 정합니다. Application Signals에서 RUM client와 서비스 trace를 연결하려면 app monitor에 X-Ray active tracing을 켜야 합니다.

**Container Insights**는 ECS, EKS, ROSA, EC2의 Kubernetes와 Fargate 컨테이너에서 성능 로그 이벤트를 EMF 구조화 JSON으로 수집합니다. CloudWatch는 이 원본에서 cluster, node, pod, task, service 단위 집계 메트릭을 만들고 자동 대시보드에 표시하며, performance log group도 자동 생성합니다. 비용을 줄이기 위해 가능한 모든 메트릭을 자동 생성하지 않으므로 더 세밀한 축이 필요하면 원본 performance log를 Logs Insights로 조회합니다. EKS의 enhanced observability는 저장 메트릭과 로그가 아닌 observation 기준으로 과금되는 별도 경계도 확인해야 합니다.

---

## 7. CloudTrail은 조회 창과 이벤트 종류에서 세 갈래로 갈린다

"누가 무엇을 호출했는가"를 조사하는 도구가 CloudTrail이고, 같은 서비스 안에 성격이 다른 세 가지 조회 수단이 있습니다.

| 축 | Event history | trail | CloudTrail Lake |
| :--- | :--- | :--- | :--- |
| 조회 창 | 최근 **90일** | S3 보존 정책에 따른다 | event data store 보존 설정에 따른다 |
| 담는 이벤트 | management event만 | 선택한 종류 전부 | 선택한 종류 전부 |
| 설정 | 불필요 | trail 생성 필요 | event data store 생성 필요 |
| 요금 | 없다 | S3 저장과 추가 이벤트 종류에 붙는다 | 수집과 쿼리에 붙는다 |
| 조회 방식 | 콘솔 검색과 다운로드 | S3 객체 또는 CloudWatch Logs | SQL |
| 무결성 증명 | 해당 없음 | log file integrity validation | 해당 없음 |

CloudTrail이 기록하는 event는 **management, data, network activity, Insights 네 종류**입니다. 강의와 오래된 자료는 세 종류로 설명하는 경우가 있는데 현재 문서는 network activity event를 포함한 네 종류입니다. trail과 event data store는 **기본으로 management event만** 기록하고 나머지 셋은 명시적으로 켜야 하며 추가 요금이 붙습니다.

"6개월 전 S3 객체 접근을 조사한다"는 지문이 두 번 걸리는 이유가 여기 있습니다. Event history는 90일이고, 애초에 data event를 담지 않습니다. S3 객체 접근은 data event이므로 미리 켜 두지 않았다면 조사할 기록 자체가 없습니다.

**CloudTrail Lake**의 보존은 요금제에 따라 갈립니다.

- One-year extendable retention pricing에서 최대 **3,653일**(약 10년)
- Seven-year retention pricing에서 최대 **2,557일**(약 7년)
- 쿼리 결과는 **7일**간 볼 수 있고 S3에 저장할 수도 있다

"1년 전 API 호출을 SQL로 조사"라는 요구는 Lake가 답이고, "S3에 원본을 보존하면서 변조되지 않았음을 증명"이라는 요구는 trail과 log file integrity validation 조합이 답입니다.

**log file integrity validation**의 동작은 다음과 같습니다.

- SHA-256 해싱과 SHA-256 with RSA 서명을 쓴다.
- digest 파일은 **매시간** 생성돼 직전 1시간의 로그 파일 목록과 해시를 담는다.
- 각 digest는 **이전 digest의 서명을 포함**해 체인을 만든다.
- digest는 로그 파일과 같은 버킷의 별도 폴더에 들어간다.
- key pair는 Region마다 다르다.

체인 구조가 방어의 핵심입니다. 로그 파일 하나를 바꾸면 그 시간대 digest와 어긋나고, digest를 함께 바꾸면 다음 digest에 담긴 서명과 어긋납니다. "S3 버킷에 넣었으니 변조되지 않았다"는 주장은 이 기능을 켜지 않았다면 성립하지 않습니다.

**organization trail**은 management account와 모든 member account의 이벤트를 동일한 S3 버킷, CloudWatch Logs, EventBridge로 보냅니다. 콘솔로 만든 trail은 전부 multi-Region trail입니다. `IncludeGlobalServiceEvents`가 true일 때 global service event는 single-Region trail의 경우 us-east-1로만 전달됩니다.

전달 지연도 알아 둘 값입니다. AWS 문서는 CloudTrail이 API 호출 후 **평균 약 5분** 안에 이벤트를 전달하며 **이 시간은 보장되지 않는다**고 명시합니다. "CloudTrail 이벤트를 트리거로 5초 안에 차단한다"는 설계가 성립하지 않는 근거입니다. 즉시 차단이 요구되면 통제는 SCP나 리소스 정책 같은 사전 통제 쪽으로 옮겨야 합니다.

---

## 8. Config는 구성 상태를 평가하고 교정은 SSM Automation이 실행한다

CloudTrail이 호출 기록이라면 Config는 구성 상태입니다. "지금 이 보안 그룹이 어떻게 설정돼 있는가"와 "그 설정이 기준에 맞는가"를 다룹니다.

{% include diagrams/static/sap-c02/config-evaluation-remediation.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/config-evaluation-remediation--4c376b21c28675f4.png" %}

그림은 왼쪽의 리소스 구성 변경에서 출발해 configuration recorder, rule 평가, 평가 결과, 자동 교정으로 이어지는 흐름과, 그 흐름에서 갈라져 나와 끝나는 두 곁가지를 함께 보여 줍니다. 아래쪽 점선 가지가 proactive evaluation이고 차단도 교정도 하지 않는 상자에서 끝납니다. 위쪽 점선 가지가 aggregator이고 평가 결과를 받기만 하는 자리입니다. 교정으로 이어지는 실선은 NON_COMPLIANT 상자에서만 나갑니다.

**configuration recorder**부터 봅니다.

- customer managed configuration recorder는 **계정당 리전당 1개**다.
- 기본값은 지원되는 모든 리소스 유형을 기록하되 **global IAM 유형 네 개**(`AWS::IAM::Group`, `AWS::IAM::Policy`, `AWS::IAM::Role`, `AWS::IAM::User`)는 제외한다.
- 기록 빈도는 Continuous recording과 Daily recording 두 가지다.
- Daily는 최근 24시간의 최종 상태를 나타내는 configuration item을 직전 것과 다를 때만 전달한다.

빈도 선택에 걸리는 제약이 둘 있습니다. **AWS Firewall Manager는 continuous recording에 의존하므로** 비용을 아끼려고 daily로 바꾸면 Firewall Manager 통제가 깨집니다. 그리고 customer managed recorder와 PAID scope의 service-linked recorder가 같은 리소스 유형을 기록하면 **더 높은 빈도가 우선**합니다. 콘솔에는 Daily로 보이면서 실제로는 continuous 요금이 청구되는 상황이 여기서 나옵니다.

**rule 평가**의 축은 두 개입니다.

| 축 | 값 |
| :--- | :--- |
| trigger 유형 | configuration change, periodic, hybrid |
| evaluation mode | proactive, detective |
| 평가 결과 | COMPLIANT, NON_COMPLIANT, ERROR, NOT_APPLICABLE |

**proactive evaluation은 배포 전 평가만 합니다.** NON_COMPLIANT로 판정된 자원을 교정하지도, 배포를 막지도 않습니다. "proactive rule로 비준수 리소스 생성을 차단한다"는 선지가 성립하지 않는 이유이고, 실제 차단이 필요하면 SCP나 CloudFormation Hooks 같은 다른 통제가 필요합니다.

**remediation**은 AWS Systems Manager Automation document로 실행됩니다. AWS 관리형 automation document 집합이 제공되고 커스텀 document도 연결할 수 있습니다. 여기에 두 가지 동작 특성이 붙습니다.

- 실패 시 재시도 횟수와 시간 창을 사용자가 지정한다(문서 예시는 300초 안에 5회). **재시도는 교정이 실패한 경우에만, 지정한 시간 창 안에서만** 일어나고 실행마다 SSM Automation 요금이 붙는다.
- 자동 교정은 **주기적으로 캡처한 compliance 스냅샷을 기준으로** 동작한다. 스냅샷 이후 이미 준수 상태가 된 리소스에도 교정이 실행될 수 있다.

두 번째 항목 때문에 **교정 runbook은 멱등해야 합니다.** 이미 닫힌 규칙을 다시 닫는 동작이 부작용을 남기지 않아야 하고, 실패 진단은 `describe-remediation-execution-status`로 합니다.

**aggregator는 read-only입니다.** 여러 계정과 리전의 평가 결과를 한자리에 모아 보는 기능이고, aggregator를 통해 source 계정에 rule을 배포하거나 snapshot을 밀어넣을 수 없습니다. aggregator 사용 자체에는 추가 비용이 없고, Organizations 소속 계정을 집계할 때는 source 계정의 authorization이 필요 없습니다. 조직 전체에 rule을 배포하려면 organization Config rule 또는 conformance pack을 씁니다.

**conformance pack**은 Config rule과 remediation action을 YAML 하나로 묶어 계정과 Region 단위 또는 조직 전체에 배포하는 단위입니다. 수동 확인 항목을 담는 process check도 포함할 수 있습니다. 쿼터는 다음과 같습니다.

| 항목 | 값 | 증설 |
| :--- | :--- | :--- |
| 리전당 계정당 Config rule | 1,000개 | 불가 |
| 계정당 conformance pack | 50개 | 불가 |
| conformance pack당 Config rule | 130개 | 불가 |
| 조직당 organization conformance pack | 50개 | 불가 |
| configuration aggregator | 50개 | 가능 |
| aggregator에 담는 계정 | 10,000개 | 불가 |

conformance pack 안의 rule도 **리전당 계정당 1,000개 rule 한도에 포함됩니다.** pack을 여러 개 배포하면서 rule 한도를 잊으면 배포가 중간에 실패합니다.

---

## 9. X-Ray의 sampling 결정은 진입 서비스에서 한 번만 일어난다

분산 추적에서 "우리 서비스만 100퍼센트 추적하겠다"는 요구가 자주 나오고, 대부분 동작하지 않습니다.

{% include diagrams/static/sap-c02/xray-parent-based-sampling.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/xray-parent-based-sampling--b0fa7ed57a9daead.png" %}

그림은 클라이언트 요청에서 진입 서비스 A를 지나 B와 C를 거쳐 수집된 trace로 이어지는 한 줄기 흐름과, 그 흐름에 붙는 두 개의 곁가지로 이루어집니다. 진입 서비스 위쪽 상자가 실제로 결정을 내리는 sampling rule이고 실선으로 연결됩니다. 서비스 C 아래의 점선 상자가 C에만 건 100퍼센트 rule이고, 점선인 이유는 이미 내려진 진입 결정을 뒤집지 못하기 때문입니다.

동작 규칙은 다음과 같습니다.

- **sampling은 parent-based다.** trace 진입 서비스가 한 번 결정하면 하위 서비스는 자신의 rule과 무관하게 그 결정을 따른다.
- 기본 sampling rule은 **reservoir 1**(초당 첫 요청 1건)에 **fixed rate 5퍼센트**다.
- rule priority는 **1에서 9999**이고 오름차순으로 평가해 첫 매치가 이긴다.
- 콘솔에 rule을 두면 X-Ray가 인스턴스 수에 맞춰 reservoir quota를 배분한다.
- 로컬 JSON으로 rule을 두면 **인스턴스마다 독립 sampling**해 전체 비율이 의도보다 올라간다.
- ADOT와 X-Ray SDK는 CloudWatch agent를 proxy로 삼아 sampling API를 호출하며 기본 포트는 **TCP 2000**이다.

"C에 100퍼센트 rule을 걸었는데 여전히 5퍼센트만 수집된다"는 증상은 세 가지를 동시에 알려줍니다. 첫째, 수집 비율이 기본 rule 값과 일치하므로 진입 지점에서 기본 rule이 결정하고 있습니다. 둘째, 하위에 건 rule은 아무 영향을 주지 못합니다. 셋째, 비율을 올리려면 진입 서비스에 매칭되는 rule을 고쳐야 합니다.

priority를 낮춰도 결과는 같습니다. priority는 **같은 서비스 안에서** 여러 rule을 평가하는 순서를 정할 뿐, 다른 서비스가 내린 결정을 무시하게 만들지 못합니다.

---

## 10. 운영 이벤트는 EventBridge 한 곳에 모아 교정으로 잇는다

알람, 구성 위반, 인프라 이벤트, API 호출은 발생 지점이 다르지만 전부 EventBridge 이벤트로 표현됩니다. 이 지점이 관측과 자동화를 잇는 접점입니다.

{% include diagrams/static/sap-c02/ops-event-routing.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/ops-event-routing--faa896cdc6c11f9f.png" %}

그림은 왼쪽 네 개의 신호 발생 지점이 가운데 EventBridge rule 하나로 모이고, 거기서 오른쪽 세 개의 목적지로 나뉘는 배치입니다. 왼쪽 네 상자에는 각 신호의 성격과 제약이, 가운데 상자에는 rule과 target의 개수 제한이, 오른쪽 세 상자에는 각 목적지가 맡는 역할이 적혀 있습니다.

EventBridge 쿼터부터 정리합니다.

| 항목 | 값 | 증설 |
| :--- | :--- | :--- |
| event bus당 rule | 기본 300개(af-south-1과 eu-south-1은 100개) | 가능 |
| rule당 target | **5개** | 불가 |
| wildcard를 포함한 rule | bus당 30개 | 불가 |
| 계정당 event bus | 100개 | |
| event pattern 크기 | 최대 2,048자 | |
| event bus policy 크기 | 최대 10,240자 | |
| 계정당 EventBridge Pipes | 1,000개 | |
| Pipes 동시 실행 | 계정당 1,000개(us-east-1, us-west-2, eu-west-1은 3,000개) | |

**rule당 target 5개**가 조정 불가라는 점이 팬아웃 설계를 가릅니다. 하나의 이벤트를 열 곳에 보내야 한다면 SNS 토픽을 target으로 두고 그 아래에서 갈라지거나, 같은 패턴의 rule을 여러 개 만들어야 합니다.

**AWS Health**는 이 경로에서 자주 등장하는 신호원이고 요금 경계가 문항이 됩니다.

| 항목 | 필요 조건 |
| :--- | :--- |
| AWS Health Dashboard | 모든 고객, 추가 비용 없음 |
| Health 이벤트를 EventBridge로 수신 | 모든 고객, 추가 비용 없음 |
| AWS Health API | Business Support+, Enterprise Support, Unified Operations |

"Business 플랜 없이 Health 이벤트를 프로그램에서 처리한다"는 요구는 API로는 불가능하고 EventBridge로는 가능합니다. 이 비대칭이 답을 가릅니다. 강의와 오래된 자료가 Personal Health Dashboard라고 부르는 것이 현재의 AWS Health Dashboard이고 서비스명은 AWS Health입니다.

**OpsCenter**는 흩어진 신호를 처리 단위로 묶는 자리입니다.

- OpsItem 단위로 운영 이슈를 모은다.
- CloudWatch 알람이 ALARM 상태로 들어갈 때, EventBridge가 이벤트를 처리할 때 OpsItem을 자동 생성하도록 구성할 수 있다.
- 각 OpsItem에는 AWS Config, CloudTrail 로그, CloudWatch Events에서 모은 컨텍스트가 붙는다.
- 상태는 Open, In progress, Resolved 세 가지다.
- related resource ARN은 최대 100개, operational data의 key는 최대 128자, value는 최대 20 KB다.
- 실행한 Automation runbook 기록은 30일 보존한다.
- OpsCenter는 유료다.

중복 OpsItem을 줄이는 방법이 두 가지입니다. related resource를 지정해 같은 리소스의 이슈를 묶거나, EventBridge event rule에 deduplication string을 직접 지정합니다.

**Incident Manager**는 알람을 티켓으로 쌓는 도구와 달리 응답자를 깨우고 완화 절차를 시작하는 incident 대응 계층입니다. 처음에는 `Get prepared`를 완료해 replication set, contact와 escalation plan, response plan을 만듭니다. response plan에는 영향도와 중복 제거 문자열, on-call schedule 또는 escalation plan, 협업 채널, Systems Manager Automation runbook을 미리 넣을 수 있습니다. CloudWatch alarm이나 EventBridge event에서 incident를 만들면 정해진 응답자와 runbook이 같은 계획으로 시작됩니다. AWS는 한 리전에만 의존하지 않도록 replication set에 최소 두 리전을 포함할 것을 권장하고, 모든 Incident Manager 리소스는 암호화됩니다.

---

## 11. Systems Manager 도구는 지속성과 대상 층에서 갈린다

Systems Manager 안에는 노드에 손대는 도구가 여러 개 들어 있고, 이름만으로는 구분되지 않습니다. 갈리는 축은 두 개입니다. **한 번만 실행하는가 계속 유지하는가**, 그리고 **노드 내부를 다루는가 AWS 리소스를 다루는가**입니다.

| 도구 | 지속성 | 대상 층 | 결정적 특성 |
| :--- | :--- | :--- | :--- |
| Run Command | 일회성 | 노드 내부 | 명령을 한 번 실행하고 끝난다 |
| State Manager | 반복 유지 | 노드 내부 | association으로 원하는 상태를 스케줄에 맞춰 재적용해 drift를 되돌린다 |
| Automation | 다단계 실행 | AWS 리소스 | runbook, 승인 단계, rate control, 다계정 다리전 실행 |
| Session Manager | 대화형 세션 | 노드 내부 | 포트 개방과 bastion 없이 접속한다 |
| Patch Manager | 스캔과 설치 | 노드 내부 | baseline 기준 준수 판정 |

"수백 대의 에이전트 설정이 사람 손에 바뀌어 계속 어긋난다"는 지문에서 Run Command와 State Manager가 갈립니다. Run Command로 배포하면 실행한 시점에만 맞고 다음에 누가 고치면 다시 어긋납니다. State Manager는 스케줄마다 원하는 상태를 다시 적용하고 association 단위로 준수 상태를 보여줍니다.

**State Manager**의 동작 제약은 다음과 같습니다.

- cron과 rate 표현식을 쓴다.
- offset 일수와 `ApplyOnlyAtCronInterval` 옵션이 있다.
- **association cron 표현식에서 month 지정은 지원하지 않는다.**
- 대상은 태그, Resource Groups, 노드 ID, 해당 Region 전체 노드 중 선택한다.
- State Manager 자체에는 추가 요금이 없다.

**Automation**의 쿼터와 구성 요소도 문항 재료입니다.

| 항목 | 값 |
| :--- | :--- |
| 계정당 동시 실행 | 100개(child automation과 rate control automation 포함) |
| 대기열 | 5,000개 |
| rate control automation 동시 실행 | 25개 |
| rate control automation 대기열 | 1,000개 |
| runbook | schema 0.3의 Automation 타입 document |
| action 유형 | 20종 |

rate control은 **동시 대상 수(concurrency)** 와 **중단 기준 오류 수(error threshold)** 를 지정합니다. 500대에 순차 교정을 걸면서 오류가 10건 넘으면 멈추는 구성이 여기서 나옵니다. 승인 단계(`aws:approve`)를 넣을 수 있고 다계정 다리전 실행과 EventBridge 트리거를 지원합니다.

**Session Manager**는 접근 경로 자체를 바꿉니다.

- inbound 포트 개방, bastion host, SSH key 관리 없이 노드에 접속한다.
- 접근 통제는 **IAM 정책으로만** 한다.
- 세션 트래픽은 TLS 1.2로 암호화하고 연결 요청은 SigV4로 서명한다.
- 로깅 대상은 S3와 CloudWatch Logs이고 KMS 암호화를 붙일 수 있다.
- API 호출은 CloudTrail에, 세션 시작과 종료는 EventBridge 이벤트로 잡힌다.

여기에 감사 요구를 무너뜨리는 예외가 하나 있습니다. **port forwarding과 SSH로 연결한 세션은 데이터가 SSH의 TLS 터널 안에 있어 명령이 로깅되지 않습니다.** "Session Manager를 쓰니 모든 명령이 기록된다"는 진술은 이 두 형태에서 성립하지 않습니다.

**Fleet Manager**는 개별 managed node의 상태와 성능, 파일과 로그, 프로세스와 OS 사용자, Windows registry를 Systems Manager 콘솔 한 곳에서 확인하고 조작하는 UI입니다. AWS와 on-premises 노드를 여러 운영체제에 걸쳐 다룰 수 있고, 기능과 대상 노드 접근은 IAM policy로 나눕니다. Fleet Manager는 State Manager처럼 원하는 상태를 반복 적용하지 않고, Run Command처럼 명령 배포만 담당하지도 않습니다. 이미 등록된 fleet을 조사하고 관리하는 화면이라는 경계를 기억합니다.

**Parameter Store**는 노드와 애플리케이션이 읽는 설정 값을 두는 자리입니다. tier가 두 개이고 선택 기준이 뚜렷합니다.

| 항목 | Standard | Advanced |
| :--- | :--- | :--- |
| 계정당 리전당 파라미터 | 10,000개 | 100,000개 |
| 값 최대 크기 | 4 KB | 8 KB |
| parameter policy | 미지원 | 지원 |
| 계정 간 공유 | 미지원 | 지원 |
| 전환 | 업그레이드 가능 | 다운그레이드 불가 |
| 요금 | 추가 요금 없음 | 과금 |

- 타입은 `String`, `StringList`, `SecureString` 세 가지이고 `SecureString`은 KMS로 암호화한다.
- 파라미터마다 최근 **100개 버전**을 보관한다.
- 기본 처리량으로 부족하면 high-throughput 모드를 별도 비용으로 켠다.
- 자격 증명과 비밀은 자동 교체와 교차 리전 복제를 갖춘 Secrets Manager를 문서가 권장한다.

**만료 알림이나 미교체 알림이 필요하다는 요구가 지문에 있으면 Advanced tier입니다.** parameter policy는 Standard에서 지원되지 않기 때문입니다.

**Change Calendar**는 위 도구들이 "언제" 움직일 수 있는지를 정합니다.

- 항목은 `ChangeCalendar` 타입의 Systems Manager document이고 iCalendar 2.0 데이터를 담는다.
- 타입은 **`DEFAULT_OPEN`**(평소 실행 가능, 이벤트 구간에는 CLOSED)과 **`DEFAULT_CLOSED`**(평소 차단, 이벤트 구간에만 OPEN) 두 가지다.
- Automation, Change Manager, maintenance window, State Manager association을 이 상태에 묶을 수 있다.
- 현재 또는 예정된 상태는 `GetCalendarState` API로 조회하고 이 API의 쿼터는 초당 10 요청이다.
- Google Calendar, Microsoft Outlook, iCloud Calendar에서 내보낸 `.ics` 파일을 가져올 수 있다.

"프로모션 기간에는 자동 교정과 패치가 돌지 않아야 한다"는 요구를 runbook 코드 수정 없이 만족시키는 방법이 Change Calendar입니다. `DEFAULT_OPEN` 달력에 그 기간을 이벤트로 넣으면 그 구간에만 차단됩니다.

**Change Manager**는 승인과 실행 기록을 포함한 운영 변경 workflow입니다. change template에 실행할 Automation runbook, 승인자, SNS 알림, 감시 CloudWatch alarm, 태그와 auto-approval 여부를 선언하고 Change Calendar의 business window와 충돌하면 실행을 막거나 추가 승인을 요구합니다. Organizations를 쓰면 delegated administrator 한 계정에서 여러 계정과 리전을 관리할 수 있습니다. 다만 AWS는 2025년 11월 7일부터 새 고객의 Change Manager 가입을 받지 않으며 기존 고객만 계속 사용할 수 있습니다. 자동 CI/CD release 자체의 기본 게이트로 쓰기보다는 예외 승인이나 수동 운영 변경에 맞는 서비스라는 문서의 경계도 함께 확인합니다.

---

## 12. Patch Manager의 준수 기준은 baseline이 정한다

패치 문항에서 답을 가르는 첫 문장은 이것입니다. **패치 준수 기준을 정하는 것은 AWS도 OS 벤더도 아니고 사용자가 정의한 patch baseline입니다.**

baseline은 세 가지로 구성합니다.

- 분류와 심각도 규칙
- 명시적 approve 목록과 reject 목록
- 출시 후 대기 일수(auto-approval delay)

동작은 `Scan`과 `Scan and install` 두 가지입니다. 실행 방법은 네 가지이고 각각 커버 범위가 다릅니다.

| 실행 방법 | 범위 | 설치 |
| :--- | :--- | :--- |
| Quick Setup의 patch policy | Organizations 연동으로 다계정 다리전 | 한다 |
| Quick Setup Host Management | 계정 범위 | **하지 않는다. 스캔만 한다** |
| maintenance window의 Run Command task | 단일 account와 Region 쌍 | 한다 |
| 온디맨드 Patch now | 단일 account와 Region 쌍 | 한다 |

AWS가 권장하는 방법은 patch policy입니다. "여러 OU와 여러 리전에 정해진 창마다 패치를 설치하고 중앙에서 준수 보고를 본다"는 지문에서 나머지 셋은 각각의 이유로 탈락합니다. Host Management는 설치를 하지 않고, maintenance window task와 Patch now는 account와 Region 쌍마다 별도 구성을 만들어 유지해야 합니다.

조직용 patch policy는 Organizations management account에서 생성해야 합니다. delegated administrator 계정이나 member account에서는 조직 정책을 설정할 수 없고, 정책을 적용할 OU와 Region을 그때 선택합니다. Quick Setup이 실제 패치를 수행하려면 대상 노드가 managed node여야 하며, 기존 instance profile에 필요한 SSM과 patch policy S3 bucket 권한이 빠져 있으면 설치 단계가 실패할 수 있습니다.

지원 범위 밖에 있는 두 가지도 기억해 둡니다.

- **OS 메이저 버전 업그레이드를 지원하지 않는다.** Windows Server 2016에서 2019로, RHEL 7에서 8로 가는 전환은 Patch Manager의 일이 아니다.
- Windows에서 애플리케이션 패치는 **Microsoft가 배포한 것으로 한정**된다.

준수 보고서는 CSV로 S3에 내보냅니다.

---

## 13. CloudFormation에서 데이터가 남는 경계와 사라지는 경계

IaC 문항의 상당수가 "스택 작업 중에 데이터가 어떻게 되는가"를 묻습니다. 여기서 두 속성의 적용 범위가 다르다는 점이 답을 가릅니다.

`DeletionPolicy` 값은 네 가지입니다.

| 값 | 동작 |
| :--- | :--- |
| `Delete` | 기본값. 리소스를 삭제한다 |
| `Retain` | 리소스를 남긴다 |
| `RetainExceptOnCreate` | 생성 스택 작업이 롤백될 때만 삭제하고 그 외에는 Retain처럼 동작한다 |
| `Snapshot` | 삭제 전 스냅샷을 만든다 |

기본값이 `Delete`인 데 예외가 있습니다. `AWS::RDS::DBCluster`와 `DBClusterIdentifier`가 없는 `AWS::RDS::DBInstance`는 **기본이 `Snapshot`** 입니다. `Snapshot`을 지원하는 리소스 유형은 DocumentDB DBCluster, EC2 Volume, ElastiCache CacheCluster와 ReplicationGroup, Neptune DBCluster, RDS DBCluster와 DBInstance, Redshift Cluster입니다.

여기가 함정입니다. **`DeletionPolicy`는 스택 삭제와 템플릿에서 리소스가 빠지는 업데이트에 적용됩니다. 업데이트 중 물리 리소스가 교체(replace)되는 경우에는 적용되지 않고 기존 리소스가 그대로 삭제됩니다.** `DeletionPolicy: Retain`을 걸어 둔 RDS 인스턴스라도 식별자를 바꾸는 업데이트를 실행하면 교체가 일어나고 원본이 사라집니다. 이 경계를 메우는 속성이 **`UpdateReplacePolicy`** 입니다.

`RetainExceptOnCreate`의 용도도 명확합니다. 생성 스택이 롤백될 때는 아직 비어 있는 신규 리소스이므로 정리하고, 그 외 모든 작업에서는 사용 중인 데이터를 남깁니다. 실패한 첫 배포가 빈 테이블을 남겨 다음 배포가 이름 충돌로 실패하는 문제를 여기서 해결합니다.

**change set**은 실행 전에 무엇이 바뀌는지 보여 주는 장치입니다.

- 추가, 수정, 삭제 대상과 속성의 변경 전후를 미리 보여준다.
- 생성 시점의 pre-deployment validation이 문법 오류, 이름 충돌, 서비스 쿼터 같은 흔한 실패를 잡는다.
- **업데이트 성공을 보장하지는 않는다.** custom resource 로직이나 서비스별 제약 같은 런타임 실패는 실행 시점에 난다.
- change set을 하나 실행하면 **그 스택에 연결된 나머지 change set이 전부 삭제된다.**

마지막 항목이 실무에서 걸립니다. 여러 후보 변경을 change set으로 만들어 두고 비교하다가 하나를 실행하면 나머지는 남지 않습니다.

**drift detection**은 CloudFormation 밖에서 일어난 변경을 찾는 기능입니다.

- 스택 전체 또는 개별 리소스를 대상으로 **수동으로 실행**한다. 자동으로 계속 감시하지 않는다.
- 드리프트 판정 대상은 **템플릿이나 template parameter로 명시적으로 설정한 속성 값**뿐이다. 리소스 속성의 기본값은 포함되지 않는다.
- drift detection을 지원하지 않는 리소스는 `NOT_CHECKED`가 된다.
- 스택 상태가 `CREATE_COMPLETE`, `UPDATE_COMPLETE`, `UPDATE_ROLLBACK_COMPLETE`, `UPDATE_ROLLBACK_FAILED`일 때 실행할 수 있다.
- **중첩 스택은 부모 스택의 drift detection에 포함되지 않는다.** 중첩 스택에 직접 실행해야 한다.
- 어떤 리소스의 `KMSKeyId` 속성에 대해서도 drift를 판정하지 않는다. 키가 여러 alias로 참조될 수 있어 일관된 결과를 보장할 수 없기 때문이다.

상태 코드는 층마다 다릅니다. 스택과 stack set과 stack instance는 `DRIFTED`, `IN_SYNC`, `NOT_CHECKED`를 갖고, 개별 리소스는 여기에 `MODIFIED`와 `DELETED`가 더해집니다. 속성 차이 유형은 `ADD`, `REMOVE`, `NOT_EQUAL`입니다. **stack set은 stack instance 중 하나라도 drift면 drift로 판정되고, stack instance는 연결된 스택이 drift면 drift로 판정됩니다.**

기본값이 판정 대상이 아니라는 규칙이 오탐과 미탐을 함께 만듭니다. 값을 명시하지 않은 속성은 밖에서 바꿔도 drift로 잡히지 않으므로, 추적하려면 기본값과 같은 값이라도 템플릿에 적어 두어야 합니다. 반대로 1024 MB와 1 GB처럼 같은 값을 다르게 표기하면 drift로 잡힙니다.

---

## 14. 배포 방식은 새 버전을 어디에 띄우는지로 갈린다

배포 문항은 이름을 외우는 문제가 아니라 두 가지를 묻는 문제입니다. **되돌리려면 무엇을 해야 하는가**, 그리고 **실패한 버전이 사용자 트래픽을 받는 구간이 있는가**입니다. 두 답 모두 새 버전을 어디에 띄우는지에서 결정됩니다.

{% include diagrams/static/sap-c02/deployment-rollback-paths.html %}
{% include diagrams/download.html png="/assets/img/diagrams/static/sap-c02/deployment-rollback-paths--ec688298254b9f85.png" %}

그림은 배포 방식별로 새 버전의 배치 위치, 실패 시 롤백 동작, 사용자 트래픽 노출 구간을 비교합니다. 롤백은 실패 조건에서 선택하는 동작이며, 노출 범위는 트래픽 전환 시점과 시험 트래픽 사용 여부에 따라 달라집니다.

**Elastic Beanstalk 배포 정책**은 다섯 가지입니다.

| 정책 | 새 버전 위치 | 롤백 | 제약 |
| :--- | :--- | :--- | :--- |
| All at once | 기존 인스턴스 | 수동 재배포 | 배포 중 다운타임이 있다 |
| Rolling | 기존 인스턴스 | 수동 재배포 | **single-instance 환경 미지원** |
| Rolling with an additional batch | 기존 인스턴스 + 추가 배치 | 수동 재배포 | **single-instance 환경 미지원** |
| Immutable | 두 번째 Auto Scaling group | 새 인스턴스 종료 | 인스턴스를 전부 교체한다 |
| Traffic splitting | 두 번째 Auto Scaling group | 트래픽 회수 후 새 인스턴스 종료 | **Application Load Balancer 환경 전용** |

여기에 Blue/Green이 별도로 있습니다. 환경 자체를 하나 더 만들고 URL을 swap하는 방식입니다. 공식 비교표에서 **"No DNS change" 항목이 No인 유일한 방식이 Blue/Green입니다.** "Immutable은 DNS 변경이 필요하다"는 진술은 방향이 반대이고, Immutable은 같은 환경 안에서 두 번째 Auto Scaling group을 씁니다.

인스턴스를 전부 교체하는 방식에는 공통 부작용이 하나 있습니다. Immutable update, Traffic splitting, 그리고 인스턴스 교체를 켠 managed platform update는 **누적된 EC2 burst balance를 잃습니다.** T 계열 인스턴스로 버스트 크레딧에 기대 운영하던 환경이 배포 직후 성능이 떨어지는 원인이 여기에 있습니다.

**CodeDeploy의 사전 정의 배포 구성**은 플랫폼마다 다릅니다.

| 플랫폼 | 사전 정의 구성 |
| :--- | :--- |
| EC2/On-Premises | `CodeDeployDefault.AllAtOnce`, `HalfAtATime`, `OneAtATime`(지정하지 않으면 기본) |
| Lambda | canary 4종(`LambdaCanary10Percent5Minutes`, `10Minutes`, `15Minutes`, `30Minutes`), linear 4종(`LambdaLinear10PercentEvery1Minute`, `2Minutes`, `3Minutes`, `10Minutes`), `LambdaAllAtOnce` |
| ECS | `ECSLinear10PercentEvery1Minutes`, `ECSLinear10PercentEvery3Minutes`, `ECSCanary10Percent5Minutes`, `ECSCanary10Percent15Minutes`, `ECSAllAtOnce` |

**canary와 linear 사전 정의 구성은 Lambda와 ECS 쪽에만 있습니다.** EC2/On-Premises에서 canary 10퍼센트를 고르는 선지는 존재하지 않는 선택지입니다. AZ별 healthy host 수를 지정하는 zonal configuration도 사전 정의 구성에는 없고 커스텀 구성으로만 씁니다.

세 방식의 트래픽 이동 형태도 정확히 구분합니다.

- **canary**는 두 번의 증분이다. 첫 증분 후 지정한 시간을 기다렸다가 나머지를 전량 옮긴다.
- **linear**는 동일 비율을 동일 간격으로 반복한다.
- **all-at-once**는 한 번에 전량 옮긴다.

**CodeDeploy 기반 ECS blue/green**에는 로드밸런서 요건이 붙습니다.

- ALB 또는 NLB가 필요하다.
- production listener 1개와 target group 2개가 있어야 한다.
- test listener는 선택이며 production listener와 같은 로드밸런서에 있어야 한다.
- **Network Load Balancer를 쓰면 `ECSAllAtOnce`만 지원한다.**

NLB 제약이 문항의 축입니다. "NLB 뒤의 ECS 서비스에 10퍼센트 canary를 적용한다"는 구성은 사전 정의 구성이든 커스텀 구성이든 성립하지 않습니다. 점진 이동이 필요하면 ALB로 바꾸는 것이 정공법이고, NLB를 유지해야 한다면 all-at-once 배포에 CloudWatch 알람 기반 자동 롤백을 붙이는 것이 현실적인 대안입니다.

배포 중 스케일링이 겹칠 때의 동작도 정해져 있습니다. ECS blue/green 배포에서 스케일링이 일어나면 CodeDeploy는 green task set이 steady state에 도달할 때까지 **최대 1시간** 기다립니다. 배포 진행 중 스케일링 이벤트가 발생하면 트래픽 이동을 **5분간** 계속하고, 그 안에 steady state에 도달하지 못하면 배포를 실패 처리합니다. 그리고 Fargate와 `CODE_DEPLOY` 컨트롤러는 `DAEMON` 스케줄링 전략을 지원하지 않습니다.

한 가지 현재 상태를 덧붙입니다. AWS 문서는 CodeDeploy 기반 ECS blue/green 페이지 첫 문단에서 **Amazon ECS 네이티브 blue/green 배포를 권장**하고 CodeDeploy 방식을 그 아래에 둡니다. 시험 대비로는 CodeDeploy 방식의 제약을 아는 것이 여전히 필요하고, 실무 선택에서는 네이티브 방식을 먼저 검토하는 것이 문서의 방향입니다.

**CodePipeline과 CodeBuild**는 트래픽을 옮기는 배포 방식이 아니라 release workflow의 경계를 정합니다. CodePipeline은 source, build, test, deploy, approval, invoke action을 stage 안에서 직렬 또는 병렬로 실행하고 artifact를 다음 stage로 넘깁니다. stage의 inbound transition을 잠시 막아 배포를 멈추거나 실패한 stage를 이전 성공 실행으로 rollback할 수 있습니다. CodeBuild는 빌드 서버를 직접 운영하지 않고 소스 컴파일, unit test, 배포 artifact 생성을 수행하며 CodePipeline의 build 또는 test action으로 연결합니다. 따라서 "파이프라인에서 테스트와 승인 뒤 CodeDeploy를 실행"은 CodePipeline과 CodeBuild의 조합이고, "트래픽을 10퍼센트만 옮김"은 CodeDeploy나 ECS 배포 구성의 책임입니다.

**EC2 Image Builder**는 애플리케이션 release가 아니라 재사용할 AMI와 container image의 공급망을 자동화합니다. image 또는 container recipe가 base image와 build, test component를 선언하고, pipeline이 build, test, distribution 순으로 실행합니다. 테스트를 통과한 AMI나 container image를 여러 Region과 계정으로 배포할 수 있고, schedule을 두어 운영체제 패치가 반영된 새 이미지를 반복 생성할 수 있습니다. recipe는 version control과 CI/CD pipeline에서도 재사용할 수 있으므로, 인스턴스마다 수동으로 패키지를 설치하는 방식과 구분합니다.

**Service Catalog**는 승인된 인프라 제품을 포트폴리오로 묶어 셀프서비스로 배포하게 하는 governance 경계입니다. 제품은 CloudFormation template 또는 Terraform configuration을 기반으로 하고, portfolio가 누가 어떤 product version을 실행할지 결정합니다. launch constraint는 사용자의 권한 대신 제품별 IAM launch role로 리소스를 만들게 하고, notification constraint는 stack event를 SNS로 보내며, template constraint는 인스턴스 타입이나 CIDR 같은 입력 범위를 제한합니다. 지속적인 소스 빌드와 트래픽 배포를 담당하는 CodePipeline과 달리, Service Catalog는 승인된 리소스 패턴의 선택과 수명주기를 통제합니다.

---

## 15. 성능 병목은 지표를 정의한 뒤에만 좁혀진다

Task 3.3은 성능 개선을 묻지만 시작점은 튜닝이 아니라 정의입니다. "느리다"는 진술은 그대로는 검증할 수 없고, 문항의 정답 선지는 대체로 측정 가능한 지표를 먼저 세우는 쪽에 있습니다.

먼저 네 용어의 층을 구분합니다.

| 용어 | 정의 | 성격 |
| :--- | :--- | :--- |
| SLI | 서비스 수준을 나타내는 실제 측정값 | 지표. 예를 들어 p99 응답 시간 |
| SLO | 그 SLI가 지켜야 하는 내부 목표 | 목표. 예를 들어 p99 300ms 이하 |
| SLA | 고객과 맺은 계약과 위반 시 보상 | 계약 |
| KPI | 비즈니스 성과를 재는 지표 | 성과. 예를 들어 결제 완료율 |

SLO는 SLA보다 엄격하게 두는 것이 일반적입니다. 계약 위반에 도달하기 전에 내부에서 먼저 신호가 울려야 대응할 시간이 생기기 때문입니다.

병목을 좁히는 순서는 다음과 같습니다.

1. **비즈니스 요구를 측정 가능한 지표로 바꾼다.** "결제가 빨라야 한다"를 "결제 API의 p99 응답 시간이 300ms 이하"로 바꾼다.
2. **그 지표를 발행한다.** 애플리케이션 지표는 EMF, 고카디널리티 축은 Contributor Insights, 외형 확인은 Synthetics canary다.
3. **어느 구간인지 좁힌다.** 분산 추적으로 구간별 지연을 나눈다. 진입 서비스에 sampling rule을 세워야 하위 서비스 trace가 함께 잡힌다.
4. **후보 조치를 세우고 되돌릴 수 있는 방식으로 시험한다.** canary 또는 linear 배포로 일부 트래픽에만 적용하고 알람으로 판정한다.
5. **판정 지표를 배포 전후로 비교한다.** anomaly detection을 쓴다면 배포 구간을 학습에서 제외한다.

병목 유형별로 관측 신호와 후보 조치가 대응됩니다.

| 병목 유형 | 관측 신호 | 후보 조치 |
| :--- | :--- | :--- |
| 같은 데이터를 반복 조회한다 | 데이터베이스 read가 요청 수에 비례해 늘고 응답 시간이 read 부하와 함께 오른다 | 캐시 계층을 둔다 |
| 특정 키에 요청이 몰린다 | Contributor Insights의 상위 기여자가 소수에 집중된다 | 키 분산이나 요청 단위 제한을 건다 |
| 지연이 특정 구간에서만 늘어난다 | trace의 구간별 지연이 한 서비스에 몰린다 | 그 서비스의 자원이나 쿼리를 고친다 |
| 사용자와 리전 사이의 왕복이 길다 | 지연이 클라이언트 지역에 따라 갈린다 | 엣지 캐싱이나 글로벌 가속 도입을 검토한다 |
| 스케일링이 부하를 따라가지 못한다 | 부하 상승과 용량 증가 사이의 시차가 크다 | 스케일링 정책의 임계와 warm-up을 재평가한다 |

지연이 사용자 지역별로 갈리면 엣지 캐싱이나 글로벌 가속으로 왕복 거리를 줄일지 검토합니다. 부하 상승과 용량 증가 사이의 시차가 크면 스케일링 정책의 임계값과 warm-up 설정을 조정할 근거가 됩니다.

세 번째 행에는 앞 절의 sampling 규칙이 그대로 걸립니다. 특정 서비스만 100퍼센트 추적하려고 그 서비스에 rule을 걸면 진입 결정에 막혀 데이터가 늘지 않습니다. 병목 조사를 위해 수집 비율을 올려야 한다면 진입 지점의 rule을 고쳐야 합니다.

---

## 16. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**CloudWatch 메트릭과 알람**

| 항목 | 값 |
| :--- | :--- |
| 표준 해상도 / 고해상도 | 1분 / 1초 |
| 메트릭 보존 | 60초 미만 3시간, 60초 15일, 300초 63일, 3,600초 455일 |
| 메트릭 자동 만료 | 신규 데이터 없이 15개월 |
| 메트릭당 dimension | 최대 30개 |
| `PutMetricData` 타임스탬프 창 | 과거 2주, 미래 2시간 |
| 고해상도 알람 period | 10초 또는 30초 |
| 알람 결측 처리 기본값 | `missing`(`AWS/DynamoDB`만 `ignore`) |
| 알람 evaluation 상한 | period 3,600초 이상이면 7일, 미만이면 1일 |
| 알람 이력 보존 | 30일 |
| 계정당 알람 개수 | 제한 없음 |
| anomaly detection 학습 범위 | 최대 2주 |
| Contributor Insights rule | 계정당 리전당 기본 100개, 증설 가능 |
| Contributor Insights 값 범위 | -1e9에서 1e9 |
| Synthetics canary 최소 주기 | 1분(60,000 ms) |
| Synthetics canary 개수 | us-east-1 300개, 대부분의 리전 500개 |
| Application Signals 지원 언어 | Java, Python, Node.js, .NET |
| Application Signals 지원 리전 | 상용 리전 대부분(Canada West 제외) |
| Transaction Search span 보관 | 100퍼센트 구조화 로그, trace당 최대 10,000 span |
| CloudWatch RUM 원본 보존 | 30일 후 자동 삭제 |
| Container Insights 집계 축 | cluster, node, pod, task, service |
| `GetMetricData` 요청 | 계정당 리전당 500 rps |
| `PutMetricData` 요청 | 계정당 리전당 500 rps |
| metric stream 필터 | 스트림당 1,000개, include와 exclude 혼용 불가 |
| metric stream 개수 | 제한 없음 |

**CloudWatch Logs와 교차 계정 관측**

| 항목 | 값 |
| :--- | :--- |
| 로그 그룹당 subscription filter | 5개, 조정 불가 |
| 로그 그룹당 metric filter | 100개, 조정 불가 |
| subscription filter 대상 | Kinesis Data Streams, Lambda, Data Firehose, OpenSearch Service |
| subscription 전달 재시도 | 최대 24시간 |
| 로그 이벤트 최대 크기 | 1,024 KB |
| `PutLogEvents` 배치 | 최대 1 MB, 기본 5,000 TPS |
| 계정당 로그 그룹 | 기본 1,000,000개 |
| resource policy | Region당 10개 |
| S3 export 준비 시간 | 최대 12시간 |
| S3 export task | 계정당 동시 1개, 24시간 뒤 timeout |
| Logs Insights 동시 쿼리 | 계정당 100개(QL), 15개(PPL과 SQL) |
| Logs Insights 쿼리 timeout / 결과 보존 | 60분 / 7일 |
| Live Tail | 계정당 동시 세션 15개, 세션당 로그 그룹 10개 |
| monitoring account당 source account | 최대 100,000개 |
| source account당 monitoring account | 최대 5개 |
| sink | 계정당 리전당 1개 |
| cross-account observability 범위 | Region 내부 |

**CloudTrail과 Config**

| 항목 | 값 |
| :--- | :--- |
| Event history | 90일, management event만 |
| CloudTrail 이벤트 종류 | management, data, network activity, Insights |
| CloudTrail 전달 시간 | 평균 약 5분, 보장되지 않음 |
| digest 파일 생성 주기 | 매시간, 이전 digest 서명 포함 |
| CloudTrail Lake 보존 | 최대 3,653일 또는 2,557일 |
| Lake 쿼리 결과 조회 | 7일 |
| configuration recorder | 계정당 리전당 1개 |
| 기본 제외 리소스 유형 | global IAM 4종 |
| Config rule | 리전당 계정당 1,000개, 조정 불가 |
| 계정당 conformance pack | 50개, pack당 rule 130개 |
| configuration aggregator | 50개(증설 가능), 담는 계정 10,000개 |
| Config 자동 교정 재시도 | 사용자가 횟수와 시간 창 지정(예시 300초 안에 5회) |

**X-Ray와 EventBridge**

| 항목 | 값 |
| :--- | :--- |
| 기본 sampling rule | reservoir 1, fixed rate 5퍼센트 |
| sampling rule priority | 1에서 9999, 오름차순 첫 매치 |
| sampling 결정 주체 | trace 진입 서비스(parent-based) |
| CloudWatch agent sampling proxy 포트 | TCP 2000 |
| event bus당 rule | 기본 300개(af-south-1과 eu-south-1은 100개) |
| rule당 target | 5개, 조정 불가 |
| wildcard 포함 rule | bus당 30개, 조정 불가 |
| event pattern / bus policy | 2,048자 / 10,240자 |
| 계정당 event bus | 100개 |
| Pipes 동시 실행 | 1,000개(us-east-1, us-west-2, eu-west-1은 3,000개) |

**Systems Manager**

| 항목 | 값 |
| :--- | :--- |
| Automation 동시 실행 / 대기열 | 100개 / 5,000개 |
| rate control automation 동시 실행 / 대기열 | 25개 / 1,000개 |
| Automation runbook | schema 0.3, action 유형 20종 |
| State Manager cron | month 지정 미지원, 추가 요금 없음 |
| Session Manager 암호화 | TLS 1.2, 요청은 SigV4 서명 |
| Session Manager 로깅 예외 | port forwarding과 SSH 세션은 로깅되지 않음 |
| Parameter Store Standard | 10,000개, 값 4 KB, policy 미지원 |
| Parameter Store Advanced | 100,000개, 값 8 KB, policy 지원, 다운그레이드 불가 |
| Parameter 버전 보관 | 최근 100개 |
| `GetCalendarState` | 초당 10 요청 |
| OpsItem | related resource 100개, key 128자, value 20 KB, runbook 기록 30일 |
| Incident Manager 초기 설정 | `Get prepared`, replication set, contact와 escalation plan, response plan |
| Incident Manager replication set | 최소 2개 리전 구성을 권장 |
| Change Manager 신규 고객 | 2025-11-07부터 가입 불가, 기존 고객은 계속 사용 |

**배포와 IaC**

| 항목 | 값 |
| :--- | :--- |
| Beanstalk 배포 정책 | All at once, Rolling, Rolling with an additional batch, Immutable, Traffic splitting |
| Rolling 계열 미지원 환경 | single-instance |
| Traffic splitting 요구 | Application Load Balancer 환경 |
| DNS 변경이 필요한 방식 | Blue/Green |
| CodeDeploy EC2/On-Premises 기본 | `CodeDeployDefault.OneAtATime` |
| NLB를 쓰는 ECS blue/green | `ECSAllAtOnce`만 지원 |
| ECS blue/green 요구 | production listener 1개, target group 2개 |
| ECS blue/green 스케일링 대기 | 최대 1시간, 배포 중 이벤트 시 5분 |
| CodePipeline action 유형 | source, build, test, deploy, approval, invoke |
| Image Builder workflow | build, test, distribution 고정 순서 |
| Image Builder workflow 수 | image 또는 pipeline당 최대 10개 |
| Service Catalog constraint | launch, notification, template |
| `DeletionPolicy` 값 | `Delete`, `Retain`, `RetainExceptOnCreate`, `Snapshot` |
| RDS DBCluster 기본 DeletionPolicy | `Snapshot` |
| 교체 경로에 적용되는 속성 | `UpdateReplacePolicy` |
| change set 실행 시 | 같은 스택의 나머지 change set이 전부 삭제된다 |
| drift 판정 대상 | 명시적으로 설정한 속성만, 기본값 제외 |
| drift 미판정 속성 | 모든 리소스의 `KMSKeyId` |
| 중첩 스택 drift | 부모 스택 실행에 포함되지 않는다 |

**AWS Health**

| 항목 | 값 |
| :--- | :--- |
| Health Dashboard와 EventBridge 수신 | 모든 고객, 추가 비용 없음 |
| Health API | Business Support+, Enterprise Support, Unified Operations |

---

## 17. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| subscription filter 대 S3 export task | subscription은 실시간 스트림이고 대상은 네 가지다. export는 준비까지 최대 12시간이 걸리고 계정당 동시 task가 1개이며 AWS가 상시 아카이빙 용도로 권하지 않는다 |
| metric filter 대 EMF 대 `PutMetricData` | metric filter는 로그 발행 코드를 못 고칠 때 쓴다. EMF는 `logs:PutLogEvents` 권한만으로 메트릭을 만들고 원본 로그가 남는다. `PutMetricData`는 별도 API 호출과 `cloudwatch:PutMetricData` 권한이 필요하다 |
| EMF dimension 대 Contributor Insights | 고카디널리티 축을 EMF dimension으로 올리면 조합마다 커스텀 메트릭이 생겨 과금이 폭증한다. 상위 기여자를 찾는 자리는 Contributor Insights이고 매칭된 로그 이벤트 수로 과금한다 |
| Application Signals 대 X-Ray sampling | Application Signals는 서비스 단위 표준 메트릭과 topology와 SLO를 만든다. X-Ray sampling은 trace를 저장할 비율을 정하며 진입 서비스의 결정이 하위로 전파된다 |
| Transaction Search 대 X-Ray trace 검색 | Transaction Search는 span 원본을 `aws/spans` 로그 그룹에서 속성으로 검색한다. X-Ray trace 검색은 sampling된 trace summary 중심이라 모든 span을 보려면 Transaction Search를 별도로 켠다 |
| CloudWatch RUM 대 Synthetics canary | RUM은 실제 사용자 세션의 client-side 성능과 오류를 수집한다. canary는 스크립트가 외부에서 주기적으로 요청해 트래픽이 없어도 경로를 검증한다 |
| Container Insights 대 raw EMF | Container Insights는 컨테이너 성능 로그를 EMF로 수집해 cluster, node, pod, task, service 집계와 대시보드를 만든다. raw EMF는 애플리케이션이 원하는 메트릭과 dimension을 직접 정의한다 |
| metric alarm 대 composite alarm | composite alarm은 SNS와 OpsItem과 incident까지만 만든다. EC2 action과 Auto Scaling action은 metric alarm만 실행할 수 있고 cross-account composite alarm은 없다 |
| 알람 action 대 Auto Scaling action | 일반 action은 상태 전이 때 1회 실행된다. Auto Scaling action만 새 상태를 유지하는 동안 분당 반복한다 |
| `missing` 대 `notBreaching` 대 `ignore` | `missing`은 데이터가 전부 없으면 INSUFFICIENT_DATA로 간다. `notBreaching`은 OK를 유지한다. `ignore`는 직전 상태를 유지한다. 기본값은 `missing`이고 `AWS/DynamoDB`만 `ignore`다 |
| metric stream 대 `GetMetricData` 폴링 | stream은 Firehose로 push하고 스트림 개수 제한이 없다. 폴링은 계정당 리전당 500 rps 쿼터와 지연을 늘린다 |
| cross-account observability 대 cross-account 대시보드 | 전자는 sink와 link로 metric, log, trace를 monitoring account에서 직접 조회하고 Logs Insights를 계정 가로질러 실행한다. 범위는 Region 내부다. 후자는 콘솔 조회 편의 기능이고 계정 가로지르는 Logs Insights 실행은 못 한다 |
| CloudTrail Event history 대 trail 대 Lake | Event history는 90일이고 management event만이며 무료다. trail은 S3 장기 보존과 CloudWatch Logs 전달, digest 기반 무결성 검증을 제공한다. Lake는 SQL 쿼리와 최대 3,653일 보존을 주되 쿼리 결과는 7일만 남는다 |
| Config rule 대 CloudTrail 대 CloudWatch alarm | Config는 구성 상태를 평가하고, CloudTrail은 누가 어떤 API를 호출했는지 기록하며, alarm은 수치 임계 초과를 감지한다. "비준수 구성 발견 시 자동 교정"은 Config rule과 SSM Automation 조합이 유일하다 |
| Config proactive 대 detective | proactive는 배포 전 평가만 하고 차단도 교정도 하지 않는다. 교정 경로는 detective 평가의 NON_COMPLIANT에서만 이어진다 |
| Config aggregator 대 organization Config rule | aggregator는 read-only 집계다. 조직 전체에 rule을 배포하려면 organization Config rule 또는 conformance pack이다 |
| Config continuous 대 daily recording | daily는 24시간 최종 상태를 직전과 다를 때만 전달해 비용을 줄인다. Firewall Manager는 continuous에 의존하고, service-linked recorder와 겹치면 더 높은 빈도가 우선한다 |
| Run Command 대 State Manager 대 Automation | Run Command는 일회성 명령이다. State Manager는 원하는 상태를 스케줄로 재적용해 drift를 되돌린다. Automation은 AWS 리소스 수준 다단계 작업이고 승인 단계와 rate control을 가진다 |
| OpsCenter 대 Incident Manager | OpsCenter는 알람과 구성 정보를 OpsItem이라는 조사 단위로 묶는다. Incident Manager는 response plan으로 응답자, escalation, 협업 채널과 Automation runbook을 시작한다 |
| Change Calendar 대 Change Manager | Change Calendar는 실행 가능 시간의 open 또는 closed 상태를 제공한다. Change Manager는 그 달력과 승인자, template, CloudWatch alarm을 묶어 운영 변경을 실행한다 |
| Quick Setup patch policy 대 Host Management | patch policy는 Organizations 연동으로 다계정 다리전 스캔과 설치를 한다. Host Management는 스캔과 준수 보고만 하고 설치하지 않는다 |
| maintenance window task 대 patch policy | maintenance window task와 Patch now는 단일 account와 Region 쌍만 대상으로 한다. 여러 OU와 리전을 한 번에 덮는 것은 patch policy다 |
| Parameter Store Standard 대 Advanced | Standard는 10,000개와 4 KB이고 parameter policy와 계정 간 공유를 지원하지 않는다. Advanced는 100,000개와 8 KB이고 둘 다 지원하되 과금되며 다운그레이드할 수 없다 |
| Parameter Store 대 Secrets Manager | Parameter Store는 정적 구성 값이고 교체 기능이 없다. 자격 증명처럼 자동 교체와 교차 리전 복제가 필요한 값은 Secrets Manager다 |
| `DeletionPolicy` 대 `UpdateReplacePolicy` | 전자는 스택 삭제와 템플릿에서 리소스가 빠지는 업데이트에 적용된다. 업데이트 중 물리 리소스 교체에는 후자가 필요하다 |
| `Retain` 대 `RetainExceptOnCreate` | `RetainExceptOnCreate`는 생성 스택 작업이 롤백될 때만 삭제하고 그 외에는 Retain처럼 동작한다. 실패한 첫 배포가 빈 리소스를 남기는 문제를 푼다 |
| change set 대 drift detection | change set은 앞으로 실행할 변경의 예상 결과를 보여준다. drift detection은 이미 CloudFormation 밖에서 일어난 변경을 찾는다. 둘 다 수동 실행이다 |
| Beanstalk Rolling 대 Immutable 대 Blue/Green | Rolling은 기존 인스턴스에 배포하므로 실패 시 배치 하나가 서비스에서 빠지고 수동 재배포로만 되돌린다. Immutable은 두 번째 Auto Scaling group을 띄우고 롤백이 새 인스턴스 종료로 끝난다. Blue/Green은 환경이 둘이고 URL swap이라 DNS 변경이 필요하다 |
| CodeDeploy canary 대 linear 대 all-at-once | canary는 첫 증분 후 대기했다가 나머지를 전량 옮기는 두 번의 증분이다. linear는 동일 비율을 동일 간격으로 반복한다. all-at-once는 한 번에 전량이다 |
| CodeDeploy EC2 구성 대 Lambda와 ECS 구성 | EC2/On-Premises 사전 정의 구성은 AllAtOnce, HalfAtATime, OneAtATime 셋뿐이다. canary와 linear는 Lambda와 ECS에만 있다 |
| ALB 뒤의 ECS 대 NLB 뒤의 ECS | ALB면 canary와 linear를 쓸 수 있다. NLB면 `ECSAllAtOnce`만 지원하므로 점진 이동 자체가 없다 |
| CodePipeline와 CodeBuild 대 CodeDeploy | CodePipeline은 stage와 action으로 source, build, test, approval, deploy 흐름을 조정하고 CodeBuild는 빌드와 테스트 artifact를 만든다. CodeDeploy는 준비된 artifact를 EC2, Lambda, ECS에 배포하고 트래픽 이동을 관리한다 |
| EC2 Image Builder 대 user data | Image Builder는 recipe와 component를 테스트한 AMI 또는 container image를 반복 생성하고 여러 리전에 배포한다. user data는 인스턴스 시작 시점의 개별 초기화라 이미지 공급망 검증을 대신하지 못한다 |
| Service Catalog 대 CodePipeline | Service Catalog는 승인된 CloudFormation 또는 Terraform product와 portfolio, constraint를 셀프서비스로 제공한다. CodePipeline은 소스 변경을 build, test, deploy stage로 흘려보내는 지속적 전달 도구다 |
| SLI 대 SLO 대 SLA | SLI는 실제 측정값, SLO는 내부 목표, SLA는 계약과 보상이다. SLO를 SLA보다 엄격하게 두어야 계약 위반 전에 대응할 시간이 생긴다 |
| Health Dashboard 대 Health API | Dashboard 조회와 EventBridge 수신은 모든 고객이 추가 비용 없이 쓴다. API 호출은 Business Support+ 이상이 필요하다 |

---

## 18. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| 결측 처리를 그대로 두었으니 데이터가 끊겨도 알람이 OK에 남는다 | 기본값은 `missing`이라 evaluation range가 전부 비면 INSUFFICIENT_DATA로 간다. OK를 유지하려면 `notBreaching`을 명시한다 |
| 결측 처리를 `breaching`으로 두면 정상 구간에서도 알람이 민감해진다 | 결측 처리 설정은 실제 데이터포인트가 evaluation periods보다 적을 때만 쓰인다. 충분하면 무시된다 |
| M out of N 알람이라 breaching이 M개 미만이면 ALARM으로 가지 않는다 | 가장 오래된 breaching이 datapoints to alarm 값만큼 오래됐고 이후가 breaching이나 missing뿐이면 ALARM으로 간다 |
| composite alarm에 Auto Scaling action을 API로 붙인다 | 콘솔 제약이 아니라 서비스 제약이다. composite alarm은 EC2 action과 Auto Scaling action을 가질 수 없다 |
| cross-account 알람에서 anomaly detection band로 판단한다 | `ANOMALY_DETECTION_BAND`는 cross-account 알람에서 지원되지 않고 cross-account composite alarm도 없다 |
| 알람 action으로 Lambda를 붙여 지속 확장을 만든다 | 알람 action은 상태 전이 때 1회 실행된다. 분당 반복 실행되는 것은 Auto Scaling action뿐이다 |
| 고해상도 커스텀 메트릭에 1분 알람을 걸어 초 단위로 감지한다 | 초 단위 감지는 period 10초 또는 30초의 고해상도 알람이어야 한다 |
| 야간 배치가 집계한 값을 아침에 `PutMetricData`로 올려 알람을 건다 | 타임스탬프는 과거 2주까지 허용되지만 알람은 현재 UTC 기준으로 평가한다. INSUFFICIENT_DATA가 뜨거나 평가가 지연된다 |
| 커스텀 메트릭을 두 dimension으로 발행했으니 하나만으로도 집계된다 | 커스텀 메트릭은 dimension을 가로질러 자동 집계되지 않는다. 필요한 조합을 직접 발행해야 한다 |
| 6개월 전 1분 단위 메트릭으로 추이를 분석한다 | 60초 period 데이터는 15일 뒤 더 긴 period로 집계된다. 원본 해상도는 남지 않는다 |
| 요청 ID를 EMF dimension으로 올려 요청별로 추적한다 | 조합마다 커스텀 메트릭이 생성돼 과금이 폭증한다. 고카디널리티 축은 Contributor Insights가 자리다 |
| 하위 서비스에만 Application Signals를 켜면 진입 trace의 sampling 비율도 올라간다 | Application Signals의 서비스 지표와 X-Ray sampling은 별개다. parent trace의 sampling 결정은 진입 서비스에서 이미 내려진다 |
| X-Ray sampling을 100퍼센트로 올리면 과거 거래의 모든 span도 검색된다 | sampling 설정은 이후 trace 수집에만 영향을 준다. 과거 원본 span 검색은 Transaction Search와 `aws/spans` 보관을 별도로 준비해야 한다 |
| CloudWatch RUM이 서버 API의 CPU와 메모리를 수집한다 | RUM은 실제 사용자 세션의 client-side 신호를 수집한다. 서버 자원은 CloudWatch agent나 Container Insights 같은 별도 경로다 |
| Container Insights를 켜면 가능한 모든 세부 메트릭이 자동 생성된다 | 비용을 줄이기 위해 일부 집계만 자동 생성한다. 추가 축과 원본은 performance log를 Logs Insights로 조회한다 |
| 로그 그룹 하나에 팀 수만큼 subscription filter를 붙인다 | 로그 그룹당 5개이고 조정 불가다. 스트림 하나로 모아 팬아웃한다 |
| subscription filter 한도를 Service Quotas에서 증설한다 | 조정 불가 쿼터라 증설 요청 대상이 아니다 |
| S3 export를 매시간 돌려 준실시간 분석을 만든다 | 준비까지 최대 12시간이 걸리고 계정당 동시 task가 1개다 |
| cross-account observability로 다른 리전의 source account 데이터를 본다 | 링크는 Region 내부에서 동작한다. 리전을 가로지르려면 다른 설계가 필요하다 |
| monitoring account에서 telemetry 유형을 다시 저장하면 로그가 넘어온다 | 공유 범위는 양쪽 선택의 교집합이다. source account 쪽 설정을 넓혀야 한다 |
| 계정마다 sink를 추가로 만들어 연결을 늘린다 | sink는 계정당 리전당 1개다 |
| CloudTrail Event history로 6개월 전 S3 객체 접근을 조사한다 | Event history는 90일이고 data event를 담지 않는다 |
| CloudTrail 로그를 S3에 저장했으니 변조되지 않았음을 증명할 수 있다 | log file integrity validation을 켜지 않았다면 digest 서명 체인이 없어 증명할 수 없다 |
| CloudTrail 이벤트를 트리거로 위험 API 호출을 즉시 차단한다 | 전달은 평균 약 5분이고 보장되지 않는다. 즉시 차단은 SCP나 리소스 정책 같은 사전 통제다 |
| proactive Config rule로 비준수 리소스 생성을 차단한다 | proactive 평가는 배포 전 평가만 한다. 차단은 SCP나 CloudFormation Hooks가 필요하다 |
| Config를 daily recording으로 바꿔 비용을 아끼면서 Firewall Manager로 실시간 통제한다 | Firewall Manager는 continuous recording에 의존한다 |
| 집계 계정의 Config aggregator에서 조직 전체에 rule을 배포한다 | aggregator는 read-only다 |
| Config 자동 교정을 켰으니 비준수 리소스에만 정확히 실행된다 | 교정은 주기적 compliance 스냅샷 기준이라 이미 준수 상태가 된 리소스에도 실행될 수 있다. runbook은 멱등해야 한다 |
| conformance pack을 여러 개 배포해도 rule 한도와 무관하다 | pack 안의 rule도 리전당 계정당 1,000개 한도에 포함된다 |
| 하위 마이크로서비스에 100퍼센트 sampling rule을 걸어 그 서비스만 전량 추적한다 | sampling은 parent-based라 진입 서비스의 결정이 하위로 전파된다 |
| 하위 서비스 rule의 priority를 1로 낮춰 진입 결정을 이긴다 | priority는 같은 서비스 안의 rule 평가 순서를 정할 뿐이다 |
| EventBridge rule 하나에 target을 10개 붙여 팬아웃한다 | rule당 target 5개는 조정 불가다. SNS 토픽이나 추가 rule로 나눈다 |
| Business 플랜 없이 Health API로 이벤트를 프로그램에서 가져온다 | API는 Business Support+ 이상이 필요하다. EventBridge 수신은 무료다 |
| OpsCenter만 구성하면 온콜 담당자와 escalation이 자동으로 시작된다 | OpsCenter는 OpsItem 조사 단위다. 응답자 호출과 runbook 시작은 Incident Manager response plan이 담당한다 |
| Incident Manager incident를 바로 만들고 나중에 replication set을 추가한다 | 처음 사용하기 전 `Get prepared`로 replication set과 contact, escalation plan, response plan을 설정해야 한다 |
| Session Manager로 열었으니 port forwarding 세션의 명령도 감사 로그에 남는다 | port forwarding과 SSH 세션은 데이터가 SSH의 TLS 터널 안에 있어 로깅되지 않는다 |
| Fleet Manager association을 만들면 파일 설정이 매일 원래 값으로 돌아온다 | Fleet Manager는 managed node를 조회하고 관리하는 UI다. 반복 상태 적용은 State Manager association이다 |
| 2026년에 새 AWS 계정에서 Change Manager를 CI/CD release gate로 켠다 | 2025-11-07부터 새 고객 가입이 닫혔고, 문서도 자동 release 과정 대신 예외 승인 운영 변경에 사용하도록 구분한다 |
| Patch Manager로 Windows Server 2016을 2019로 올린다 | OS 메이저 버전 업그레이드를 지원하지 않는다 |
| Quick Setup Host Management로 조직 전체 패치를 설치한다 | 스캔과 준수 보고만 하고 설치하지 않는다. 설치는 patch policy다 |
| maintenance window task로 여러 계정과 리전을 한 번에 패치한다 | maintenance window task와 Patch now는 단일 account와 Region 쌍만 대상으로 한다 |
| Organizations delegated administrator에서 Quick Setup 조직 patch policy를 만든다 | 조직용 patch policy 생성은 management account에서만 가능하고 delegated administrator와 member account는 사용할 수 없다 |
| Standard tier 파라미터에 만료 알림 policy를 건다 | parameter policy는 Advanced tier에서만 지원한다 |
| Advanced tier로 올렸다가 비용 때문에 Standard로 되돌린다 | Advanced 파라미터는 다운그레이드할 수 없다 |
| `DeletionPolicy: Retain`이면 업데이트로 교체돼도 원본이 남는다 | 교체에는 `DeletionPolicy`가 적용되지 않고 `UpdateReplacePolicy`가 필요하다 |
| `DeletionPolicy`를 `Snapshot`으로 바꾸면 교체 사고를 막는다 | `Snapshot`도 `DeletionPolicy` 값이라 교체 경로에는 적용되지 않는다 |
| change set을 검토하고 실행했으니 실패하지 않는다 | custom resource 로직과 서비스별 런타임 제약은 실행 시점에 실패할 수 있다 |
| change set 여러 개를 만들어 두고 하나씩 차례로 실행한다 | 하나를 실행하면 그 스택의 나머지 change set이 전부 삭제된다 |
| 부모 스택에 drift detection을 돌리면 중첩 스택 drift도 잡힌다 | 중첩 스택은 포함되지 않는다. 직접 실행해야 한다 |
| 템플릿에 안 적은 속성을 밖에서 바꿔도 drift로 잡힌다 | 명시적으로 설정한 속성 값만 판정 대상이고 기본값은 포함되지 않는다 |
| single-instance Beanstalk 환경에 Rolling 배포를 걸어 무중단으로 만든다 | Rolling과 Rolling with an additional batch는 load-balanced 환경 전용이다 |
| Beanstalk Immutable 배포는 DNS 변경이 필요하다 | DNS 변경이 필요한 쪽은 Blue/Green이다. Immutable은 같은 환경 안에서 두 번째 Auto Scaling group을 쓴다 |
| Immutable로 바꿔도 T 계열 인스턴스의 버스트 크레딧은 유지된다 | 인스턴스를 전부 교체하므로 누적된 EC2 burst balance가 사라진다 |
| EC2/On-Premises CodeDeploy에서 canary 10퍼센트 사전 정의 구성을 고른다 | canary와 linear 사전 정의 구성은 Lambda와 ECS 쪽에만 있다 |
| NLB 뒤의 ECS 서비스에 커스텀 구성으로 canary를 만든다 | NLB 제약은 배포 방식 자체의 제약이라 커스텀 구성으로도 점진 이동을 만들 수 없다 |
| ECS 서비스를 `DAEMON` 전략으로 바꿔 blue/green 배포 단위를 줄인다 | Fargate와 `CODE_DEPLOY` 컨트롤러는 `DAEMON` 스케줄링 전략을 지원하지 않는다 |
| CodeBuild가 stage 순서와 수동 승인을 모두 관리한다 | CodeBuild는 컴파일, 테스트, artifact 생성 역할이고 stage와 approval 전환은 CodePipeline이 관리한다 |
| Image Builder로 만든 AMI가 자동으로 애플리케이션 트래픽을 canary 이동한다 | Image Builder는 이미지 build, test, distribution 공급망이다. 런타임 트래픽 이동은 CodeDeploy나 ECS 배포가 담당한다 |
| Service Catalog portfolio를 만들면 소스 커밋마다 product가 자동 배포된다 | Service Catalog는 승인된 product와 launch, notification, template constraint를 셀프서비스로 제공하고 지속 배포는 CodePipeline 영역이다 |

---

## 19. 예상 문제 10문항

**Q1.** 하나의 애플리케이션 log group을 보안팀, SRE팀, 데이터팀, 사기탐지팀, 결제팀이 각각 subscription filter로 구독하고 있습니다. 여섯 번째 팀이 자체 분석 파이프라인을 붙이려 하자 filter 생성이 실패합니다. 애플리케이션은 로그를 이 log group 하나에만 쓰며, 로그 사본을 여러 벌 만드는 비용은 피해야 합니다. MOST appropriate 조치는 무엇입니까?

- A. subscription filter 하나로 Kinesis Data Streams에 보내고 각 팀이 그 스트림에서 소비하도록 팬아웃한다
- B. Service Quotas에서 log group당 subscription filter 한도 증설을 요청한다
- C. 팀 수만큼 log group을 만들고 애플리케이션이 모든 log group에 로그를 쓰게 한다
- D. 여섯 번째 팀에는 S3 export task를 매시간 실행해 데이터를 전달한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

로그 그룹당 subscription filter는 5개이고 이 한도는 조정할 수 없습니다. 팬아웃이 더 필요하면 하나의 스트림으로 모아 소비자를 그 위에 두는 구조로 바꿔야 합니다. Kinesis Data Streams는 여러 소비자가 같은 데이터를 독립적으로 읽을 수 있어 로그 사본을 늘리지 않습니다.

- B가 틀린 이유: log group당 subscription filter 5개는 조정 불가 quota다. 증설 요청 대상이 아니다.
- C가 틀린 이유: 로그를 팀 수만큼 중복 저장하게 되어 수집과 보관 비용이 배로 늘고 애플리케이션 코드 변경도 필요하다. 비용을 피하라는 제약과 충돌한다.
- D가 틀린 이유: S3 export는 데이터가 export 가능해지기까지 최대 12시간이 걸리고 계정당 동시 실행 task가 1개로 조정 불가다. 매시간 실행하는 구성이 성립하지 않는다.

</details>

**Q2.** 12개 계정, 3개 리전에 흩어진 애플리케이션 로그가 각 계정의 CloudWatch Logs에 쌓입니다. 보안팀은 중앙 계정에서 모든 로그를 5분 이내에 검색할 수 있어야 한다고 요구합니다. 현재는 야간 S3 export task로 모으고 있어 데이터가 최대 반나절 늦게 보입니다. 로그 원본은 각 계정에 그대로 남아야 하고 인스턴스에 새 에이전트를 설치할 수는 없습니다. MOST appropriate 아키텍처는 무엇입니까?

- A. 각 계정 log group에 subscription filter를 걸어 중앙 계정의 Kinesis Data Streams로 보내고, Data Firehose로 OpenSearch Service에 적재한다
- B. S3 export task 실행 주기를 15분으로 줄이고 Athena로 조회한다
- C. 중앙 계정을 monitoring account로 만들고 CloudWatch cross-account observability로 링크한 뒤 Logs Insights로 조회한다
- D. 각 계정에서 Logs Insights 쿼리를 스케줄 실행해 결과를 중앙 S3 버킷에 적재한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

subscription filter는 로그를 near-real-time으로 밀어내는 경로이고 대상은 Kinesis Data Streams, Lambda, Data Firehose, OpenSearch Service 넷입니다. 교차 계정 교차 리전 구독에서 log group과 destination은 같은 리전에 있어야 하지만 destination이 가리키는 실제 리소스는 다른 리전에 둘 수 있습니다. 따라서 리전마다 destination을 하나씩 만들고 세 destination이 모두 중앙 계정의 같은 스트림을 가리키게 하면 12개 계정 3개 리전 요구를 한 파이프라인으로 덮습니다.

- B가 틀린 이유: export는 데이터가 export 가능해지기까지 최대 12시간이 걸리고 계정당 동시 task가 1개다. 주기를 줄여도 지연 자체가 줄지 않고, AWS 문서도 상시 아카이빙 용도로 정기 export를 권하지 않는다.
- C가 틀린 이유: cross-account observability의 링크는 Region 내부에서 동작한다. 3개 리전을 한 번에 조회할 수 없어 요구 범위를 덮지 못한다.
- D가 틀린 이유: 쿼리를 미리 정해두어야 하므로 임의 검색이 불가능하고, 계정당 동시 쿼리 100개 제한과 결과 7일 보존 제약도 걸린다.

</details>

**Q3.** SRE팀이 CPU 사용률, 요청 큐 길이, 응답 지연 세 메트릭이 동시에 임계를 넘을 때만 Auto Scaling group을 확장하도록 만들려 합니다. 세 알람을 묶은 composite alarm을 만들었지만 Auto Scaling action을 연결하려 하자 선택지가 나타나지 않습니다. LEAST operational overhead로 요구를 구현하는 방법은 무엇입니까?

- A. metric math로 세 메트릭을 하나의 식으로 결합한 metric alarm을 만들고 그 알람에 Auto Scaling policy를 연결한다
- B. API로 composite alarm에 Auto Scaling action을 직접 붙인다
- C. composite alarm이 SNS를 통해 Lambda를 호출하고 그 Lambda가 `SetDesiredCapacity`를 실행한다
- D. 세 개의 metric alarm 각각에 같은 Auto Scaling policy를 연결한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

composite alarm은 SNS 알림과 investigation, OpsItem, incident 생성을 할 수 있지만 EC2 action과 Auto Scaling action은 실행할 수 없습니다. AND 조건을 유지하면서 Auto Scaling을 트리거하려면 metric math로 조건을 하나의 메트릭 식으로 만들고 그 위에 metric alarm을 세우는 방법이 표준입니다.

- B가 틀린 이유: 콘솔 제약이 아니라 서비스 제약이다. composite alarm은 API로도 Auto Scaling action을 가질 수 없다.
- C가 틀린 이유: 스케일링 정책 대신 커스텀 코드를 유지해야 한다. 게다가 알람 action은 상태가 바뀔 때만 실행되고 분당 반복 실행되는 예외는 Auto Scaling action에만 적용되므로, 부하가 지속되는 동안 추가 확장이 일어나지 않는다.
- D가 틀린 이유: 세 알람 중 하나만 울려도 확장되는 OR 조건이 되어 요구한 AND 조건과 다르다.

</details>

**Q4.** 요청은 진입 서비스 A를 거쳐 B, C 순으로 흐릅니다. C 팀이 자기 서비스의 지연 문제를 조사하려고 X-Ray 콘솔에 C의 요청에만 매칭되는 sampling rule을 만들고 fixed rate를 100퍼센트로 설정했습니다. 그런데도 C의 trace는 여전히 전체의 약 5퍼센트만 수집됩니다. A와 B의 코드는 다른 팀 소유라 변경 요청에 몇 주가 걸립니다. MOST appropriate 조치는 무엇입니까?

- A. 진입 서비스 A의 요청에 매칭되는 sampling rule을 만들어 수집 비율을 올린다
- B. C의 인스턴스에 로컬 JSON sampling rule 파일을 두고 reservoir를 크게 설정한다
- C. C에 만든 rule의 priority를 1로 낮춰 다른 rule보다 먼저 평가되게 한다
- D. C의 CloudWatch agent가 사용하는 sampling proxy 포트를 TCP 2000에서 변경한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

X-Ray sampling은 parent-based입니다. trace의 진입 서비스가 한 번 결정하면 하위 서비스는 자신의 rule과 무관하게 그 결정을 따릅니다. 따라서 하위 서비스에만 rule을 걸어도 적용되지 않고, 수집 비율을 올리려면 진입 지점의 rule을 바꿔야 합니다. 기본 rule은 reservoir 1에 fixed rate 5퍼센트라는 값이 관측된 5퍼센트와 일치합니다.

- B가 틀린 이유: 로컬 rule은 인스턴스마다 독립적으로 sampling한다는 차이를 만들 뿐 parent 결정을 뒤집지 못한다.
- C가 틀린 이유: priority는 같은 서비스 안에서 여러 rule을 평가하는 순서를 정한다. 진입 서비스의 결정을 무시하게 만들지 못한다.
- D가 틀린 이유: TCP 2000은 SDK가 sampling API를 호출할 때 쓰는 proxy 기본 포트다. 포트 변경은 sampling 비율과 무관하다.

</details>

**Q5.** 조직 전체에서 0.0.0.0/0에 TCP 22를 연 security group을 자동으로 닫아야 합니다. 이미 존재하는 위반도 정리해야 하고, 감사인은 위반 발생 시점과 교정 실행 결과가 기록으로 남기를 요구합니다. 커스텀 코드 유지 부담은 최소화해야 합니다. 대상은 60개 계정이고 앞으로 만들어질 계정도 자동으로 포함되어야 합니다. LEAST operational overhead로 요구를 만족하는 방법은 무엇입니까?

- A. Config managed rule을 organization Config rule로 배포하고 SSM Automation document를 자동 remediation으로 연결한다
- B. 같은 Config rule을 proactive evaluation mode로 배포해 비준수 security group 생성을 차단한다
- C. EventBridge로 `AuthorizeSecurityGroupIngress` API 호출을 잡아 Lambda가 규칙을 되돌리게 한다
- D. 집계 계정에 Config aggregator를 만들고 그 계정에서 rule과 remediation을 배포한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Config rule은 리소스 구성 상태를 평가하므로 이미 존재하는 위반도 detective 평가로 잡아냅니다. Config remediation은 SSM Automation document로 실행되며 AWS 관리형 automation document를 그대로 연결할 수 있어 커스텀 코드가 없습니다. 평가 결과와 remediation 실행 기록이 모두 남아 감사 요구도 만족합니다.

- B가 틀린 이유: proactive evaluation은 배포 전 평가만 수행한다. NON_COMPLIANT 자원을 교정하지도 배포를 막지도 않는다. 차단이 필요하면 SCP 같은 다른 통제가 필요하다.
- C가 틀린 이유: API 호출을 트리거로 삼으므로 이미 존재하는 위반을 잡지 못하고, Lambda 코드를 조직 전체에 배포하고 유지해야 한다.
- D가 틀린 이유: Config aggregator는 read-only 집계 도구다. aggregator를 통해 source 계정에 rule을 배포하거나 remediation을 실행할 수 없다.

</details>

**Q6.** 수백 대의 EC2 인스턴스에서 CloudWatch agent 설정 파일이 담당자 손에 의해 수시로 변경되어 일부 인스턴스의 메트릭이 누락됩니다. 팀은 매일 원하는 설정 상태를 다시 적용하고, 어떤 인스턴스가 적용에 실패했는지 준수 상태로 확인하려 합니다. 인스턴스는 3개 리전에 흩어져 있고 SSM Agent는 이미 설치되어 있습니다. LEAST operational overhead로 요구를 만족하는 방법은 무엇입니까?

- A. State Manager association을 만들어 원하는 상태를 스케줄에 맞춰 반복 적용한다
- B. EventBridge Scheduler가 매일 Run Command를 호출해 설정 파일을 배포한다
- C. Automation runbook을 rate control로 실행해 인스턴스를 순회하며 설정을 적용한다
- D. 설정을 포함한 AMI를 다시 만들고 인스턴스를 교체한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

State Manager association은 원하는 상태를 스케줄로 재적용해 drift를 되돌리는 기능입니다. cron과 rate 표현식을 쓰고 대상은 태그, Resource Groups, 노드 ID로 지정하며 association 단위로 준수 상태를 보여줍니다. State Manager 자체에는 추가 요금이 없습니다.

- B가 틀린 이유: Run Command는 일회성 명령 실행이다. 스케줄과 대상 관리, 준수 집계를 직접 구성해야 하므로 운영 부담이 더 크다.
- C가 틀린 이유: Automation은 AWS 리소스 수준의 다단계 작업을 위한 도구다. 노드 내부 파일 상태를 지속 유지하는 용도로는 과하다.
- D가 틀린 이유: 수백 대를 교체하는 비용과 위험이 크고, 사람이 다시 설정을 바꾸면 같은 문제가 재발한다. 상태 유지 메커니즘이 없다.

</details>

**Q7.** AWS Organizations에 3개 OU와 5개 리전이 있고 Linux와 Windows 노드가 섞여 있습니다. 매달 정해진 창에 승인된 패치를 설치하고 준수 보고를 중앙에서 봐야 합니다. 팀은 Quick Setup의 Host Management를 켜 두었는데 준수 상태만 보이고 패치가 설치되지 않습니다. MOST appropriate 조치는 무엇입니까?

- A. Quick Setup에서 patch policy를 만들어 대상 OU와 리전에 배포한다
- B. Host Management 구성에서 패치 설치 옵션을 활성화한다
- C. 리전마다 maintenance window를 만들고 Run Command task로 Patch Manager를 실행한다
- D. 매달 Patch now를 스케줄 실행해 모든 계정과 리전을 순회한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

Quick Setup의 patch policy는 AWS가 권장하는 실행 방법이며 Organizations 연동으로 다계정 다리전 패치를 한 번에 구성합니다. 스캔과 설치, 준수 보고를 함께 다룹니다.

- B가 틀린 이유: Quick Setup Host Management 옵션은 스캔과 준수 보고만 수행하고 패치를 설치하지 않는다. 설치 옵션 자체가 없다.
- C가 틀린 이유: maintenance window task는 단일 account와 Region 쌍만 대상으로 한다. 계정 수와 5개 리전 조합만큼 별도 구성을 만들고 유지해야 한다.
- D가 틀린 이유: Patch now는 온디맨드 실행이고 역시 단일 account와 Region 쌍을 대상으로 한다. 정해진 창에 맞춘 반복 실행 구조가 아니다.

</details>

**Q8.** Network Load Balancer 뒤에서 동작하는 ECS on Fargate 서비스를 CodeDeploy blue/green으로 배포하려 합니다. 팀은 트래픽을 10퍼센트 옮긴 뒤 15분 관찰하고 나머지를 옮기는 방식을 원하는데, `CodeDeployDefault.ECSCanary10Percent15Minutes`를 지정하자 배포 생성이 실패합니다. MOST appropriate 대응은 무엇입니까?

- A. 로드밸런서를 Application Load Balancer로 바꿔 canary 구성을 쓰거나, NLB를 유지하려면 all-at-once로 배포하고 CloudWatch 알람 기반 자동 롤백을 설정한다
- B. 같은 비율과 대기 시간을 갖는 커스텀 deployment configuration을 만들어 지정한다
- C. `CodeDeployDefault.ECSLinear10PercentEvery3Minutes`로 바꿔 점진 배포한다
- D. 서비스의 스케줄링 전략을 `DAEMON`으로 바꿔 배포 단위를 줄인다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

CodeDeploy 기반 ECS blue/green에서 Network Load Balancer를 사용하면 `CodeDeployDefault.ECSAllAtOnce`만 지원됩니다. 점진 트래픽 이동이 필요하면 ALB로 바꾸는 것이 정공법이고, NLB를 유지해야 한다면 all-at-once 배포에 알람 기반 자동 롤백을 붙여 위험을 낮추는 것이 현실적인 대안입니다.

- B가 틀린 이유: NLB 제약은 사전 정의 구성에만 걸리는 것이 아니라 배포 방식 자체의 제약이다. 커스텀 구성으로도 점진 이동을 만들 수 없다.
- C가 틀린 이유: linear 구성 역시 NLB에서 지원되지 않는다. 같은 이유로 실패한다.
- D가 틀린 이유: Fargate와 `CODE_DEPLOY` 컨트롤러는 `DAEMON` 스케줄링 전략을 지원하지 않는다. 배포 실패 원인과도 무관하다.

</details>

**Q9.** CloudFormation으로 관리하는 RDS DB instance에 `DeletionPolicy: Retain`을 설정해 두었습니다. 그런데 `DBInstanceIdentifier`를 바꾸는 스택 업데이트를 실행하자 기존 인스턴스가 교체되면서 삭제됐습니다. 같은 사고를 막아야 하고, 스택 업데이트 자체는 계속 사용해야 합니다. MOST appropriate 조치는 무엇입니까?

- A. 리소스에 `UpdateReplacePolicy`를 `Retain` 또는 `Snapshot`으로 지정한다
- B. `DeletionPolicy`를 `Snapshot`으로 바꾼다
- C. 업데이트 전에 change set을 만들어 검토하는 절차를 표준화한다
- D. `DeletionPolicy`를 `RetainExceptOnCreate`로 바꾼다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

`DeletionPolicy`는 스택 삭제와 템플릿에서 리소스가 빠지는 업데이트에 적용됩니다. 업데이트 중 물리 리소스가 교체되는 경우에는 적용되지 않고 기존 리소스가 그대로 삭제됩니다. 이 경계를 메우는 속성이 `UpdateReplacePolicy`입니다.

- B가 틀린 이유: `Snapshot`도 `DeletionPolicy` 값이라 교체 경로에는 적용되지 않는다. 값을 바꿔도 같은 사고가 반복된다.
- C가 틀린 이유: change set은 교체 여부를 미리 보여주지만 삭제 자체를 막지 않는다. 절차만으로는 사람이 놓치는 경우를 방지하지 못한다.
- D가 틀린 이유: `RetainExceptOnCreate`는 생성 스택 작업이 롤백될 때만 리소스를 삭제하고 그 외에는 Retain처럼 동작하는 `DeletionPolicy` 값이다. 교체 경로에는 여전히 적용되지 않는다.

</details>

**Q10.** 단일 리전에 20개 계정이 있습니다. 중앙 운영 계정을 monitoring account로 지정하고 각 source account가 link를 만들었습니다. 운영팀은 여러 계정의 로그를 한 번의 Logs Insights 쿼리로 조회하고 X-Ray trace도 보려 했지만 메트릭만 보입니다. source account의 link는 metric만 공유하도록 설정되어 있고 monitoring account는 metric, log, trace를 선택했습니다. MOST appropriate 조치는 무엇입니까?

- A. 각 source account의 link 설정에서 공유 telemetry 유형에 로그와 X-Ray trace를 추가한다
- B. monitoring account의 sink 설정에서 telemetry 유형을 다시 저장한다
- C. 계정마다 별도의 sink를 monitoring account에 추가로 만든다
- D. monitoring account에서 모든 link를 해제한 뒤 monitoring account가 link를 다시 만든다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A**

source account가 monitoring account보다 적은 telemetry 유형을 선택하면 링크는 생성되지만 양쪽에서 함께 선택된 유형만 공유됩니다. 지금은 source 쪽이 metric만 선택했으므로 로그와 trace가 넘어오지 않습니다. source 쪽 설정을 넓히는 것이 유일한 해결입니다.

- B가 틀린 이유: monitoring account는 이미 세 유형을 선택했다. 공유 범위는 양쪽 선택의 교집합이므로 monitoring 쪽만 다시 저장해도 결과가 같다.
- C가 틀린 이유: sink는 계정당 리전당 1개다. 추가로 만들 수 없다.
- D가 틀린 이유: 링크 해제는 source account에서만 수행한다. 또 재생성하더라도 source의 telemetry 선택이 그대로면 같은 결과가 나온다.

</details>

---

## 20. Reference

- [Amazon CloudWatch - CloudWatch concepts](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html)
- [Amazon CloudWatch - Using Amazon CloudWatch alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- [Amazon CloudWatch - Configuring how CloudWatch alarms treat missing data](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html)
- [Amazon CloudWatch - Using CloudWatch anomaly detection](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Anomaly_Detection.html)
- [Amazon CloudWatch - Use metric streams](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Metric-Streams.html)
- [Amazon CloudWatch - Embedded metric format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html)
- [Amazon CloudWatch - Use synthetic monitoring canaries](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries.html)
- [Amazon CloudWatch - Application Signals](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Monitoring-Sections.html)
- [Amazon CloudWatch - Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Transaction-Search.html)
- [Amazon CloudWatch - CloudWatch RUM](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-RUM.html)
- [Amazon CloudWatch - Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html)
- [Amazon CloudWatch - CloudWatch cross-account observability](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Unified-Cross-Account.html)
- [Amazon CloudWatch - Use Contributor Insights to analyze high-cardinality data](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContributorInsights.html)
- [Amazon CloudWatch - CloudWatch service quotas](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_limits.html)
- [Amazon CloudWatch Logs - CloudWatch Logs quotas](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/cloudwatch_limits_cwl.html)
- [Amazon CloudWatch Logs - Real-time processing of log data with subscriptions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/SubscriptionFilters.html)
- [Amazon CloudWatch Logs - Cross-account cross-Region subscriptions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CrossAccountSubscriptions.html)
- [Amazon CloudWatch Logs - Exporting log data to Amazon S3](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/S3Export.html)
- [Amazon CloudWatch Logs - Analyzing log data with CloudWatch Logs Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html)
- [Amazon CloudWatch Logs - Creating metrics from log events using filters](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html)
- [AWS CloudTrail - CloudTrail concepts](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-concepts.html)
- [AWS CloudTrail - Validating CloudTrail log file integrity](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html)
- [AWS CloudTrail - Working with CloudTrail Lake](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html)
- [AWS Config - AWS Config concepts](https://docs.aws.amazon.com/config/latest/developerguide/config-concepts.html)
- [AWS Config - Managing the configuration recorder](https://docs.aws.amazon.com/config/latest/developerguide/stop-start-recorder.html)
- [AWS Config - Selecting which resources AWS Config records](https://docs.aws.amazon.com/config/latest/developerguide/select-resources.html)
- [AWS Config - Remediating noncompliant resources with AWS Config rules](https://docs.aws.amazon.com/config/latest/developerguide/remediation.html)
- [AWS Config - Setting up automatic remediation](https://docs.aws.amazon.com/config/latest/developerguide/setup-autoremediation.html)
- [AWS Config - Conformance packs](https://docs.aws.amazon.com/config/latest/developerguide/conformance-packs.html)
- [AWS Config - Service limits](https://docs.aws.amazon.com/config/latest/developerguide/configlimits.html)
- [AWS X-Ray - Configuring sampling rules](https://docs.aws.amazon.com/xray/latest/devguide/xray-console-sampling.html)
- [Amazon EventBridge - Amazon EventBridge quotas](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-quota.html)
- [AWS Systems Manager - AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [AWS Systems Manager - AWS Systems Manager Patch Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/patch-manager.html)
- [AWS Systems Manager - AWS Systems Manager Automation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-automation.html)
- [AWS Systems Manager - AWS Systems Manager State Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-state.html)
- [AWS Systems Manager - AWS Systems Manager Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/execute-remote-commands.html)
- [AWS Systems Manager - AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [AWS Systems Manager - AWS Systems Manager Change Calendar](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-change-calendar.html)
- [AWS Systems Manager - AWS Systems Manager OpsCenter](https://docs.aws.amazon.com/systems-manager/latest/userguide/OpsCenter.html)
- [AWS Systems Manager - Incident Manager getting started](https://docs.aws.amazon.com/incident-manager/latest/userguide/getting-started.html)
- [AWS Systems Manager - Incident Manager response plans](https://docs.aws.amazon.com/incident-manager/latest/userguide/response-plans.html)
- [AWS Systems Manager - Fleet Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/fleet-manager.html)
- [AWS Systems Manager - Change Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/change-manager.html)
- [AWS Systems Manager - Change Manager availability change](https://docs.aws.amazon.com/systems-manager/latest/userguide/change-manager-availability-change.html)
- [AWS Systems Manager - Quick Setup patch policy](https://docs.aws.amazon.com/systems-manager/latest/userguide/quick-setup-patch-manager.html)
- [AWS Elastic Beanstalk - Deploying a new application version](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features.deploy-existing-version.html)
- [AWS CodePipeline - CodePipeline concepts](https://docs.aws.amazon.com/codepipeline/latest/userguide/concepts.html)
- [AWS CodeBuild - What is AWS CodeBuild?](https://docs.aws.amazon.com/codebuild/latest/userguide/welcome.html)
- [AWS CodeDeploy - Deployment configurations on an Amazon ECS compute platform](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html)
- [Amazon ECS - Blue/green deployment with CodeDeploy](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-bluegreen.html)
- [EC2 Image Builder - What is Image Builder?](https://docs.aws.amazon.com/imagebuilder/latest/userguide/what-is-image-builder.html)
- [EC2 Image Builder - How Image Builder works](https://docs.aws.amazon.com/imagebuilder/latest/userguide/how-image-builder-works.html)
- [AWS Service Catalog - Overview](https://docs.aws.amazon.com/servicecatalog/latest/adminguide/what-is_concepts.html)
- [AWS CloudFormation - DeletionPolicy attribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-attribute-deletionpolicy.html)
- [AWS CloudFormation - Updating stacks using change sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)
- [AWS CloudFormation - Detect unmanaged configuration changes with drift detection](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-drift.html)
- [AWS Health - What is AWS Health?](https://docs.aws.amazon.com/health/latest/ug/what-is-aws-health.html)
- [AWS Well-Architected Framework - Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
