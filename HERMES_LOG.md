# Shared Context — GP Singh CTF Lab
> Read and written by both Claude (kali) and Hermes (claw-core).
> Every completed machine and generated artifact is logged here.

---

## Who I Am
- **Name:** GP Singh
- **Role:** Cybersecurity Analyst 1 → targeting Senior/Staff Security Engineer
- **Goal:** OSCP by 2028, 10 writeups by Nov 2026
- **Platform:** GitHub @ PyHackSecGP
- **HTB target:** 1 machine per day

## Lab Architecture
- **Mjolnir (100.71.84.2):** Kali hacking machine — Claude Code, all CTF work
- **Hermes (100.126.22.55):** LLM inference server — Ollama (hermes3:70b, qwen3.5, llama3.2:3b)
- **Network:** Tailscale private mesh

## CTF Directory Layout (kali)
```
/home/tony/ctf/
  htb/active/        — current machines
  htb/completed/     — rooted machines
  thm/active/
  thm/completed/
  writeups/drafts/   — generated writeups
  writeups/published/
  tools/             — htb_start.py, htb_complete.py, report_gen.py
```

## Machines Completed
| Date | Platform | Machine | Difficulty | Techniques |
|------|----------|---------|------------|-----------|
| 2026-05-31 | HTB | Cap | Easy | IDOR on PCAP endpoint, FTP plaintext creds, cap_setuid Python privesc |

## Active Machines
| Platform | Machine | Status |
|----------|---------|--------|
| — | — | — |

---

## Hermes Work Log
<!-- Hermes appends entries here after every generation task -->

### 2026-05-31 16:32 — Hermes online — bidirectional logging established with kali (100.71.84.2)

### 2026-05-31 — Session Init
Log file created. Hermes (hermes3:70b on claw-core) is online and authorized to write via SSH.

---

## Claude Session Notes
<!-- Claude appends key decisions and findings here -->

### 2026-05-31 — HTB Cap Session
- Rooted Cap (Easy Linux): IDOR + cap_setuid chain
- Built htb_start.py, htb_complete.py, report_gen.py (Ollama), htb-workflow skill
- SSH bidirectional: kali ↔ claw-core established
- Writeup draft: /home/tony/ctf/writeups/drafts/htb-cap.md
