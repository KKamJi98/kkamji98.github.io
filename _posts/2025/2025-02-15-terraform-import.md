---
title: Terraform Import 개념, 사용 방법
date: 2025-02-15 09:02:29 +0900
author: kkamji
categories: [IaC, Terraform]
tags: [terraform, import, ec2, aws]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/terraform/terraform.webp
---

Cloud 환경에서 Terraform을 사용하여 인프라를 관리하다 보면, 기존에 수동으로 생성한 리소스를 Terraform 코드로 관리해야 하는 경우가 있습니다. 이때 `terraform import` 명령어를 사용하면 기존 리소스를 Terraform 상태 파일(`.tfstate`)에 추가할 수 있습니다.

이번 포스팅에서는 `terraform import` 의 기본 개념과 사용 방법, 그리고 `terraform state show` 명령어를 통해 코드와 리소스를 쉽게 매칭시키는 방법에 대해 알아보겠습니다.

---

## 1. terraform import 란?

`terraform import` 명령어는 기존에 생성된 리소스를 Terraform 코드로 가져오는 기능을 제공합니다. `terraform import`를 사용하면 기존 리소스의 상태를 `.tfstate` 파일에 추가할 수 있으며, 이를 통해 Terraform 코드로 리소스를 관리할 수 있게 됩니다.

> - `terraform import`는 자동으로 `.tf` 코드(리소스 블록)를 생성해주지 않습니다.  
>   즉, 해당 리소스에 대응하는 Terraform 코드 블록은 사용자가 직접 작성해야 하며, 이후 상태와 코드가 일치하는지 확인해야 합니다.
> - 만약 Terraform 코드와 실제 리소스의 설정이 일치하지 않으면, `terraform import` 후 `terraform apply` 시 예상치 못한 변경사항이 발생할 수 있습니다.  
>   예를 들어: 기존 리소스의 속성값이 코드와 다를 경우, `apply` 시 코드에 맞춰 리소스가 수정될 수 있으므로 주의해야 합니다.
{: .prompt-danger}

---

## 2. terraform import 사용 방법

> 기존에 생성된 AWS EC2를 `terraform import` 명령어를 사용하여 해당 리소스를 가져오고, 코드와 리소스가 매칭되지 않을 시, `terraform state show` 명령어를 통해 코드와 리소스를 매칭시키는 방법을 알아보겠습니다.
{: .prompt-tip}

### 2.1 기존 리소스 정보 확인

![Existing EC2](/assets/img/kkam-img/kkamji-ec2.webp)

```shell
❯ aws ec2 describe-instances | jq '.Reservations[] | select(.Instances[].Tags[].Value=="kkamji-ec2")'
{
  "Groups": [],
  "Instances": [
    {
      "AmiLaunchIndex": 0,
      "ImageId": "ami-024ea438ab0376a47",
      "InstanceId": "i-028c380e41117d2a7",
      "InstanceType": "t2.micro",
      "LaunchTime": "2025-02-15T13:22:41+00:00",
      "Monitoring": {
        "State": "disabled"
      },
      "Placement": {
        "AvailabilityZone": "ap-northeast-2c",
        "GroupName": "",
        "Tenancy": "default"
      },
      "PrivateDnsName": "ip-172-31-43-148.ap-northeast-2.compute.internal",
      "PrivateIpAddress": "172.31.43.148",
      "ProductCodes": [],
      "PublicDnsName": "ec2-54-180-88-112.ap-northeast-2.compute.amazonaws.com",
      "PublicIpAddress": "54.180.88.112",
      "State": {
        "Code": 16,
        "Name": "running"
      },
      ...
      ...
      "BootMode": "uefi-preferred",
      "PlatformDetails": "Linux/UNIX",
      "UsageOperation": "RunInstances",
      "UsageOperationUpdateTime": "2025-02-15T13:22:41+00:00",
      "PrivateDnsNameOptions": {
        "HostnameType": "ip-name",
        "EnableResourceNameDnsARecord": true,
        "EnableResourceNameDnsAAAARecord": false
      },
      "MaintenanceOptions": {
        "AutoRecovery": "default"
      },
      "CurrentInstanceBootMode": "legacy-bios"
    }
  ],
  "OwnerId": "xxxxxxxxxxxx",
  "ReservationId": "r-093fe889700651ca2"
}
```

### 2.2 Terraform 코드 작성

```hcl
# main.tf

resource "aws_instance" "kkamji-ec2" {
  ami           = "ami-024ea438ab0376a47"
  instance_type = "t3.medium"
  tags = {
    Name = "kkamji-ec2"
  }

  lifecycle {
    ignore_changes = [ 
      user_data,
      user_data_replace_on_change
    ]
  }
}
```

### 2.3 Import 명령어 실행

