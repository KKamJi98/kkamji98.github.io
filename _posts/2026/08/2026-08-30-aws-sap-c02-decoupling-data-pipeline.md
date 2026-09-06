---
title: "SAP-C02 박살내기 8 - 디커플링과 데이터 파이프라인"
author: kkamji
categories: [Certification, AWS SAP-C02]
tags: [aws, sap-c02, certification, sqs, sns, eventbridge, kinesis, step-functions, glue, athena, redshift]
comments: true
image:
  path: /assets/img/aws/aws.webp
date: 2026-08-30 10:00:00 +0900
---

계좌별 주문 이벤트를 SQS FIFO 큐로 보내면서 message group ID를 계좌 번호로 두면 계좌 안에서의 순서가 지켜집니다. 여기까지는 설계대로 동작합니다. 그런데 컨슈머 버그로 특정 메시지가 계속 실패해 큐가 밀리기 시작하고, 운영 대응으로 dead-letter queue를 붙이면서 `maxReceiveCount`를 5로 잡으면 정산이 틀어집니다.

큐 타입도 message group ID도 바뀌지 않았습니다. 달라진 것은 실패한 메시지가 DLQ로 빠져나간다는 사실 하나입니다. 그 메시지 뒤에 있던 같은 계좌의 주문들이 앞으로 당겨져 처리되고, 순서가 계약이었던 워크로드에서 계약이 깨집니다. AWS 문서는 FIFO 큐에 DLQ를 붙이면 메시지와 연산의 정확한 순서가 깨지므로 순서가 의미를 갖는 워크로드에는 쓰지 말라고 명시합니다.

SAP-C02 Domain 2가 이 층에서 문항을 냅니다. 동기 호출 하나를 끊을 때 후보는 큐, 토픽, 이벤트 버스, 스트림, 워크플로 다섯 가지이고, 각각이 보장하는 것과 보장하지 않는 것이 다릅니다. 그 뒤에 붙는 분석 계층도 마찬가지로 인프라 유무, 카탈로그 위치, 리전 제약이 선지를 가릅니다. 서비스 이름을 아는 것으로는 답이 좁혀지지 않고, 각 서비스가 **하지 못하는 일**을 알아야 좁혀집니다.

> **TL;DR**  
> - SQS는 pull이고 최대 14일 보존한다. SNS standard 토픽은 기본적으로 보존하지 않지만 A2A FIFO 토픽은 1-365일 archive를 설정할 수 있다. EventBridge event bus도 기본 보존은 없지만 archive를 설정하면 지정 기간 또는 기본 무기한 보존과 source bus replay를 사용할 수 있고 순서는 보장하지 않는다.  
> - FIFO 큐에 DLQ를 붙이면 순서 보장이 깨진다. standard 큐는 DLQ 이동 시 원본 enqueue timestamp를 유지하므로 DLQ 보존을 소스보다 길게 잡는다.  
> - FIFO 처리량은 message group ID의 distinct 값이 정한다. group이 하나면 파티션 하나에 몰려 300 TPS에 갇힌다.  
> - SNS archive와 replay는 A2A FIFO 토픽 전용이고 보존 기간은 1-365일이다. standard 토픽은 기본적으로 메시지를 보존하지 않는다.  
> - EventBridge rule당 target은 5개이고 조정할 수 없다. 그 이상 팬아웃하려면 SNS 토픽을 target으로 둔다.  
> - Step Functions Standard는 exactly-once에 최대 1년이고 `.sync`와 콜백을 지원한다. Express는 5분이고 두 통합 패턴과 Distributed Map을 지원하지 않는다.  
> - state와 execution의 input과 output은 256 KiB가 하드 쿼터다. Standard 실행 이력은 25,000 이벤트에서 실행이 실패한다.  
> - Kinesis Data Streams는 저장하는 스트림이고 Firehose는 저장하지 않는 전달 파이프라인이다. 재처리 요구가 있으면 스트림이 앞에 있어야 한다.  
> - 공유 처리량 컨슈머는 샤드당 2 MB/s를 나눠 쓰고 컨슈머 5개에서 전파 지연이 약 1,000 ms다. EFO는 컨슈머 수와 무관하게 약 70 ms다.  
> - Firehose buffer interval hint는 60초에서 900초다. 1초 미만 지연 요건은 Firehose로 충족하지 못한다.  
> - Redshift Spectrum은 클러스터와 S3 버킷이 같은 리전이어야 한다.  
> - Lake Formation의 fine-grained access control은 엔진마다 지원 범위가 다르고 아예 지원하지 않는 엔진이 있다.  
{: .prompt-info}

---

## 1. 큐와 토픽과 이벤트 버스가 각각 책임지는 것

동기 호출을 끊는다는 말은 호출자와 피호출자 사이에 무언가를 끼워 넣는다는 뜻입니다. 무엇을 끼우느냐에 따라 얻는 보장과 잃는 보장이 달라집니다. AWS decision guide가 세 서비스를 가르는 축은 통신 모델, 영속성, 필터링 위치입니다.

| 축 | SQS | SNS | EventBridge |
| :--- | :--- | :--- | :--- |
| 통신 모델 | pull. 컨슈머가 polling한다 | push. 구독자에게 밀어 넣는다 | rule 매칭 후 target 라우팅 |
| 영속성 | 소비 또는 만료까지 보존, 최대 14일 | 기본 보존 없음. A2A FIFO 토픽은 archive 설정 가능 | 기본 event bus는 보존 없음. archive 설정 시 지정 기간 또는 무기한 보존 |
| 전달 보장 | at-least-once | HTTP/S는 at-least-once, Lambda 비동기 호출도 at-least-once, SQS FIFO는 조건부 exactly-once | at-least-once |
| 순서 | FIFO 큐로 보장 | FIFO 토픽으로 보장 | 보장하지 않는다 |
| 필터링 | 자체 필터링이 없다 | subscription filter policy | event pattern 기반 content filtering |
| 재시도 | 컨슈머가 제어한다. visibility timeout과 `maxReceiveCount` | 프로토콜별 재시도 정책과 DLQ | 기본 24시간, 최대 185회 |
| 팬아웃 한계 | 해당 없음 | standard 토픽 구독 12,500,000개 | rule당 target 5개, 조정 불가 |
| 크로스 계정 | 큐 정책 | 토픽 정책 | 다른 계정의 이벤트 버스를 target으로 지원 |

이 표에서 시험이 실제로 쓰는 항목은 세 줄입니다. 첫째, 영속성입니다. "이벤트를 나중에 다시 처리해야 한다"는 요구가 지문에 있으면 SNS standard 토픽과 archive 없는 EventBridge event bus는 그 자체로는 답이 되지 못합니다. EventBridge archive를 설정하면 source bus로 재생할 수 있지만 순서는 보장하지 않습니다. 둘째, 순서입니다. EventBridge는 target에 임의 순서로 전달하므로 순서 요구가 있으면 후보에서 빠집니다. 셋째, 팬아웃 한계입니다. rule당 target 5개라는 숫자가 선지를 직접 자릅니다.

SNS와 SQS를 함께 쓰는 팬아웃 패턴이 자주 나오는 이유도 여기 있습니다. SNS standard 토픽은 팬아웃을 하고 기본 보존을 하지 않으며, SQS는 팬아웃을 하지 않고 보존을 합니다. 두 요구가 함께 있으면 토픽 뒤에 큐를 붙여 각각의 결핍을 메웁니다.

---

## 2. SQS 메시지 수명주기와 visibility timeout이 결정하는 것

SQS 메시지는 큐에 들어온 뒤 컨슈머가 `ReceiveMessage`로 가져가면 사라지지 않고 다른 컨슈머에게 보이지 않는 상태가 됩니다. 이 상태가 in-flight이고 지속 시간이 visibility timeout입니다. 컨슈머가 그 안에 `DeleteMessage`를 호출하면 메시지가 제거되고, 호출하지 못하면 메시지가 다시 보이면서 수신 횟수가 하나 올라갑니다.

![SQS 메시지가 큐에서 in-flight를 거쳐 삭제되거나 DLQ로 이동하는 수명주기](/assets/img/sap-c02/sqs-message-lifecycle-dlq.webp)

그림은 프로듀서가 넣은 메시지가 소스 큐와 in-flight 상태를 지나 컨슈머에 도달한 뒤, 처리에 성공해 삭제되는 경로와 실패해 수신 횟수가 올라가는 경로로 갈리는 구조를 담았습니다. 수신 횟수가 `maxReceiveCount`에 닿으면 DLQ로 넘어가고, 그렇지 않으면 소스 큐로 되돌아옵니다. 각 상자의 부제에 보존 기간과 visibility timeout 범위를 적어 두었습니다.

수치는 다음과 같습니다.

- 메시지 보존은 기본 4일, 최소 60초, 최대 1,209,600초(14일)다.
- visibility timeout은 기본 30초, 최소 0초, 최대 12시간이다.
- message timer와 delay queue는 기본 0초, 최대 15분이다.
- long polling 대기는 최대 20초다.
- 배치 요청은 최대 10건이고 메시지 metadata attribute는 최대 10개다.
- 큐 정책은 최대 8,192 bytes와 20 statement다.

visibility timeout이 시험에서 답을 가르는 방식은 두 가지입니다. 하나는 처리 시간보다 짧게 잡았을 때 같은 메시지가 여러 컨슈머에게 중복 전달되는 상황이고, 다른 하나는 너무 길게 잡았을 때 컨슈머가 죽은 뒤 재처리가 그만큼 늦어지는 상황입니다. 처리 시간이 가변적이면 `ChangeMessageVisibility`로 연장하는 것이 정답 방향이고, timeout 상한 12시간을 넘겨야 하는 작업이라면 애초에 큐 컨슈머가 아니라 워크플로로 옮겨야 합니다.

in-flight 메시지 수에도 상한이 있습니다. standard 큐는 약 120,000이 상한이고 short polling을 쓰면 `OverLimit` 에러가 납니다. long polling을 쓰면 에러 없이 처리가 밀립니다. FIFO 큐는 최대 120,000이며 초과해도 에러를 반환하지 않고 처리 성능만 영향을 받습니다. 큐에 쌓이는 메시지 수 자체에는 제한이 없으므로, 지문에 "메시지가 무한정 쌓인다"는 표현이 나오면 그것은 쿼터 문제가 아니라 컨슈머 처리량 문제입니다.

메시지 크기는 갱신된 값과 예전 값을 둘 다 기억해야 합니다. 현재 문서는 최대 1,048,576 bytes(1 MiB)이고 최소 1 byte입니다. 널리 알려진 256 KB는 갱신 전 값입니다. 어느 쪽이든 그보다 큰 payload는 Extended Client Library로 S3에 두고 참조만 보내며 이때 payload 상한은 2 GB입니다.

---

## 3. standard 큐와 FIFO 큐가 갈리는 지점

큐 타입 선택은 순서와 중복이라는 두 축의 요구를 처리량과 맞바꾸는 결정입니다.

| 축 | standard | FIFO |
| :--- | :--- | :--- |
| 순서 | 보장하지 않는다 | message group 안에서 엄격한 순서 |
| 중복 | at-least-once. 중복이 발생할 수 있다 | 중복 제거를 지원한다 |
| 처리량 | API action당 사실상 무제한 | 파티션당 300 TPS, 배칭 3,000 messages/s |
| in-flight | 약 120,000 | 최대 120,000 |
| in-flight 초과 시 | short polling이면 `OverLimit` 에러 | 에러 없이 처리만 지연된다 |
| 큐 이름 | 최대 80자 | `.fifo` 접미사 필수이고 접미사도 80자에 포함된다 |
| DLQ 이동 시 timestamp | 원본 enqueue timestamp 유지 | 리셋된다 |
| DLQ 사용 부작용 | 없다 | 순서 보장이 깨진다 |

FIFO 큐에서 message group 수에는 쿼터가 없습니다. 그래서 "message group을 늘리면 쿼터에 걸린다"는 선지는 성립하지 않습니다. 오히려 message group을 늘리는 것이 처리량을 늘리는 정석입니다.

standard 큐를 골라야 하는 상황은 순서가 애플리케이션 계약이 아닌 경우입니다. 이미지 썸네일 생성, 알림 발송, 로그 적재처럼 각 메시지가 독립적이면 standard 큐가 처리량과 운영 부담 양쪽에서 유리합니다. 반대로 계좌별 거래, 재고 차감, 상태 기계 전이처럼 앞 메시지의 결과가 뒤 메시지의 입력이 되는 경우에만 FIFO가 필요합니다.

---

## 4. FIFO 처리량은 message group ID가 결정한다

FIFO 큐의 처리량 한계는 큐 단위가 아니라 파티션 단위입니다. 파티션 배정은 message group ID의 내부 해시로 결정되고 파티션 관리는 SQS가 자동으로 합니다. 사용자가 파티션 수를 조작하는 API는 없으며, 처리량을 늘리는 유일한 수단은 message group ID의 distinct 값을 늘리는 것입니다.

high throughput 모드가 아닌 FIFO 큐는 파티션당 API action별 300 TPS이고 배칭을 쓰면 API action별 3,000 messages/s입니다. 300 API call에 각 10 message를 실은 결과이고, send와 receive와 delete 각각에 따로 적용됩니다.

high throughput FIFO를 켜면 상한이 리전마다 크게 갈립니다.

| 비배칭 TPS | 리전 |
| :--- | :--- |
| 70,000 | us-east-1, us-west-2, eu-west-1 |
| 19,000 | us-east-2, eu-central-1 |
| 9,000 | ap-south-1, ap-southeast-1, ap-southeast-2, ap-northeast-1, eu-south-2 |
| 4,500 | eu-west-2, sa-east-1 |
| 2,400 | 나머지 리전 |

배칭을 쓰면 각 값의 10배입니다. 이 표에서 함정이 하나 나옵니다. ap-northeast-2는 9,000 구간에 들어 있지 않아 기본값인 2,400 TPS 구간입니다. "high throughput FIFO를 켰으니 어느 리전에서든 수만 TPS가 나온다"는 전제로 답을 고르면 틀립니다. 리전 간 차이가 약 29배입니다.

한 가지 더 있습니다. high throughput 모드를 켜도 message group ID가 하나뿐이면 파티션 하나에만 트래픽이 몰려 300 TPS에 갇힙니다. 처리량 문항에서 "high throughput 모드를 활성화한다"만 적힌 선지와 "message group ID를 주문 ID 단위로 세분화한다"가 함께 적힌 선지가 있으면 후자가 답에 가깝습니다.

---

