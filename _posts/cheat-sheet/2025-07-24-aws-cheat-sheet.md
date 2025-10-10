---
title: AWS CLI Command Cheat Sheet
date: 2025-07-24 23:15:53 +0900
author: kkamji
categories: [Cloud, AWS]
tags: [aws, cli, devops, cloud, aws-cli, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/aws/aws.webp
---

AWS CLI를 사용하며 알게된 CLI 명령어들을 공유합니다.

---

## 1. 기본 설정

```shell
aws configure                                        # AWS CLI 기본 설정
aws configure list                                   # 현재 설정 확인
aws configure list-profiles                          # Profile목록 확인
aws configure set region us-west-2                   # 기본 리전 설정
aws sts get-caller-identity                          # 현재 사용자/역할 확인
aws sts assume-role --role-arn <arn> --role-session-name <name>  # 역할 전환
```

---

## 2. Profile및 리전 관리

```shell
# Profile사용
aws configure --profile myprofile                    # Profile설정
aws s3 ls --profile myprofile                        # 특정 프로파일로 명령 실행
export AWS_PROFILE=myprofile                         # 기본 Profile설정

# 리전 지정
aws ec2 describe-instances --region us-east-1        # 특정 리전에서 명령 실행
export AWS_DEFAULT_REGION=us-east-1                  # 기본 리전 설정
```

---

## 3. 디버깅 및 문제 해결

```shell
aws configure list                                   # 현재 설정 확인
aws sts get-caller-identity                          # 현재 자격 증명 확인
aws --debug s3 ls                                    # 디버그 모드로 실행
aws --no-verify-ssl s3 ls                            # SSL 검증 비활성화
aws --cli-read-timeout 0 s3 sync ./large-folder s3://my-bucket/  # 타임아웃 비활성화
```

---

## 4. EC2 관련 명령어

```shell
# 인스턴스 관리
aws ec2 describe-instances                           # 모든 인스턴스 조회
aws ec2 describe-instances --instance-ids i-1234567890abcdef0  # 특정 인스턴스 조회
aws ec2 run-instances --image-id ami-12345678 --count 1 --instance-type t2.micro  # 인스턴스 시작
aws ec2 start-instances --instance-ids i-1234567890abcdef0     # 인스턴스 시작
aws ec2 stop-instances --instance-ids i-1234567890abcdef0      # 인스턴스 중지
aws ec2 terminate-instances --instance-ids i-1234567890abcdef0 # 인스턴스 종료
aws ec2 reboot-instances --instance-ids i-1234567890abcdef0    # 인스턴스 재부팅

# AMI 관리
aws ec2 describe-images --owners self                # 내 AMI 목록
aws ec2 create-image --instance-id i-1234567890abcdef0 --name "MyAMI"  # AMI 생성
aws ec2 deregister-image --image-id ami-12345678     # AMI 삭제

# 보안 그룹
aws ec2 describe-security-groups                     # 보안 그룹 목록
aws ec2 create-security-group --group-name MySecurityGroup --description "My security group"
aws ec2 authorize-security-group-ingress --group-id sg-12345678 --protocol tcp --port 22 --cidr 0.0.0.0/0

# 키 페어
aws ec2 describe-key-pairs                           # 키 페어 목록
aws ec2 create-key-pair --key-name MyKeyPair --query 'KeyMaterial' --output text > MyKeyPair.pem
```

---

## 5. S3 관련 명령어

```shell
# 버킷 관리
aws s3 ls                                            # 모든 버킷 목록
aws s3 mb s3://my-bucket                             # 버킷 생성
aws s3 rb s3://my-bucket                             # 빈 버킷 삭제
aws s3 rb s3://my-bucket --force                     # 버킷과 모든 객체 삭제

# 파일 업로드/다운로드
aws s3 cp file.txt s3://my-bucket/                   # 파일 업로드
aws s3 cp s3://my-bucket/file.txt ./                 # 파일 다운로드
aws s3 sync ./local-folder s3://my-bucket/folder/    # 폴더 동기화
aws s3 sync s3://my-bucket/folder/ ./local-folder    # S3에서 로컬로 동기화

# 객체 관리
aws s3 ls s3://my-bucket                             # 버킷 내용 목록
aws s3 ls s3://my-bucket --recursive                 # 재귀적 목록
aws s3 rm s3://my-bucket/file.txt                    # 파일 삭제
aws s3 rm s3://my-bucket --recursive                 # 모든 객체 삭제
```

---

## 6. IAM 관련 명령어

```shell
# 사용자 관리
aws iam list-users                                   # 사용자 목록
aws iam create-user --user-name MyUser               # 사용자 생성
aws iam delete-user --user-name MyUser               # 사용자 삭제
aws iam get-user --user-name MyUser                  # 사용자 정보 조회

# 역할 관리
aws iam list-roles                                   # 역할 목록
aws iam create-role --role-name MyRole --assume-role-policy-document file://trust-policy.json
aws iam delete-role --role-name MyRole               # 역할 삭제
aws iam get-role --role-name MyRole                  # 역할 정보 조회

# 정책 관리
aws iam list-policies                                # 정책 목록
aws iam create-policy --policy-name MyPolicy --policy-document file://policy.json
aws iam attach-user-policy --user-name MyUser --policy-arn arn:aws:iam::123456789012:policy/MyPolicy
aws iam detach-user-policy --user-name MyUser --policy-arn arn:aws:iam::123456789012:policy/MyPolicy

# 액세스 키 관리
aws iam list-access-keys --user-name MyUser          # 액세스 키 목록
aws iam create-access-key --user-name MyUser         # 액세스 키 생성
aws iam delete-access-key --user-name MyUser --access-key-id AKIAIOSFODNN7EXAMPLE
```

---

## 7. VPC 관련 명령어

```shell
# VPC 관리
aws ec2 describe-vpcs                                # VPC 목록
aws ec2 create-vpc --cidr-block 10.0.0.0/16         # VPC 생성
aws ec2 delete-vpc --vpc-id vpc-12345678             # VPC 삭제

# 서브넷 관리
aws ec2 describe-subnets                             # 서브넷 목록
aws ec2 create-subnet --vpc-id vpc-12345678 --cidr-block 10.0.1.0/24
aws ec2 delete-subnet --subnet-id subnet-12345678    # 서브넷 삭제

# 인터넷 게이트웨이
aws ec2 describe-internet-gateways                   # 인터넷 게이트웨이 목록
aws ec2 create-internet-gateway                      # 인터넷 게이트웨이 생성
aws ec2 attach-internet-gateway --vpc-id vpc-12345678 --internet-gateway-id igw-12345678

# 라우팅 테이블
aws ec2 describe-route-tables                        # 라우팅 테이블 목록
aws ec2 create-route-table --vpc-id vpc-12345678     # 라우팅 테이블 생성
aws ec2 create-route --route-table-id rtb-12345678 --destination-cidr-block 0.0.0.0/0 --gateway-id igw-12345678
```

---

## 8. EKS 관련 명령어

```shell
# 클러스터 관리
aws eks list-clusters                                # EKS 클러스터 목록
aws eks describe-cluster --name my-cluster           # 클러스터 정보 조회
aws eks create-cluster --name my-cluster --version 1.21 --role-arn arn:aws:iam::123456789012:role/eks-service-role
aws eks delete-cluster --name my-cluster             # 클러스터 삭제
aws eks update-cluster-version --name my-cluster --version 1.22  # 클러스터 버전 업데이트
aws eks update-cluster-config --name my-cluster --logging '{"enable":[{"types":["api","audit","authenticator","controllerManager","scheduler"]}]}'

# 노드 그룹 관리
aws eks list-nodegroups --cluster-name my-cluster    # 노드 그룹 목록
aws eks describe-nodegroup --cluster-name my-cluster --nodegroup-name my-nodegroup
aws eks create-nodegroup --cluster-name my-cluster --nodegroup-name my-nodegroup --subnets subnet-12345678 --instance-types t3.medium --ami-type AL2_x86_64 --capacity-type ON_DEMAND
aws eks delete-nodegroup --cluster-name my-cluster --nodegroup-name my-nodegroup
aws eks update-nodegroup-version --cluster-name my-cluster --nodegroup-name my-nodegroup  # 노드 그룹 버전 업데이트
aws eks update-nodegroup-config --cluster-name my-cluster --nodegroup-name my-nodegroup --scaling-config minSize=1,maxSize=10,desiredSize=3

# Fargate Profile관리
aws eks list-fargate-profiles --cluster-name my-cluster  # Fargate Profile목록
aws eks describe-fargate-profile --cluster-name my-cluster --fargate-profile-name my-fargate-profile
aws eks create-fargate-profile --cluster-name my-cluster --fargate-profile-name my-fargate-profile --pod-execution-role-arn arn:aws:iam::123456789012:role/eks-fargate-profile
aws eks delete-fargate-profile --cluster-name my-cluster --fargate-profile-name my-fargate-profile

# 특정 버전과 호환되는 Add-on 리스트 확인
aws eks describe-addon-versions --kubernetes-version <k8s-version> # 특정 K8s 버전과 호환되는 애드온 버전 확인 ex) `--kubernetes-version 1.33`

# 특정 버전과 호환되는 Add-on 리스트 확인 (table 형태)
aws eks describe-addon-versions \
  --kubernetes-version 1.33 \
  --query 'sort_by(addons, &owner)[].{addonName: addonName, owner: owner, publisher: publisher, type: type}' \
  --output table

# 특정 버전과 호환되는 vpc-cni의 사용 가능한 버전 확인 (table 형태)
aws eks describe-addon-versions \
  --kubernetes-version 1.33 \
  --addon-name vpc-cni \
  --query 'addons[].addonVersions[].addonVersion' \
  --output table

# 애드온 관리
aws eks list-addons --cluster-name my-cluster        # 애드온 목록
aws eks describe-addon --cluster-name my-cluster --addon-name vpc-cni
aws eks describe-addon-versions --kubernetes-version <k8s-version> --addon-name <add-on-name> # 특정 K8s 버전과 특정 애드온 버전 확인



# 애드온 생성, 업데이트, 삭제
aws eks create-addon --cluster-name my-cluster --addon-name vpc-cni --addon-version v1.12.6-eksbuild.2
aws eks update-addon --cluster-name my-cluster --addon-name vpc-cni --addon-version v1.13.4-eksbuild.1
aws eks delete-addon --cluster-name my-cluster --addon-name vpc-cni

# kubeconfig 업데이트
aws eks update-kubeconfig --region us-west-2 --name my-cluster  # kubeconfig 업데이트
aws eks update-kubeconfig --region us-west-2 --name my-cluster --alias my-cluster-alias  # 별칭과 함께 업데이트
aws eks update-kubeconfig --region us-west-2 --name my-cluster --role-arn arn:aws:iam::123456789012:role/EKSRole  # 특정 역할로 업데이트

# 클러스터 액세스 관리
aws eks list-access-entries --cluster-name my-cluster  # 액세스 엔트리 목록
aws eks create-access-entry --cluster-name my-cluster --principal-arn arn:aws:iam::123456789012:user/my-user
aws eks associate-access-policy --cluster-name my-cluster --principal-arn arn:aws:iam::123456789012:user/my-user --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy

# EKS 클러스터 문제 해결
aws eks describe-cluster --name my-cluster --query 'cluster.status'  # 클러스터 상태
aws eks describe-cluster --name my-cluster --query 'cluster.health'  # 클러스터 헬스 상태
aws ec2 describe-instances --filters "Name=tag:kubernetes.io/cluster/my-cluster,Values=owned" --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PrivateIpAddress]'  # EKS 노드 EC2 인스턴스 상태
```

---

## 9. CloudFormation 관련 명령어

```shell
# 스택 관리
aws cloudformation list-stacks                       # 스택 목록
aws cloudformation describe-stacks --stack-name my-stack  # 스택 정보 조회
aws cloudformation create-stack --stack-name my-stack --template-body file://template.yaml
aws cloudformation update-stack --stack-name my-stack --template-body file://template.yaml
aws cloudformation delete-stack --stack-name my-stack # 스택 삭제

# 스택 이벤트 및 리소스
aws cloudformation describe-stack-events --stack-name my-stack  # 스택 이벤트 조회
aws cloudformation describe-stack-resources --stack-name my-stack  # 스택 리소스 조회
aws cloudformation list-stack-resources --stack-name my-stack   # 스택 리소스 목록
```

---

## 10. CloudWatch 관련 명령어

```shell
# 로그 그룹 관리
aws logs describe-log-groups                         # 로그 그룹 목록
aws logs create-log-group --log-group-name my-log-group  # 로그 그룹 생성
aws logs delete-log-group --log-group-name my-log-group  # 로그 그룹 삭제

# 로그 스트림
aws logs describe-log-streams --log-group-name my-log-group  # 로그 스트림 목록
aws logs get-log-events --log-group-name my-log-group --log-stream-name my-log-stream

# 메트릭
aws cloudwatch list-metrics                          # 메트릭 목록
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value=i-1234567890abcdef0 --statistics Average --start-time 2023-01-01T00:00:00Z --end-time 2023-01-01T23:59:59Z --period 3600
```

---

## 11. Lambda 관련 명령어

```shell
# 함수 관리
aws lambda list-functions                            # Lambda 함수 목록
aws lambda get-function --function-name my-function  # 함수 정보 조회
aws lambda create-function --function-name my-function --runtime python3.9 --role arn:aws:iam::123456789012:role/lambda-role --handler lambda_function.lambda_handler --zip-file fileb://function.zip
aws lambda update-function-code --function-name my-function --zip-file fileb://function.zip
aws lambda delete-function --function-name my-function  # 함수 삭제

# 함수 실행
aws lambda invoke --function-name my-function --payload '{"key":"value"}' response.json
aws lambda invoke --function-name my-function --invocation-type Event --payload '{"key":"value"}' response.json  # 비동기 실행
```

---

## 12. RDS 관련 명령어

```shell
# DB 인스턴스 관리
aws rds describe-db-instances                        # DB 인스턴스 목록
aws rds create-db-instance --db-instance-identifier mydb --db-instance-class db.t3.micro --engine mysql --master-username admin --master-user-password mypassword --allocated-storage 20
aws rds delete-db-instance --db-instance-identifier mydb --skip-final-snapshot  # DB 인스턴스 삭제

# 스냅샷 관리
aws rds describe-db-snapshots                        # 스냅샷 목록
aws rds create-db-snapshot --db-instance-identifier mydb --db-snapshot-identifier mydb-snapshot
aws rds delete-db-snapshot --db-snapshot-identifier mydb-snapshot  # 스냅샷 삭제
```

---

## 13. 유용한 필터링 및 출력 옵션

```shell
# JMESPath 쿼리 사용
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType]' --output table
aws s3api list-objects-v2 --bucket my-bucket --query 'Contents[?Size > `1000000`].[Key,Size]' --output table

# 태그 필터링
aws ec2 describe-instances --filters "Name=tag:Environment,Values=production"
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running"

# 출력 형식 변경
aws ec2 describe-instances --output json             # JSON 출력
aws ec2 describe-instances --output table            # 테이블 형식 출력
aws ec2 describe-instances --output text             # 텍스트 출력
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
