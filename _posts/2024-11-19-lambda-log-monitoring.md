---
title: AWS Lambda 로그 모니터링 하기 - ELK, Amazon Data Firehose
date: 2024-11-19 19:12:30 +0900
author: kkamji
categories: [Kubernetes]
tags: [lambda, amazon-data-firehose, logstash, elasticsearch, kibana]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/monitoring/elk.webp
---

최근 서버리스 기반 단어 암기 앱 [Remember Me](https://github.com/vocaAppServerless) 프로젝트를 **AWS Lambda**와 **API Gateway**를 활용하여 진행하고 있습니다. 서버리스 아키텍처를 구축하면서 다수의 **Lambda** 함수를 프로비저닝 하였는데, 이 과정에서 각 **Lambda** 함수의 로그가 CloudWatch Logs에 분산되어 저장되어 어떻게 이 로그 데이터를 수집하고 한 곳에서 관리할 수 있을지에 대해 고민하게 되었습니다.  

이러한 로그 데이터를 효율적으로 수집하고 중앙 집중화하여 관리하는 방안을 찾던 중, 이전에 경험했던 **EFK Stack**을 떠올리게 되었습니다. **Amazon Data Firehose**를 활용해 로그를 **Logstash**로 전송하고, 여기서 데이터를 필터링 및 변환하여 **Elasticsearch**에 저장한 후, **Kibana**를 통해 로그 데이터를 시각화하는 방식을 구상하게 되었습니다.

해당 포스트에서는 로컬 Kubernetes 환경에 **Elasticsearch**, **Logstash**, **Kibana**를 배포하고 CloudWatch Logs에 쌓이는 로그 데이터를 **Amazon Data Firehose**로 전송하는 것을 다뤄보도록 하겠습니다.

## ELK Stack 구축

이전에 작성한 [EFK Stack 구축하기 (2) - Elasticsearch](https://kkamji.net/posts/elasticsearch/)와 [EFK Stack 구축하기 (3) - Kibana](https://kkamji.net/posts/kibana/)를 참고해 **Elasticsearch**와 **Kibana**를 구축하고, **Logstash**는 별도의 Deployment를 통해 구축해보도록 하겠습니다.

### Elasticsearch 배포

```bash
## CRD 설치
❯ kubectl create -f https://download.elastic.co/downloads/eck/2.15.0/crds.yaml
customresourcedefinition.apiextensions.k8s.io/agents.agent.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/apmservers.apm.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/beats.beat.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/elasticmapsservers.maps.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/elasticsearchautoscalers.autoscaling.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/elasticsearches.elasticsearch.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/enterprisesearches.enterprisesearch.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/kibanas.kibana.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/logstashes.logstash.k8s.elastic.co created
customresourcedefinition.apiextensions.k8s.io/stackconfigpolicies.stackconfigpolicy.k8s.elastic.co created

## operator와 RBAC rule 설치
❯ kubectl apply -f https://download.elastic.co/downloads/eck/2.15.0/operator.yaml
namespace/elastic-system created
serviceaccount/elastic-operator created
secret/elastic-webhook-server-cert created
configmap/elastic-operator created
clusterrole.rbac.authorization.k8s.io/elastic-operator created
clusterrole.rbac.authorization.k8s.io/elastic-operator-view created
clusterrole.rbac.authorization.k8s.io/elastic-operator-edit created
clusterrolebinding.rbac.authorization.k8s.io/elastic-operator created
service/elastic-webhook-server created
statefulset.apps/elastic-operator created
validatingwebhookconfiguration.admissionregistration.k8s.io/elastic-webhook.k8s.elastic.co created

## Elasticsearch 리소스 manifest 파일 생성 elasticsearch.yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: elasticsearch
  namespace: logging
spec:
  version: 8.16.0
  nodeSets:
  - name: default
    count: 1
    config:
      # mmap 파일은 메모리 매핑을 통해 파일을 메모리에 올려 빠르게 액세스할 수 있지만, 시스템에 메모리 부족이 발생할 수 있음
      # Kubernetes와 같은 컨테이너 환경에서는 메모리 제약이 있을 수 있어 false로 설정하여 메모리 관련 문제를 방지할 수 있음
      node.store.allow_mmap: false 
    volumeClaimTemplates:
    - metadata:
        name: elasticsearch-data
      spec:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 10Gi
        storageClassName: local-path

## 배포
❯ kubectl apply -f elasticsearch.yaml 
elasticsearch.elasticsearch.k8s.elastic.co/elasticsearch created

## 네임스페이스 변경
❯ kubens logging       
✔ Active namespace is "logging"

## 배포 확인
❯ kubectl get all 
NAME                             READY   STATUS    RESTARTS   AGE
pod/elasticsearch-es-default-0   1/1     Running   0          4m35s

NAME                                     TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/elasticsearch-es-default         ClusterIP   None             <none>        9200/TCP   4m37s
service/elasticsearch-es-http            ClusterIP   10.98.237.32     <none>        9200/TCP   4m40s
service/elasticsearch-es-internal-http   ClusterIP   10.101.122.149   <none>        9200/TCP   4m40s
service/elasticsearch-es-transport       ClusterIP   None             <none>        9300/TCP   4m40s

NAME                                        READY   AGE
statefulset.apps/elasticsearch-es-default   1/1     4m37s
```

### Kibana 배포

```bash
## Kibana 리소스 manifest 파일 생성 -> kibana.yaml
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: kibana
  namespace: logging
spec:
  version: 8.16.0
  count: 1
  elasticsearchRef:
    name: elasticsearch

## 배포
❯ kubectl apply -f kibana.yaml       
kibana.kibana.k8s.elastic.co/kibana created

## 확인
❯ k get kibana      
NAME     HEALTH   NODES   VERSION   AGE
kibana   green    1       8.16.0    3m1s

## 초기 비밀번호 확인 (초기 유저 아이디: elastic)
❯ kubectl get secret elasticsearch-es-elastic-user -o=jsonpath='{.data.elastic}' | base64 --decode; echo

Rkxxxxx19xxxxxmVxxxa

## 포트포워딩 후 확인
![kibana_login](/assets/img/monitoring/kibana_login.webp)
```

### Logstash 배포

```bash
apiVersion: logstash.k8s.elastic.co/v1alpha1
kind: Logstash
metadata:
  name: logstash
spec:
  count: 1
  elasticsearchRefs:
    - name: elasticsearch
      clusterName: elasticsearch
  version: 8.16.0
  pipelines:
    - pipeline.id: main
      config.string: |
        input {
          http {
            port => 5044
            codec => "json_lines"
          }
        }
        output {
          elasticsearch {
            hosts => ["{elasticsearch domain}"]
            index => "lambda-logs-%{+YYYY.MM.dd}"
            user => "{elastic}"
            password => "{password}"
          }
        }
  services:
    - name: http
      service:
        spec:
          type: ClusterIP
          ports:
            - port: 5044
              protocol: TCP
              targetPort: 5044
  volumeClaimTemplates:
    - metadata:
        name: logstash-data
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 5Gi
        storageClassName: local-path
```

## Logstash -> Elasticsearch 연동 테스트

### curl 명령어를 통해 logstash에 로그 데이터 전송

```bash
❯ curl -X POST "{log_stash_url}" \
     -H "Content-Type: application/json" \
     -d '{"message": "테스트 로그 메시지", "level": "info", "timestamp": "2024-11-20T05:49:03+09:00"}'

ok
```

### 로그 확인 {elasticsearch url}/_search

> logstash로 전송한 로그가 elasticsearch로 전송된 것을 확인할 수 있습니다.
{: .prompt-tip}

![elasticsearch_search](/assets/img/monitoring/elasticsearch_search.webp)

## Amazon Data Firehose Stream 생성

![amazon_data_firehose](/assets/img/monitoring/amazon_data_firehose.webp)


---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.instagram.com/kkam._.ji/)**
{: .prompt-info}
