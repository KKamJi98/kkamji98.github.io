---
title: InfluxDB Migration 1.x to 1.x
date: 2025-04-06 10:49:55 +0900
author: kkamji
categories: [influxdb]
tags: [influxdb, ec2, aws, tsdb, migration, export, import]
comments: true
image:
  path: /assets/img/kkam-img/kkam.webp
---

Legacy EC2 Instance에 설치되어 있는 InfluxDB 1.x를 새로운 EC2 Instance로 마이그레이션 하는 방법에 대해 정리해보았습니다.

---

## Environment

- EC2 Instance(t2.micro) 2대  
  - `influxdb-1` (Old) ip: `10.0.1.129`
  - `influxdb-2` (New) ip: `10.0.1.67`
- `influxdb v1.11.8`  

---

## InfluxDB, TSDB란?

**InfluxDB**는 시계열(TS, Time-Series) 데이터에 특화된 오픈소스 데이터베이스입니다. 시계열 데이터는 센서, 모니터링, 로그 등 시간축을 따라 들어오는 연속적·대량 데이터를 다루는 데 최적화된 구조를 갖춥니다. 이러한 **TSDB(Time-Series Database)**는 시간 정보를 핵심 인덱스로 사용해 빠른 수집·보관·분석이 가능하며, InfluxDB 역시 Measurement·Tag·Field·Time 구성을 통해 고속 쓰기와 효율적 조회를 지원합니다.

InfluxDB는 DevOps 모니터링(서버 CPU, 메모리 지표)이나 IoT 센서, 주가·환율 같은 금융 데이터 등 폭넓은 시나리오에 활용될 수 있습니다. Retention Policy로 오래된 데이터를 자동 정리하여 스토리지 사용을 조절하고, Telegraf·Grafana 등과 연동해 실시간 대시보드도 쉽게 구성할 수 있어 인프라 및 애플리케이션 모니터링에 적합합니다.

---

## Export 데이터에서 Line Protocol과 Export 방식의 차이

InfluxDB 1.x 버전에서 데이터를 내보낼 때는 크게 두 가지 접근 방식을 사용할 수 있습니다.

### 1) **Line Protocol 기반 Export**

`influx_inspect export -lponly` 옵션이나, `SELECT` 결과를 직접 Line Protocol로 변환하는 방식입니다.

- **장점**: InfluxDB가 이해하는 **Native** 포맷이므로, timestamp·tag·field 정보를 그대로 보존하여 Import 시 매끄럽습니다.  
- **단점**: CSV보다 사람이 읽기에는 다소 불편할 수 있습니다.

### 2) **CSV 기반 Export**

`influx -execute "SELECT..." -format csv` 명령어로 CSV 파일을 얻을 수 있습니다.

- **장점**: 사람이 직관적으로 보기 편하고 엑셀 등 다른 툴에서 확인하기 좋습니다.  
- **단점**: **직접 Import는 불가능**합니다. InfluxDB가 CSV 형식을 바로 파싱하지 못하므로, 중간에 Line Protocol 변환 과정이 필요합니다.

> 이번 포스팅에서는 **Line Protocol** 형식으로 마이그레이션하는 스크립트를 활용합니다.

---

## 테스트 시나리오

마이그레이션이 정상 동작하는지, 누락 없이 잘 덮어씌울 수 있는지 확인하기 위해 아래와 같은 시나리오로 검증했습니다. Grafana를 사용해 Old Influx와 New Influx를 DataSource를 한 대시보드를 통해 비교 관찰했습니다.

1. **New Influx(influxdb-2)에서 Measurement를 삭제한 뒤**, Old Influx(influxdb-1) Original DB를 Migration  
   - 특정 Measurement를 인위적으로 삭제하고 다시 가져오면, 정상 복원되는지 확인

2. **influxdb-2의 특정 구간 데이터를 삭제한 뒤**(예: 5시간 전부터 3시간 전 까지), Old → New 마이그레이션 후 그 구간이 복구되는지 확인
   ```sql
   influx -database test_db -execute "DELETE FROM test_data WHERE time < now() - 3h AND time > now() - 5h"
   ```
   - 시간 구간에 구멍을 만든 뒤 스크립트를 실행해 데이터를 복원했습니다.

