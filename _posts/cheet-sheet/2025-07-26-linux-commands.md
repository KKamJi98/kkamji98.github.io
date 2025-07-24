---
title: Linux Command Cheat Sheet
date: 2025-07-26 22:28:00 +0900
author: kkamji
categories: [Linux]
tags: [linux, bash, shell, devops, command-line]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/linux/linux-terminal.webp
---

Linux 시스템 관리 및 일상 업무에서 자주 사용하는 명령어들을 정리한 치트시트입니다.

## 파일 및 디렉토리 관리

```shell
# 기본 파일 조작
ls                                                   # 현재 디렉토리 파일 목록
ls -la                                               # 숨김 파일 포함 상세 목록
ls -lh                                               # 파일 크기를 읽기 쉽게 표시
ls -lt                                               # 수정 시간순 정렬
ls -lS                                               # 파일 크기순 정렬
pwd                                                  # 현재 디렉토리 경로 출력
cd /path/to/directory                                # 디렉토리 이동
cd ~                                                 # 홈 디렉토리로 이동
cd -                                                 # 이전 디렉토리로 이동
mkdir directory_name                                 # 디렉토리 생성
mkdir -p /path/to/nested/directory                   # 중첩 디렉토리 생성
rmdir directory_name                                 # 빈 디렉토리 삭제
rm -rf directory_name                                # 디렉토리와 내용 모두 삭제

# 파일 복사, 이동, 삭제
cp file1 file2                                       # 파일 복사
cp -r dir1 dir2                                      # 디렉토리 재귀 복사
cp -p file1 file2                                    # 권한과 타임스탬프 유지하며 복사
mv file1 file2                                       # 파일 이동/이름 변경
rm file                                              # 파일 삭제
rm -f file                                           # 강제 삭제
rm -i file                                           # 삭제 전 확인

# 파일 링크
ln file hardlink                                     # 하드링크 생성
ln -s /path/to/file symlink                          # 심볼릭 링크 생성
readlink symlink                                     # 심볼릭 링크가 가리키는 경로 확인
```

## 파일 내용 확인 및 편집

```shell
# 파일 내용 보기
cat file                                             # 파일 전체 내용 출력
less file                                            # 페이지 단위로 파일 내용 보기
more file                                            # 페이지 단위로 파일 내용 보기
head file                                            # 파일 앞부분 10줄 출력
head -n 20 file                                      # 파일 앞부분 20줄 출력
tail file                                            # 파일 뒷부분 10줄 출력
tail -n 20 file                                      # 파일 뒷부분 20줄 출력
tail -f file                                         # 파일 실시간 모니터링

# 파일 편집
nano file                                            # nano 에디터로 파일 편집
vim file                                             # vim 에디터로 파일 편집
emacs file                                           # emacs 에디터로 파일 편집

# 파일 비교
diff file1 file2                                     # 두 파일 차이점 비교
diff -u file1 file2                                  # unified 형식으로 차이점 표시
cmp file1 file2                                      # 두 파일이 동일한지 확인
```

## 텍스트 처리 및 검색

```shell
# 텍스트 검색
grep "pattern" file                                  # 파일에서 패턴 검색
grep -i "pattern" file                               # 대소문자 구분 없이 검색
grep -r "pattern" directory                          # 디렉토리 내 재귀 검색
grep -n "pattern" file                               # 줄 번호와 함께 검색
grep -v "pattern" file                               # 패턴과 일치하지 않는 줄 출력
grep -c "pattern" file                               # 패턴 매칭 줄 수 카운트
grep -E "pattern1|pattern2" file                     # 확장 정규식 사용

# 텍스트 처리
sort file                                            # 파일 내용 정렬
sort -r file                                         # 역순 정렬
sort -n file                                         # 숫자 기준 정렬
sort -k 2 file                                       # 두 번째 필드 기준 정렬
uniq file                                            # 중복 줄 제거
uniq -c file                                         # 중복 줄 개수와 함께 출력
cut -d',' -f1,3 file                                 # CSV 파일에서 1,3번째 필드 추출
cut -c1-10 file                                      # 각 줄의 1-10번째 문자 추출
awk '{print $1}' file                                # 첫 번째 필드 출력
awk -F',' '{print $2}' file                          # 쉼표 구분자로 두 번째 필드 출력
sed 's/old/new/g' file                               # 문자열 치환
sed -i 's/old/new/g' file                            # 파일 내용 직접 수정

# 파이프와 리다이렉션
command1 | command2                                  # 파이프로 명령 연결
command > file                                       # 출력을 파일로 리다이렉션
command >> file                                      # 출력을 파일에 추가
command < file                                       # 파일을 입력으로 사용
command 2> error.log                                 # 에러를 파일로 리다이렉션
command &> output.log                                # 출력과 에러를 모두 파일로
```

## 파일 권한 및 소유권

