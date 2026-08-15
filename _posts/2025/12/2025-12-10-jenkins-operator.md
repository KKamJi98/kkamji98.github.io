---
title: "Jenkins Operator 알아보기 - Kubernetes 선언적 운영 [Jenkins 3]"
date: 2025-12-10 19:50:12 +0900
author: kkamji
categories: [DevOps]
tags: [devops, ci-cd, jenkins, jenkins-operator, kubernetes]
comments: true
image:
  path: /assets/img/ci-cd/jenkins/jenkins.webp
---

Kubernetes에 Jenkins를 올리는 가장 단순한 방법은 Helm chart로 Deployment 하나를 띄우는 것입니다. 그러나 운영이 시작되면 관리할 상태는 Pod 하나가 아닙니다. 설정 변경마다 재시작할지 판단해야 하고, 플러그인 목록과 버전을 추적해야 하고, 접속 credential을 Secret으로 관리해야 하고, Jenkins가 살아있는지 확인하고 죽으면 복구해야 합니다. Jenkins Operator는 이 일련의 운영 작업을 Kubernetes의 Operator 패턴으로 자동화합니다. Jenkins 커스텀 리소스에 원하는 상태를 선언하면 Operator가 나머지를 조정합니다.

---

## 1. Operator 패턴이 푸는 문제

Kubernetes의 Deployment는 "컨테이너 N개 띄우기"라는 단일 상태만 관리합니다. Jenkins처럼 내부 상태가 큰 애플리케이션은 그보다 훨씬 많은 조정이 필요합니다. 설정이 바뀌면 어느 범위까지 재시작 없이 반영되는지, 플러그인 설치가 실패하면 어떻게 복구하는지, 백업을 언제 어떻게 수행하는지를 사람이 일일이 판단하는 대신, Operator가 커스텀 리소스(CR)의 spec을 읽어 현재 상태를 원하는 상태로 계속 맞춥니다.

Operator는 CRD(Custom Resource Definition)와 컨트롤러로 구성됩니다. CRD는 "Jenkins라는 리소스 종류가 있다"라고 Kubernetes API에 등록하고, 컨트롤러는 그 리소스를 감시(watch)하다가 변화가 생기면 조정(reconcile)을 수행합니다. 선언한 spec과 실제 클러스터 상태가 어긋나면 다시 맞추려고 하므로, GitOps 도구와 조합하면 Jenkins 구성 자체를 Git으로 관리할 수 있습니다.

---

## 2. Jenkins CR 하나가 관리하는 것들

Jenkins Operator가 조정하는 대상은 Jenkins CR의 spec으로 선언합니다.

- **master Pod**: 이미지, 리소스, 환경 변수, 컨테이너 설정
- **basePlugins**: Operator 동작에 필요한 필수 플러그인과 버전 고정
- **plugins**: 사용자가 추가하는 플러그인
- **configurationAsCode**: JCasC로 적용할 설정
- **groovyScripts**: 초기화 시 실행할 Groovy 스크립트
- **seedJobs**: Job DSL로 파이프라인을 심는 seed job 정의
- **backup/restore**: 백업 수행 방법과 주기

Operator는 이 선언을 읽어 Namespace, RBAC, Service, Secret, ConfigMap, master Pod를 생성하고, Jenkins 기동 후 API 토큰을 발급받아 플러그인 설치와 설정 적용을 진행합니다.

![Jenkins Operator reconcile loop](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-operator-reconcile-loop.webp)
> Jenkins Operator reconcile loop  

조정(reconcile)은 두 단계로 진행됩니다. Base reconciliation loop가 namespace, RBAC, master Pod, API 토큰, 보안 강화 스크립트처럼 Jenkins가 동작하기 위한 기본 요소를 먼저 확보합니다. User reconciliation loop가 그 위에 JCasC 설정, seed job, Groovy 스크립트, 백업 잡처럼 사용자가 선언한 구성을 적용합니다. 각 단계가 완료된 시각은 CR의 status 필드에 기록되며, 동일한 에러가 10회 반복되면 ReconcileLoopFailed로 조정을 멈춥니다. base 단계가 실패하면 user 단계는 실행되지 않으므로, 설정이 반영되지 않는 문제를 디버깅할 때는 어느 단계에서 멈췄는지 status와 Operator 로그를 먼저 확인합니다.

