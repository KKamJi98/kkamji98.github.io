---
title: EFK Stack 구축하기 (2) - Elasticsearch
date: 2024-08-10 04:51:41 +0900
author: kkamji
categories: [Monitoring & Observability, Metric]
tags: [kubernetes, aws, eks, elasticsearch, elk, efk]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/observability/efk.png
---

저번 포스트에서 시스템에서 로그를 수집 후 전송해주는 도구인 **Fluent Bit**을 설치했습니다. 이번 포스트에서는 **EFK Stack**의 핵심인 분산형 검색 및 분석 엔진 입니다. **Fluent Bit**에서 수집된 로그는 **Elasticsearch**에 저장될 수 있으며, **Elasticsearch**는 다양한 유형의 데이터에 대해 거의 실시간 검색 및 분석을 제공합니다.  

해당 포스트에서는 **Elasticsearch**에 대해 알아보고 구축해보도록 하겠습니다. **Elasticsearch**를 구축하는 방법은 **AWS OpenSearch**, **Elastic Cloud**, **Elastic Cloud on Kubernetes(ECK)** 등이 존재합니다. 현재 **Weasel**에서는 EKS를 사용중이었으므로, 쿠버네티스 환경에 Elasticsearch를 구축하는 방법인 **ECK**를 선택했습니다.

---

## 1. Elastic Cloud on Kubernetes(ECK)란?

**Elastic Cloud on Kubernetes(ECK)**란 **Elasticsearch**와 같은 Elastic 제품을 Kubernetes Cluster에서 쉽게 배포하고 관리할 수 있게 해주는 Kubernetes Operator입니다. **ECK**를 통해 Kubernetes 환경에서 **Elasticsearch** 클러스터를 운영할 수 있습니다.

---

## 2. ECK 배포

### 2.1. Custom Resource Definitions(CRD) 설치

> **ECK**를 사용하기 위해서는 **Custom Resource Definition(CRD)**를 Kubernetes에 설치해야 합니다. Kubernetes의 **Custom Resource**를 활용하면 사용자가 정의한 오브젝트를 직접 구현해서 사용하거나 여러 종류의 리소스를 추상화해서 관리할 수 있습니다. Elastic사에서는 **ECK**를 사용하기 위한 **Custom Resource**를 아래와 같은 명령어를 통해 설치할 수 있도록 제공해주고 있습니다.  
{: .prompt-info}

```bash
❯ kubectl create -f https://download.elastic.co/downloads/eck/2.14.0/crds.yaml
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
```

### 2.2. Operator 설치

> Kubernetes Operator는 Kubernetes Cluster에서 Application의 배포, 관리, 확장 등을 자동화하는 소프트웨어 확장입니다. Operator는 쿠버네티스의 기본 개념인 "Controller"와 "CRD"를 결합하여 작동하며 Application과, Application의 구성 요소들을 관리하는 역할을 합니다.  
{: .prompt-info}

```bash
❯ kubectl apply -f https://download.elastic.co/downloads/eck/2.5.0/operator.yaml
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
```

---

## 3. Elasticsearch 클러스터 배포

> 하나의 **Elasticsearch** 노드를 가진 **Elasticsearch** 클러스터를 배포해보도록 하겠습니다. 추가적으로 AWS-EBS Volume을 사용하기 위해서는 `volumeClaimTemplates`를 생성 후 어떤 PVC를 생성할지 설정해주어야합니다.  
{: .prompt-info}

### 3.1. 정의 파일 (`elasticsearch.yaml`)

```yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: weasel-elasticsearch
  namespace: logging
spec:
  version: 8.15.0
  nodeSets:
  - name: default
    count: 1
    volumeClaimTemplates:
    - metadata:
        name: elasticsearch-data
      spec:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 5Gi
        storageClassName: gp2
```

### 3.2. 적용

```bash
❯ k apply -f elasticsearch.yaml
elasticsearch.elasticsearch.k8s.elastic.co/weasel-elasticsearch configured
```

---

## 4. 확인

```bash
❯ kubectl get elasticsearch --watch
NAME                   HEALTH    NODES   VERSION   PHASE             AGE
weasel-elasticsearch   unknown           8.15.0    ApplyingChanges   13s
weasel-elasticsearch   unknown   1       8.15.0    ApplyingChanges   99s
weasel-elasticsearch   green     1       8.15.0    Ready             105s

❯ k get pods -n logging --watch
NAME                                READY   STATUS    RESTARTS   AGE
fluent-bit-fg9ls                    1/1     Running   0          36h
fluent-bit-l2nxq                    1/1     Running   0          36h
weasel-elasticsearch-es-default-0   0/1     Pending   0          1s
weasel-elasticsearch-es-default-0   0/1     Pending   0          3s
weasel-elasticsearch-es-default-0   0/1     Init:0/2   0          3s
weasel-elasticsearch-es-default-0   0/1     Init:0/2   0          11s
weasel-elasticsearch-es-default-0   0/1     Init:0/2   0          12s
weasel-elasticsearch-es-default-0   0/1     Init:0/2   0          12s
weasel-elasticsearch-es-default-0   0/1     Init:1/2   0          13s
weasel-elasticsearch-es-default-0   0/1     PodInitializing   0          14s
weasel-elasticsearch-es-default-0   0/1     Running           0          15s
weasel-elasticsearch-es-default-0   1/1     Running           0          46s
```

확인 결과는 다음과 같습니다.

1. **elasticsearch** statefulSet이 생성되고 elasticsearch pod 생성
2. **elasticsearch** pod의 PVC가 요구하는 PV가 아직 생성되지 않아 Pending (1s~3s)
3. Init container가 실행 (3s~13s)
4. **elasitcsearch** pod 초기화 후 동작 (14s~)

---

## 5. Reference

<https://www.elastic.co/docs> - [공식 문서]  
<https://devocean.sk.com/blog/techBoardDetail.do?ID=165640&boardType=techBlog> - [로그분석에 활용할 수 있는 EFK 스택 간단하게 정리해보기]  
<https://oliveyoung.tech/blog/2024-04-02/opensearch-efk/> - [AWS OpenSearch를 사용한 EFK Stack 구축하기 | 올리브영 테크블로그]  
<https://techblog.gccompany.co.kr/eks-%ED%99%98%EA%B2%BD%EC%97%90%EC%84%9C%EC%9D%98-efk-%EB%8F%84%EC%9E%85%EA%B8%B0-e8a92695e991> - [EKS 환경에서의 EFK 도입기]  
<https://medium.com/musinsa-tech/%EB%AC%B4%EC%8B%A0%EC%82%AC%EC%9D%98-%EC%97%98%EB%9D%BC%EC%8A%A4%ED%8B%B1%EC%84%9C%EC%B9%98-muse-musinsa-elasticsearch-e6355516186a> - [무신사의 엘라스틱서치 MusE (Musinsa Elasticsearch)]  

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
