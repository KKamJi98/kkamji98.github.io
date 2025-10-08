# custom 디렉터리 사용 가이드

## 구성 요소 개요

- `init.lua`: Neovim 초기화 스크립트. LSP, 플러그인, UI 최적화를 포함합니다.
- `sg_all_sgr_audit*.py`: AWS Security Group(SG) 감사용 도구. 단일 실행 버전과 멀티스레드 확장 버전이 함께 존재합니다.

## 공통 준비 사항

- Python 3.10 이상을 권장합니다. (Boto3 최신 버전과의 호환성 기준)
- AWS API 호출이 필요하므로 `boto3` 패키지를 설치하고, 유효한 자격 증명이 환경 변수/프로파일 등에 구성되어 있어야 합니다.
- 권장 설치:

```bash
python -m pip install --upgrade boto3 botocore
```

- SG 대상 목록(`sg_list`) 파일을 미리 작성합니다.

```txt
# 예시: sg_list.txt
sg-0123456789abcdef0
sg-0fedcba9876543210
```

JSON 로그를 재활용하는 경우 `sg_all_sgr_audit_multi_v2.py`가 자동으로 SG ID를 추출합니다.

## Neovim 설정 (init.lua)

- 목적: 안정성과 성능을 고려한 개인용 Neovim 풀 설정입니다.
- 적용 방법:
  1. Neovim 설정 디렉터리를 준비합니다.
  2. 기존 설정이 있다면 백업합니다.
  3. `custom/init.lua`를 `~/.config/nvim/init.lua`로 복사합니다.

```bash
mkdir -p ~/.config/nvim
cp custom/init.lua ~/.config/nvim/init.lua
```

- 주요 특징:
  - `lazy.nvim` 기반 플러그인 관리.
  - AWS·Python 개발을 위한 LSP 기본값 제공.
  - OSC52 클립보드 연동, tokyonight 테마 등 UI 개선.

## AWS SG 감사 스크립트 공통 옵션

```bash
python custom/<script_name>.py \
  --region ap-northeast-2 \
  --profile myaws \
  --sg-list /path/to/sg_list.txt \
  --out /tmp/sg_audit.csv
```

- `--region`: 대상 리전을 지정합니다.
- `--profile`: 로컬 `~/.aws/credentials`에 정의된 프로파일 이름입니다.
- `--sg-list`: SG ID가 포함된 텍스트 파일 경로입니다.
- `--out`: 출력 CSV 파일 경로입니다.

모든 스크립트는 `sg_id, SG_Name, ... Usage_Status` 컬럼을 가진 CSV를 생성합니다. 존재하지 않는 SG는 `Usage_Status=NOT_FOUND`로 기록됩니다.

## sg_all_sgr_audit.py (단일 스레드)

- 특징:
  - 가장 단순한 구현. 순차적으로 SG 메타데이터와 규칙을 조회합니다.
  - AWS API 호출 수가 적은 환경이나 디버깅 시 유용합니다.
- 사용 예:

```bash
python custom/sg_all_sgr_audit.py \
  --region ap-northeast-2 \
  --profile myaws \
  --sg-list ./fixtures/sg_list.txt \
  --out ./outputs/sg_audit_basic.csv
```

- 예상 실행 시간은 SG 수에 비례합니다. 수십 개 이상의 SG를 처리할 경우 멀티스레드 버전 사용을 권장합니다.

## sg_all_sgr_audit_multi.py (병렬 & 프리페치)

- 특징:
  - SG별 스캔을 멀티스레드로 처리(`--max-workers` 기본 8).
  - AutoScalingGroup/LaunchConfiguration/LaunchTemplate 정보를 사전 프리페치하여 스로틀을 완화합니다.
  - 자격 증명 루프 감지 시 기본 체인으로 폴백합니다.
- 추가 옵션:
  - `--max-workers`: 동시 실행 스레드 수. SG 수와 계정 한도에 맞춰 조정합니다.
- 사용 예:

```bash
python custom/sg_all_sgr_audit_multi.py \
  --region ap-northeast-2 \
  --profile myaws \
  --sg-list ./fixtures/sg_list.txt \
  --out ./outputs/sg_audit_multi.csv \
  --max-workers 12
```

- CloudTrail/RateLimit를 고려해 8~16 사이 값을 추천합니다.

## sg_all_sgr_audit_multi_v2.py (유연 입력 & 중복 제거)

- 특징:
  - `sg_list`의 각 줄에서 SG ID를 정규식으로 추출합니다. JSON 라인, 로그, 복합 문자열 모두 처리 가능합니다.
  - `describe_security_group_rules` 결과 중복을 제거해 CSV 품질을 개선합니다.
  - 나머지 동작은 `sg_all_sgr_audit_multi.py`와 동일합니다.
- 사용 예:

```bash
python custom/sg_all_sgr_audit_multi_v2.py \
  --region ap-northeast-2 \
  --profile myaws \
  --sg-list ./fixtures/sg_list_mixed.log \
  --out ./outputs/sg_audit_multi_v2.csv \
  --max-workers 16
```

- JSON 라인 예시:

```json
{"account":"prod","sg":{"id":"sg-0123456789abcdef0"}}
{"account":"prod","description":"candidate sg-0fedcba9876543210 for audit"}
```

## 실행 후 권장 절차

1. CSV 파일의 `Usage_Status`와 `Resources` 컬럼을 검토하여 미사용 SG를 식별합니다.
2. RateLimit 경고가 발생하면 `--max-workers` 값을 낮추거나, SG 목록을 분할해 순차 실행합니다.
3. 감사 결과를 다른 팀에 공유할 때는 민감한 리소스 식별자가 노출되지 않도록 필터링하세요.