```shell
# 권한 확인 및 변경
ls -l file                                           # 파일 권한 확인
chmod 755 file                                       # 8진수로 권한 설정
chmod u+x file                                       # 소유자에게 실행 권한 추가
chmod g-w file                                       # 그룹에서 쓰기 권한 제거
chmod o=r file                                       # 기타 사용자에게 읽기 권한만 부여
chmod -R 755 directory                               # 디렉토리와 하위 파일 권한 재귀 변경

# 소유권 변경
chown user file                                      # 파일 소유자 변경
chown user:group file                                # 파일 소유자와 그룹 변경
chown -R user:group directory                        # 디렉토리와 하위 파일 소유권 재귀 변경
chgrp group file                                     # 파일 그룹 변경

# 특수 권한
chmod +t directory                                   # sticky bit 설정
chmod g+s file                                       # setgid 설정
chmod u+s file                                       # setuid 설정
```

## 프로세스 관리

```shell
# 프로세스 확인
ps                                                   # 현재 터미널의 프로세스 목록
ps aux                                               # 모든 프로세스 상세 정보
ps -ef                                               # 모든 프로세스 전체 형식
ps -u username                                       # 특정 사용자의 프로세스
pgrep process_name                                   # 프로세스 이름으로 PID 찾기
pidof process_name                                   # 프로세스 이름으로 PID 찾기
top                                                  # 실시간 프로세스 모니터링
htop                                                 # 향상된 프로세스 모니터링
jobs                                                 # 백그라운드 작업 목록

# 프로세스 제어
kill PID                                             # 프로세스 종료 (SIGTERM)
kill -9 PID                                          # 프로세스 강제 종료 (SIGKILL)
kill -HUP PID                                        # 프로세스에 HUP 시그널 전송
killall process_name                                 # 이름으로 프로세스 종료
pkill process_name                                   # 이름으로 프로세스 종료
nohup command &                                      # 터미널 종료 후에도 실행 유지
command &                                            # 백그라운드에서 명령 실행
fg %1                                                # 백그라운드 작업을 포그라운드로
bg %1                                                # 중단된 작업을 백그라운드로
Ctrl+Z                                               # 현재 프로세스 일시 중단
Ctrl+C                                               # 현재 프로세스 종료
```

## 시스템 정보 및 모니터링

```shell
# 시스템 정보
uname -a                                             # 시스템 전체 정보
uname -r                                             # 커널 버전
hostname                                             # 호스트명 확인
whoami                                               # 현재 사용자명
id                                                   # 사용자 ID 및 그룹 정보
w                                                    # 로그인한 사용자 정보
who                                                  # 로그인한 사용자 목록
last                                                 # 최근 로그인 기록
uptime                                               # 시스템 가동 시간 및 부하
date                                                 # 현재 날짜와 시간
cal                                                  # 달력 출력

# 하드웨어 정보
lscpu                                                # CPU 정보
lsblk                                                # 블록 디바이스 정보
lsusb                                                # USB 디바이스 정보
lspci                                                # PCI 디바이스 정보
dmidecode                                            # 하드웨어 상세 정보
free -h                                              # 메모리 사용량 (읽기 쉬운 형식)
df -h                                                # 디스크 사용량 (읽기 쉬운 형식)
du -h directory                                      # 디렉토리 크기
du -sh *                                             # 현재 디렉토리 내 각 항목 크기

# 네트워크 정보
ifconfig                                             # 네트워크 인터페이스 정보
ip addr show                                         # IP 주소 정보
ip route show                                        # 라우팅 테이블
netstat -tuln                                        # 네트워크 연결 상태
ss -tuln                                             # 소켓 통계 (netstat 대체)
ping host                                            # 호스트 연결 테스트
traceroute host                                      # 네트워크 경로 추적
wget url                                             # 파일 다운로드
curl url                                             # HTTP 요청
```

## 압축 및 아카이브

```shell
# tar 아카이브
tar -cvf archive.tar files                           # tar 아카이브 생성
tar -xvf archive.tar                                 # tar 아카이브 추출
tar -tvf archive.tar                                 # tar 아카이브 내용 확인
tar -czvf archive.tar.gz files                       # gzip 압축과 함께 아카이브
tar -xzvf archive.tar.gz                             # gzip 압축 아카이브 추출
tar -cjvf archive.tar.bz2 files                      # bzip2 압축과 함께 아카이브
tar -xjvf archive.tar.bz2                            # bzip2 압축 아카이브 추출

# 압축
gzip file                                            # gzip 압축
gunzip file.gz                                       # gzip 압축 해제
zip archive.zip files                                # zip 압축
unzip archive.zip                                    # zip 압축 해제
```

## 환경 변수 및 셸 설정

```shell
# 환경 변수
env                                                  # 모든 환경 변수 출력
echo $PATH                                           # PATH 환경 변수 출력
export VAR=value                                     # 환경 변수 설정
unset VAR                                            # 환경 변수 제거
which command                                        # 명령어 위치 찾기
type command                                         # 명령어 타입 확인
whereis command                                      # 명령어 관련 파일 위치

# 셸 히스토리
history                                              # 명령어 히스토리
history | grep pattern                               # 히스토리에서 패턴 검색
!!                                                   # 마지막 명령어 재실행
!n                                                   # n번째 명령어 실행
!pattern                                             # 패턴으로 시작하는 마지막 명령어 실행

# 별칭
alias ll='ls -la'                                    # 별칭 설정
alias                                                # 모든 별칭 확인
unalias ll                                           # 별칭 제거
```