3. **Old Influxdb(Influxdb-1)**에서 마이그레이션 하려는 데이터의 같은 시간에 **New Influxdb(influxdb-2)**에 이미 데이터가 존재할 때, **값을 덮어 씌우는지(Overwrite)** 여부 확인  
   - Migration 전, 일부 시간대에 '이상한 데이터'를 삽입한 뒤 해당 시간대에 값을 덮어씌운 뒤, 확인

---

## 1분 간격 더미 데이터 스크립트

테스트 편의를 위해, 아래 스크립트를 cron에 등록해 Old Influx와 New Influx 양쪽으로 분 단위 데이터를 쌓았습니다.

```bash
#!/bin/bash

# 한국 시간(UTC+9) 시+분 합산으로 데이터 생성
hour=$(TZ="Asia/Seoul" date +"%H")
minute=$(TZ="Asia/Seoul" date +"%M")
sum=$((10#$hour + 10#$minute))

# 1) local influx (old)
curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=${sum}"

# 2) remote influx (new)
curl -i -XPOST "http://10.0.1.67:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=${sum}"
```

이 스크립트를 1분마다 실행하면 같은 시점의 데이터가 Old·New에 동시 기록됩니다. 특정 시점에 New DB에서 일부 데이터를 지우거나 덮어쓰고, 마이그레이션을 통해 데이터를 재확인할 수 있습니다.

![dummy_data_grafana](/assets/img/influxdb/dummy_data_grafana.webp)

---

## New InfluxDB의 Measurement 삭제

Old InfluxDB에서 데이터를 마이그레이션하기 전에 New InfluxDB에 있는 Measurement를 삭제합니다. 아래 명령어로 특정 Measurement를 삭제할 수 있습니다.

```shell
## 현재 Measurement의 데이터 개수 확인
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT COUNT(*) FROM test_data"
name: test_data
time count_value
---- -----------
0    1225

## 특정 Measurement 삭제
influx -database test_db -execute "DROP MEASUREMENT test_data"

## 삭제 후 데이터 개수 확인
root@ip-10-0-1-67:~# influx -database test_db -execute "DROP MEASUREMENT test_data"
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT COUNT(*) FROM test_data"
## 결과 없음
```

### Grafana에서 확인

![delete_measurements](/assets/img/influxdb/delete_measurements.webp)

---

## Old InfluxDB에서 데이터 Export 및및 New InfluxDB에 Import

기존 Old InfluxDB에서 데이터를 추출하여 SCP 또는 rsync로 New InfluxDB로 복사한 뒤, `influx_inspect export`를 통해 Line Protocol 형식으로 Export합니다. 이후 `curl`을 사용해 New InfluxDB에 데이터를 Import합니다.
아래 스크립트를 사용해 자동화 했습니다.

### 사용 스크립트 설명

아래 스크립트는 Old InfluxDB에서 데이터를 추출(Export)하여 Line Protocol로 변환한 뒤, New InfluxDB에 데이터베이스를 생성하고 Import까지 진행합니다.

```bash
#!/bin/bash
## influxdb_migration.sh

set -e

# 소스 인스턴스의 InfluxDB 데이터 디렉터리 및 WAL 경로 (환경에 맞게 수정)
SOURCE_DATADIR="/var/lib/influxdb/data"
SOURCE_WALDIR="/var/lib/influxdb/wal"

# 대상 인스턴스의 IP 또는 호스트명
TARGET_HOST="10.0.1.67"

echo "=== 데이터베이스 목록 추출 ==="
DATABASES=$(influx -execute "SHOW DATABASES" -format csv | tail -n +2 | tr -d '"' | sed 's/^databases,//')

for DB in $DATABASES; do
  # _internal 제외, 빈 문자열 제외
  if [[ -z "$DB" || "$DB" == "_internal" ]]; then
      continue
  fi

  echo "=== '$DB' 데이터베이스 데이터 내보내기 ==="
  EXPORT_FILE="/tmp/${DB}_export.lp"
  CLEAN_FILE="/tmp/${DB}_export_clean.lp"

  # Line Protocol로 export
  influx_inspect export -database "$DB" \
    -datadir "$SOURCE_DATADIR" \
    -waldir "$SOURCE_WALDIR" \
    -lponly \
    -out "$EXPORT_FILE"

  echo "=== '$DB'에서 DDL(데이터베이스 생성) 문 제거 ==="
  grep -v "^CREATE DATABASE" "$EXPORT_FILE" > "$CLEAN_FILE"

  echo "=== 대상 인스턴스에서 '$DB' 데이터베이스 생성 ==="
  curl -i -XPOST "http://${TARGET_HOST}:8086/query" \
    --data-urlencode "q=CREATE DATABASE $DB" >/dev/null

  echo "=== '$DB' 데이터 전송 ==="
  curl -i -XPOST "http://${TARGET_HOST}:8086/write?db=${DB}&precision=ns" \
    --data-binary @"$CLEAN_FILE"

  echo "=== '$DB' 마이그레이션 완료 ==="
done

echo "=== 모든 데이터베이스 마이그레이션 완료 ==="
```