```shell
❯ terraform import aws_instance.kkamji-ec2 i-028c380e41117d2a7

Import successful!

The resources that were imported are shown above. These resources are now in
your Terraform state and will henceforth be managed by Terraform.
```

### 2.4 terraform state 확인

```shell
❯ terraform state list                                               
aws_instance.kkamji-ec2
```

### 2.5 terraform plan

> import가 잘 되었다면 `terraform plan`시, 변경사항이 없어야 합니다.
> 하지만 코드와 리소스의 상태가 일치하지 않는 경우, 아래와 같이 변경사항이 발생할 수 있습니다.
{: .prompt-tip}

```shell
❯ terraform plan                                              
Running plan in HCP Terraform. Output will stream here. Pressing Ctrl-C
will stop streaming the logs, but will not stop the plan running remotely.

Preparing the remote plan...

To view this run in a browser, visit:
https://app.terraform.io/app/xxx/import_ec2/runs/run-ZzGZrWmaZWg2vCwP

Waiting for the plan to start...

Terraform v1.10.4
on linux_amd64
Initializing plugins and modules...
aws_instance.kkamji-ec2: Refreshing state... [id=i-028c380e41117d2a7]

Terraform used the selected providers to generate the following execution plan. Resource actions are indicated with the
following symbols:
  ~ update in-place

Terraform will perform the following actions:

  # aws_instance.kkamji-ec2 will be updated in-place
  ~ resource "aws_instance" "kkamji-ec2" {
        id                                   = "i-028c380e41117d2a7"
      ~ instance_type                        = "t2.micro" -> "t3.medium"
      ~ public_dns                           = "ec2-54-180-88-112.ap-northeast-2.compute.amazonaws.com" -> (known after apply)
      ~ public_ip                            = "54.180.88.112" -> (known after apply)
        tags                                 = {
            "Name" = "kkamji-ec2"
        }
        # (36 unchanged attributes hidden)

        # (8 unchanged blocks hidden)
    }

Plan: 0 to add, 1 to change, 0 to destroy.

------------------------------------------------------------------------

Cost Estimation:

Resources: 1 of 1 estimated
           $31.820799999999999744/mo +$23.3856

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Note: You didn't use the -out option to save this plan, so Terraform can't guarantee to take exactly these actions if you
run "terraform apply" now.
```

### 2.6 `terraform state show` - 손쉽게 코드와 리소스 매칭시키기

> 위와 같이 코드와 리소스의 상태가 일치하지 않아 `terraform plan` 시 변경사항이 발생하면 코드를 수정해야합니다. (수정하지 않으면 해당 리소스가 삭제 후 다시 만들어지거나, 변경될 수 있습니다.)  
> 이런 경우 `terraform state show` 명령어를 통해 실제 리소스의 상태를 확인하고 해당 결과를 참고하면 쉽게 코드와 리소스를 매칭시킬 수 있습니다.
{: .prompt-tip}

```shell
❯ terraform state show aws_instance.kkamji-ec2 | grep -i "instance_type"
    instance_type                        = "t2.micro"

## 코드 변경 (instance_type 수정)
```hcl
resource "aws_instance" "kkamji-ec2" {
  ami           = "ami-024ea438ab0376a47"
  instance_type = "t2.micro"
  tags = {
    Name = "kkamji-ec2"
  }

  lifecycle {
    ignore_changes = [ 
      user_data,
      user_data_replace_on_change
    ]
  }
}
```

### 7. `terraform plan` - 변경사항 확인

> 아래와 같이 `No changes. Your infrastructure matches the configuration.` 메시지가 나오면 변경사항이 없다는 뜻입니다. terraform import 성공!
{: .prompt-tip}

```shell
❯ tf plan                                                        
Running plan in HCP Terraform. Output will stream here. Pressing Ctrl-C
will stop streaming the logs, but will not stop the plan running remotely.

Preparing the remote plan...

To view this run in a browser, visit:
https://app.terraform.io/app/xxx/import_ec2/runs/run-fJbdtF2CXXbSMFdS

Waiting for the plan to start...

Terraform v1.10.4
on linux_amd64
Initializing plugins and modules...
aws_instance.kkamji-ec2: Refreshing state... [id=i-028c380e41117d2a7]

No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration and found no differences, so no changes are
needed.

------------------------------------------------------------------------

Cost Estimation:

Resources: 1 of 1 estimated
           $8.435199999999999744/mo +$0.0

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

Note: You didn't use the -out option to save this plan, so Terraform can't guarantee to take exactly these actions if you
run "terraform apply" now.
```

## 마무리

terraform import를 통해 클라우드 환경에서 수동으로 생성한 리소스를 Terraform 상태에 가져오고, terraform state show를 활용해 코드와 실제 리소스 설정을 손쉽게 맞추는 과정을 다뤄봤습니다.

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