## 5. 중복 제거 인터벌 5분이 exactly-once를 끝내지 않는다

FIFO 큐의 중복 제거는 5분 인터벌 안에서만 동작합니다. 같은 `MessageDeduplicationId`로 5분 안에 `SendMessage`를 재시도하면 중복이 큐에 들어가지 않지만, 5분을 넘긴 재전송은 새 메시지로 취급됩니다.

중복 제거는 두 가지 방식 중 하나를 반드시 설정해야 동작합니다. 하나는 content-based deduplication이고 다른 하나는 명시적 `MessageDeduplicationId`입니다. content-based를 켜면 SQS가 메시지 본문의 SHA-256 해시를 dedup ID로 씁니다. 여기서 걸리는 지점이 있습니다. **해시 대상은 본문뿐이고 message attribute는 제외됩니다.** 본문이 같고 attribute만 다른 두 메시지는 중복으로 판정되어 뒤에 온 것이 버려집니다.

이 두 사실이 함께 만드는 결론은 명확합니다. FIFO 큐를 쓴다고 해서 애플리케이션 레벨의 멱등 처리를 없앨 수 없습니다. 재시도 경로가 5분을 넘길 수 있으면 컨슈머 쪽에서 처리 완료 여부를 별도로 기록해야 합니다. 시험 지문이 "exactly-once processing"을 요구하면서 재시도 윈도가 길다고 적으면, FIFO 큐만으로 답을 만드는 선지는 불완전합니다.

---

## 6. DLQ와 redrive가 순서 계약을 깨는 자리

dead-letter queue는 소스 큐와 같은 AWS 계정 및 같은 리전에 있어야 합니다. 크로스 계정이나 크로스 리전 DLQ를 제시하는 선지는 이 한 줄로 탈락합니다.

redrive policy의 `maxReceiveCount`는 DLQ로 옮기기 전 소스 큐에서 수신될 수 있는 횟수입니다. 반대 방향인 redrive allow policy는 어떤 소스 큐가 이 큐를 DLQ로 쓸 수 있는지를 정하고, `byQueue` 옵션에 소스 큐 ARN을 최대 10개까지 지정합니다. `denyAll`이면 어떤 큐도 이 큐를 DLQ로 쓸 수 없습니다.

DLQ에서 실제로 답을 가르는 것은 세 가지 부작용입니다.

**첫째, standard 큐의 timestamp입니다.** standard 큐에서 DLQ로 옮겨진 메시지는 원래 enqueue timestamp를 유지합니다. 소스 큐에서 이미 사흘을 보냈다면 DLQ 보존이 4일일 때 하루만 남습니다. 그래서 DLQ 보존 기간은 소스보다 길게 잡아야 조사할 시간이 확보됩니다. FIFO 큐는 DLQ 이동 시 timestamp가 리셋되므로 이 함정이 없습니다.

**둘째, standard 큐의 `maxReceiveCount` 값입니다.** 이 값이 3보다 크면 3회 이상 수신되고 삭제되지 않은 메시지를 큐 뒤로 보냅니다. 그 결과 `ApproximateAgeOfOldestMessage` 메트릭이 왜곡됩니다. 이 메트릭으로 지연 알람을 걸어 둔 환경에서 값이 이상하게 보이면 원인이 여기일 수 있습니다.

**셋째, FIFO 큐의 순서입니다.** AWS 문서가 FIFO 큐에 DLQ를 쓰면 메시지와 연산의 정확한 순서가 깨진다고 명시합니다. FIFO 큐에서 처리 실패는 해당 message group만 막고 다른 message group은 계속 흐릅니다. 순서가 계약이면 DLQ로 걷어내는 대신 영향 범위를 그 group 하나로 가둔 채 `ApproximateAgeOfOldestMessage` 알람으로 운영이 개입하는 것이 문서에 부합하는 선택입니다.

---

## 7. SNS 팬아웃에서 standard 토픽과 FIFO 토픽이 갈린다

SNS standard 토픽은 메시지를 기본 보존하지 않고 실시간으로 전달합니다. A2A FIFO 토픽에는 1-365일 archive를 설정할 수 있습니다. 보존이 필요하면 구독에 SQS 큐를 붙이는 것도 문서화된 방식입니다. 전달 보장은 구독 프로토콜과 조건에 따라 다릅니다. HTTP/S 구독자에게는 at-least-once이고 Lambda는 standard 토픽의 비동기 호출이라 at-least-once입니다. SQS FIFO 구독의 exactly-once 전달과 처리는 필터 미사용, 권한, visibility timeout 안의 삭제, 네트워크 정상 조건을 모두 만족할 때만 성립합니다.

| 축 | standard 토픽 | FIFO 토픽 |
| :--- | :--- | :--- |
| 토픽 수 | 계정당 100,000 | 계정당 1,000 |
| 구독 수 | 토픽당 12,500,000 | 토픽당 100 |
| 처리량 | us-east-1 30,000 messages/s, 대부분 리전은 300에서 1,500 | message group당 300 messages/s |
| 처리량 확장 | 해당 없음 | `FifoThroughputScope=Topic`이면 토픽당 3,000 messages/s 또는 20 MB/s 중 먼저 닿는 값 |
| archive와 replay | 지원하지 않는다 | A2A에서 `ArchivePolicy`와 `ReplayPolicy` 지원. 보존 1-365일 |
| 대표 조합 | SQS standard, Lambda, HTTP/S, email, SMS, mobile push | SQS FIFO 큐 |

Publish 계정 쿼터도 리전별로 갈립니다. standard 토픽은 us-east-1이 30,000 messages/s, us-west-2와 eu-west-1이 9,000, us-east-2와 us-west-1과 ap-south-1과 ap-northeast-2와 ap-southeast-1과 ap-southeast-2와 ap-northeast-1과 eu-central-1이 1,500, 나머지가 300입니다. FIFO 토픽은 앞의 두 구간이 standard와 같고, standard에서 1,500과 300이던 구간이 모두 3,000입니다. 이 쿼터는 `Publish`와 `PublishBatch`를 합산한 계정 단위 값입니다.

메시지 크기는 최대 262,144 bytes(256 KiB)이고 메시지 헤더는 최대 16,384 bytes입니다. 더 큰 payload는 SQS와 마찬가지로 Extended Client Library로 최대 2 GB까지 다룹니다.

여기서 시험이 반복해서 묻는 조합이 SNS FIFO 토픽과 SQS FIFO 큐입니다. 순서 보장 팬아웃은 이 조합이 문서화된 패턴이고, 재생 요구가 함께 붙으면 A2A FIFO 토픽의 `ArchivePolicy`와 `ReplayPolicy`가 답의 근거가 됩니다. archive 보존은 1-365일입니다. standard 토픽에서는 이 두 정책이 지원되지 않으므로, standard 토픽으로 이벤트를 남기려면 Firehose 구독으로 외부 저장소에 흘려보내는 별도 구성이 필요하고 그것으로는 구독 엔드포인트로의 SNS replay가 되지 않습니다. Lambda 구독은 standard 토픽만 지원하며 비동기 호출이므로 함수는 중복 이벤트를 처리할 수 있게 멱등적으로 작성해야 합니다.

FIFO 토픽의 구독 수 상한이 100개라는 점도 함께 봅니다. 수천 개 구독이 필요한 팬아웃 요구와 순서 보장 요구가 동시에 나오면 두 요구가 충돌합니다.

---

## 8. SNS 메시지 필터링과 전달 재시도

구독 필터 정책은 토픽당 200개, 계정당 10,000개입니다. 필터를 걸면 구독자가 관심 있는 메시지만 받게 되어 다운스트림에서 조건 분기를 구현할 필요가 없어집니다. standard 토픽은 메시지 속성을 기준으로 필터링하고 FIFO 토픽은 본문 기준 필터링도 지원합니다.

Firehose 구독은 별도 쿼터를 갖습니다. 토픽당 구독 소유자별 5개입니다. SNS 메시지를 S3나 OpenSearch로 흘려 감사 로그를 남기는 구성을 설계할 때 이 숫자가 상한입니다.

전달 재시도는 구독 프로토콜별 정책을 따르고, 재시도를 모두 소진한 메시지는 구독에 붙인 DLQ로 갑니다. SNS의 DLQ는 토픽이 아니라 **구독**에 붙는다는 점이 SQS와 다릅니다. 같은 토픽의 구독 A는 정상이고 구독 B만 실패하는 상황에서 실패한 것만 격리하려면 구독 단위로 DLQ를 걸어야 합니다.

---

## 9. EventBridge rule의 target 5개 상한과 팬아웃 우회

EventBridge는 이벤트를 event pattern으로 매칭해 target에 라우팅합니다. 쿼터는 다음과 같습니다.

| 항목 | 값 |
| :--- | :--- |
| 이벤트 버스 | 계정당 100개, 조정 가능 |
| 버스당 rule | 300개. af-south-1과 eu-south-1은 100개 |
| rule당 target | **5개. 조정 불가** |
| event pattern 크기 | 최대 2,048자 |
| event bus policy 크기 | 최대 10,240자 |
| 와일드카드 포함 rule | 버스당 30개. 조정 불가 |
| API destination | 계정당 3,000개, connection 3,000개, destination당 호출률 300/s |

`PutEvents` TPS는 us-east-1과 us-west-2와 eu-west-1이 10,000, us-east-2와 eu-central-1과 eu-south-2가 2,400, 나머지가 400에서 1,200 사이입니다.

전달 방식은 at-least-once이고 순서 보장이 없습니다. 기본 24시간 동안 최대 185회까지 exponential backoff와 jitter로 재시도합니다.

![EventBridge rule의 target 5개 상한을 SNS 토픽으로 넘겨 팬아웃하는 구조](/assets/img/sap-c02/eventbridge-fanout-target-limit.webp)

그림은 사용자 지정 이벤트 버스에 들어온 이벤트가 rule을 거쳐 target으로 나가는 구조에서, target 슬롯이 5개로 고정되어 있다는 점과 그중 하나를 SNS 토픽으로 채우면 팬아웃 지점이 토픽으로 옮겨간다는 점을 함께 담았습니다. 토픽 뒤에는 팀별 SQS 큐와 HTTP/S 구독자가 붙습니다.

이 구조가 답이 되는 이유는 두 가지입니다. 첫째, 개수 제약을 넘습니다. rule당 5개는 조정 불가이고 standard 토픽은 구독을 12,500,000개까지 받습니다. 둘째, 운영 주체가 바뀝니다. rule을 나누는 방식은 팀이 늘어날 때마다 중앙 팀이 어느 rule에 넣을지 판단하고 수정해야 합니다. 토픽으로 옮기면 각 팀이 자기 구독만 관리합니다. "LEAST operational overhead"라는 한정어가 붙으면 이 차이가 답을 가릅니다.

Schema Registry도 함께 봅니다. registry 10개, registry당 schema 100개, schema당 version 100개, discovered schema 200개, 중첩 추론 깊이 255 level이 상한입니다. 스키마 자동 탐색을 켜면 버스로 들어온 이벤트에서 스키마를 추론해 registry에 넣고, 개발자는 그 스키마로 코드 바인딩을 생성합니다.

---

## 10. EventBridge archive와 replay가 보장하지 않는 것

EventBridge archive는 이벤트 버스로 들어온 이벤트를 보관합니다. 보존은 일 단위로 지정하며 기본값은 무기한입니다. archive 하나는 소스 이벤트 버스 하나에서만 이벤트를 받고 생성 후 소스 버스를 바꿀 수 없습니다. 버스 하나에 archive를 여러 개 만들 수는 있습니다.

replay 쪽에는 제약이 더 많습니다.

- replay는 archive의 **소스 이벤트 버스로만** 재생한다. 다른 버스로 보낼 수 없다.
- 계정당 리전당 동시 활성 replay는 최대 10개다.
- replay 기록은 90일 뒤 삭제된다.
- replay는 archive에서 이벤트를 제거하지 않는다.
- **replay는 원래 적재 순서를 보장하지 않는다.** 이벤트 시각 기준 1분 단위 구간으로 나눠 앞 구간부터 재생한다.

버스 도착과 archive 적재 사이에 지연이 있으므로 AWS는 replay 시작 시각을 10분 늦추라고 권고합니다. archive를 만들면 replay된 이벤트가 다시 archive되지 않도록 `replay-name` 필드를 거르는 managed rule이 자동으로 생성됩니다.

시험에서 이 절이 쓰이는 방식은 "장애 구간의 이벤트를 원래 순서대로 재처리한다"는 요구입니다. archive와 replay는 재처리는 하지만 순서는 지키지 않으므로, 순서까지 요구하는 지문에서는 SQS FIFO나 Kinesis Data Streams 쪽으로 답이 갑니다.

---

## 11. Pipes와 Scheduler가 rule과 다른 자리

EventBridge라는 이름 아래에 성격이 다른 세 가지가 있습니다.

| 축 | rule (event bus) | Pipes | Scheduler |
| :--- | :--- | :--- | :--- |
| 목적 | 이벤트를 패턴 매칭해 여러 target에 라우팅 | 소스 하나에서 타깃 하나로 point-to-point 연결 | cron, rate, 일회성 호출의 중앙 관리 |
| 중간 처리 | 없다 | filter와 enrichment 단계를 갖는다 | 없다 |
| 팬아웃 | rule당 target 5개 | 1대1 | 1대1 |
| 대표 소스 | AWS 서비스 이벤트, 커스텀 이벤트, SaaS | SQS, Kinesis, DynamoDB Streams, MSK 등 폴링 소스 | 없다. 시간이 트리거다 |
| 쿼터 | 버스당 rule 300개, `PutEvents` 최대 10,000 TPS | 동시 실행 1,000 또는 3,000, pipe 계정당 1,000개 | schedule 10,000,000개, invocation 1,000 TPS |

Pipes의 동시 실행 상한은 us-east-1과 us-west-2와 eu-west-1이 3,000이고 나머지 리전이 1,000입니다. Pipes가 답이 되는 지문은 "DynamoDB Streams나 Kinesis에서 이벤트를 읽어 변환한 뒤 하나의 대상으로 보내는 글루 코드를 없애고 싶다"는 형태입니다. Lambda 함수를 소스와 타깃 사이에 두고 폴링과 배치 처리를 직접 구현하던 코드가 Pipes 설정으로 대체됩니다.

