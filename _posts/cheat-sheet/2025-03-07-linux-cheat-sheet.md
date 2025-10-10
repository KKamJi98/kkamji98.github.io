---
title: Linux Command Cheat Sheet
date: 2025-03-07 21:28:11 +0900
author: kkamji
categories: [System, Linux]
tags: [linux, bash, shell, devops, command-line, cli, cheat-sheet]     # TAG names should always be lowercase
comments: true
image:
  path: /assets/img/linux/linux.webp
---

Linux를 사용하며 알게된 CLI 명령어들을 공유합니다.

---

## 1. 파일 및 디렉토리 관리

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

---

## 2. 파일 내용 확인 및 편집

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

---

## 3. 텍스트 처리 및 검색

```shell
# 텍스트 검색 (grep)
grep "pattern" file                                  # 파일에서 패턴 검색
grep -i "pattern" file                               # 대소문자 구분 없이 검색
grep -r "pattern" directory                          # 디렉토리 내 재귀 검색
grep -n "pattern" file                               # 줄 번호와 함께 검색
grep -v "pattern" file                               # 패턴과 일치하지 않는 줄 출력
grep -c "pattern" file                               # 패턴 매칭 줄 수 카운트
grep -E "pattern1|pattern2" file                     # 확장 정규식 사용
grep -o "pattern" file                               # 매칭되는 부분만 출력
grep -A 3 -B 2 "pattern" file                        # 매칭된 줄의 앞 2줄, 뒤 3줄 함께 출력

# 텍스트 처리 (sort, uniq, cut)
sort file                                            # 파일 내용 정렬
sort -r file                                         # 역순 정렬
sort -n file                                         # 숫자 기준 정렬
sort -k 2 file                                       # 두 번째 필드 기준 정렬
uniq file                                            # 중복 줄 제거 (정렬된 상태여야 함)
uniq -c file                                         # 중복 줄 개수와 함께 출력
cut -d',' -f1,3 file                                 # CSV 파일에서 1,3번째 필드 추출
cut -c1-10 file                                      # 각 줄의 1-10번째 문자 추출

# 텍스트 처리 (awk, sed)
awk '{print $1}' file                                # 첫 번째 필드 출력
awk -F',' '{print $2}' file                          # 쉼표 구분자로 두 번째 필드 출력
awk '/pattern/ {print $3}' file                      # 패턴이 있는 줄의 세 번째 필드 출력
sed 's/old/new/g' file                               # 문자열 치환
sed -i 's/old/new/g' file                            # 파일 내용 직접 수정
sed '1,5d' file                                      # 1-5번째 줄 삭제

# 파이프와 리다이렉션
command1 | command2                                  # 파이프로 명령 연결
command > file                                       # 출력을 파일로 리다이렉션 (덮어쓰기)
command >> file                                      # 출력을 파일에 추가
command < file                                       # 파일을 입력으로 사용
command 2> error.log                                 # 에러를 파일로 리다이렉션
command &> output.log                                # 출력과 에러를 모두 파일로

# 고급 예제
find . -name "*.log" -type f -print0 | xargs -0 grep "ERROR" # .log 파일에서 "ERROR" 문자열 검색
awk -F':' '{print $1, $3}' /etc/passwd | sort -k2 -n  # /etc/passwd에서 사용자명과 UID를 UID 순으로 정렬
grep -r "FAIL" /var/log/ | awk -F: '{print $1}' | sort | uniq -c | sort -nr # 로그에서 "FAIL"이 많은 파일 순으로 정렬
```

---

## 4. 파일 권한 및 소유권

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

---

## 5. 프로세스 관리

```shell
# 프로세스 확인
ps                                                   # 현재 터미널의 프로세스 목록
ps aux                                               # 모든 프로세스 상세 정보 (BSD 형식)
ps -ef                                               # 모든 프로세스 상세 정보 (System V 형식)
ps -u username                                       # 특정 사용자의 프로세스
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head      # 메모리 사용량 상위 프로세스 확인
pgrep process_name                                   # 프로세스 이름으로 PID 찾기
pidof process_name                                   # 프로세스 이름으로 PID 찾기
top                                                  # 실시간 프로세스 모니터링 (Shift+M: 메모리, Shift+P: CPU)
htop                                                 # 향상된 프로세스 모니터링 (F4: 필터, F5: 트리, F9: 종료)
jobs                                                 # 백그라운드 작업 목록

# 프로세스 제어
kill PID                                             # 프로세스에 종료 시그널(SIGTERM, 15) 전송
kill -9 PID                                          # 프로세스 강제 종료 (SIGKILL, 9)
kill -l                                              # 사용 가능한 모든 시그널 목록 확인
kill -HUP PID                                        # 프로세스에 재시작/설정 리로드 시그널(SIGHUP, 1) 전송
killall process_name                                 # 이름으로 프로세스 종료
pkill -f "process_pattern"                           # 패턴으로 프로세스 종료
nohup command &                                      # 터미널 종료 후에도 실행 유지
command &                                            # 백그라운드에서 명령 실행
fg %1                                                # 백그라운드 작업을 포그라운드로
bg %1                                                # 중단된 작업을 백그라운드로
Ctrl+Z                                               # 현재 프로세스 일시 중단
Ctrl+C                                               # 현재 프로세스 종료 (SIGINT)
```

