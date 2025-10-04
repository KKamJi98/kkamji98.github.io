---
title: Kubernetes에 MongoDB 배포하기
date: 2024-11-12 19:15:30 +0900
author: kkamji
categories: [Kubernetes]
tags: [kubernetes, mongodb, helm]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/mongodb/mongodb.webp
---

**MongoDB**는 현대 애플리케이션에서 중요한 역할을 하는 NoSQL 데이터베이스로, 다양한 형태의 데이터와 복잡한 구조를 유연하게 처리할 수 있는 장점을 가지고 있습니다. 관계형 데이터베이스와 비교했을 때, MongoDB는 문서 지향(Document-Oriented) 모델을 채택하여 데이터의 스키마를 자유롭게 설계할 수 있습니다. 이를 통해 불규칙하거나 복잡한 데이터구조를 다룰 때 유용하게 사용할 수 있습니다.

사이드 프로젝트로 영어 단어장 애플리케이션 만들기를 진행하며 프로젝트에 어떤 데이터베이스를 사용하는게 적합할까? 라는 고민을 하게 되었고 **MongoDB**를 채택하게 되었습니다. 이유는 바로 하나의 단어에 여러 개의 뜻이 존재하는 경우, 관계형 데이터베이스에서는 이를 처리하기 위해 복잡한 테이블 설계나 조인(join) 연산이 필요하지만 **MongoDB**를 사용할 경우 단일 문서에 배열 형태로 여러 뜻을 저장할 수 있어 구조를 단순화할 수 있다는 이점이 있었기 때문입니다. 따라서 **MongoDB** 사용을 확정하였고 해당 포스트에서 Kubernetes에 MongoDB를 구축하고 배포하는 과정을 공유하려 합니다.

**MongoDB**를 사용하는 방법에는 **MongoDB Atlas**, **MongoDB Enterprise**, **MongoDB Community Edition**의 방법이 있으며, 이번 과정에서는 **MongoDB Community Edition**을 **Helm**을 사용해 배포하겠습니다.

---

## 1. 구성 환경

- Helm (v3.16.2)
- Kubernetes (v1.29.6)
- Storage-Class (rancher/local-path-provisioner)

---

## 2. Helm Repository 추가

```bash
❯ helm repo add mongodb https://mongodb.github.io/helm-charts
"mongodb" has been added to your repositories
❯ helm repo update                                           
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "mongodb" chart repository
Update Complete. ⎈Happy Helming!⎈
```

---

## 3. Helm을 사용해 MongoDB Operator 배포

> mongodb라는 namespace에 MongoDB Operator를 배포하도록 하겠습니다.
{: .prompt-tip}

```bash
❯ helm install community-operator mongodb/community-operator --namespace mongodb --create-namespace

NAME: community-operator
LAST DEPLOYED: Tue Nov 12 15:08:45 2024
NAMESPACE: mongodb
STATUS: deployed
REVISION: 1
TEST SUITE: None
```

---

## 4. MongoDB Operator 확인

```bash
❯ kubens mongodb   
✔ Active namespace is "mongodb"
❯ k get all            
NAME                                               READY   STATUS    RESTARTS   AGE
pod/mongodb-kubernetes-operator-6d7f45687c-48222   1/1     Running   0          3m49s

NAME                                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/mongodb-kubernetes-operator   1/1     1            1           3m50s

NAME                                                     DESIRED   CURRENT   READY   AGE
replicaset.apps/mongodb-kubernetes-operator-6d7f45687c   1         1         1       3m50s
```

---

## 5. MongoDB Custom Resource (CR) 정의 파일 생성

> MongoDB Operator를 통해 MongoDB 인스턴스를 배포하려면 Custom Resource(CR)을 정의하여 MongoDB 클러스터를 생성해야 합니다.  
> storageClassName에는 현재 사용중인 storageClassName을 지정해주셔야 합니다.  
> ex) gp2, gp3, local-path  
> 최신 버전인 8.0 버전을 설치하겠습니다.  
{: .prompt-tip}