Scheduler는 rule의 scheduled expression과 자주 헷갈립니다. Scheduler는 schedule을 10,000,000개까지 두고 필요하면 수십억 개까지 조정할 수 있으며, schedule group 500개로 묶어 관리합니다. invocation은 주요 리전에서 1,000 TPS이고 그 외 리전은 500 TPS입니다. target `Input` payload는 256 KB 고정이고 단일 schedule에 대한 읽기와 쓰기는 10 TPS입니다. "사용자마다 다른 시각에 한 번 실행되는 알림을 수백만 건 예약한다"는 요구는 rule로는 감당하지 못하고 Scheduler가 답입니다.

---

## 12. Amazon MQ를 고르는 조건은 프로토콜이다

Amazon MQ는 Apache ActiveMQ Classic과 RabbitMQ를 관리형으로 제공합니다. 표준 메시징 프로토콜을 그대로 쓰므로 기존 브로커를 **메시징 코드 재작성 없이** 이전하는 것이 문서에 적힌 목적입니다.

| 축 | Amazon MQ | SQS와 SNS |
| :--- | :--- | :--- |
| 프로토콜 | 표준 메시징 프로토콜 | AWS 고유 API |
| 이전 비용 | 기존 브로커 코드를 그대로 쓴다 | 애플리케이션 메시징 코드를 다시 쓴다 |
| 확장 | 브로커 인스턴스 단위 | 서비스가 자동으로 확장한다 |
| 네트워크 | VPC private endpoint 기반 | 리전 서비스 엔드포인트. VPC endpoint는 별도 구성 |
| 선택 이유 | 리플랫폼 요구, 프로토콜 호환 요구 | 신규 설계, 운영 부담 최소화 |

접근은 VPC 내 private endpoint로 제한할 수 있고 전송 중 암호화와 저장 시 암호화를 제공합니다. 가용성 쪽에서는 RabbitMQ quorum queue가 여러 AZ에 분산된 leader와 follower로 구성되고, ActiveMQ는 cross-Region data replication으로 replica 승격 방식의 failover를 지원합니다.

선지 판별 기준은 단순합니다. 지문에 JMS, AMQP, MQTT, STOMP 같은 표준 프로토콜이 나오거나 "메시징 코드를 수정하지 않는다"는 제약이 있으면 Amazon MQ입니다. 그런 제약 없이 신규 설계라면 운영 부담이 낮은 SQS와 SNS가 답입니다. 이 판단은 처리량이나 비용보다 앞서고, MSK를 고르는 기준과도 다릅니다. MSK는 Kafka API 호환이지 JMS 호환이 아닙니다.

---

## 13. Step Functions Standard와 Express는 실행 의미부터 다르다

워크플로 타입은 state machine을 만든 뒤에 바꿀 수 없습니다. 잘못 고르면 새로 만들어야 하므로 선택 기준이 그만큼 중요합니다.

![Step Functions 워크플로 타입이 실행 의미와 지속 시간과 통합 패턴에서 갈리는 구조](/assets/img/sap-c02/stepfunctions-workflow-type-split.webp)

그림은 오케스트레이션 요구가 Standard와 Asynchronous Express와 Synchronous Express 세 갈래로 나뉘는 구조를 담고, 각 갈래마다 그 타입에서 걸리는 대표 제약을 하나씩 붙여 두었습니다.

| 축 | Standard | Asynchronous Express | Synchronous Express |
| :--- | :--- | :--- | :--- |
| 최대 실행 시간 | 1년 | 5분 | 5분. 콘솔 호출은 60초에 만료 |
| 실행 의미 | exactly-once | at-least-once | at-most-once |
| 상태 지속 | state transition 사이에 내부 persist | 없다 | 없다 |
| 실행 이력 | 25,000 이벤트 상한, 90일 보존, 콘솔 시각 디버깅 | Step Functions가 기록하지 않는다 | 기록하지 않는다 |
| 상태 전이율 | 5,000/s(주요 3리전) 또는 800/s | 무제한 | 무제한 |
| `StartExecution` refill | 300/s 또는 150/s | 6,000/s | 6,000/s |
| `.sync`와 `.waitForTaskToken` | 지원 | 미지원 | 미지원 |
| Distributed Map, Activity | 지원 | 미지원 | 미지원 |
| 과금 | state transition 수 | 실행 수 + 실행 시간 + 메모리 | 동일 |
| 적합 대상 | 비멱등 작업(결제, EMR 클러스터 기동) | 멱등 작업(IoT 인제스트, 스트림 변환) | 마이크로서비스 오케스트레이션 |

실행 의미가 선지를 가르는 방식은 이렇습니다. "결제 승인은 절대 중복 호출되면 안 된다"는 제약이 있으면 at-least-once인 Asynchronous Express가 탈락합니다. "요청이 유실되면 안 된다"는 제약이 있으면 at-most-once인 Synchronous Express가 탈락합니다. 둘 다 있으면 exactly-once인 Standard만 남습니다.

통합 패턴은 두 번째 필터입니다. ECS task나 EMR 스텝의 **완료를 기다려야** 하면 `.sync`가 필요하고, 사람의 승인처럼 외부 신호를 기다려야 하면 `.waitForTaskToken`이 필요합니다. Express는 둘 다 지원하지 않습니다.

실행 이력에도 함정이 있습니다. Standard의 실행 이력은 단일 실행당 25,000 이벤트가 상한이고 **도달하면 실행 자체가 실패합니다.** "Standard는 1년까지 도니 긴 루프를 그 안에서 다 돌린다"는 판단이 여기서 깨집니다. 루프가 길면 실행을 나눠 새로 시작해야 합니다. Express는 이력 이벤트에 상한이 없지만 Step Functions가 이력을 기록하지 않으므로 CloudWatch Logs를 켜야 실행 내용을 볼 수 있습니다.

실행 이력 보존은 종료 후 90일입니다. 규제 목적으로 더 짧게 두어야 하면 support case로 30일까지 줄일 수 있습니다.

콘솔에서 `StartSyncExecution`을 실행하면 60초에 만료됩니다. 5분까지 동기 실행하려면 SDK나 CLI로 호출해야 합니다. 콘솔에서 테스트했더니 60초에 끊긴다는 지문이 나오면 워크플로 타입 문제가 아니라 호출 경로 문제입니다.

HTTP Task에도 별도 쿼터가 있습니다. 요청과 응답을 합쳐 60초가 하드 쿼터이고 token bucket 300에 refill 300/s입니다.

---

## 14. Distributed Map과 payload 256 KiB 벽

Step Functions에서 대량 반복을 다루는 방법은 두 가지이고 성격이 완전히 다릅니다.

inline Map은 반복 대상을 **상태 입력으로** 받습니다. 그런데 task와 state와 execution의 input과 output은 UTF-8 기준 256 KiB가 상한입니다. 객체 수백만 개의 목록은 여기 들어가지 않고, 억지로 넣는다 해도 Standard 실행 이력 25,000 이벤트 상한에 먼저 걸립니다.

Distributed Map은 S3 객체 목록이나 CSV 파일을 소스로 직접 읽습니다. 쿼터는 다음과 같습니다.

- 단일 Map Run 안의 병렬 자식 실행은 최대 10,000개다.
- Express 자식은 최대 1,000 TPS로 디스패치된다.
- Standard 자식은 최대 100 TPS로 디스패치된다.
- 계정당 open Map Run은 1,000개다.
- Map Run redrive는 1,000회다.

Map Run redrive가 시험에서 답의 근거가 됩니다. 500만 개 항목 중 실패한 것만 골라 재실행하라는 요구를 이 기능 하나가 충족합니다. 실패 항목을 추적하는 로직을 직접 구현하는 선지는 "관리형 서비스로 위임"이라는 방향과 반대입니다.

Distributed Map은 Standard workflow에서만 쓸 수 있고, 자식으로는 Express와 Standard를 모두 쓸 수 있습니다. 처리량이 필요하면 자식을 Express로 두어 1,000 TPS 디스패치를 확보합니다.

state machine definition 자체는 1 MB, API 요청 전체도 1 MB가 상한입니다. 큰 데이터를 상태 사이로 옮겨야 하면 S3에 두고 참조만 넘기는 것이 정석입니다.

---

## 15. Kinesis Data Streams 샤드가 정하는 상한

provisioned 모드의 샤드는 쓰기 1 MB/s 또는 1,000 records/s, 읽기 2 MB/s 또는 2,000 records/s가 상한입니다. 읽기 쪽은 API 관점으로도 기억해야 합니다. `GetRecords`는 샤드당 5 TPS이고 호출당 최대 10 MB 또는 10,000 records를 반환하며, 10 MB를 반환하면 이후 5초 동안의 호출이 예외를 던집니다.

레코드 크기는 갱신되었습니다. payload는 base64 인코딩 전 기준 최대 10 MiB입니다. 널리 알려진 1 MB는 갱신 전 값입니다. `PutRecords` 요청 전체도 파티션 키를 포함해 10 MiB가 상한이고 요청당 500 records까지 넣습니다.

보존 기간은 최소 24시간, 최대 8,760시간(365일)입니다. 이 값이 Firehose와의 차이를 만드는 결정적 지점입니다.

on-demand 모드는 신규 스트림이 기본 4 MB/s 쓰기와 8 MB/s 읽기로 시작합니다. us-east-1과 us-west-2와 eu-west-1은 10 GB/s 쓰기와 20 GB/s 읽기까지 확장하고 다른 리전은 200 MB/s 쓰기와 400 MB/s 읽기까지입니다. capacity mode 전환은 스트림당 24시간 안에 2회로 제한되므로 "트래픽 패턴에 맞춰 수시로 전환한다"는 운영은 성립하지 않습니다.

계정 쿼터도 리전에 따라 갈립니다. provisioned 샤드는 us-east-1과 us-west-2와 eu-west-1이 계정당 20,000개이고 나머지 리전은 1,000개 또는 6,000개입니다. on-demand 스트림 수는 기본 50개입니다.

On-demand Advantage는 계정 레벨 설정이며 warm throughput 사전 설정과 스트림 고정요금 제거가 함께 따라옵니다. EFO 컨슈머 등록 상한도 이 모드에서 달라집니다.

---

## 16. 컨슈머를 늘려도 처리량이 늘지 않는 이유

Kinesis에서 자주 나오는 성능 문항의 구조는 같습니다. 샤드 수는 처리량 기준으로 충분한데 컨슈머를 늘릴수록 지연이 늘어납니다. 원인은 처리량 부족이 아니라 읽기 모델입니다.

![Kinesis 공유 처리량 컨슈머와 enhanced fan-out 컨슈머의 읽기 경로와 전파 지연 차이](/assets/img/sap-c02/kinesis-efo-vs-shared-consumers.webp)

그림은 같은 샤드를 읽는 두 방식을 두 줄로 나란히 놓고, 공유 처리량 쪽은 2 MB/s를 컨슈머들이 나눠 쓰며 폴링한다는 점을, EFO 쪽은 컨슈머마다 2 MB/s를 전용으로 받고 push로 읽는다는 점을 각각의 전파 지연 값과 함께 담았습니다.

| 축 | 공유 처리량 | enhanced fan-out |
| :--- | :--- | :--- |
| 읽기 처리량 | 샤드당 총 2 MB/s를 모든 컨슈머가 나눈다 | 컨슈머마다 샤드당 2 MB/s 전용 |
| 전파 지연 | 컨슈머 1개 약 200 ms, 5개 약 1,000 ms | 컨슈머 수와 무관하게 약 70 ms |
| 전달 방식 | `GetRecords` pull. 샤드당 5 TPS | `SubscribeToShard` HTTP/2 push |
| 컨슈머 수 | 제한 없다. 처리량을 나눠 쓴다 | On-demand Advantage 50개, 그 외 20개 |
| 비용 | 추가 없다 | data retrieval과 consumer-shard hour가 붙는다 |

지연 요건이 200 ms인데 컨슈머가 다섯 개라면 공유 처리량 모드로는 요건을 충족하지 못합니다. 샤드를 늘려도 컨슈머들이 `GetRecords`를 나눠 호출하는 구조는 그대로이고, 폴링 빈도를 높이면 샤드당 5 TPS 제한과 10 MB 반환 후 5초 예외에 걸려 `ProvisionedThroughputExceededException`만 늘어납니다. on-demand로 전환하는 것도 용량 관리 방식만 바꿀 뿐 읽기 모델을 바꾸지 않습니다. 답은 EFO 등록입니다.

반대 방향의 함정도 있습니다. EFO는 무료가 아닙니다. data retrieval 비용과 consumer-shard hour 비용이 추가되고 등록 가능한 컨슈머 수에도 상한이 있습니다. 지연 요건이 없는데 비용 최적화를 묻는 지문이라면 EFO는 답이 아닙니다.

---

## 17. Firehose는 저장소가 아니다

Amazon Data Firehose는 이름이 `Kinesis Data Firehose`에서 바뀌었습니다. Exam Guide Appendix와 현재 문서 모두 `Amazon Data Firehose`를 씁니다.

![Kinesis Data Streams와 Firehose 사이에서 재처리가 가능한 구간과 불가능한 구간의 경계](/assets/img/sap-c02/kinesis-firehose-replay-boundary.webp)

그림은 프로듀서에서 목적지까지 이어지는 파이프라인을 두 구간으로 나눠, 스트림에 데이터가 남아 재처리가 가능한 구간과 전달만 하고 남기지 않는 구간을 구분해 담았습니다. 목적지 상자에는 각 목적지에서 걸리는 제약을 부제로 붙였습니다.

Firehose의 성격을 정하는 사실은 다음과 같습니다.

- 레코드는 base64 인코딩 전 기준 최대 1,000 KiB다. `PutRecordBatch`는 호출당 500 records 또는 4 MiB 중 작은 쪽이 상한이다.
- **buffer interval hint 범위는 60초에서 900초다.** 1초 미만 지연 요건은 충족하지 못한다.
- 목적지가 사용 불가일 때 Direct PUT 소스면 최대 24시간 데이터를 보관한다. 소스가 Kinesis Data Streams이면 KDS 보존 설정을 따른다.
- Firehose 자체는 데이터 저장소가 아니므로 replay 대상이 아니다.
- Redshift와 OpenSearch Service 전달의 retry duration 범위는 0초에서 7,200초다.
- **Redshift로 전달하려면 publicly accessible한 클러스터여야 한다.**
- Redshift 전달은 S3를 먼저 거친 뒤 `COPY` 명령으로 로드하는 2단계 구조다.
- dynamic partitioning 활성 파티션은 스트림당 기본 500개이고 활성 파티션당 최대 1 GB/s다.

