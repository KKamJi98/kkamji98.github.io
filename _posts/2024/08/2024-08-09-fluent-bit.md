---
title: EFK Stack 구축하기 (1) - Fluent Bit 
date: 2024-08-09 06:48:43 +0900
author: kkamji
categories: [Monitoring & Observability, Metric]
tags: [kubernetes, aws, eks, elasticsearch, fluent-bit, fluentd, logstash, elk, efk, kibana]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/observability/efk.png
---

로그 분석 기술에는 Splunk, DataDog, ELK, EFK 등의 기술들이 존재하지만, 가장 먼저 떠오르는 기술은 **ELK(Elasticsearch, Logstash, Fluentd)** 스택과 **EFK(Elasticsearch, Fluent Bit, Kibana)** 스택이 있습니다. 두 스택 모두 로그 데이터의 수집, 저장, 분석을 위한 도구입니다.  

두 스택 모두 실시간 분산 검색 및 분석 엔진으로 **Elasticsearch**를 사용하고 **Kibana**를 사용해 **Elasticsearch**에서 저장된 데이터를 시각화합니다. 그렇다면 **Logstash**와 **Fluent Bit**는 무엇일까요? 정답은 바로 로그 데이터를 수집, 처리, 전송을 위한 오픈 소스 도구입니다. 개인적으로 로그 분석의 시작은 로그 데이터를 수집하는 작업부터라고 생각합니다. 해당 포스트에서는 로그 데이터를 수집하는 Fluent Bit에 대해 다뤄보도록 하겠습니다.

---

## 1. Fluentd vs Fluent Bit

**Fluentd**와 **Fluent Bit** 모두 CNCF 산하 프로젝트이며 다양한 시스템에서 로그 데이터를 수집하고 전송해주는 도구입니다. **Fluent Bit**은 2014년 Treasure Data의 Fluentd팀에서 개발한 경량 로그 프로세서입니다. 프로젝트 초기에는 임베디드 리눅스와 게이트웨이와 같은 리소스가 제한된 환경에서 로그를 수집을 위한 목표로 시작되었습니다.  

**Fluent Bit**은 C 언어로 작성되어 매우 가볍고, 메모리와 CPU 사용량이 적음과 동시에 빠른 처리 속도(고성능)를 제공하기 때문에 로그 데이터를 실시간으로 빠르게 수집하고 전송할 수 있다는 장점이 있습니다. 따라서 리소스가 제한되거나 분산 시스템인 **Container**, **Cloud Native** 환경에서 폭넓게 사용되는 강력한 로그 관리 도구로 자리잡게 되었습니다. 제가 로그 수집 도구로 **Fluent Bit**을 선택한 이유는 크게 두 가지 입니다. 바로 **EKS(Elastic Kubernetes Service)** 환경에서 **DaemonSet**을 사용해 모든 노드에서 로그를 수집함과 동시에 적은 리소스를 사용할 수 있다는 장점입니다.

---

## 2. Fluent Bit의 주요 개념

### 2.1. Event, Record

**Fluent Bit**에서 검색한 로그나 메트릭에 속하는 모든 수신 데이터는 **Event** 혹은 **Record**로 간주되며 다음과 같은 세 가지 구성 요소로 이루어지며 형식은 다음과 같습니다

```bash
[[TIMESTAMP, METADATA], MESSAGE]

# v2.1.0 이전 버전
[TIMESTAMP, MESSAGE]
```

1. **Timestamp** - 로그가 생성된 시점
2. **Key/Value Metadata** - 로그에 대한 추가 정보
3. **Payload** - 실제 로그 메시지 내용

예시는 다음과 같습니다.

```bash
Jan 18 12:52:16 flb systemd[2222]: Starting GNOME Terminal Server
Jan 18 12:52:16 flb dbus-daemon[2243]: [session uid=1000 pid=2243] Successfully activated service 'org.gnome.Terminal'
Jan 18 12:52:16 flb systemd[2222]: Started GNOME Terminal Server.
Jan 18 12:52:16 flb gsd-media-keys[2640]: # watch_fast: "/org/gnome/terminal/legacy/" (establishing: 0, active: 0)
```

위와 같은 로그에서 `Jan 18 12:52:16`는 **Timestamp**, `[session uid=1000 pid=2243]`는 **Key/Value Metadata**, `systemd[2222]: Starting GNOME Terminal Server`는 실제 메시지 내용인 **Payload**입니다.

### 2.2. Filltering

특정 경우에는 Event의 내용을 수정해야 합니다. Event를 수정, 보강, 삭제하는 과정을 **Filltering**이라고 합니다. **Filtering** 과정을 통해 로그 데이터를 보다 유용하게 만들거나 필요한 정보만을 남길 수 있습니다. **Filtering**의 주요 사용 사례는 다음과 같습니다.

1. 특정 정보 추가 - 이벤트에 IP 주소나 메타데이터와 같은 정보 추가

    ```bash
    # 모든 로그에 key1, value1과 key2, value2에 해당하는 Key/Value Metadata 추가
    [FILTER]
        Name            modify
        Match           *
        Add             key1 value1
        Add             key2 value2
    ```

2. 특정 내용 선택 - 이벤트의 내용 중 특정 부분만을 선택

    ```bash
    # 로그 메시지가 ERROR로 시작하는 항목만 선택
    [FILTER]
        Name            grep
        Match           *
        Regex           log ^ERROR
    ```

3. 특정 패턴과 일치하는 이벤트 삭제 - 특정 패턴과 일치하는 이벤트 삭제

    ```bash
    # 로그 메시지가 DEBUG로 시작하는 모든 이벤트 삭제
    [FILTER]
        Name            grep
        Match           *
        Exclude         log ^DEBUG
    ```

