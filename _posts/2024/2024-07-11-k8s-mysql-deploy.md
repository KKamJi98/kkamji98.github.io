---
title: Kubernetes을 사용해 MySQL서버 구축 & 배포하기
date: 2024-07-11 19:43:16 +0900
author: kkamji
categories: [Kubernetes]
tags: [mysql, kubernetes, pv, pvc, config-map, local]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/mysql/mysql.webp
---

2024년 07월 08일부터 Weasel 이라는 프로젝트를 시작했습니다. RDS를 띄우기 전, 개발 및 테스트 용도로 사용될 MySQL 서버가 필요했습니다.
해당 포스트에서는 Kubernetes Cluster에 MySQL 서버를 구축하고 배포하는 과정에 대해 다뤄보겠습니다.

> 2024/08/28 - Mysql 같은 경우 클러스터링을 할 경우 여러 개의 Pods를 띄울 상황이 생깁니다. 해당 경우 Deployment가 아닌 StatefulSet을 사용해야 합니다.
{: .prompt-info}

---

## 1. 사전 준비물

쿠버네티스

---

## 2. PV, PVC 생성

> 기본적으로 Pod가 실행되면서 생긴 데이터는 Pod가 삭제되거나 재시작될 때 유지되지 않습니다. 따라서 데이터를 영구적으로 저장할 PV, PVC를 생성해주었습니다. 해당 방법과 더불어 Storage Class를 사용하는 방법도 추천드립니다.
{: .prompt-info}

### 2.1 mysql-pv.yaml

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: mysql-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: "/mnt/data"
```

### 2.2 mysql-pvc.yaml

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

---

## 3. ConfigMap 생성

> 팀원들이 사용할 사용자 계정을 생성해야했고, ConfigMap의 데이터를 컨테이너의 `/docker-entrypoint-initdb.d` 디렉토리에 마운트하면 MySQL 컨테이너가 초기화 되면서 해당 파일이 같이 실행되는 것을 알게 되었습니다.
{: .prompt-info}

### 3.1 mysql-configmap.yaml

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mysql-initdb-config
data:
  init.sql: |
    GRANT ALL PRIVILEGES ON *.* TO 's5t1'@'%' WITH GRANT OPTION;
    FLUSH PRIVILEGES;
```

---

## 4. secrets 생성

> MySQL 초기화에 필요한 환경변수들을 Secret으로 생성해주었습니다. 여기서 주의할 점은 시크릿을 암호화하지 않게되면 base64로 인코딩 한 값을 kubectl 명령어를 통해 확인할 수 있으므로, 쿠버네티스 클러스터 설정에서 `EncryptionConfigure`를 사용해주어야 합니다. 추가로 HashiCorp Vault, AWS Secret Manager를 사용하는 방법도 추천드립니다.
{: .prompt-info}

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysql-secret
type: Opaque
data:
  mysql-root-password: {mysql-root-password}
  mysql-user-id: {mysql-user-id}
  mysql-user-password: {mysql-user-password}
  mysql-database-name: {mysql-database-name}
```

---

## 5. Deployment 생성

> 앞에서 만든 ConfigMap, Secret을 사용해 MySQL Deployment를 생성해주었습니다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
spec:
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - image: mysql:5.7
        name: mysql
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: mysql-root-password
        - name: MYSQL_USER
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: mysql-user-id
        - name: MYSQL_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: mysql-user-password
        - name: MYSQL_DATABASE
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: mysql-database-name
        ports:
        - containerPort: 3306
          name: mysql
        volumeMounts:
        - name: mysql-storage
          mountPath: /var/lib/mysql
        - name: initdb
          mountPath: /docker-entrypoint-initdb.d # 초기화 스크립트를 저장하는 특별한 위치 디렉토리에 있는 모든 .sh, .sql, .sql.gz 파일이 자동으로 실행
      volumes:
      - name: mysql-storage
        persistentVolumeClaim:
          claimName: mysql-pvc
      - name: initdb
        configMap:
          name: mysql-initdb-config
```

---

## 6. Service 생성

> 간단한 배포를 위해 NodePort를 사용했고, 30006번 포트로 배포했습니다.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  type: NodePort
  ports:
  - name: mysql-port
    port: 3306
    targetPort: 3306
    nodePort: 30006
  selector:
    app: mysql
```

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