Direct PUT 소스 쿼터는 us-east-1과 us-west-2와 eu-west-1이 500,000 records/s와 2,000 requests/s와 5 MiB/s이고 다른 리전은 100,000과 1,000과 1 MiB/s입니다. 소스가 Kinesis Data Streams이면 이 쿼터가 적용되지 않고 무제한으로 확장합니다. 인제스트가 Direct PUT 쿼터에 막힌다는 지문이 나오면 앞에 스트림을 두는 것이 해법 중 하나입니다.

목적지는 S3, Redshift, OpenSearch Service, OpenSearch Serverless, Splunk, Apache Iceberg Tables, 그리고 Datadog과 Dynatrace와 LogicMonitor와 MongoDB와 New Relic과 Coralogix와 Elastic 같은 커스텀 HTTP endpoint입니다. 이 목록에 없는 대상으로 직접 전달하는 선지는 성립하지 않습니다.

과금 구조도 설계 판단에 들어갑니다. 인제스트 과금은 레코드 수에 레코드 크기를 곱하되 크기를 5 KB 단위로 올림해 계산합니다. 같은 바이트 총량이라도 레코드가 잘게 쪼개지면 비용이 오릅니다. 작은 이벤트를 묶어서 보내는 것이 비용 측면에서 유리한 이유입니다.

| 축 | Kinesis Data Streams | Amazon Data Firehose |
| :--- | :--- | :--- |
| 성격 | 저장하는 스트림. 재처리가 가능하다 | 저장하지 않는 전달 파이프라인 |
| 보존 | 24시간에서 365일 | 목적지 장애 시 Direct PUT 소스만 24시간 버퍼링 |
| 지연 | EFO 약 70 ms, 공유 처리량 약 200 ms | buffer interval hint 60에서 900초 |
| 용량 관리 | provisioned 샤드 또는 on-demand | 프로비저닝이 없다. 자동 확장한다 |
| 레코드 크기 | 최대 10 MiB | 최대 1,000 KiB |
| 컨슈머 | 임의 애플리케이션, KCL, Lambda, EFO 20개 또는 50개 | 고정된 목적지 세트 |
| 순서 | 샤드 안에서 순서가 유지된다 | 순서 보장 개념이 없다 |

---

## 18. MSK를 고르는 조건과 Serverless의 벽

Amazon MSK는 오픈소스 Apache Kafka를 그대로 실행합니다. 기존 Kafka 애플리케이션과 파트너 도구를 코드 변경 없이 씁니다. broker는 AZ당 최소 1개를 배치하고 AZ마다 별도 VPC 서브넷을 씁니다. KRaft 컨트롤러는 추가 비용과 관리가 없습니다.

| 축 | Kinesis Data Streams | Amazon MSK |
| :--- | :--- | :--- |
| API | AWS 고유 API | 오픈소스 Apache Kafka API 그대로 |
| 이전 비용 | 기존 Kafka 앱은 재작성이 필요하다 | 기존 Kafka 앱과 도구와 플러그인을 그대로 쓴다 |
| 용량 단위 | 샤드 또는 on-demand 처리량 | broker 노드 또는 Serverless |
| 레코드 크기 | 10 MiB | Kafka 설정에 종속. Serverless는 8 MiB 하드 상한 |
| 운영 부담 | 샤드 관리만 | broker 타입, 버전, 파티션 설계 |
| 복제 | 리전 안에서 자동 | MSK Replicator로 클러스터 간 복제를 구성한다 |

MSK Provisioned는 Standard broker와 Express broker 두 종류가 있고, MSK Serverless는 클러스터 레벨에서만 리소스를 프로비저닝합니다.

Serverless의 쿼터가 마이그레이션 판단을 가릅니다.

| 항목 | MSK Serverless |
| :--- | :--- |
| ingress | 클러스터 200 MBps, 파티션당 5 MBps |
| egress | 클러스터 400 MBps, 파티션당 10 MBps |
| 파티션(leader) | 2,400개. compacted 토픽은 120개 |
| 클라이언트 연결 | 3,000개 |
| 메시지 최대 크기 | 8 MiB |
| 요청 | 15,000/s |
| consumer group | 500개 |
| 클라이언트 VPC | 5개 |
| 보존 | 무제한 |
| 계정당 클러스터 | 10개 |

파티션 수천 개짜리 Kafka 워크로드를 Serverless로 그대로 옮기는 선지는 이 표의 2,400개에서 막힙니다. 그 이상은 Provisioned를 골라야 합니다.

Provisioned Standard broker는 계정당 broker 90개, 클러스터당 broker 30개(ZooKeeper) 또는 60개(KRaft), broker당 스토리지 1 GiB에서 16,384 GiB입니다. IAM 인증을 쓰면 broker당 TCP 연결 3,000개와 연결 시도 100/s(M5, M7g) 또는 4/s(t3)가 상한입니다.

Express broker는 스토리지가 무제한이고 파티션당 처리량 상한이 15 MB/s입니다. broker 크기별로 ingress sustained가 15.6에서 500 MBps, egress가 31.2에서 1,000 MBps이고, broker당 최대 파티션은 `express.m7g.large` 1,500개에서 `express.m7g.16xlarge` 32,000개입니다.

MSK Replicator는 MSK Provisioned 클러스터 사이를 같은 리전 또는 다른 리전으로 복제합니다. 계정당 15개, Replicator당 토픽 750개, ingress 1 GB/s가 상한이고 레코드 최대 크기는 cross-Region이 10 MB, same-Region이 20 MB입니다. MSK Connect는 Kafka Connect 기반 스트리밍 커넥터입니다.

---

## 19. Managed Service for Apache Flink의 KPU 계산

Amazon Managed Service for Apache Flink는 이름이 `Kinesis Data Analytics for Apache Flink`에서 바뀌었습니다. Java, Scala, Python, SQL로 스트림 처리를 작성하고 프로비저닝과 AZ failover와 병렬 처리와 오토스케일링과 checkpoint 및 snapshot 백업을 서비스가 담당합니다. Studio는 노트북 기반 대화형 탐색용이고 장기 실행 애플리케이션으로 승격할 수 있습니다.

용량 단위인 KPU는 1 vCPU와 4 GB 메모리이고 KPU마다 running application storage 50 GB가 따라옵니다. 할당 KPU는 `Parallelism`을 `ParallelismPerKPU`로 나눈 값입니다.

| 항목 | 값 |
| :--- | :--- |
| `Parallelism` | 기본 1, 기본 최대 256 |
| `ParallelismPerKPU` | 기본 1, 최대 8 |
| 애플리케이션당 KPU | 기본 상한 64. 증설 요청 대상 |
| 추가 과금 | orchestration 용도로 KPU 1개가 더 붙는다 |

"parallelism을 올리면 상한 없이 확장한다"는 전제는 성립하지 않습니다. 애플리케이션당 KPU 기본 상한이 64이고 `Parallelism` 상한은 `ParallelismPerKPU`와 KPU 상한의 곱으로 결정됩니다.

Flink가 답이 되는 지문은 스트림 위에서 윈도 집계, 조인, 상태 기반 이벤트 패턴 탐지를 해야 하는 경우입니다. 단순히 스트림을 받아 목적지로 흘리는 것이라면 Firehose가, 스트림을 읽어 임의 코드를 돌리는 것이라면 Lambda 컨슈머가 더 단순한 답입니다.

---

## 20. Glue와 Data Catalog와 Lake Formation의 권한 층

AWS Glue는 서버리스 데이터 통합 서비스입니다. 70개 이상의 데이터 소스를 연결하고 crawler로 스키마를 추론해 Glue Data Catalog에 등록합니다. 같은 카탈로그를 Athena와 EMR과 Redshift Spectrum이 조회합니다.

Lake Formation은 그 카탈로그 리소스에 대한 fine-grained access control을 제공하는 authorization layer입니다. 쓰려면 먼저 S3 location을 등록하고 IAM principal에 테이블과 데이터베이스와 S3 location 권한을 부여해야 합니다. 권한을 통과시키는 서비스는 temporary credential을 발급받는 trusted caller로 동작합니다.

![Glue crawler와 Data Catalog와 Lake Formation을 거쳐 분석 엔진에 도달하는 권한 경로](/assets/img/sap-c02/glue-catalog-lake-formation-access.webp)

그림은 S3 데이터 레이크에서 시작해 crawler와 Data Catalog와 Lake Formation 권한 계층을 거쳐 분석 엔진에 도달하는 경로를 담고, 엔진마다 Lake Formation의 지원 범위가 다르다는 점을 각 상자의 부제로 붙였습니다.

여기서 시험이 파고드는 지점이 엔진별 지원 범위입니다.

| 엔진 | Lake Formation FGAC 지원 범위 |
| :--- | :--- |
| Athena SQL | table, column, row, cell 읽기 |
| Redshift Spectrum (provisioned와 serverless) | table, column, row, cell 읽기 |
| EMR(EC2) Spark | table, column, row, cell 읽기 |
| EMR Serverless Spark | table, column, row, cell 읽기 |
| EMR(EC2) Hive | row와 cell을 지원하지 않는다 |
| Glue ETL | 5.0 이상에서 column과 row 읽기 |
| Athena Spark | 지원하지 않는다 |
| EMR Serverless Hive | 지원하지 않는다 |
| Amazon EMR on EKS | 지원하지 않는다 |

"Lake Formation 권한을 걸면 모든 분석 엔진에서 row-level 통제가 강제된다"는 전제로 답을 고르면 틀립니다. 지문이 특정 엔진을 지목하면 그 엔진이 지원 범위에 있는지부터 확인해야 합니다.

Glue job 쪽 수치도 함께 봅니다. DPU 1개는 4 vCPU와 16 GB 메모리입니다.

| worker type | DPU | vCPU와 메모리 |
| :--- | :--- | :--- |
| `G.025X` | 0.25 | 2 vCPU, 4 GB, 84 GB disk. Glue 3.0 이상 스트리밍 전용 |
| `G.1X` | 1 | 4 vCPU, 16 GB, 94 GB |
| `G.2X` | 2 | 8 vCPU, 32 GB, 138 GB |
| `G.4X` | 4 | 16 vCPU, 64 GB, 256 GB |
| `G.8X` | 8 | 32 vCPU, 128 GB, 512 GB |
| `G.12X` | 12 | 위 비율의 확장 |
| `G.16X` | 16 | 위 비율의 확장 |
| `R.1X`에서 `R.8X` | 해당 계열 | 메모리 최적화 구성 |

job timeout 최대는 7일(10,080분)이고 미지정 시 기본값은 Glue 4.0 이하가 2,880분, 5.0 이상이 480분입니다. retry는 0에서 10회이고 기본 최대 동시 실행은 1입니다. Flex execution은 Glue 3.0 이상과 `G.1X`, `G.2X`에서만 지원합니다.

Lake Formation과 Glue job이 만나는 자리에도 제약이 있습니다. cell-level filter가 걸린 테이블을 읽는 Glue job은 job bookmark, bounded execution, push-down predicate, server-side catalog partition predicate, `enableUpdateCatalog`를 쓸 수 없습니다. 세밀한 권한과 증분 처리 최적화를 동시에 요구하는 설계는 이 지점에서 충돌합니다.

---

## 21. Athena와 Redshift와 EMR이 갈리는 기준

세 서비스는 모두 대용량 데이터를 다루지만 문서가 제시하는 선택 기준이 명확히 다릅니다.

| 축 | Athena | Redshift | EMR |
| :--- | :--- | :--- | :--- |
| 위치 | S3 데이터를 그 자리에서 조회한다 | 자체 관리 스토리지에 적재한다. Spectrum으로 S3도 본다 | 클러스터에서 프레임워크를 실행한다 |
| 인프라 | 없다 | 클러스터 또는 Serverless workgroup | 클러스터를 명시적으로 관리한다 |
| 적합 | ad-hoc SQL, 로그 조사 | 여러 소스를 통합해 장기 보관하고 대형 테이블을 다중 조인한다 | 커스텀 코드, Spark와 Hadoop과 Presto와 HBase, ML과 그래프 |
| 카탈로그 | Glue Data Catalog. Hive metastore 호환 | 로컬 카탈로그와 external schema | Hive metastore 또는 Glue Data Catalog |

Athena는 S3의 비정형과 반정형과 정형 데이터를 ANSI SQL로 조회하며 데이터를 적재하거나 집계할 필요가 없습니다. CSV, JSON, Parquet, ORC를 읽습니다.

federated query는 S3 밖의 소스를 같은 SQL로 조회하는 기능입니다. data source connector를 배포하고 그 연결 정보를 Glue connection으로 등록한 뒤 SQL에서 그 이름으로 참조합니다. 크로스 계정 federated query도 별도 설정으로 가능합니다. federated query는 쿼리당 최소 10 MB가 과금 단위이고, provisioned capacity는 DPU-hour당 0.30 USD입니다.

EMR의 인스턴스 구성은 두 방식이 있고 이 차이가 비용 문항에서 답을 가릅니다.

| 축 | uniform instance group | instance fleet |
| :--- | :--- | :--- |
| instance type 수 | 그룹당 1개 | fleet당 최대 5개 |
| 구매 옵션 혼합 | 불가능하다. 그룹 전체가 On-Demand이거나 Spot이다 | 가능하다. target capacity를 두 옵션으로 채운다 |
| 생성 후 변경 | 구매 옵션을 바꿀 수 없다 | 바꿀 수 있다 |
| AZ | 단일 subnet 또는 AZ | 여러 AZ를 후보로 지정한다 |
| 용량 기준 | 인스턴스 수 | target capacity와 weighted capacity 또는 vCPU |

Reserved Instance는 EC2에서 구매해야 EMR이 조건 일치 시 자동으로 씁니다. Dedicated Instance는 dedicated tenancy VPC를 만들어 그 안에서 클러스터를 띄워야 적용되며, EMR은 개별 인스턴스에 `dedicated` 속성을 설정하는 방식을 지원하지 않습니다. 정의된 기간 Spot은 2021-07-01부터 신규 고객에게 제공되지 않고 2022-12-31에 종료되었으므로 선지에 나오면 그것만으로 탈락입니다.

EMR Serverless는 application 단위로 worker를 자동 산정하고 잡이 끝나면 회수합니다. 초 단위 응답이 필요하면 `initial-capacity`로 pre-initialized capacity를 둡니다. 리전 서비스로 여러 AZ에 걸쳐 실행되고 application마다 격리된 VPC에서 돕니다.

---

## 22. Redshift Serverless RPU와 Concurrency Scaling의 사각지대

Redshift Serverless는 RPU 단위로 용량을 잽니다. 1 RPU가 16 GB 메모리입니다.