### 2.3. Tag

**Fluent Bit**에서 들어오는 모든 이벤트는 **Tag**를 할당 받습니다. Tag란 **Event**가 나중에 어떤 **Filter** 또는 출력 단계로 이동할지를 결정하는 데 사용되는 내부 문자열입니다. 대부분의 **Tag**는 설정 파일에서 수동으로 할당됩니다. **Tag**가 명시되지 않은 경우, **Fluent Bit**은 해당 이벤트가 생성된 입력 플로그인 인스턴스의 이름을 **Tag**로 할당합니다.

### 2.4. Match

**Fluent Bit**은 수집하고 처리된 **Event**를 **Routing** 단계를 통해 하나 이상의 목적지로 전달할 수 있습니다. **Match**는 **Tag**가 정의된 규칙과 일치하는 이벤트를 선택하는 간단한 규칙을 나타냅니다.

---

## 3. Fluent Bit 설치하기

> **Fluent Bit**은 **DaemonSet**으로 배포되며, Kubernetes Cluster의 모든 Node에서 사용할 수 있습니다. **Fluent Bit**을 배포하는 데 권장되는 방식은 공식 Helm Chart를 사용하는 것입니다. Helm은 Kubernetes용 Package Manager입니다.
{: .prompt-info}

기본 차트 값에는 Docker parsing, systemd logs, Kubernetes Metadata 추가, Elasticsearch Cluster로 출력하는 구성이 포함되어 있습니다. **Fluent Bit**의 설정을 변경하거나 추가 기능을 구성하려면 [`values.yaml`](https://github.com/fluent/helm-charts/blob/main/charts/fluent-bit/values.yaml) 파일을 수정해야 합니다.

### 3.1. Fluent Helm Charts repo 추가

```bash
❯ helm repo add fluent https://fluent.github.io/helm-charts

# 확인

❯ helm search repo fluent
NAME                    CHART VERSION   APP VERSION     DESCRIPTION                                       
fluent/fluent-bit       0.47.5          3.1.4           Fast and lightweight log processor and forwarde...
fluent/fluent-operator  3.0.0           3.0.0           Fluent Operator provides great flexibility in b...
fluent/fluentd          0.5.2           v1.16.2         A Helm chart for Kubernetes  
```

### 3.2. Chart를 사용해 Fluent Bit 설치

```bash
# 네임스페이스 생성
❯ kubectl create ns logging
namespace/logging created

# fluent-bit 설치
❯ helm upgrade --install fluent-bit fluent/fluent-bit -n logging
Release "fluent-bit" does not exist. Installing it now.
NAME: fluent-bit
LAST DEPLOYED: Fri Aug  9 06:34:23 2024
NAMESPACE: logging
STATUS: deployed
REVISION: 1
NOTES:
Get Fluent Bit build information by running these commands:

export POD_NAME=$(kubectl get pods --namespace logging -l "app.kubernetes.io/name=fluent-bit,app.kubernetes.io/instance=fluent-bit" -o jsonpath="{.items[0].metadata.name}")
kubectl --namespace logging port-forward $POD_NAME 2020:2020
curl http://127.0.0.1:2020

# 확인

❯ export POD_NAME=$(kubectl get pods --namespace logging -l "app.kubernetes.io/name=fluent-bit,app.kubernetes.io/instance=fluent-bit" -o jsonpath="{.items[0].metadata.name}")
❯ kubectl --namespace logging port-forward $POD_NAME 2020:2020
Forwarding from 127.0.0.1:2020 -> 2020
Forwarding from [::1]:2020 -> 2020

# 다른 터미널에서
❯ curl http://127.0.0.1:2020
{"fluent-bit":{"version":"3.1.4","edition":"Community","flags":["FLB_HAVE_SYS_WAIT_H","FLB_HAVE_IN_STORAGE_BACKLOG","FLB_HAVE_CHUNK_TRACE","FLB_HAVE_PARSER","FLB_HAVE_RECORD_ACCESSOR","FLB_HAVE_STREAM_PROCESSOR","FLB_HAVE_TLS","FLB_HAVE_OPENSSL","FLB_HAVE_METRICS","FLB_HAVE_WASM","FLB_HAVE_AWS","FLB_HAVE_AWS_CREDENTIAL_PROCESS","FLB_HAVE_SIGNV4","FLB_HAVE_SQLDB","FLB_LOG_NO_CONTROL_CHARS","FLB_HAVE_METRICS","FLB_HAVE_HTTP_SERVER","FLB_HAVE_SYSTEMD","FLB_HAVE_SYSTEMD_SDBUS","FLB_HAVE_FORK","FLB_HAVE_TIMESPEC_GET","FLB_HAVE_GMTOFF","FLB_HAVE_UNIX_SOCKET","FLB_HAVE_LIBYAML","FLB_HAVE_ATTRIBUTE_ALLOC_SIZE","FLB_HAVE_PROXY_GO","FLB_HAVE_JEMALLOC","FLB_HAVE_LIBBACKTRACE","FLB_HAVE_REGEX","FLB_HAVE_UTF8_ENCODER","FLB_HAVE_LUAJIT","FLB_HAVE_C_TLS","FLB_HAVE_ACCEPT4","FLB_HAVE_INOTIFY","FLB_HAVE_GETENTROPY","FLB_HAVE_GETENTROPY_SYS_RANDOM"]}}
```

---

## 4. Reference

<https://docs.fluentbit.io/manual> - Fluent Bit 공식문서  
<https://github.com/fluent/helm-charts> - Fluent Helm Chart

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
