# HTB Cap — Notes
**Date:** 2026-05-31  
**Difficulty:** Easy (Linux)  
**Target IP:** 10.129.12.255  
**My IP (tun0):** 10.10.14.135  

---

## Open Ports & Services
- 21/tcp — vsftpd 3.0.3 (anon login blocked)
- 22/tcp — OpenSSH 8.2p1 Ubuntu
- 80/tcp — Gunicorn "Security Dashboard"

## Enumeration Findings
- Web app at /capture generates 5s PCAP, saves to /data/<id>, download at /download/<id>
- IDOR: /data/0 accessible — pre-existing capture from box setup
- Username "nathan" visible in web app nav
- capture0.pcap contains plaintext FTP session: USER nathan / PASS Buck3tH4TF0RM3!
- Password reused on SSH — direct shell as nathan

## Exploit Path
1. Browse to /capture → redirects to /data/1
2. Fuzz to /data/0 (IDOR) → download /download/0
3. tcpdump -r capture0.pcap → FTP creds in plaintext
4. ssh nathan@10.129.12.255 with recovered password

## Privilege Escalation
- getcap -r / reveals: /usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
- cap_setuid allows calling setuid(0) to become root without sudo
- One-liner: python3 -c "import os; os.setuid(0); os.system('/bin/bash')"
- Instant root shell

## Flags
- user.txt: ea34748abba367e85ac0aec4f9932bad
- root.txt: 3a0175a10c1007605d6b3813fb2cb37b

## Lessons Learned
- IDOR on sequential IDs is always worth testing — /data/0 is the obvious first check
- FTP sends credentials unencrypted — any PCAP capturing that session = game over
- Linux capabilities (getcap) are a common privesc vector — always run after no sudo
- cap_setuid on any interpreter (python, perl, ruby) = instant root

## Tools Used
- nmap
- curl
- ftp
- tcpdump
- ssh
- getcap / python3 (privesc)