| 항목 | 값 |
| :--- | :--- |
| base capacity 기본값 | 128 RPU |
| 범위 | 4에서 512 RPU |
| 상향 리전 | us-east-1, us-east-2, us-west-2, eu-west-1, eu-central-1에서 최대 1024 RPU |
| 증가 단위 | 4에서 8까지 4 단위, 8에서 512까지 8 단위, 512에서 1024까지 32 단위 |
| base 4 RPU | managed storage 32 TB까지 |
| base 8과 16 RPU | managed storage 128 TB까지 |
| 128 TB 초과 | 최소 32 RPU |

base 4 RPU 구성은 테이블당 100 컬럼과 64 GB 메모리가 실질 상한이고 일부 리전에서만 생성됩니다. 비용을 낮추려고 4 RPU를 골랐다가 스토리지와 컬럼 수에서 막히는 조합이 오답 선지로 나옵니다.

provisioned 클러스터 쪽의 동시성 대응은 Concurrency Scaling입니다. read와 write를 모두 처리하지만 지원 범위가 좁습니다.

- 지원하는 write 문장은 `COPY`, `INSERT`, `DELETE`, `UPDATE`, CTAS, `VACUUM`과 materialized view 수동 refresh, 자동 vacuum이다. 그 외 DML과 DDL은 지원하지 않는다.
- write 확장은 RG와 RA3 노드에서만 동작한다.
- interleaved sort key 테이블, 임시 테이블, Python UDF와 Lambda UDF를 포함한 쿼리, 시스템 테이블에 접근하는 쿼리는 CS 클러스터로 라우팅되지 않는다.
- 대상 클러스터는 EC2-VPC 플랫폼이어야 하고 단일 노드가 아니어야 하며, RG와 RA3와 ra3.xlplus 계열에서 최대 32 compute node이고 최초 생성 시 노드 수도 32 이하여야 한다.
- 라우팅은 WLM 큐의 Concurrency Scaling mode를 `auto`로 두어 켠다. 기본 CS 클러스터 수는 1이고 `max_concurrency_scaling_clusters`로 조정한다.

비용도 함께 봅니다. 무료 크레딧은 메인 클러스터가 켜져 있는 동안 24시간마다 1시간씩 적립되고 클러스터당 최대 30시간까지 누적됩니다. 크레딧을 다 쓰면 클러스터 타입의 per-second on-demand 요율로 과금되고 CS 클러스터가 뜰 때마다 1분 최소 과금이 붙습니다.

| 축 | provisioned | Serverless |
| :--- | :--- | :--- |
| 용량 단위 | 노드 타입과 노드 수 | RPU |
| 기본값 | 노드를 직접 고른다 | base capacity 128 RPU |
| 동시성 급증 대응 | Concurrency Scaling. WLM 큐를 `auto`로 둔다 | 자동 RPU 스케일링과 price-performance target |
| data lake 쿼리 | Spectrum 서버. RG는 자체 컴퓨트 | 자체 컴퓨트 |
| CS write 지원 | RG와 RA3 노드만 | 해당 없음 |

---

## 23. Spectrum의 리전 제약과 설계 권고

Redshift Spectrum은 S3의 데이터를 external table로 조회합니다. 제약이 두 개 있고 둘 다 문항으로 나옵니다.

**첫째, 클러스터와 S3 버킷이 같은 리전에 있어야 합니다.** 다른 리전의 데이터 레이크를 Spectrum으로 조회하는 구성은 성립하지 않습니다. 조회 대상 데이터를 클러스터와 같은 리전으로 복제하거나 클러스터를 데이터가 있는 리전으로 옮겨야 합니다.

**둘째, external schema가 카탈로그를 참조하고 IAM role ARN이 클러스터에 연결되어야 합니다.** external schema는 Glue Data Catalog, Athena Data Catalog, EMR의 Hive metastore 중 무엇이든 참조할 수 있습니다. 카탈로그 종류를 바꾸는 것은 리전 제약과 무관하므로, 리전이 다른 상황에서 카탈로그를 바꾸는 선지는 답이 되지 못합니다.

실행 위치도 갱신되었습니다. RG provisioned 클러스터와 Redshift Serverless는 data lake 쿼리를 별도의 Spectrum 서버가 아니라 자체 컴퓨트로 실행합니다.

설계 권고는 큰 fact 테이블을 S3에 두고 작은 dimension 테이블을 Redshift 로컬에 두는 것입니다. 조인 대상 중 큰 쪽을 스캔 과금 구간에 두고 작은 쪽을 로컬에 두면 스캔량과 조인 비용 양쪽이 유리해집니다.

과금은 us-east-1 기준 스캔 TB당 5 USD이고 쿼리당 최소 10 MB에 MB 단위로 올림합니다. `CREATE`, `ALTER`, `DROP TABLE` 같은 DDL과 실패한 쿼리는 과금되지 않습니다. Parquet이나 ORC 같은 컬럼 포맷과 파티셔닝이 비용을 직접 줄이는 이유가 이 과금 구조입니다.

---

## 24. OpenSearch와 QuickSight의 용량 단위

OpenSearch Service 도메인은 최대 1,002 data node와 최대 25 PB 부착 스토리지를 지원하고, read-only 데이터를 위해 UltraWarm과 cold storage 계층을 제공합니다. legacy Elasticsearch는 오픈소스 최종 버전인 7.10까지 지원하며 표준 지원이 끝난 버전에는 extended support 요금이 자동으로 붙습니다.

과금에서 눈여겨볼 지점이 있습니다. OpenSearch Service는 AZ 사이 트래픽, 도메인 안의 shard 재배치 트래픽, UltraWarm과 cold 노드와 S3 사이의 전송에 과금하지 않습니다. "멀티 AZ 구성이 AZ 간 전송 비용을 늘린다"는 일반론이 이 서비스에는 적용되지 않습니다.

OpenSearch Serverless는 OCU 단위로 용량을 잽니다.

| 항목 | 값 |
| :--- | :--- |
| OCU 1개 | 6 GiB 메모리와 그에 대응하는 vCPU |
| 설정 단위 | collection group 단위로 indexing과 search의 최소와 최대를 따로 정한다 |
| 최소 | 0 OCU까지 내려간다 |
| 최대 | indexing과 search 각각 1,700 OCU |
| 설정 가능한 값 | 2, 4, 8, 16 또는 16의 배수 |
| collection당 index | 최대 1,000개 |
| Classic collection 스토리지 | OCU당 hot ephemeral storage 120 GiB, collection당 managed hot storage 10 TiB |

search와 vector search collection은 전부 hot에 두고 time series collection만 hot과 warm을 섞습니다.

QuickSight는 Amazon Quick으로 개편되었고 기존 QuickSight는 Amazon Quick 안의 Amazon Quick Sight 기능으로 남았습니다. 기존 API와 SDK와 통합은 변경 없이 동작합니다. Exam Guide v1.2 Appendix는 아직 `Amazon QuickSight`로 적혀 있으므로 시험 지문은 구명칭을 쓸 가능성이 높습니다.

---

## 25. 암기해야 하는 하드 리밋과 동작 제약

시험에서 선지를 직접 가르는 수치와 동작입니다.

**SQS**

| 항목 | 값 |
| :--- | :--- |
| 메시지 크기 | 최대 1,048,576 bytes(1 MiB), 최소 1 byte. 예전 값 256 KB도 함께 기억한다 |
| Extended Client payload | 최대 2 GB |
| 메시지 보존 | 기본 4일, 최소 60초, 최대 14일 |
| visibility timeout | 기본 30초, 최소 0초, 최대 12시간 |
| message timer와 delay queue | 기본 0초, 최대 15분 |
| long polling 대기 | 최대 20초 |
| 배치 요청 | 최대 10건 |
| metadata attribute | 최대 10개 |
| 큐 정책 | 8,192 bytes, 20 statement |
| standard in-flight | 약 120,000. short polling이면 `OverLimit` |
| FIFO in-flight | 최대 120,000. 초과해도 에러 없이 지연만 |
| 큐 이름 | 최대 80자. FIFO는 `.fifo` 접미사 포함 |
| FIFO message group 수 | 쿼터가 없다 |
| FIFO 비배칭 TPS | 파티션당 300. 배칭 3,000 messages/s |
| high throughput FIFO | 리전별 2,400에서 70,000 TPS. 배칭은 10배 |
| FIFO 중복 제거 인터벌 | 5분 |
| DLQ 위치 | 소스 큐와 같은 계정, 같은 리전 |
| redrive allow policy `byQueue` | 소스 큐 ARN 최대 10개 |

**SNS**

| 항목 | 값 |
| :--- | :--- |
| 메시지 크기 | 262,144 bytes(256 KiB). 헤더 16,384 bytes |
| 토픽 수 | standard 100,000, FIFO 1,000 |
| 구독 수 | standard 12,500,000/토픽, FIFO 100/토픽 |
| Firehose 구독 | 토픽당 구독 소유자별 5개 |
| 구독 필터 정책 | 토픽당 200개, 계정당 10,000개 |
| FIFO 처리량 | message group당 300 messages/s |
| `FifoThroughputScope=Topic` | 토픽당 3,000 messages/s 또는 20 MB/s |
| Publish 계정 쿼터 | standard는 us-east-1 30,000, 대부분 300에서 1,500 |
| archive와 replay | A2A FIFO 토픽 전용, 보존 1-365일 |

**EventBridge**

| 항목 | 값 |
| :--- | :--- |
| 이벤트 버스 | 계정당 100개, 조정 가능 |
| 버스당 rule | 300개. af-south-1과 eu-south-1은 100개 |
| rule당 target | 5개. 조정 불가 |
| event pattern | 2,048자 |
| event bus policy | 10,240자 |
| 와일드카드 rule | 버스당 30개. 조정 불가 |
| `PutEvents` TPS | 주요 3리전 10,000, 그 외 400에서 2,400 |
| 재시도 | 기본 24시간, 최대 185회 |
| API destination | 계정당 3,000개, 호출률 300/s |
| Pipes 동시 실행 | 주요 3리전 3,000, 그 외 1,000. pipe 1,000개 |
| Schema Registry | registry 10개, schema 100개, version 100개, 추론 깊이 255 |
| Scheduler | schedule 10,000,000개, invocation 1,000 TPS, `Input` 256 KB |
| archive 보존 | 일 단위 지정, 기본 무기한 |
| 동시 replay | 계정당 리전당 10개. 기록은 90일 뒤 삭제 |

**Step Functions**

| 항목 | 값 |
| :--- | :--- |
| Standard 최대 실행 시간 | 1년 |
| Express 최대 실행 시간 | 5분. 콘솔 `StartSyncExecution`은 60초 |
| Standard 실행 이력 | 25,000 이벤트. 도달하면 실행 실패 |
| 실행 이력 보존 | 종료 후 90일. support case로 30일 단축 가능 |
| input과 output | 256 KiB |
| state machine definition | 1 MB. API 요청 전체도 1 MB |
| `StateTransition` | Standard 주요 3리전 5,000/s, 그 외 800/s. Express 무제한 |
| `StartExecution` refill | Standard 300/s 또는 150/s, Express 6,000/s |
| Distributed Map 자식 실행 | 단일 Map Run당 10,000개 |
| Distributed Map 디스패치 | Express 자식 1,000 TPS, Standard 자식 100 TPS |
| open Map Run | 계정당 1,000개. redrive 1,000회 |
| HTTP Task | 요청과 응답 합쳐 60초. bucket 300, refill 300/s |

**Kinesis Data Streams와 Firehose**

| 항목 | 값 |
| :--- | :--- |
| 샤드 쓰기 | 1 MB/s 또는 1,000 records/s |
| 샤드 읽기 | 2 MB/s. `GetRecords` 샤드당 5 TPS, 호출당 10 MB 또는 10,000 records |
| 10 MB 반환 후 | 이후 5초 동안 호출이 예외를 던진다 |
| 레코드 payload | 최대 10 MiB. `PutRecords` 요청 전체도 10 MiB, 500 records |
| 보존 | 24시간에서 8,760시간(365일) |
| on-demand 시작 용량 | 4 MB/s 쓰기, 8 MB/s 읽기 |
| on-demand 상한 | 주요 3리전 10 GB/s 쓰기, 그 외 200 MB/s 쓰기 |
| capacity mode 전환 | 스트림당 24시간에 2회 |
| provisioned 샤드 쿼터 | 주요 3리전 20,000개, 그 외 1,000개 또는 6,000개 |
| on-demand 스트림 수 | 기본 50개 |
| EFO 처리량 | 컨슈머마다 샤드당 2 MB/s |
| EFO 컨슈머 수 | On-demand Advantage 50개, 그 외 20개 |
| 전파 지연 | 공유 1개 약 200 ms, 5개 약 1,000 ms. EFO 약 70 ms |
| Firehose 레코드 | 최대 1,000 KiB. `PutRecordBatch` 500 records 또는 4 MiB |
| Firehose buffer interval | 60초에서 900초 |
| Firehose Direct PUT 버퍼링 | 목적지 장애 시 최대 24시간 |
| Firehose retry duration | Redshift와 OpenSearch 전달에서 0초에서 7,200초 |
| Firehose dynamic partitioning | 스트림당 활성 파티션 500개, 파티션당 1 GB/s |
| Firehose 인제스트 과금 | 레코드 크기를 5 KB 단위로 올림해 계산한다 |

**MSK와 Flink**

| 항목 | 값 |
| :--- | :--- |
| Serverless ingress와 egress | 200 MBps와 400 MBps. 파티션당 5와 10 MBps |
| Serverless 파티션 | leader 2,400개. compacted 토픽 120개 |
| Serverless 메시지 | 최대 8 MiB |
| Serverless 클라이언트 연결 | 3,000개. 요청 15,000/s |
| Serverless 계정 상한 | 클러스터 10개 |
| Standard broker | 계정당 90개, 클러스터당 30개(ZooKeeper) 또는 60개(KRaft) |
| Standard broker 스토리지 | 1 GiB에서 16,384 GiB |
| Express broker | 스토리지 무제한, 파티션당 15 MB/s |
| Express broker 파티션 | `express.m7g.large` 1,500개에서 `express.m7g.16xlarge` 32,000개 |
| MSK Replicator | 계정당 15개, 토픽 750개, ingress 1 GB/s |
| Replicator 레코드 | cross-Region 10 MB, same-Region 20 MB |
| Flink KPU | 1 vCPU, 4 GB 메모리, storage 50 GB |
| Flink `Parallelism` | 기본 1, 기본 최대 256 |
| Flink `ParallelismPerKPU` | 기본 1, 최대 8 |
| Flink 애플리케이션당 KPU | 기본 상한 64. orchestration용 1 KPU 추가 과금 |