설정 변경 반영 방식에도 순서가 있습니다. JCasC YAML처럼 user configuration에 해당하는 변경은 재시작 없이 live Jenkins에 적용되지만, master 이미지나 basePlugins처럼 base configuration의 변경은 master Pod 재생성으로 이어집니다. 운영 중인 Jenkins에서 이 구분을 모르고 base 설정을 건드리면 실행 중인 빌드와 함께 재시작이 발생할 수 있습니다.

---

## 3. 이름이 같은 다른 Operator들 구분하기

검색하다 보면 "Jenkins Operator"라는 이름의 프로젝트가 여러 개 나옵니다. 2026년 8월 기준으로 정리하면 다음과 같습니다.

| 프로젝트 | 상태 |
| :--- | :--- |
| jenkinsci/kubernetes-operator | 유지보수 지속. stable v0.8.1 (2024-07), 최신 prerelease v0.9.0-beta2 (2025-12) |
| openshift/jenkins-operator (Red Hat) | 저장소 삭제됨 |
| redhat-developer/openshift-jenkins-operator | 보관 처리(archived) |
| jenkinsci/jenkins-automation-operator | 2021-06 이후 방치 상태 |

이 글의 대상은 jenkinsci/kubernetes-operator입니다. 2019년 VirtusLab에서 시작해 jenkinsci 조직으로 이관된 프로젝트로, 2026-08 기준 archived가 아니고 이슈 활동도 이어지고 있으나, 릴리스 주기가 느리고 핵심 유지보수자가 사실상 한 명이라 커뮤니티 건전성은 활발하다고 보기 어렵습니다. GitHub의 저장소 최신 활동 시각만 보고 판단하면 안 됩니다. 자동화 봇이 관리하는 브랜치 푸시가 활동처럼 보이는 경우가 있으므로, 실제 사람 커밋과 릴리스 이력을 기준으로 평가해야 합니다.

참고로 이 Operator는 2021년 1월 OLM(OperatorHub) community-operators에서 제거되었습니다. 현재 설치 경로는 Helm chart 또는 YAML 매니페스트입니다. OpenShift 쪽 Jenkins 이미지는 별개 이야기로, 공식 문서 기준 maintenance mode입니다.

---

## 4. 설치 실습

실습 환경은 Kubernetes 클러스터와 helm, kubectl입니다.

```shell
##############################################################
# Jenkins Namespace 생성
##############################################################
kubectl create namespace jenkins

##############################################################
# Jenkins Operator 설치
##############################################################
helm repo add jenkins https://raw.githubusercontent.com/jenkinsci/kubernetes-operator/master/chart
helm repo update
helm pull jenkins/jenkins-operator --version 0.8.1
tar -xvf jenkins-operator-0.8.1.tgz
cd jenkins-operator

cat <<EOF > custom_values.yaml
jenkins:
  enabled: true
  name: jenkins
  namespace: jenkins
  image: jenkins/jenkins:2.528.3-lts

  basePlugins:
  - name: kubernetes
    version: 4392.v19cea_fdb_5913
  - name: workflow-job
    version: 1546.v62a_c59c112dd
  - name: workflow-aggregator
    version: 608.v67378e9d3db_1
  - name: git
    version: 5.7.0
  - name: job-dsl
    version: "1.93"
  - name: configuration-as-code
    version: "1985.vdda_32d0c4ea_b_"
  - name: kubernetes-credentials-provider
    version: 1.299.v610fa_e76761a_

  service:
    type: NodePort
    port: 8080
    nodePort: 30003
EOF
helm upgrade -i -n jenkins jenkins . -f custom_values.yaml

##############################################################
# Jenkins Operator 설치 확인
##############################################################
kubectl get crds | grep -i jenkins
# jenkins.jenkins.io                             2025-12-10T14:02:11Z

kubectl get pods,svc -n jenkins
# NAME                                            READY   STATUS    RESTARTS   AGE
# pod/jenkins-jenkins                             2/2     Running   0          10m
# pod/jenkins-jenkins-operator-5679c97c76-6v62p   1/1     Running   0          36m

# NAME                                     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
# service/jenkins-operator-http-jenkins    NodePort    10.43.171.181   <none>        8080:30003/TCP   36m
# service/jenkins-operator-slave-jenkins   ClusterIP   10.43.142.76    <none>        50000/TCP        36m

##############################################################
# Jenkins Instance 접속
##############################################################
# Username 확인
kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.user}' | base64 -d

# 초기 Password 확인
kubectl --namespace jenkins get secret jenkins-operator-credentials-jenkins -o 'jsonpath={.data.password}' | base64 -d

open http://localhost:30003
```

