---
title: Terraform templatefile() 함수 개념, 사용 방법
date: 2025-02-09 16:55:42 +0900
author: kkamji
categories: [IaC, Terraform]
tags: [terraform, templatefile, ec2, user-data, file, prometheus, node-exporter]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/iac/terraform/terraform.webp
---

Terraform에서 인프라 코드를 작성하다 보면 간단한 리소스 정의는 **HCL(HashiCorp Configuration Language)**로도 충분히 표현할 수 있습니다. 하지만 실제 운영 환경에서는 배포 초기에 실행해야 하는 스크립트나, 규모가 큰 애플리케이션 설정 파일 등을 다루어야 할 때가 많습니다. **HCL** 내부에 길고 복잡한 내용 설정들을 넣는 것은 **가독성**을 떨어뜨리고 **유지보수**를 어렵게 만들 수 있습니다. 이런 경우 Terraform에서 제공하는 `templatefile()` 함수를 사용하면 이러한 문제를 해결할 수 있습니다.

templatefile() 함수는 Terraform에서 제공하는 함수 중 하나로, **파일 내용을 읽어와서 변수를 적용한 뒤 문자열로 반환**하는 기능을 합니다. 해당 함수를 사용하면 별도의 파일에 작성된 내용을 Terraform 코드에 삽입할 수 있어 가독성을 높이고 유지보수를 용이하게 할 수 있습니다.

아래에서 `templatefile()` 함수의 사용 방법과 예시에 대해 알아보도록 하겠습니다.

---

## 1. `templatefile()` 사용 방법

### 1.1. 기본 문법

```hcl
templatefile(path, vars)
```

---

## 2. 사용 예시

> `templatefile()` 함수를 사용하여 EC2 인스턴스를 생성하는 코드에서 User_Data를 분리한 뒤 변수를 통해 템플릿 파일에, 값을 적용하는 예시입니다.
{: .prompt-tip}

### 2.1. TemplateFile 예시 (user_data.tpl)

```bash
#!/bin/bash
echo "Hello, ${name}"
echo "환경: ${environment}"
```

### 2.2. `templatefile()` 사용 예시

```hcl
resource "aws_instance" "example" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"

  user_data = templatefile(
    "${path.module}/userdata.tpl",
    {
      name        = "Alice"
      environment = "staging"
    }
  )
}
```

### 2.3. 결과 확인

> 위의 예시를 기반으로 `terraform apply`를 통해 인스턴스를 생성한 뒤, User_Data가 제대로 반영되었는지 확인해보도록 하겠습니다.
{: .prompt-tip}

```bash
❯ terraform apply --auto-approve
data.terraform_remote_state.basic: Reading...
data.terraform_remote_state.basic: Read complete after 5s

Terraform used the selected providers to generate the following execution plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_instance.templatefile_example will be created
  + resource "aws_instance" "templatefile_example" {
      + ami                                  = "ami-0b5511d5304edfc79"
      + arn                                  = (known after apply)
      + associate_public_ip_address          = (known after apply)
      + availability_zone                    = (known after apply)
      + cpu_core_count                       = (known after apply)
      + cpu_threads_per_core                 = (known after apply)
      + disable_api_stop                     = (known after apply)
...
...
...
      + tenancy                              = (known after apply)
      + user_data                            = "e8cea3cb64491b46830407d36ba14a85a7ad6347"
      + user_data_base64                     = (known after apply)
      + user_data_replace_on_change          = false
...
...
...
Changes to Outputs:
  + templatefile_ec2_instance_public_ip = (known after apply)
...
...
...
Outputs:

templatefile_ec2_instance_public_ip = "15.165.74.152"

#####################################################################################################################
#####################################################################################################################

❯ ssh ubuntu@15.165.74.152
...
...
...

❯ ubuntu@ip-10-0-1-200:~$ sudo cat /var/lib/cloud/instance/user-data.txt
#!/bin/bash
echo "Hello, Alice"
echo "환경: staging"
```

---

## 3. 결론

Terraform에서 제공하는 templatefile() 함수는 HCL 코드 내부에 복잡한 스크립트나 설정 파일을 직접 작성하지 않아도 되도록 해주어 유지보수와 가독성을 개선해 줍니다. 특히 AWS 환경에서 EC2를 생성할 때 자주 사용하는 User Data 스크립트나, 대규모 애플리케이션의 설정 파일 등을 템플릿 형태로 관리하면 반복 작업도 줄어들고 환경별 변수를 쉽게 관리할 수 있습니다.

규모가 커질수록 텍스트 기반 설정 파일(예: Nginx config, Prometheus config, Node Exporter config 등)이 많아지기 마련인데, 이런 경우에도 templatefile()를 활용해 인프라 코드와 설정 파일을 분리하게되면, 각각의 상황과 환경에 따라 Terraform 변수만 교체해 주면 되므로 개발과 운영 환경 관리에 도움이 될 것 같습니다.

---
> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKamJi](https://www.linkedin.com/in/taejikim/)**
{: .prompt-info}