**분석 계층**

| 항목 | 값 |
| :--- | :--- |
| Glue DPU | 4 vCPU와 16 GB 메모리 |
| Glue job timeout | 최대 7일(10,080분). 기본 4.0 이하 2,880분, 5.0 이상 480분 |
| Glue retry | 0에서 10회. 기본 동시 실행 1 |
| Glue Flex execution | Glue 3.0 이상과 `G.1X`, `G.2X`만 |
| Redshift Serverless RPU | 1 RPU = 16 GB. 기본 128, 범위 4에서 512, 5개 리전 1024 |
| RPU 증가 단위 | 4에서 8까지 4, 8에서 512까지 8, 512에서 1024까지 32 |
| RPU와 스토리지 | 4 RPU는 32 TB, 8과 16 RPU는 128 TB. 초과 시 최소 32 RPU |
| CS 클러스터 조건 | EC2-VPC, 단일 노드 아님, 최대 32 compute node |
| CS 무료 크레딧 | 24시간마다 1시간 적립, 최대 30시간 누적 |
| Spectrum 과금 | us-east-1 스캔 TB당 5 USD, 쿼리당 최소 10 MB |
| Athena provisioned capacity | DPU-hour당 0.30 USD |
| Athena federated query | 쿼리당 최소 10 MB |
| EMR instance fleet | fleet당 instance type 최대 5개 |
| OpenSearch Service 도메인 | 최대 1,002 data node, 최대 25 PB |
| OpenSearch Serverless OCU | 6 GiB 메모리. indexing과 search 각각 최대 1,700 OCU |
| OpenSearch collection | collection당 index 1,000개, managed hot storage 10 TiB |

---

## 26. 답이 갈리는 짝 비교

| 짝 | 차이를 만드는 제약 |
| :--- | :--- |
| SQS standard 대 FIFO | standard는 순서를 보장하지 않고 처리량이 사실상 무제한이다. FIFO는 message group 안 순서를 보장하고 파티션당 300 TPS에 묶인다 |
| SQS 대 SNS | SQS는 pull이고 최대 14일 보존한다. SNS standard 토픽은 push이고 기본 보존이 없다. 보존이 필요한 팬아웃은 두 서비스를 겹쳐 쓴다 |
| SNS 대 EventBridge | SNS는 구독자에게 직접 밀어 넣고 속성 기반 필터를 쓴다. EventBridge는 event pattern으로 내용 기반 매칭을 하고 SaaS와 AWS 서비스 이벤트를 소스로 받으며 rule당 target이 5개다 |
| SNS standard 토픽 대 FIFO 토픽 | standard는 구독 12,500,000개에 처리량이 크고 archive와 replay가 없다. FIFO는 구독 100개에 message group당 300 messages/s이며 A2A archive와 replay를 1-365일 지원한다 |
| EventBridge rule 대 Pipes | rule은 하나의 이벤트를 여러 target에 라우팅한다. Pipes는 폴링 소스 하나를 타깃 하나에 연결하고 중간에 filter와 enrichment를 둔다 |
| EventBridge rule의 schedule 대 Scheduler | rule은 버스당 300개 안에서 정기 실행을 만든다. Scheduler는 schedule을 1,000만 개 단위로 두고 일회성 예약과 group 관리를 지원한다 |
| Amazon MQ 대 SQS와 SNS | Amazon MQ는 표준 메시징 프로토콜을 유지해 코드 재작성을 없앤다. SQS와 SNS는 AWS 고유 API라 신규 설계에 유리하고 운영 부담이 낮다 |
| Step Functions Standard 대 Express | Standard는 exactly-once에 최대 1년이고 `.sync`와 콜백과 Distributed Map을 지원하며 이력이 25,000 이벤트에 묶인다. Express는 5분에 이력 제한이 없고 세 기능을 지원하지 않는다 |
| Asynchronous Express 대 Synchronous Express | 전자는 at-least-once라 중복 실행이 가능하고, 후자는 at-most-once라 실행 누락이 가능하다 |
| inline Map 대 Distributed Map | inline Map은 반복 대상을 상태 입력으로 받아 256 KiB에 묶인다. Distributed Map은 S3 목록을 직접 읽고 자식 실행 10,000개와 Map Run redrive를 지원한다 |
| Kinesis Data Streams 대 Firehose | 스트림은 24시간에서 365일 보존해 재처리가 가능하다. Firehose는 저장하지 않고 buffer interval이 최소 60초다 |
| 공유 처리량 컨슈머 대 EFO 컨슈머 | 공유는 샤드당 2 MB/s를 나눠 쓰고 컨슈머 5개에서 약 1,000 ms다. EFO는 컨슈머마다 2 MB/s 전용에 약 70 ms이고 등록 수가 20개 또는 50개다 |
| Kinesis Data Streams 대 MSK | 스트림은 AWS 고유 API이고 샤드로 용량을 잰다. MSK는 Kafka API 그대로라 기존 앱과 도구를 쓰고 broker와 파티션을 설계한다 |
| MSK Serverless 대 Provisioned | Serverless는 클러스터 레벨만 프로비저닝하고 파티션 2,400개와 ingress 200 MBps와 메시지 8 MiB에 묶인다. Provisioned는 broker 타입과 수를 직접 정한다 |
| MSK Standard broker 대 Express broker | Standard는 broker당 스토리지가 1 GiB에서 16,384 GiB다. Express는 스토리지가 무제한이고 파티션당 15 MB/s에 파티션 수용량이 크다 |
| Amazon MQ 대 MSK | Amazon MQ는 JMS 같은 표준 프로토콜 호환이고, MSK는 Kafka API 호환이다. 기존 코드가 무엇으로 쓰였는지가 갈림길이다 |
| Managed Service for Apache Flink 대 Lambda 컨슈머 | Flink는 윈도 집계와 조인과 상태 기반 패턴 탐지를 맡는다. Lambda는 상태 없는 레코드 단위 처리에 맞다 |
| Athena 대 Redshift | Athena는 인프라 없이 S3를 그 자리에서 조회한다. Redshift는 여러 소스를 통합해 장기 보관하고 대형 테이블 다중 조인을 돈다 |
| Athena 대 EMR | Athena는 SQL만이다. EMR은 커스텀 코드로 Spark, Hadoop, Presto, HBase를 돌린다 |
| Redshift provisioned 대 Serverless | provisioned는 노드로 용량을 재고 Concurrency Scaling으로 급증을 흡수한다. Serverless는 RPU로 재고 자동 스케일링과 price-performance target을 쓴다 |
| Redshift Spectrum 대 Athena | 둘 다 S3를 조회하지만 Spectrum은 Redshift 클러스터와 같은 리전이어야 하고 로컬 테이블과의 조인이 목적이다. Athena는 클러스터가 없다 |
| Glue Data Catalog 대 Lake Formation | 카탈로그는 메타데이터 저장소다. Lake Formation은 그 위에 얹히는 authorization layer이고 엔진마다 지원 범위가 다르다 |
| EMR uniform instance group 대 instance fleet | group은 하나의 instance type과 하나의 구매 옵션이고 생성 후 바꿀 수 없다. fleet은 최대 5개 타입과 두 구매 옵션을 섞고 여러 AZ를 후보로 둔다 |
| OpenSearch Service 도메인 대 Serverless collection | 도메인은 node와 스토리지로 용량을 잰다. Serverless는 OCU로 재고 indexing과 search를 따로 스케일한다 |

---

## 27. 그럴듯하지만 성립하지 않는 조합

| 조합 | 성립하지 않는 이유 |
| :--- | :--- |
| FIFO 큐에 DLQ를 붙여 순서와 자동 재처리를 둘 다 얻는다 | AWS 문서가 FIFO 큐에 DLQ를 쓰면 메시지와 연산의 정확한 순서가 깨진다고 명시한다 |
| DLQ 보존 기간을 소스 큐와 같게 두면 안전하다 | standard 큐는 DLQ로 옮겨도 원래 enqueue timestamp를 유지하므로 소스에서 쓴 시간만큼 DLQ 보존이 줄어든다. 소스보다 길게 잡는다 |
| DLQ를 다른 계정의 큐로 지정해 격리한다 | DLQ는 소스 큐와 같은 계정, 같은 리전이어야 한다 |
| high throughput FIFO를 켜면 어느 리전에서든 수만 TPS가 나온다 | 리전별로 2,400에서 70,000 TPS로 약 29배 차이가 난다. ap-northeast-2는 9,000 구간에 없고 기본값 2,400 구간이다 |
| high throughput FIFO를 켰으니 message group은 하나여도 된다 | 파티션 배정이 message group ID 해시로 결정되므로 group이 하나면 파티션 하나에 몰려 300 TPS에 갇힌다 |
| FIFO 큐를 쓰면 언제 재전송해도 중복이 생기지 않는다 | 중복 제거 인터벌은 5분이다. 재시도가 5분을 넘기면 같은 dedup ID라도 새 메시지로 들어간다 |
| content-based deduplication을 켜고 attribute를 다르게 실어 구분한다 | 해시 대상은 본문뿐이고 attribute는 제외된다. 본문이 같으면 attribute가 달라도 중복으로 버려진다 |
| visibility timeout을 0으로 낮춰 실패 메시지를 빨리 재처리한다 | 즉시 재수신되어 폭주 루프가 생기고 수신 API 비용만 늘어난다 |
| SNS standard 토픽에 메시지를 보존해 두고 나중에 재처리한다 | standard 토픽은 기본 메시지를 보존하지 않는다. archive와 replay는 A2A FIFO 토픽에서만 1-365일 지원된다 |
| standard 토픽에 `ArchivePolicy`를 걸어 구독별 재생을 만든다 | 두 정책은 A2A FIFO 토픽에서만 지원된다. standard 토픽에서는 N/A다 |
| SNS FIFO 토픽으로 수천 개 구독에 순서 보장 팬아웃을 한다 | FIFO 토픽의 구독 상한은 토픽당 100개다 |
| SNS DLQ를 토픽에 붙여 전체 전달 실패를 모은다 | SNS의 DLQ는 구독에 붙는다. 구독마다 따로 설정한다 |
| EventBridge rule 하나로 10개 이상 서비스에 팬아웃한다 | rule당 target은 5개이고 조정 불가다. rule을 나누거나 SNS 토픽을 target으로 둔다 |
| EventBridge로 순서가 보장된 이벤트 처리를 구현한다 | EventBridge는 target에 임의 순서로 전달하며 순서 보장이 없다 |
| EventBridge archive replay로 장애 구간을 원래 순서대로 재처리한다 | replay는 순서를 보장하지 않고 이벤트 시각 기준 1분 구간으로 나눠 재생한다 |
| archive replay 대상 버스를 다른 계정의 버스로 지정한다 | replay는 archive의 소스 이벤트 버스로만 재생한다. 소스 버스는 생성 후 바꿀 수 없다 |
| Express workflow로 ECS task를 실행하고 완료를 기다린다 | Express는 `.sync`와 `.waitForTaskToken` 통합 패턴을 지원하지 않는다 |
| 결제 같은 비멱등 처리를 Express로 저비용 실행한다 | Asynchronous Express는 at-least-once라 중복 실행될 수 있다. exactly-once는 Standard다 |
| Synchronous Express로 유실이 허용되지 않는 요청을 처리한다 | Synchronous Express는 at-most-once라 실행 누락이 가능하다 |
| Standard workflow는 1년까지 도니 긴 루프를 그 안에서 다 돌린다 | 실행 이력이 25,000 이벤트에 닿으면 실행 자체가 실패한다 |
| 워크플로 타입을 나중에 Standard에서 Express로 바꾼다 | workflow type은 state machine 생성 후 변경할 수 없다 |
| Step Functions 상태 사이에 대용량 payload를 그대로 넘긴다 | input과 output은 256 KiB가 하드 쿼터다. S3에 두고 참조만 넘긴다 |
| inline Map으로 S3 객체 수백만 개를 반복한다 | 반복 대상이 상태 입력이라 256 KiB에 걸리고, Standard 실행 이력 25,000 이벤트에도 걸린다 |
| 콘솔에서 `StartSyncExecution`을 5분까지 돌린다 | 콘솔 실행은 60초에 만료된다. 5분까지 쓰려면 SDK나 CLI로 호출한다 |
| Firehose로 1초 미만 지연의 실시간 알림 파이프라인을 만든다 | buffer interval hint가 최소 60초다. 저지연이면 Kinesis Data Streams와 EFO 또는 Flink다 |
| Firehose에 쌓인 데이터를 다시 읽어 재처리한다 | Firehose는 저장소가 아니다. 목적지 장애 시 Direct PUT 소스만 24시간 버퍼링한다 |
| Firehose를 프라이빗 서브넷의 Redshift 클러스터에 직접 전달한다 | Firehose에서 Redshift로 전달하려면 publicly accessible한 클러스터여야 한다 |
| 컨슈머를 늘리기만 하면 Kinesis 읽기 처리량이 늘어난다 | 공유 처리량 모드는 샤드당 2 MB/s를 나눠 쓰고 컨슈머 5개에서 전파 지연이 약 1,000 ms로 늘어난다 |
| `GetRecords` 폴링을 더 자주 해서 지연을 줄인다 | 샤드당 5 TPS 제한이 있고 10 MB를 반환하면 이후 5초간 예외가 난다 |
| Kinesis capacity mode를 트래픽에 맞춰 수시로 바꾼다 | 스트림당 24시간 안에 2회로 제한된다 |
| 파티션 수천 개짜리 Kafka 워크로드를 MSK Serverless로 그대로 옮긴다 | Serverless는 클러스터당 leader 파티션 2,400개, ingress 200 MBps, 메시지 8 MiB가 상한이다 |
| Flink에서 parallelism을 올리면 KPU 상한 없이 확장된다 | 애플리케이션당 KPU 기본 상한이 64이고 `Parallelism` 상한은 `ParallelismPerKPU`와 KPU 상한의 곱으로 정해진다 |
| Lake Formation 권한을 걸면 모든 분석 엔진에서 row-level 통제가 강제된다 | Athena Spark와 EMR Serverless Hive와 Amazon EMR on EKS는 Lake Formation 권한을 지원하지 않는다. EMR(EC2) Hive는 row와 cell을 지원하지 않는다 |
| Lake Formation cell-level filter를 걸고 Glue job의 job bookmark로 증분 처리를 이어간다 | cell-level filter가 걸린 테이블을 읽는 job은 job bookmark, bounded execution, push-down predicate, `enableUpdateCatalog`를 쓸 수 없다 |
| Redshift Spectrum으로 다른 리전의 S3 데이터를 조회한다 | 클러스터와 S3 버킷이 같은 리전에 있어야 한다 |
| Spectrum 조회가 실패하니 external schema의 카탈로그 종류를 바꾼다 | Glue Data Catalog, Athena Data Catalog, Hive metastore 중 무엇을 참조해도 리전 제약은 그대로다 |
| Concurrency Scaling을 켜면 모든 쿼리가 급증 시 흡수된다 | interleaved sort key 테이블, 임시 테이블, Python UDF와 Lambda UDF 포함 쿼리, 시스템 테이블 접근 쿼리는 CS 클러스터로 라우팅되지 않는다 |
| Concurrency Scaling으로 어떤 노드 타입에서든 write를 확장한다 | write 확장은 RG와 RA3 노드에서만 동작하고 클러스터가 32 compute node 이하여야 한다 |
| Redshift Serverless base capacity를 4 RPU로 두고 대용량 웨어하우스를 돌린다 | 4 RPU는 managed storage 32 TB와 테이블당 100 컬럼이 실질 상한이고 일부 리전에서만 생성된다 |
| EMR uniform instance group에서 On-Demand와 Spot을 섞어 비용을 낮춘다 | group은 전체가 하나의 구매 옵션이고 생성 후 변경할 수 없다. 혼합은 instance fleet이다 |
| EMR 인스턴스에 `dedicated` 속성을 설정해 전용 하드웨어를 쓴다 | EMR은 개별 인스턴스의 `dedicated` 속성 설정을 지원하지 않는다. dedicated tenancy VPC 안에서 클러스터를 띄운다 |
| 정의된 기간 Spot으로 EMR 잡의 중단을 막는다 | 정의된 기간 Spot은 2022-12-31에 종료되었다 |
| OpenSearch Service를 멀티 AZ로 두면 AZ 간 전송 비용이 늘어난다 | OpenSearch Service는 AZ 간 트래픽과 shard 재배치 트래픽에 과금하지 않는다 |