---

## 6. 시스템 정보 및 모니터링

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
```

---

## 7. 압축 및 아카이브

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

---

## 8. 환경 변수 및 셸 설정

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

---

## 9. 사용자 및 그룹 관리

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

---

## 10. 시스템 서비스 관리 (systemd)

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

---

## 11. 패키지 관리

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

---

## 12. 로그 관리

```shell
# 시스템 로그
sudo tail -f /var/log/syslog                         # 시스템 로그 실시간 확인 (Debian 계열)
sudo tail -f /var/log/messages                       # 시스템 로그 실시간 확인 (RHEL 계열)
sudo tail -f /var/log/auth.log                       # 인증 로그 확인 (Debian 계열)
sudo tail -f /var/log/secure                         # 인증 로그 확인 (RHEL 계열)
sudo tail -f /var/log/kern.log                       # 커널 로그 확인
journalctl                                           # systemd 저널 확인
journalctl -f                                        # systemd 저널 실시간 확인
journalctl --since "1 hour ago"                      # 1시간 전부터 로그
journalctl --until "2025-10-11"                      # 특정 날짜까지 로그
dmesg                                                # 커널 메시지 확인
dmesg | tail                                         # 최근 커널 메시지
```

---

## 13. 네트워크

### 13.1. 로컬 네트워크 설정

```shell
# 로컬 네트워크 설정 확인
ip addr show                                         # IP 주소, MAC 주소, 인터페이스 상태 확인
ip -c addr show                                      # 컬러로 보기
ip -br link                                          # 인터페이스 목록 간략히 보기 (UP/DOWN, IP)
ip route show                                        # 라우팅 테이블 확인
ip -c route                                          # 라우팅 테이블 컬러로 확인
ifconfig                                             # (구 버전) 네트워크 인터페이스 정보
```

### 13.2. 연결 및 경로 추적

```shell
# 기본 연결 및 경로 추적 (ping, mtr, traceroute)
ping -c 4 google.com                                 # 4번의 ICMP 요청으로 기본 연결 확인
traceroute google.com                                # 대상까지의 네트워크 경로 추적 (UDP 기본)

# mtr (My Traceroute) - ping과 traceroute를 결합한 강력한 도구
sudo mtr 1.1.1.1                                     # 실시간 인터랙티브 모드로 경로 추적
sudo mtr -n 8.8.8.8                                  # DNS 조회 없이 IP 주소로만 표시
sudo mtr -rwzc 100 1.1.1.1                            # 100회 실행 후 리포트 출력 (자동화용)
sudo mtr -rwzc 100 -T -P 443 example.com             # TCP 443 포트로 경로 추적 (방화벽 통과 시 유용)
sudo mtr -rwzc 100 -u -P 53 1.1.1.1                  # UDP 53 포트로 경로 추적 (DNS 쿼리 경로)
sudo mtr -rwzc 50 -s 1472 1.1.1.1                    # 패킷 크기 설정 (MTU 문제 확인)
sudo mtr -rwzc 100 -I eth1 -a 192.168.10.101 8.8.8.8  # 특정 인터페이스와 소스 IP 지정
sudo mtr -rwzc 200 -T -P 443 example.com > mtr_443.txt # 결과를 파일로 저장
```

### 13.3. 포트 및 서비스 확인

```shell
# 포트 및 서비스 확인 (ss, netstat)
ss -tnlp                                             # TCP 리스닝 소켓과 사용하는 프로세스 확인
ss -unlp                                             # UDP 리스닝 소켓과 사용하는 프로세스 확인
ss -tuna                                             # 모든 TCP/UDP 소켓 상태 확인
netstat -tnlp                                        # (구 버전) ss와 유사한 기능
```

### 13.4. DNS 조회

```shell
# DNS 조회 (dig, nslookup, host)
nslookup google.com                                  # 도메인의 IP 주소 확인
dig google.com +short                                # 간단한 A 레코드 조회
dig google.com MX                                    # 메일 서버(MX) 레코드 조회
host google.com                                      # 간단한 DNS 정보 조회
```

### 13.5. 패킷 캡처 및 분석

```shell
# tcpdump - 강력하고 유연한 저수준 패킷 캡처 도구
# 기본 사용법
sudo tcpdump -i any                                  # 모든 인터페이스의 트래픽 캡처
sudo tcpdump -i eth0 -nn                             # eth0 인터페이스, 호스트명/포트번호 해석 없이(-nn)
sudo tcpdump -i eth0 -w capture.pcap                 # 캡처 결과를 파일로 저장
sudo tcpdump -r capture.pcap                         # 저장된 파일 읽기
# 필터링 (BPF - Berkeley Packet Filter)
sudo tcpdump -i eth0 host 1.2.3.4                    # 특정 호스트(IP)와 관련된 트래픽
sudo tcpdump -i eth0 src 1.2.3.4                     # 소스 IP가 1.2.3.4인 트래픽
sudo tcpdump -i eth0 dst 1.2.3.4                     # 목적지 IP가 1.2.3.4인 트래픽
sudo tcpdump -i eth0 port 443                        # 443 포트를 사용하는 트래픽
sudo tcpdump -i eth0 tcp portrange 22-80             # 22-80번 TCP 포트 범위의 트래픽
sudo tcpdump -i eth0 'tcp[tcpflags] & (tcp-syn|tcp-fin) != 0' # TCP SYN 또는 FIN 플래그가 있는 패킷
sudo tcpdump -i eth0 'icmp[icmptype] = icmp-echo or icmp[icmptype] = icmp-echoreply' # Ping 요청/응답
# 출력 제어 및 고급 기능
sudo tcpdump -i eth0 -s 0 -A 'port 80'               # HTTP(80) 트래픽의 전체 패킷(-s 0)을 ASCII로(-A) 보기
sudo tcpdump -i eth0 -C 10M -W 5 -w capture.pcap     # 10MB 단위로 파일을 5개까지 로테이션하며 저장
sudo tcpdump -i eth1 -nn 'udp port 8472'             # VXLAN 캡슐화 트래픽 확인
sudo tcpdump -i cilium_vxlan -nn icmp                # 가상 터널 인터페이스 내부의 ICMP 패킷 확인