## 사용자 및 그룹 관리

```shell
# 사용자 관리
sudo useradd username                                # 사용자 추가
sudo userdel username                                # 사용자 삭제
sudo usermod -aG group username                      # 사용자를 그룹에 추가
passwd                                               # 비밀번호 변경
sudo passwd username                                 # 다른 사용자 비밀번호 변경
su username                                          # 사용자 전환
sudo command                                         # 관리자 권한으로 명령 실행

# 그룹 관리
groups                                               # 현재 사용자의 그룹 확인
groups username                                      # 특정 사용자의 그룹 확인
sudo groupadd groupname                              # 그룹 추가
sudo groupdel groupname                              # 그룹 삭제
```

## 시스템 서비스 관리 (systemd)

```shell
# 서비스 관리
sudo systemctl start service                         # 서비스 시작
sudo systemctl stop service                          # 서비스 중지
sudo systemctl restart service                       # 서비스 재시작
sudo systemctl reload service                        # 서비스 설정 다시 로드
sudo systemctl enable service                        # 부팅 시 자동 시작 설정
sudo systemctl disable service                       # 부팅 시 자동 시작 해제
systemctl status service                             # 서비스 상태 확인
systemctl is-active service                          # 서비스 활성 상태 확인
systemctl is-enabled service                         # 서비스 자동 시작 설정 확인
systemctl list-units --type=service                  # 모든 서비스 목록
journalctl -u service                                # 서비스 로그 확인
journalctl -f -u service                             # 서비스 로그 실시간 확인
```

## 패키지 관리

```shell
# Ubuntu/Debian (apt)
sudo apt update                                      # 패키지 목록 업데이트
sudo apt upgrade                                     # 패키지 업그레이드
sudo apt install package                             # 패키지 설치
sudo apt remove package                              # 패키지 제거
sudo apt purge package                               # 패키지와 설정 파일 완전 제거
sudo apt autoremove                                  # 불필요한 패키지 자동 제거
apt search package                                   # 패키지 검색
apt show package                                     # 패키지 정보 확인

# CentOS/RHEL (yum/dnf)
sudo yum update                                      # 패키지 업데이트
sudo yum install package                             # 패키지 설치
sudo yum remove package                              # 패키지 제거
yum search package                                   # 패키지 검색
yum info package                                     # 패키지 정보 확인
```

## 로그 관리

```shell
# 시스템 로그
sudo tail -f /var/log/syslog                         # 시스템 로그 실시간 확인
sudo tail -f /var/log/auth.log                       # 인증 로그 확인
sudo tail -f /var/log/kern.log                       # 커널 로그 확인
journalctl                                           # systemd 저널 확인
journalctl -f                                        # systemd 저널 실시간 확인
journalctl --since "1 hour ago"                      # 1시간 전부터 로그
journalctl --until "2023-01-01"                      # 특정 날짜까지 로그
dmesg                                                # 커널 메시지 확인
dmesg | tail                                         # 최근 커널 메시지
```

## 네트워크 도구

```shell
# 연결 테스트
ping -c 4 host                                       # 4번 ping 테스트
traceroute host                                      # 경로 추적
nslookup domain                                      # DNS 조회
dig domain                                           # DNS 상세 조회
host domain                                          # 간단한 DNS 조회

# 네트워크 연결
ssh user@host                                        # SSH 연결
scp file user@host:/path                             # SCP 파일 전송
rsync -av source/ destination/                       # rsync 동기화
wget -O file url                                     # 파일 다운로드
curl -o file url                                     # 파일 다운로드
```

## 유용한 단축키 및 팁

```shell
# 터미널 단축키
Ctrl+A                                               # 줄 시작으로 이동
Ctrl+E                                               # 줄 끝으로 이동
Ctrl+U                                               # 커서 앞 모든 텍스트 삭제
Ctrl+K                                               # 커서 뒤 모든 텍스트 삭제
Ctrl+W                                               # 커서 앞 단어 삭제
Ctrl+L                                               # 화면 지우기 (clear와 동일)
Ctrl+R                                               # 히스토리 검색
Tab                                                  # 자동 완성
Tab Tab                                              # 가능한 완성 목록 표시

# 유용한 조합
find /path -name "*.txt" -exec grep -l "pattern" {} \;  # 패턴을 포함한 파일 찾기
ps aux | grep process_name                           # 특정 프로세스 찾기
df -h | grep -v tmpfs                                # tmpfs 제외한 디스크 사용량
netstat -tuln | grep :80                             # 80번 포트 사용 확인
history | grep command                               # 히스토리에서 명령어 검색
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam.\_\.Ji](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