---

## 28. 예상 문제 10문항

**Q1.** 한 거래소가 계좌별 주문 이벤트를 Amazon SQS FIFO 큐로 전달합니다. message group ID는 계좌 번호이고, 같은 계좌 안에서 주문 순서가 뒤바뀌면 정산이 틀어집니다. 최근 특정 메시지가 컨슈머 버그로 계속 실패하면서 큐 전체가 밀렸고, 팀은 실패 메시지를 자동으로 걷어내는 방안을 논의 중입니다. 순서 계약을 지키는 해법은 무엇입니까?

- A. FIFO 큐에 dead-letter queue를 붙이고 `maxReceiveCount`를 5로 설정한다
- B. standard 큐로 바꾸고 컨슈머가 시퀀스 번호로 순서를 재구성한다
- C. dead-letter queue를 붙이지 않고 실패 메시지가 자신의 message group만 막게 두면서 `ApproximateAgeOfOldestMessage` 알람으로 운영자가 개입하게 한다
- D. visibility timeout을 0초로 낮춰 실패 메시지가 즉시 다시 보이게 한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: C**

AWS 문서는 FIFO 큐에 dead-letter queue를 쓰면 메시지와 연산의 정확한 순서가 깨지므로 순서가 의미를 갖는 워크로드에는 쓰지 말라고 명시합니다. FIFO 큐에서 처리 실패는 해당 message group만 막고 다른 message group은 계속 흘러가므로, 영향 범위를 계좌 하나로 가둔 채 알람으로 운영이 개입하는 것이 순서 계약을 지키는 방식입니다.

- A가 틀린 이유: DLQ로 메시지를 옮기는 순간 그 계좌의 이벤트 순서가 끊긴다. 뒤따르던 주문이 먼저 처리되어 정산이 틀어진다.
- B가 틀린 이유: standard 큐는 순서를 보장하지 않으며 중복 전달도 가능하다. 애플리케이션에서 재정렬하려면 버퍼링과 타임아웃 처리를 새로 구현해야 하고 순서 보장은 여전히 근사값이다.
- D가 틀린 이유: visibility timeout을 0으로 두면 실패 메시지를 즉시 재수신해 폭주 루프가 생긴다. 순서는 지켜지지만 큐가 더 빨리 막히고 수신 API 비용만 늘어난다.

</details>

**Q2.** 한 회사가 재고 변경 이벤트를 세 개의 다운스트림 서비스에 전달합니다. 각 서비스는 이미 Amazon SQS 컨슈머로 구현되어 있고 재사용해야 합니다. 요구는 두 가지입니다. 첫째, 세 서비스 모두 SKU별로 동일한 순서로 이벤트를 받아야 합니다. 둘째, 다운스트림 장애로 처리가 밀린 경우 지난 이벤트를 다시 재생할 수 있어야 합니다. MOST appropriate 아키텍처는 무엇입니까?

- A. standard SNS 토픽에 standard SQS 큐 세 개를 구독시킨다
- B. FIFO SNS 토픽에 `ArchivePolicy`와 `ReplayPolicy`를 설정하고 FIFO SQS 큐 세 개를 구독시킨다
- C. EventBridge 사용자 지정 이벤트 버스를 두고 rule로 SQS 큐 세 개를 target으로 지정한다
- D. Amazon Kinesis Data Streams에 이벤트를 넣고 세 서비스가 각각 컨슈머 애플리케이션을 구현한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

FIFO 토픽과 FIFO 큐 조합은 AWS가 문서화한 순서 보장 팬아웃 패턴입니다. message group ID를 SKU로 두면 SKU 단위 순서가 유지됩니다. `ArchivePolicy`와 `ReplayPolicy`는 FIFO 토픽에서만 지원되며 구독별로 지난 이벤트를 재생할 수 있게 합니다.

- A가 틀린 이유: standard 토픽과 standard 큐는 순서를 보장하지 않는다. `ArchivePolicy`와 `ReplayPolicy` 기반 재생은 FIFO 토픽 전용이라 standard 토픽에서는 구독별 재생을 걸 수 없다.
- C가 틀린 이유: EventBridge는 target에 임의 순서로 전달하며 순서 보장이 없다. archive를 설정하면 이벤트를 보존하고 source bus로 replay할 수 있지만 replay 순서가 보장되지 않아 SKU별 순서 요구를 충족하지 못한다.
- D가 틀린 이유: 샤드 안 순서 보장과 최대 365일 보존으로 두 요구는 만족하지만, 지문이 기존 SQS 컨슈머 재사용을 조건으로 명시했다. 세 서비스 모두 컨슈머 애플리케이션을 새로 구현해야 한다.

</details>

**Q3.** 한 회사가 주문 완료 이벤트 하나를 12개 마이크로서비스에 전달하려 합니다. 각 서비스 팀은 자기 팀의 구독을 독립적으로 추가하거나 제거하고 싶어 하며, 중앙 플랫폼 팀이 그때마다 라우팅 설정을 고치는 일을 없애려 합니다. 이벤트는 이미 Amazon EventBridge 사용자 지정 이벤트 버스로 들어옵니다. LEAST operational overhead 해법은 무엇입니까?

- A. rule 하나를 만들고 12개 서비스를 모두 target으로 등록한다
- B. rule의 target으로 Amazon SNS 토픽 하나를 지정하고 각 서비스 팀이 자기 SQS 큐를 그 토픽에 구독시킨다
- C. rule을 세 개로 나누고 각 rule에 서비스 네 개씩 target으로 등록한다
- D. rule의 target으로 AWS Step Functions Parallel 상태를 실행하는 state machine을 지정하고 브랜치마다 서비스를 호출한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

EventBridge rule 하나가 가질 수 있는 target은 최대 5개이고 이 값은 조정할 수 없습니다. SNS 토픽을 target으로 두면 팬아웃 지점이 토픽으로 옮겨가고, standard 토픽은 토픽당 구독을 12,500,000개까지 받습니다. 각 팀이 자기 구독만 관리하면 되므로 중앙 팀 개입이 사라집니다.

- A가 틀린 이유: rule당 target 5개 상한 때문에 12개를 등록할 수 없다.
- C가 틀린 이유: 상한은 피하지만 rule이 세 개로 늘어 팀이 늘어날 때마다 중앙 팀이 어느 rule에 넣을지 판단하고 수정해야 한다. 운영 부담이 목표와 반대다.
- D가 틀린 이유: 동작은 하지만 서비스가 추가될 때마다 state machine 정의를 수정하고 배포해야 하며 실행마다 state transition 비용이 붙는다.

</details>

**Q4.** 한 결제 회사가 정산 워크플로를 오케스트레이션합니다. 워크플로는 카드사 승인 호출, 원장 기록, 정산 파일 생성 순으로 진행되고 마지막 단계는 Amazon ECS task로 실행되며 완료를 기다려야 합니다. 승인 호출은 절대 중복 실행되면 안 되고, 전체 실행은 길어야 40분입니다. 팀은 실행 이력을 콘솔에서 시각적으로 추적하려 합니다. MOST appropriate 구성은 무엇입니까?

- A. AWS Step Functions Asynchronous Express workflow를 사용한다
- B. AWS Step Functions Standard workflow를 사용한다
- C. AWS Step Functions Synchronous Express workflow를 사용한다
- D. Amazon EventBridge rule로 Lambda 함수를 순차 호출하는 체인을 만든다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Standard workflow는 실행 의미가 exactly-once라 중복 실행 금지 요구를 충족합니다. `.sync` 통합 패턴을 지원해 ECS task 완료를 기다릴 수 있고, 실행 이력이 콘솔에 남아 시각적 추적이 가능합니다. 최대 실행 시간이 1년이므로 40분도 여유롭습니다.

- A가 틀린 이유: Asynchronous Express는 at-least-once 실행이라 카드사 승인이 중복 호출될 수 있다. 최대 실행 시간도 5분이고 `.sync` 통합을 지원하지 않아 ECS task 완료를 기다릴 수 없다.
- C가 틀린 이유: Synchronous Express는 at-most-once라 승인 자체가 누락될 수 있고 최대 실행 시간이 5분이다. `.sync` 통합도 지원하지 않는다.
- D가 틀린 이유: 상태 전이, 재시도, 보상 처리, 실행 추적을 전부 직접 구현해야 하고 exactly-once 보장도 없다. 관리형 서비스로 위임하는 요구에 어긋난다.

</details>

**Q5.** 한 회사가 Amazon S3 버킷에 있는 객체 500만 개를 순회하며 객체마다 짧은 변환 작업을 실행하는 배치를 만듭니다. 각 객체 처리는 20초 이내에 끝나고 서로 독립적입니다. 실패한 객체만 골라 재실행할 수 있어야 하고, 전체 작업은 몇 시간 안에 끝나야 합니다. MOST appropriate 구현은 무엇입니까?

- A. Standard workflow의 inline Map 상태에 객체 목록을 입력으로 넘겨 병렬 처리한다
- B. Standard workflow의 Distributed Map 상태로 S3 객체 목록을 반복하고 Express 자식 워크플로에서 변환을 수행하며 실패 시 Map Run redrive로 재실행한다
- C. Lambda 함수 하나가 객체 목록 전체를 순회하며 변환한다
- D. Amazon EventBridge Scheduler로 5분마다 Lambda 함수를 호출해 미처리 객체를 조금씩 처리한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Distributed Map은 S3 객체 목록을 소스로 직접 받고 단일 Map Run 안에서 최대 10,000개의 자식 실행을 병렬로 돌립니다. Express 자식은 최대 1,000 TPS로 디스패치되어 500만 개 처리에 적합합니다. Map Run redrive로 실패한 항목만 다시 실행할 수 있어 재실행 요구도 충족합니다.

- A가 틀린 이유: inline Map은 반복 대상을 상태 입력으로 받아야 하는데 state input과 output은 256 KiB가 하드 쿼터다. 500만 개 목록이 들어가지 않고, 들어간다 해도 Standard 실행 이력 25,000 이벤트 상한에 걸려 실행이 실패한다.
- C가 틀린 이유: Lambda 함수 타임아웃 상한은 900초다. 500만 개를 한 함수 안에서 순회할 수 없다.
- D가 틀린 이유: 5분 간격 호출과 900초 타임아웃 조합으로는 처리량이 턱없이 부족해 몇 시간 안에 끝나지 않는다. 미처리 상태 추적도 직접 구현해야 한다.

</details>

**Q6.** 한 회사가 애플리케이션 로그를 Amazon S3와 Amazon OpenSearch Service에 동시에 적재합니다. 요구가 두 가지 추가되었습니다. 첫째, 파싱 로직에 버그가 있었던 지난 5일치 로그를 원본부터 다시 처리해야 합니다. 둘째, 앞으로 이상 탐지 애플리케이션을 컨슈머로 추가할 예정입니다. 현재 구조는 애플리케이션이 Amazon Data Firehose 전송 스트림 두 개에 직접 PUT 합니다. MOST appropriate 재설계는 무엇입니까?

- A. Firehose 전송 스트림을 세 개로 늘리고 이상 탐지 애플리케이션을 세 번째 스트림의 HTTP 엔드포인트로 등록한다
- B. Amazon Kinesis Data Streams를 앞에 두고 보존 기간을 7일로 설정한 뒤 S3와 OpenSearch Service로 가는 Firehose 전송 스트림 두 개를 스트림의 컨슈머로 연결하고 이상 탐지 애플리케이션도 컨슈머로 추가한다
- C. Firehose가 S3에 쓴 객체를 S3 이벤트 알림으로 다시 읽어 재처리한다
- D. Amazon MSK 클러스터를 도입하고 세 컨슈머를 Kafka 컨슈머 그룹으로 구현한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Firehose는 데이터 저장소가 아니라 전달 파이프라인이라 재처리 대상이 아닙니다. 목적지 장애 시 Direct PUT 소스에 한해 24시간 버퍼링할 뿐입니다. Kinesis Data Streams는 보존 기간을 24시간에서 365일까지 설정할 수 있어 5일 재처리 요구를 충족하고, 같은 스트림에 컨슈머를 추가하면 원본 데이터를 여러 애플리케이션이 나눠 읽습니다. Firehose 소스가 Kinesis Data Streams이면 Direct PUT 쿼터도 적용되지 않습니다.