# termshark - 터미널용 Wireshark (TUI), 직관적인 분석 환경 제공
# 기본 사용법
sudo termshark -i eth1                               # 실시간으로 eth1 인터페이스 캡처 및 분석
sudo termshark -i eth1 'tcp port 80'                 # BPF 필터로 HTTP 트래픽만 실시간 분석
termshark -r /tmp/cap.pcap                           # 저장된 pcap 파일 열기
# 필터링 (Wireshark 디스플레이 필터)
termshark -r /tmp/cap.pcap -Y 'http.request'         # 저장된 파일에 디스플레이 필터(-Y) 적용
termshark -r /tmp/cap.pcap -Y 'dns.qry.name == "google.com"' # 특정 DNS 쿼리 필터링
termshark -r /tmp/cap.pcap 'icmp or tcp port 443'    # BPF 필터를 적용하여 파일 열기
# termshark 내에서 'z' -> 'Follow TCP/UDP/TLS Stream' 과 같은 Wireshark 핵심 기능 사용 가능
# 파이프(|)를 눌러 디스플레이 필터 실시간 변경, Tab으로 패널 이동 등 다양한 인터랙션 제공
```

### 13.6. 원격 연결 및 파일 전송

```shell
# 원격 연결 및 파일 전송 (ssh, scp, rsync, wget, curl)
ssh user@host                                        # SSH 원격 접속
scp file user@host:/path                             # SCP로 안전하게 파일 전송
rsync -avz --progress source/ destination/           # 효율적인 파일 동기화 (압축, 진행상황 표시)
wget -c https://example.com/large-file.zip           # 이어받기 기능으로 대용량 파일 다운로드
curl -L http://example.com                           # 리다이렉션을 따라가며 HTTP 요청
curl -s -o /dev/null -w "%{http_code}" http://example.com # HTTP 상태 코드만 확인
```

---

## 14. 유용한 단축키 및 팁

```shell
# 터미널 단축키 (커서 이동)
Ctrl+A                                               # 줄 시작으로 이동
Ctrl+E                                               # 줄 끝으로 이동
Ctrl+F / Right Arrow                                 # 커서 한 글자 앞으로 이동
Ctrl+B / Left Arrow                                  # 커서 한 글자 뒤로 이동
Alt+F  / Ctrl+Right Arrow                            # 커서 한 단어 앞으로 이동
Alt+B  / Ctrl+Left Arrow                             # 커서 한 단어 뒤로 이동

# 터미널 단축키 (텍스트 편집)
Ctrl+U                                               # 커서 앞 모든 텍스트 삭제
Ctrl+K                                               # 커서 뒤의 모든 입력 삭제 (줄 끝까지)
Ctrl+W                                               # 커서 앞 단어 삭제
Ctrl+Y                                               # 삭제한 내용 붙여넣기 (Yank)
Ctrl+L                                               # 화면 지우기 (clear와 동일)
Ctrl+R                                               # 히스토리 검색 (Reverse Search)
Ctrl+_                                               # 마지막 작업 실행 취소 (Undo)

# 터미널 단축키 (자동 완성)
Tab                                                  # 자동 완성
Tab Tab                                              # 가능한 완성 목록 표시
```

---

> **궁금하신 점이나 추가해야 할 부분은 댓글이나 아래의 링크를 통해 문의해주세요.**  
> **Written with [KKam._.Ji](https://www.linkedin.com/in/taejikim/)**  
{: .prompt-info}
