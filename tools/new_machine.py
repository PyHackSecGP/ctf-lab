#!/usr/bin/env python3
"""
new_machine.py — Spin up a new CTF machine workspace
Usage: python3 ~/tools/new_machine.py --name <machine> --ip <ip> --platform htb|thm
Creates folder structure, notes template, and opens Claude Code
"""

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path


CTF_BASE = Path.home() / "ctf"

NOTES_TEMPLATE = """# {machine} — {platform} Notes
**IP:** {ip}
**Date:** {date}
**Difficulty:** [Easy/Medium/Hard]
**OS:** [Linux/Windows]

---

## Initial Recon
<!-- Run: sudo nmap -sC -sV -oA scans/initial {ip} -->

```
# paste nmap output here
```

**Open Ports:**
| Port | Service | Version |
|------|---------|---------|
|      |         |         |

---

## Enumeration

### Web (if applicable)
<!-- gobuster dir -u http://{ip} -w /usr/share/seclists/Discovery/Web-Content/common.txt -->

### Service-specific


---

## Foothold

**Vulnerability found:**
**CVE (if applicable):**
**Exploit used:**

```bash
# commands used
```

---

## Privilege Escalation

**Vector found:**
**Technique:**

```bash
# commands used
```

---

## Flags
- User: `[get from machine]`
- Root: `[get from machine]`

---

## Lessons Learned
1.
2.
3.

## Tools Used
-
"""


def create_machine(name: str, ip: str, platform: str) -> None:
    """Create machine directory with full structure."""
    machine_dir = CTF_BASE / platform / "active" / name
    scans_dir = machine_dir / "scans"
    loot_dir = machine_dir / "loot"
    exploits_dir = machine_dir / "exploits"

    for d in [machine_dir, scans_dir, loot_dir, exploits_dir]:
        d.mkdir(parents=True, exist_ok=True)

    notes_path = machine_dir / "notes.md"
    notes_path.write_text(NOTES_TEMPLATE.format(
        machine=name.title(),
        platform=platform.upper(),
        ip=ip,
        date=datetime.now().strftime("%Y-%m-%d")
    ))

    print(f"[+] Machine workspace created: {machine_dir}")
    print(f"[+] Notes template: {notes_path}")
    print(f"\n[*] Directory structure:")
    print(f"    {machine_dir}/")
    print(f"    ├── notes.md     ← your working notes")
    print(f"    ├── scans/       ← nmap, gobuster output")
    print(f"    ├── loot/        ← creds, hashes, files")
    print(f"    └── exploits/    ← custom scripts")

    # Quick recon commands printed
    print(f"\n[*] FIRST COMMANDS TO RUN:")
    print(f"    sudo nmap -sC -sV -oA {scans_dir}/initial {ip}")
    print(f"    sudo nmap -p- --min-rate 5000 -oA {scans_dir}/allports {ip}")

    # Auto-start claude in the machine dir
    print(f"\n[*] Starting Claude Code in machine directory...")
    print(f"    cd {machine_dir} && claude")
    print(f"\n    Tell Claude: 'Starting {name.title()} on {platform.upper()}, IP is {ip}. Help me work through this methodically.'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create new CTF machine workspace")
    parser.add_argument("--name", required=True, help="Machine name (e.g. lame)")
    parser.add_argument("--ip", required=True, help="Target IP address")
    parser.add_argument("--platform", default="htb", choices=["htb", "thm"])
    args = parser.parse_args()

    create_machine(args.name.lower(), args.ip, args.platform)


if __name__ == "__main__":
    main()