- A가 틀린 이유: Firehose 스트림을 늘려도 데이터가 보존되지 않아 5일 재처리가 불가능하다. 애플리케이션이 세 스트림에 각각 PUT 하게 되어 인제스트 비용도 세 배가 된다.
- C가 틀린 이유: S3에 적재된 결과물은 이미 버그가 있는 파싱을 거친 데이터다. 원본부터 재처리하라는 요구를 충족하지 못한다.
- D가 틀린 이유: 요구는 충족할 수 있으나 broker 타입과 버전, 파티션 설계를 직접 관리해야 하고 컨슈머를 Kafka API로 새로 구현해야 한다. 기존 Firehose 전달 경로도 재구성 대상이 된다.

</details>

**Q7.** 한 IoT 플랫폼이 Amazon Kinesis Data Streams에서 센서 데이터를 읽습니다. 현재 다섯 개 애플리케이션이 같은 스트림을 구독하고 있는데, 컨슈머를 늘릴수록 데이터가 도착하기까지의 지연이 늘어 실시간 알림 요건인 200 ms를 넘겼습니다. 샤드 수는 처리량 기준으로는 충분합니다. 지연 요건을 충족하는 해법은 무엇입니까?

- A. 샤드 수를 두 배로 늘린다
- B. 각 애플리케이션을 enhanced fan-out 컨슈머로 등록하고 `SubscribeToShard`로 읽게 한다
- C. `GetRecords` 호출 주기를 줄여 폴링 빈도를 높인다
- D. 스트림을 on-demand 용량 모드로 전환한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

공유 처리량 컨슈머는 샤드당 총 2 MB/s를 나눠 쓰고 전파 지연이 컨슈머 한 개일 때 평균 약 200 ms, 다섯 개일 때 약 1,000 ms로 늘어납니다. enhanced fan-out 컨슈머는 샤드당 2 MB/s를 전용으로 받고 HTTP/2 push를 쓰므로 컨슈머 수와 무관하게 평균 약 70 ms를 유지합니다.

- A가 틀린 이유: 지연의 원인은 처리량 부족이 아니라 공유 폴링 모델이다. 샤드를 늘려도 컨슈머들이 `GetRecords`를 나눠 호출하는 구조는 그대로다.
- C가 틀린 이유: `GetRecords`는 샤드당 5 TPS로 제한되며 호출이 10 MB를 반환하면 이후 5초간 호출이 예외를 던진다. 폴링을 더 자주 해도 `ProvisionedThroughputExceededException`만 늘어난다.
- D가 틀린 이유: on-demand는 용량 관리 방식을 바꿀 뿐 컨슈머 간 처리량 공유와 전파 지연 특성을 바꾸지 않는다.

</details>

**Q8.** 한 분석 팀이 us-east-1의 Amazon Redshift 프로비저닝 클러스터에서 데이터 웨어하우스를 운영합니다. 원본 로그는 eu-west-1의 Amazon S3 데이터 레이크에 Parquet으로 쌓입니다. 팀이 Redshift Spectrum external table을 만들어 조회하려 했으나 쿼리가 실패합니다. 로그 데이터는 페타바이트 규모이고 조회는 하루 몇 차례 수행됩니다. 쿼리를 성립시키는 해법은 무엇입니까?

- A. external schema를 다시 만들고 Glue Data Catalog 대신 Hive metastore를 참조한다
- B. 조회 대상 데이터를 S3 cross-Region replication으로 us-east-1 버킷에 복제하고 그 버킷을 참조하는 external table을 만든다
- C. 클러스터에 연결된 IAM role에 `s3:GetObject` 권한을 추가한다
- D. 클러스터에서 Concurrency Scaling을 활성화한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Redshift Spectrum은 클러스터와 S3 버킷이 같은 리전에 있어야 합니다. 리전이 다르면 external table 조회가 성립하지 않으므로, 조회 대상 데이터를 클러스터와 같은 리전으로 복제하거나 클러스터를 데이터가 있는 리전으로 옮겨야 합니다.

- A가 틀린 이유: external schema는 Glue Data Catalog, Athena Data Catalog, EMR의 Hive metastore 중 무엇을 참조해도 되지만 카탈로그 종류는 실패 원인과 무관하다. 리전 제약은 그대로 남는다.
- C가 틀린 이유: IAM 권한 부족이면 접근 거부 오류가 나지만 이 시나리오의 원인은 리전 불일치다. 권한을 추가해도 다른 리전 버킷은 조회되지 않는다.
- D가 틀린 이유: Concurrency Scaling은 동시 쿼리 급증을 흡수하는 기능이며 Spectrum의 리전 제약과 무관하다. 게다가 interleaved sort key 테이블이나 시스템 테이블 접근 쿼리처럼 라우팅되지 않는 조건도 별도로 존재한다.

</details>

**Q9.** 한 제조 회사가 온프레미스 주문 시스템을 AWS로 옮깁니다. 시스템은 JMS 기반 메시징을 쓰고 있으며 오랜 기간 검증된 메시징 코드를 수정하지 말라는 조건이 붙었습니다. 이전 후에도 브로커는 VPC 내부에서만 접근 가능해야 하고, Availability Zone 장애 시에도 메시지가 유실되지 않아야 합니다. 12개월 안에 이전을 마쳐야 합니다. MOST appropriate 해법은 무엇입니까?

- A. 메시징 코드를 Amazon SQS SDK 호출로 바꾸고 FIFO 큐로 이전한다
- B. Amazon MQ에서 ActiveMQ 브로커를 active/standby 이중화 구성으로 만들고 VPC 내부 엔드포인트로만 접근하게 한다
- C. Amazon MSK 클러스터를 만들고 애플리케이션을 Kafka 클라이언트로 다시 작성한다
- D. Amazon EventBridge 사용자 지정 이벤트 버스로 이전하고 API destination으로 백엔드를 호출한다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: B**

Amazon MQ는 Apache ActiveMQ Classic과 RabbitMQ를 관리형으로 제공하며 표준 메시징 프로토콜을 그대로 씁니다. 기존 JMS 코드를 재작성하지 않고 이전하는 것이 이 서비스의 문서화된 목적입니다. VPC 내 private endpoint로 접근을 제한할 수 있고, 여러 AZ에 걸친 이중화 구성으로 AZ 장애에 대비합니다.

- A가 틀린 이유: SQS는 AWS 고유 API를 쓰므로 메시징 코드를 전부 다시 써야 한다. 코드 수정 금지 조건에 정면으로 어긋난다.
- C가 틀린 이유: MSK는 Kafka API를 그대로 쓸 수 있다는 이점이 있지만 기존 코드는 JMS 기반이라 Kafka 클라이언트로 재작성해야 한다. broker 타입과 파티션 설계 운영 부담도 새로 생긴다.
- D가 틀린 이유: EventBridge는 이벤트 라우팅 서비스이며 JMS 프로토콜을 제공하지 않는다. 애플리케이션 전면 재작성이 필요하고 순서 보장도 없다.

</details>

**Q10.** (다답형) 한 회사가 프라이빗 서브넷의 EC2 워커에서 실행되는 데이터 파이프라인을 개선합니다. 워커는 Amazon S3에서 파일을 읽고 변환한 뒤 Amazon RDS에 적재합니다. 최근 두 가지 문제가 보고되었습니다. 첫째, 트래픽이 몰리면 RDS 커넥션 한계를 넘겨 적재가 실패합니다. 둘째, NAT gateway 데이터 처리 요금이 월 비용의 큰 비중을 차지합니다. 두 문제를 해결하는 조치 세 가지를 고르십시오.

- A. 워커 앞에 Amazon SQS 큐를 두어 인입을 버퍼링하고 컨슈머 수로 RDS에 대한 쓰기 속도를 제어한다
- B. VPC에 S3용 gateway endpoint를 만들고 프라이빗 서브넷 라우팅 테이블에 연결한다
- C. Amazon Data Firehose의 buffer interval hint를 30초로 설정해 적재 지연을 줄인다
- D. 적재를 담당하는 AWS Lambda 컨슈머에 reserved concurrency를 설정해 동시 커넥션 수가 RDS 상한을 넘지 않게 한다
- E. S3 버킷을 다른 리전에 복제해 읽기 지연을 줄인다
- F. EventBridge rule 하나의 target 수를 10개로 늘려 처리 병렬도를 높인다

<details markdown="1">
<summary>정답과 해설</summary>

**정답: A, B, D**

A는 큐를 버퍼로 두어 인입 급증을 흡수하고 다운스트림이 감당 가능한 속도로만 소비하게 하는 표준 패턴입니다. B는 S3 트래픽을 gateway endpoint로 흘려 NAT gateway 데이터 처리 요금 자체를 발생시키지 않습니다. D는 Lambda의 reserved concurrency가 상한으로 동작하는 성질을 이용해 동시 데이터베이스 커넥션 수를 구조적으로 제한합니다.

- C가 틀린 이유: Firehose buffer interval hint의 범위는 60초에서 900초라 30초를 설정할 수 없다. 게다가 이 시나리오의 문제는 지연이 아니라 커넥션 한계와 전송 비용이다.
- E가 틀린 이유: 크로스 리전 복제는 리전 간 전송 요금과 저장 비용을 추가할 뿐 NAT gateway 비용을 줄이지 않는다. 워커가 다른 리전 버킷을 읽으면 비용이 더 늘어난다.
- F가 틀린 이유: EventBridge rule당 target은 최대 5개이며 조정할 수 없다. 병렬도를 높인다 해도 RDS 커넥션 한계를 더 빨리 넘길 뿐이다.

</details>

---

## 29. Reference

- [Amazon SQS - Amazon SQS message quotas](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-messages.html)
- [Amazon SQS - Amazon SQS queue quotas](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-queues.html)
- [Amazon SQS - Amazon SQS FIFO queue quotas](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas-fifo.html)
- [Amazon SQS - High throughput for FIFO queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/high-throughput-fifo.html)
- [Amazon SQS - Exactly-once processing in Amazon SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-exactly-once-processing.html)
- [Amazon SQS - Amazon SQS dead-letter queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [AWS Decision Guides - Choosing between Amazon SNS, Amazon SQS, and Amazon EventBridge](https://docs.aws.amazon.com/decision-guides/latest/sns-or-sqs-or-eventbridge/sns-or-sqs-or-eventbridge.html)
- [AWS General Reference - Amazon Simple Notification Service endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/sns.html)
- [Amazon SNS - Message ordering and deduplication with FIFO topics](https://docs.aws.amazon.com/sns/latest/dg/sns-fifo-topics.html)
- [Amazon SNS - Message archiving for FIFO topic owners](https://docs.aws.amazon.com/sns/latest/dg/message-archiving-and-replay-topic-owner.html)
- [AWS Lambda - Invoking Lambda with Amazon SNS notifications](https://docs.aws.amazon.com/lambda/latest/dg/with-sns.html)
- [Amazon SNS - Message deduplication for FIFO topics](https://docs.aws.amazon.com/sns/latest/dg/fifo-message-dedup.html)
- [Amazon SNS - Message delivery for FIFO topics](https://docs.aws.amazon.com/sns/latest/dg/fifo-message-delivery.html)
- [Amazon EventBridge - Amazon EventBridge quotas](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-quota.html)
- [Amazon EventBridge - EventBridge Pipes](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-pipes.html)
- [Amazon EventBridge - Archive and replay events](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-archive.html)
- [Amazon EventBridge Scheduler - Quotas for EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/scheduler-quotas.html)
- [AWS Step Functions - Quotas](https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html)
- [AWS Step Functions - Choosing workflow type in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [AWS Step Functions - Distributed Map state](https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html)
- [Amazon Kinesis Data Streams - Quotas and limits](https://docs.aws.amazon.com/streams/latest/dev/service-sizes-and-limits.html)
- [Amazon Kinesis Data Streams - Enhanced fan-out consumers](https://docs.aws.amazon.com/streams/latest/dev/enhanced-consumers.html)
- [Amazon Kinesis Data Streams - Choosing the data stream capacity mode](https://docs.aws.amazon.com/streams/latest/dev/how-do-i-size-a-stream.html)
- [Amazon Data Firehose - Amazon Data Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)
- [Amazon Data Firehose - What is Amazon Data Firehose?](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html)
- [Amazon MSK - What is Amazon Managed Streaming for Apache Kafka?](https://docs.aws.amazon.com/msk/latest/developerguide/what-is-msk.html)
- [Amazon MSK - Amazon MSK quota](https://docs.aws.amazon.com/msk/latest/developerguide/limits.html)
- [Amazon MQ - What is Amazon MQ?](https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/welcome.html)
- [Amazon Managed Service for Apache Flink - What is Amazon Managed Service for Apache Flink?](https://docs.aws.amazon.com/managed-flink/latest/java/what-is.html)
- [Amazon Managed Service for Apache Flink - Application scaling](https://docs.aws.amazon.com/managed-flink/latest/java/how-scaling.html)
- [AWS Glue - What is AWS Glue?](https://docs.aws.amazon.com/glue/latest/dg/what-is-glue.html)
- [AWS Glue - Configuring job properties for Spark jobs](https://docs.aws.amazon.com/glue/latest/dg/add-job.html)
- [AWS Lake Formation - Integrating with other AWS services](https://docs.aws.amazon.com/lake-formation/latest/dg/working-with-services.html)
- [Amazon Athena - When should I use Athena?](https://docs.aws.amazon.com/athena/latest/ug/when-should-i-use-ate.html)
- [Amazon Athena - Connecting to data sources](https://docs.aws.amazon.com/athena/latest/ug/connect-to-a-data-source.html)
- [Amazon Redshift - Working with concurrency scaling](https://docs.aws.amazon.com/redshift/latest/dg/concurrency-scaling.html)
- [Amazon Redshift - Understanding Amazon Redshift Serverless capacity](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-capacity.html)
- [Amazon Redshift - Getting started with Amazon Redshift Spectrum](https://docs.aws.amazon.com/redshift/latest/dg/c-getting-started-using-spectrum.html)
- [Amazon EMR - Instance purchasing options](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-instance-purchasing-options.html)
- [Amazon EMR Serverless - What is Amazon EMR Serverless?](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/emr-serverless.html)
- [Amazon OpenSearch Service - What is Amazon OpenSearch Service?](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html)
- [Amazon OpenSearch Serverless - Managing capacity limits](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-scaling.html)
- [Amazon QuickSight - What is Amazon QuickSight?](https://docs.aws.amazon.com/quicksight/latest/user/welcome.html)
- [Amazon Redshift pricing](https://aws.amazon.com/redshift/pricing/)
- [Amazon Athena pricing](https://aws.amazon.com/athena/pricing/)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