- **SHOW DATABASES**로 기존 DB 목록을 받아옵니다.  
- **influx_inspect export**로 각 DB를 Line Protocol 형식으로 추출합니다.  
- `grep -v "^CREATE DATABASE"`로 Export 파일 내 `CREATE DATABASE` 문을 제거합니다.  
- `curl -XPOST`를 통해 New InfluxDB에 해당 DB를 생성하고, Line Protocol 데이터를 write합니다.

```shell
## Old InfluxDB에서 스크립트 실행
root@ip-10-0-1-129:~# bash influxdb_migration.sh
=== 데이터베이스 목록 추출 ===
=== 'test_db' 데이터베이스 데이터 내보내기 ===
writing out wal file data for test_db/autogen...complete.
=== 'test_db'에서 DDL 명령문 제거 (순수 데이터만 추출) ===
=== 대상 인스턴스에서 'test_db' 데이터베이스 생성 ===
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    58    0    33  100    25   7202   5456 --:--:-- --:--:-- --:--:-- 14500
=== 'test_db' 데이터 대상 인스턴스로 전송 ===
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: 5a193929-12ed-11f0-8581-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: 5a193929-12ed-11f0-8581-02dcd5ada24d
Date: Sun, 06 Apr 2025 13:45:07 GMT

=== 'test_db' 마이그레이션 완료 ===
=== 모든 데이터베이스 마이그레이션 완료 ===

## New InfluxDB에서 데이터 확인
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT COUNT(*) FROM test_data"
name: test_data
time count_value
---- -----------
0    1233
```

### Grafana에서 결과 확인

![migration_grafana](/assets/img/influxdb/migration_grafana.webp)

---

## Old InfluxDB에서 특정 시간대 데이터 삭제 후 마이그레이션

Old InfluxDB에서 특정 시간대 데이터를 삭제한 뒤, New InfluxDB로 마이그레이션을 진행합니다. 아래 명령어로 특정 시간대 데이터를 삭제할 수 있습니다.

```shell
## New InfluxDB의 특정 시간대 데이터 확인 ( 현재시간 5시간 이전 ~ 3시간 이전 )
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT COUNT(*) FROM test_data WHERE time < now() - 3h AND time > now() - 5h"
name: test_data
time                count_value
----                -----------
1743929389592826534 120

## New InfluxDB에서 해당 시간데 데이터 삭제
root@ip-10-0-1-67:~# influx -database test_db -execute "DELETE FROM test_data WHERE time < now() - 3h AND time > now() - 5h"

## New InfluxDB에서 삭제된 데이터 확인
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT COUNT(*) FROM test_data WHERE time < now() - 3h AND time > now() - 5h"
## 결과 없음
```

### Grafana에서 결과 확인

![delete_partial_measurement](/assets/img/influxdb/delete_partial_measurement.webp)

> 약 17:00 ~ 20:00 사이의 데이터가 삭제되어 그래프가 흐트러진 것을 확인할 수 있습니다.  
> 이후 Old InfluxDB에서 마이그레이션을 진행하면, New InfluxDB에 해당 시간대 데이터가 복원되어야 합니다.  
{: .prompt-tip}