master Pod를 보면 컨테이너가 2개입니다. 하나는 Jenkins 자체이고, 다른 하나는 Operator가 설정 적용과 상태 확인에 사용하는 jam (jenkins-api-client) 컨테이너입니다. Operator가 Jenkins REST API를 호출해 플러그인을 설치하고 Groovy 스크립트를 실행하는 통로가 이 사이드카입니다.

![Jenkins Instance Login Page](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-instance-login-page.webp)
![Jenkins Instance Main Page](/assets/img/ci-cd/jenkins/jenkins-operator/jenkins-instance-main-page.webp)

접속 계정은 Operator가 생성한 secret에서 확인합니다. 초기 관리자 비밀번호를 별도 파일에서 찾는 일반적인 Jenkins 초기화 과정과 다르게, Operator가 credential을 발급하고 관리하는 것이 이 구성의 특징입니다.

---

## 5. 운영 관점에서 알아야 할 제약

**master는 기본으로 bare Pod로 실행됩니다.** Deployment가 아니므로 롤링 업데이트가 없고, 재시작은 Pod 삭제 후 재생성으로 이루어집니다. Deployment로 바꾸려면 Jenkins CR의 master에 `jenkins.io/use-deployment: "true"` 어노테이션을 지정합니다.

**spec.master의 변경은 매번 재시작을 유발합니다.** 이미지, 리소스, 환경 변수 등 master 정의를 바꾸면 Pod가 재생성됩니다. 앞서 설명한 user configuration과 base configuration의 반영 방식 차이와 함께 기억해야 하는 운영 규칙입니다.

**적용된 Groovy 스크립트는 해시로 추적됩니다.** Operator는 적용 완료된 스크립트의 해시를 기록해 두고, 해시가 바뀌지 않으면 재실행하지 않습니다. 덕분에 reconcile이 반복돼도 설정이 멱등하게 유지됩니다.

**백업은 별도 provider로 동작합니다.** 기본 제공되는 pvc provider는 지정한 시각에 backup Pod를 띄워 jenkins-home을 압축해 PVC에 저장합니다. 백업 대상에서 일부 디렉터리와 최상위 config.xml은 제외되므로, 전체 복제가 아니라 상태 복구용이라는 점을 이해하고 사용해야 합니다.

**API 버전이 v1alpha2입니다.** 2019년 출시 이후 지금까지 alpha 단계에서 벗어나지 않았습니다. 스펙이 안정적이지 않을 수 있다는 점은 도입 검토 시 고려해야 합니다.

---

## 6. Reference

- [Jenkins GitHub - kubernetes-operator](https://github.com/jenkinsci/kubernetes-operator)
- [Jenkins Docs - Architecture and Design](https://jenkinsci.github.io/kubernetes-operator/docs/how-it-works/architecture-and-design/)
- [Jenkins Docs - Installing the Operator](https://jenkinsci.github.io/kubernetes-operator/docs/getting-started/latest/installing-the-operator/)
- [Jenkins Docs - CRD Schema](https://jenkinsci.github.io/kubernetes-operator/docs/getting-started/latest/schema/)
- [Jenkins Docs - Configuring Seed Jobs and Pipelines](https://jenkinsci.github.io/kubernetes-operator/docs/getting-started/latest/configuring-seed-jobs-and-pipelines/)
- [Jenkins Docs - Configuring Backup and Restore](https://jenkinsci.github.io/kubernetes-operator/docs/getting-started/latest/configuring-backup-and-restore/)
- [Jenkins GitHub - Source jenkins_controller.go](https://github.com/jenkinsci/kubernetes-operator/blob/master/internal/controller/jenkins_controller.go)

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