```yaml
# mongodb-custom-resource.yaml
apiVersion: mongodbcommunity.mongodb.com/v1
kind: MongoDBCommunity
metadata:
  name: mongodb
  namespace: mongodb
spec:
  members: 3
  type: ReplicaSet
  version: "8.0.0" # MongoDB 버전
  security:
    authentication:
      modes: ["SCRAM"] #SCRAM(Salted Challenge Response Authentication Mechanism) 인증을 사용하도록 설정
  users:
    - name: my-user # 사용자의 이름
      db: admin # 사용자가 인증할 데이터베이스
      passwordSecretRef: # 사용자의 Password를 지정하기 위한 Secret 지정
        name: mongodb-user-password
      roles: # 사용자에게 부여할 권한
        - name: clusterAdmin
          db: admin
        - name: userAdminAnyDatabase
          db: admin
      scramCredentialsSecretName: my-scram # SCRAM 인증을 위한 자격 증명 시크릿의 이름
  ## StatefulSet의 Spec Override => 본인의 Storage Class 명을 지정하거나 pvc에 맞는 pv를 직접 생성
  statefulSet:
    spec:
      volumeClaimTemplates:
        - metadata:
            name: data-volume
          spec:
            accessModes: ["ReadWriteOnce"]
            storageClassName: "local-path"  # 여기서 storageClassName을 지정합니다.
            resources:
              requests:
                storage: 10Gi
        - metadata:
            name: logs-volume
          spec:
            accessModes: ["ReadWriteOnce"]
            storageClassName: "local-path"  # 로그 볼륨에도 storageClassName을 지정합니다.
            resources:
              requests:
                storage: 5Gi
  additionalMongodConfig:
    storage.wiredTiger.engineConfig.journalCompressor: zlib
---
apiVersion: v1
kind: Secret
metadata:
  name: mongodb-user-password
type: Opaque
stringData:
  password: <your-password-here> # User의 Password 지정
```

---

## 6. MongoDB Custom Resource (CR)을 사용해 MongoDB 배포

```bash
❯ k apply -f mongodb-custom-resource.yaml 
mongodbcommunity.mongodbcommunity.mongodb.com/mongodb created
secret/mongodb-user-password created
```

---

## 7. MongoDB 배포 확인

```bash
❯ k get all                         
NAME                                               READY   STATUS    RESTARTS   AGE
pod/mongodb-0                                      2/2     Running   0          4m49s
pod/mongodb-kubernetes-operator-6d7f45687c-48222   1/1     Running   0          83m

NAME                  TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)     AGE
service/mongodb-svc   ClusterIP   None         <none>        27017/TCP   4m53s

NAME                                          READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/mongodb-kubernetes-operator   1/1     1            1           83m

NAME                                                     DESIRED   CURRENT   READY   AGE
replicaset.apps/mongodb-kubernetes-operator-6d7f45687c   1         1         1       83m

NAME                           READY   AGE
statefulset.apps/mongodb       1/1     4m52s
statefulset.apps/mongodb-arb   0/0     4m51s

❯ kubectl port-forward svc/mongodb-svc 27017:27017 -n mongodb

Forwarding from 127.0.0.1:27017 -> 27017
Forwarding from [::1]:27017 -> 27017

```

---

## 8. MongoDB 접속 확인

```bash
❯ mongosh --username {user_name} --password {user_password} --authenticationDatabase admin
Current Mongosh Log ID: 67330bd4cc38dd6e68c1c18b
Connecting to:          mongodb://<credentials>@127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&authSource=admin&appName=mongosh+2.3.3
Using MongoDB:          8.0.0
Using Mongosh:          2.3.3

For mongosh info see: https://www.mongodb.com/docs/mongodb-shell/

------
   The server generated these startup warnings when booting
   2024-11-12T07:28:08.638+00:00: Using the XFS filesystem is strongly recommended with the WiredTiger storage engine. See http://dochub.mongodb.org/core/prodnotes-filesystem
   2024-11-12T07:28:12.220+00:00: For customers running the tcmalloc-google memory allocator, we suggest setting the contents of sysfsFile to 'always'
   2024-11-12T07:28:12.220+00:00: For customers running the updated tcmalloc-google memory allocator, we suggest setting the contents of sysfsFile to 'defer+madvise'
   2024-11-12T07:28:12.220+00:00: We suggest setting the contents of sysfsFile to 0.
   2024-11-12T07:28:12.220+00:00: vm.max_map_count is too low
------

mongodb [direct: primary] test> show dbs
admin   172.00 KiB
config  176.00 KiB
local   500.00 KiB
mongodb [direct: primary] test> 
```

---

## 9. Reference

MongoDB Github - <https://github.com/mongodb/mongo>  
MongoDB 공식문서 - <https://www.mongodb.com/ko-kr/docs/manual/>  
MongoDB Operator - <https://github.com/mongodb/mongodb-kubernetes-operator/tree/master>

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