```shell
## Old InfluxDB에서 마이그레이션 스크립트 실행
root@ip-10-0-1-129:~# bash influxdb_migration.sh
=== 데이터베이스 목록 추출 ===
=== 'test_db' 데이터베이스 데이터 내보내기 ===
writing out wal file data for test_db/autogen...complete.
=== 'test_db'에서 DDL 명령문 제거 (순수 데이터만 추출) ===
=== 대상 인스턴스에서 'test_db' 데이터베이스 생성 ===
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    58    0    33  100    25   7202   5456 --:--:-- --:--:-- --:--:-- 14500
=== 'test_db' 데이터 대상 인스턴스로 전송 ===
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: 5a193929-12ed-11f0-8581-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: 5a193929-12ed-11f0-8581-02dcd5ada24d
Date: Sun, 06 Apr 2025 13:45:07 GMT

=== 'test_db' 마이그레이션 완료 ===
=== 모든 데이터베이스 마이그레이션 완료 ===
root@ip-10-0-1-129:~# bash influxdb_migration.sh
=== 데이터베이스 목록 추출 ===
=== 'test_db' 데이터베이스 데이터 내보내기 ===
writing out wal file data for test_db/autogen...complete.
=== 'test_db'에서 DDL 명령문 제거 (순수 데이터만 추출) ===
=== 대상 인스턴스에서 'test_db' 데이터베이스 생성 ===
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    58    0    33  100    25  15006  11368 --:--:-- --:--:-- --:--:-- 29000
=== 'test_db' 데이터 대상 인스턴스로 전송 ===
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: 280bcfaf-12ef-11f0-85b1-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: 280bcfaf-12ef-11f0-85b1-02dcd5ada24d
Date: Sun, 06 Apr 2025 13:58:02 GMT

=== 'test_db' 마이그레이션 완료 ===
=== 모든 데이터베이스 마이그레이션 완료 ===
```

### Grafana에서 결과 확인

![restored_partial_measurement](/assets/img/influxdb/restored_partial_measurement.webp)

> 약 17:00 ~ 20:00 사이의 삭제된 데이터가 복원되어 그래프가 되돌아온 것을 확인할 수 있습니다.  
{: .prompt-tip}

---

## Old InfluxDB에서 특정 시간대 데이터 덮어쓰기

Old InfluxDB에서 특정 시간대에 '이상한 데이터'를 삽입한 뒤, New InfluxDB로 마이그레이션을 진행합니다.

### 이상한 데이터 삽입 후 마이그레이션션

```shell
## New InfluxDB에서 데이터 삭제
root@ip-10-0-1-67:~# influx -database test_db -execute "DELETE FROM test_data"

## New InfluxDB에서 해당 시간대에 이상한 데이터 삽입 (100, 150, 200)
root@ip-10-0-1-67:~# TS1=$(($(date -d '3 hours ago' +%s) * 1000000000))
root@ip-10-0-1-67:~# TS2=$(($(date -d '4 hours ago' +%s) * 1000000000))
root@ip-10-0-1-67:~# TS3=$(($(date -d '5 hours ago' +%s) * 1000000000))

root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=100 $TS1"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: c597d158-12f3-11f0-8620-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: c597d158-12f3-11f0-8620-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:31:04 GMT

root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=0 $TS2"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: c7b7aac9-12f3-11f0-8621-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: c7b7aac9-12f3-11f0-8621-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:31:08 GMT

root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=100 $TS3"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: c9f80438-12f3-11f0-8622-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: c9f80438-12f3-11f0-8622-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:31:12 GMT

## 데이터 확인
root@ip-10-0-1-67:~# influx -database test_db -execute "SELECT * FROM test_data"
name: test_data
time                location   value
----                --------   -----
1743931839000000000 serverroom 100
1743935436000000000 serverroom 0
1743939033000000000 serverroom 100

## Migration 스크립트 실행
root@ip-10-0-1-129:~# bash influxdb_migration.sh
=== 데이터베이스 목록 추출 ===
=== 'test_db' 데이터베이스 데이터 내보내기 ===
writing out wal file data for test_db/autogen...complete.
=== 'test_db'에서 DDL 명령문 제거 (순수 데이터만 추출) ===
=== 대상 인스턴스에서 'test_db' 데이터베이스 생성 ===
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100    58    0    33  100    25   8830   6689 --:--:-- --:--:-- --:--:-- 19333
=== 'test_db' 데이터 대상 인스턴스로 전송 ===
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: 1db7ca55-12f3-11f0-8617-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: 1db7ca55-12f3-11f0-8617-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:26:23 GMT

=== 'test_db' 마이그레이션 완료 ===
=== 모든 데이터베이스 마이그레이션 완료 ===
```

