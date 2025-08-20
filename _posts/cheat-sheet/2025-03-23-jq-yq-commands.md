---
title: jq & yq Command Cheat Sheet
date: 2025-03-23 01:41:04 +0900
author: kkamji
categories: [System, Linux]
tags: [jq, yq, json, yaml, parsing, cli, devops, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/linux/linux.webp
---

JSON과 YAML 데이터를 처리하는 도구인 jq와 yq사용하며 알게된 CLI 명령어들을 공유합니다.

---

## 1. jq 기본 사용법

```shell
# 기본 구조
jq '.' file.json                                     # JSON 파일 예쁘게 출력
jq '.' <<< '{"name":"John","age":30}'                # 문자열에서 JSON 파싱
echo '{"name":"John","age":30}' | jq '.'             # 파이프로 JSON 처리
curl -s https://api.github.com/users/octocat | jq '.'  # API 응답 파싱

# 기본 필터링
jq '.name' file.json                                 # 특정 키 값 추출
jq '.user.name' file.json                            # 중첩된 객체 접근
jq '.users[0]' file.json                             # 배열 첫 번째 요소
jq '.users[0].name' file.json                        # 배열 요소의 속성
jq '.users[]' file.json                              # 배열의 모든 요소
jq '.users[].name' file.json                         # 배열 모든 요소의 name 속성
```

---

## 2. jq 고급 필터링 및 선택

```shell
# 조건부 필터링
jq '.users[] | select(.age > 25)' file.json          # 조건에 맞는 요소만 선택
jq '.users[] | select(.name == "John")' file.json    # 특정 값과 일치하는 요소
jq '.users[] | select(.active == true)' file.json    # boolean 값으로 필터링
jq '.users[] | select(.tags | contains(["admin"]))' file.json  # 배열에 특정 값 포함

# 배열 슬라이싱
jq '.users[1:3]' file.json                           # 인덱스 1부터 2까지
jq '.users[:3]' file.json                            # 처음부터 인덱스 2까지
jq '.users[2:]' file.json                            # 인덱스 2부터 끝까지
jq '.users[-2:]' file.json                           # 뒤에서 2번째부터 끝까지

# 키 존재 여부 확인
jq '.users[] | select(has("email"))' file.json       # email 키가 있는 요소만
jq '.users[] | select(.email != null)' file.json     # email 값이 null이 아닌 요소
jq 'has("users")' file.json                          # 최상위에 users 키 존재 여부
```

---

## 3. jq 데이터 변환 및 조작

```shell
# 객체 생성 및 변환
jq '.users[] | {name: .name, email: .email}' file.json  # 새로운 객체 생성
jq '.users[] | {fullName: (.firstName + " " + .lastName)}' file.json  # 문자열 연결
jq '.users[] | {name, age}' file.json                # 축약 문법 (키와 값이 같을 때)
jq '{userCount: (.users | length), users: .users}' file.json  # 계산된 값 포함

# 배열 변환
jq '.users | map(.name)' file.json                   # 배열의 각 요소를 name으로 변환
jq '.users | map(select(.age > 25))' file.json       # 조건에 맞는 요소만 매핑
jq '.users | map({name, isAdult: (.age >= 18)})' file.json  # 계산된 속성 추가

# 그룹화 및 집계
jq '.users | group_by(.department)' file.json        # 부서별 그룹화
jq '.users | group_by(.age) | map({age: .[0].age, count: length})' file.json  # 나이별 개수
jq '.users | map(.age) | add / length' file.json     # 평균 나이 계산
jq '.users | map(.salary) | max' file.json           # 최대 급여
jq '.users | map(.salary) | min' file.json           # 최소 급여
```

---

## 4. jq 경로 탐색 및 키 조작

```shell
# 모든 경로 탐색
jq 'paths' file.json                                 # 모든 경로 배열로 출력
jq 'paths | join(".")' file.json                     # 경로를 점 표기법으로 연결
jq 'paths(scalars)' file.json                       # 스칼라 값의 경로만
jq 'paths(objects)' file.json                       # 객체의 경로만
jq 'paths(arrays)' file.json                        # 배열의 경로만

# 키 조작
jq 'keys' file.json                                  # 모든 키 목록
jq 'keys_unsorted' file.json                        # 정렬되지 않은 키 목록
jq '.users[0] | keys' file.json                     # 특정 객체의 키들
jq 'to_entries' file.json                           # 키-값 쌍을 배열로 변환
jq 'to_entries | map(select(.key | startswith("user")))' file.json  # 특정 접두사 키만

# 재귀적 탐색
jq '.. | objects | select(has("name"))' file.json   # name 키를 가진 모든 객체
jq '.. | select(type == "string")' file.json        # 모든 문자열 값
jq '.. | select(type == "number")' file.json        # 모든 숫자 값
```

---

## 5. jq 문자열 및 타입 처리

```shell
# 문자열 조작
jq '.users[].name | ascii_downcase' file.json       # 소문자 변환
jq '.users[].name | ascii_upcase' file.json         # 대문자 변환
jq '.users[].email | split("@")[0]' file.json       # 이메일에서 사용자명 추출
jq '.users[].name | length' file.json               # 문자열 길이
jq '.description | gsub("old"; "new")' file.json    # 문자열 치환

# 타입 확인 및 변환
jq '.users[] | type' file.json                      # 각 요소의 타입
jq '.age | tostring' file.json                      # 숫자를 문자열로
jq '.ageString | tonumber' file.json                # 문자열을 숫자로
jq '.users | length' file.json                      # 배열 길이
jq '. | type' file.json                             # 루트 객체 타입

# 날짜 및 시간 처리
jq '.timestamp | strftime("%Y-%m-%d %H:%M:%S")' file.json  # Unix 타임스탬프 포맷
jq '.dateString | strptime("%Y-%m-%d") | mktime' file.json  # 문자열을 Unix 타임스탬프로
jq 'now' file.json                                  # 현재 Unix 타임스탬프
```

---

## 6. jq 고급 기능

```shell
# 조건문 및 논리 연산
jq '.users[] | if .age >= 18 then "adult" else "minor" end' file.json  # 조건문
jq '.users[] | select(.active and .verified)' file.json  # AND 조건
jq '.users[] | select(.role == "admin" or .role == "moderator")' file.json  # OR 조건
jq '.users[] | select(.age >= 18 and .department == "IT")' file.json  # 복합 조건

# 에러 처리
jq '.users[]?.email // "No email"' file.json        # null 값에 대한 기본값
jq '.users[] | .email // empty' file.json           # null 값 제거
jq 'try .nonexistent.field catch "Field not found"' file.json  # 에러 처리

# 변수 사용
jq --arg name "John" '.users[] | select(.name == $name)' file.json  # 외부 변수 사용
jq --argjson age 25 '.users[] | select(.age > $age)' file.json  # JSON 변수 사용
jq '.users as $users | $users | length' file.json   # 내부 변수 정의

# 함수 정의
jq 'def isAdult: .age >= 18; .users[] | select(isAdult)' file.json  # 사용자 정의 함수
```

---

## 7. yq 기본 사용법

```shell
# 기본 구조 (yq v4 기준)
yq '.' file.yaml                                     # YAML 파일 예쁘게 출력
yq eval '.' file.yaml                                # 명시적 eval 사용
yq -o json '.' file.yaml                             # YAML을 JSON으로 변환
yq -P '.' file.json                                  # JSON을 YAML로 변환

# 기본 필터링
yq '.name' file.yaml                                 # 특정 키 값 추출
yq '.spec.containers[0].image' file.yaml             # 중첩된 값 접근
yq '.items[]' file.yaml                              # 배열의 모든 요소
yq '.items[].metadata.name' file.yaml                # 배열 요소의 속성
```

---

## 8. yq 고급 필터링 및 선택

```shell
# 조건부 필터링
yq '.items[] | select(.kind == "Pod")' file.yaml     # 조건에 맞는 요소만
yq '.spec.containers[] | select(.name == "nginx")' file.yaml  # 특정 컨테이너만
yq '.items[] | select(.metadata.labels.app == "web")' file.yaml  # 라벨로 필터링

# 배열 조작
yq '.items | length' file.yaml                       # 배열 길이
yq '.items[0:2]' file.yaml                           # 배열 슬라이싱
yq '.items | sort_by(.metadata.name)' file.yaml      # 정렬
yq '.items | reverse' file.yaml                      # 역순 정렬
```

---

## 9. yq 경로 탐색 및 키 조작

```shell
# 모든 경로 탐색
yq 'paths' file.yaml                                 # 모든 경로 배열로 출력
yq 'paths | join(".")' file.yaml                     # 경로를 점 표기법으로 연결
yq 'paths(scalars)' file.yaml                       # 스칼라 값의 경로만
yq '.. | path | join(".")' file.yaml                 # 모든 노드의 경로

# 키 조작
yq 'keys' file.yaml                                  # 모든 키 목록
yq '.metadata | keys' file.yaml                     # 특정 객체의 키들
yq 'to_entries' file.yaml                           # 키-값 쌍을 배열로 변환
yq 'with_entries(select(.key | startswith("app")))' file.yaml  # 특정 접두사 키만

# 재귀적 탐색
yq '.. | select(tag == "!!str")' file.yaml          # 모든 문자열 값
yq '.. | select(type == "!!int")' file.yaml         # 모든 정수 값
yq '.. | select(has("name"))' file.yaml             # name 키를 가진 모든 객체
```

---

## 10. yq 데이터 변환 및 수정

```shell
# 값 수정
yq '.spec.replicas = 3' file.yaml                   # 값 변경
yq '.metadata.labels.version = "v2.0"' file.yaml    # 새 라벨 추가
yq 'del(.spec.template.spec.nodeSelector)' file.yaml  # 키 삭제
yq '.spec.containers[0].image = "nginx:1.20"' file.yaml  # 배열 요소 수정

# 객체 생성 및 병합
yq '.metadata.labels += {"environment": "production"}' file.yaml  # 객체 병합
yq '. * {"spec": {"replicas": 5}}' file.yaml        # 깊은 병합
yq 'select(.kind == "Deployment") | .spec.replicas = 3' file.yaml  # 조건부 수정

# 배열 조작
yq '.spec.containers += [{"name": "sidecar", "image": "busybox"}]' file.yaml  # 배열에 요소 추가
yq '.spec.containers |= map(select(.name != "old-container"))' file.yaml  # 배열에서 요소 제거
yq '.spec.containers |= sort_by(.name)' file.yaml   # 배열 정렬
```

---

## 11. yq 다중 문서 처리

```shell
# 다중 YAML 문서
yq 'select(.kind == "Deployment")' multi-doc.yaml   # 특정 종류 문서만 선택
yq 'select(document_index == 0)' multi-doc.yaml     # 첫 번째 문서만
yq '. as $item ireduce ({}; . * $item)' multi-doc.yaml  # 모든 문서 병합

# 파일 간 작업
yq eval-all '. as $item ireduce ({}; . * $item)' file1.yaml file2.yaml  # 여러 파일 병합
yq eval-all 'select(fileIndex == 0)' file1.yaml file2.yaml  # 첫 번째 파일만
```

---

## 12. 실제 사용 예제

```shell
# Kubernetes 매니페스트 처리
kubectl get pods -o json | jq '.items[] | {name: .metadata.name, status: .status.phase, node: .spec.nodeName}'
kubectl get deployments -o yaml | yq '.items[] | select(.spec.replicas > 1) | .metadata.name'

# AWS CLI 출력 처리
aws ec2 describe-instances | jq '.Reservations[].Instances[] | {id: .InstanceId, state: .State.Name, type: .InstanceType}'
aws eks describe-cluster --name my-cluster | jq '.cluster | {name: .name, status: .status, version: .version}'

# 설정 파일 처리
yq '.services.web.environment.DATABASE_URL = "postgresql://localhost:5432/mydb"' docker-compose.yml
jq '.scripts.start = "node server.js"' package.json

# 로그 분석
cat app.log | jq -r 'select(.level == "ERROR") | .message'
kubectl logs deployment/my-app -o json | jq -r '.log | fromjson | select(.severity == "ERROR")'

# 데이터 변환
curl -s https://api.github.com/repos/kubernetes/kubernetes/releases | jq '.[0] | {name: .name, published: .published_at, assets: [.assets[] | {name: .name, download_count: .download_count}]}'
```

---

## 13. 유용한 팁과 트릭

```shell
# 컬러 출력
jq -C '.' file.json                                  # 컬러 출력 강제
jq --color-output '.' file.json                     # 컬러 출력 (긴 형태)

# Raw 출력
jq -r '.users[].name' file.json                     # 따옴표 없이 문자열 출력
yq -r '.metadata.name' file.yaml                    # Raw 문자열 출력

# 압축 출력
jq -c '.' file.json                                  # 압축된 JSON 출력
yq -o json -I=0 '.' file.yaml                       # 압축된 JSON 변환

# 정렬된 키
jq -S '.' file.json                                  # 키를 알파벳순으로 정렬
yq 'sort_keys(.)' file.yaml                         # YAML 키 정렬

# 스트림 처리
jq --stream '.' large-file.json                     # 대용량 파일 스트림 처리
yq --stream '.' large-file.yaml                     # YAML 스트림 처리

# 에러 무시
jq -e '.' file.json                                  # 빈 결과나 false에서 exit code 1
jq --exit-status '.' file.json                      # 긴 형태
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