### Grafana에서 이상한 값 확인

![check_strange_data](/assets/img/influxdb/check_strange_data.webp)

### 데이터 덮어쓰기  

> 100, 0, 100으로 삽입한 데이터로 인해 그래프가 흐트러진 것을 확인할 수 있습니다. 이제 해당 값을 50, 50, 50으로 덮어씌워 보겠습니다.  
{: .prompt-tip}

```shell
## 데이터 삽입 (덮어쓰기)
root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=50 $TS1"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: d7d53509-12f4-11f0-863f-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: d7d53509-12f4-11f0-863f-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:38:45 GMT

root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=50 $TS2"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: dd490164-12f4-11f0-8640-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: dd490164-12f4-11f0-8640-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:38:54 GMT

root@ip-10-0-1-67:~# curl -i -XPOST "http://localhost:8086/write?db=test_db" \
  --data-binary "test_data,location=serverroom value=50 $TS3"
HTTP/1.1 204 No Content
Content-Type: application/json
Request-Id: e074ed20-12f4-11f0-8641-02dcd5ada24d
X-Influxdb-Build: OSS
X-Influxdb-Version: v1.11.8
X-Request-Id: e074ed20-12f4-11f0-8641-02dcd5ada24d
Date: Sun, 06 Apr 2025 14:38:59 GMT
```

### Grafana 확인

![check_overwrite_data](/assets/img/influxdb/check_overwrite_data.webp)

---

## 결과

1. **InfluxDB 1.x → 1.x 마이그레이션**  
   - `influx_inspect export -lponly`와 `curl write` 조합으로 DB별 데이터를 안정적으로 옮길 수 있었습니다.  
   - Old DB를 종료하지 않아도 마이그레이션이 가능했습니다.

2. **InfluxDB의 불변성**  
   - 한 번 기록된 데이터(timestamp + tag + field)는 Overwrite가 아니라 **Immutable**에 가깝습니다.  
   - 정확히 같은 timestamp+tag+field 조합이면 upsert처럼 갱신될 수 있으나, 보통은 추가 포인트로 처리됩니다.

3. **테스트 시 부실한 점**  
   - GB~TB 단위 대규모 데이터의 성능 테스트는 미흡했습니다.  
   - Write가 계속 들어오는 환경에서 마지막 순간의 데이터가 누락될 위험을 완전히 배제하기 어렵습니다.  
   - Best Practice로는 마이그레이션 직전에 read-only 상태를 설정하거나, write를 잠시 중단하는 방법이 있습니다.

4. **1.x→2.x, 2.x→2.x 마이그레이션**    
   - Flux, Bucket 등 구조적 차이가 있으므로 절차가 달라질 수 있습니다.  
   - 2.x에서는 `influx backup/restore`, `influxd upgrade` 등을 검토해야 합니다.  
   - 1.x to 2.x 직접 restore는 지원되지 않습니다.

---

## 마무리

`influx_inspect export → curl write` 방식을 통해 DB 전체를 옮겼으며, 특정 시간대 데이터를 삭제했다가 다시 가져오는 시나리오로 데이터 누락 여부를 검증했습니다. 기본적인 기능으로는 문제가 없었지만, 실제 운영환경에서는 다음 사항을 유념해야 합니다.

1. **Downtime 없이 진행할 경우** 최신 시점 데이터 누락 가능성이 있습니다.  
2. **백업**을 반드시 해두어야 합니다. `/tmp/...` 경로에 생성된 Export 파일을 잘 보관해야 합니다.  
3. **DB 구조와 Retention Policy** 등을 함께 점검해야 합니다.  
4. 대규모 마이그레이션 시 **성능 테스트**와 모니터링이 필수입니다.

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim//)**  
{: .prompt-info}
