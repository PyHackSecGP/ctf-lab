#!/usr/bin/env python3
"""
htb_start.py — HTB/THM machine setup automation for GP Singh
Usage: python3 htb_start.py --machine <name> --ip <ip> [--platform htb|thm] [--difficulty easy|medium|hard]

Creates folder structure, notes template, runs nmap, commits scaffold to git.
"""

import argparse
import subprocess
import sys
import re
from datetime import datetime
from pathlib import Path


CTF_BASE = Path.home() / "ctf"
MY_IP = "10.10.14.135"  # tun0 — update if it changes


NOTES_TEMPLATE = """# {platform_upper} {machine_title} — Notes
**Date:** {date}
**Difficulty:** {difficulty}
**Target IP:** {target_ip}
**My IP (tun0):** {my_ip}

---

## Open Ports & Services
<!-- filled during recon -->

## Enumeration Findings
<!-- web dirs, users, files, credentials -->

## Exploit Path
<!-- what worked and why -->

## Privilege Escalation
<!-- method, binary, capability, cron, etc -->

## Flags
- user.txt:
- root.txt:

## Lessons Learned
<!-- key takeaways, techniques, CVEs -->

## Tools Used
- nmap
"""


def get_tun0_ip() -> str:
    """Get current tun0 IP."""
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", "tun0"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
    except Exception:
        pass
    return MY_IP


def run_nmap_allports(target_ip: str, output_file: Path) -> list[str]:
    """Run fast all-port scan. Returns list of open port numbers."""
    print(f"[*] Nmap all-ports scan (this takes ~30s)...")
    cmd = [
        "nmap", "-p-", "--min-rate", "5000", "-T4",
        target_ip, "-oN", str(output_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    open_ports = re.findall(r"(\d+)/tcp\s+open", result.stdout)
    if open_ports:
        print(f"[+] Open ports: {', '.join(open_ports)}")
    else:
        print("[!] No open ports found — check IP and VPN")

    output_file.write_text(result.stdout)
    return open_ports


def run_nmap_services(target_ip: str, ports: list[str], output_file: Path) -> str:
    """Run service/version scan on open ports. Returns raw output."""
    if not ports:
        return ""
    port_str = ",".join(ports)
    print(f"[*] Nmap service scan on ports {port_str}...")
    cmd = [
        "nmap", "-p", port_str, "-sV", "-sC",
        target_ip, "-oN", str(output_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    output_file.write_text(result.stdout)
    return result.stdout


def parse_services(nmap_output: str) -> list[str]:
    """Extract service lines from nmap output for notes."""
    lines = []
    for line in nmap_output.splitlines():
        if re.match(r"^\d+/tcp", line.strip()):
            lines.append(f"- {line.strip()}")
    return lines


def create_machine(machine: str, target_ip: str, platform: str, difficulty: str) -> None:
    """Full machine setup: dirs, notes, nmap, git commit."""
    machine_dir = CTF_BASE / platform / "active" / machine
    machine_dir.mkdir(parents=True, exist_ok=True)

    my_ip = get_tun0_ip()
    print(f"[*] Your tun0 IP: {my_ip}")

    # Write notes template
    notes_path = machine_dir / "notes.md"
    if notes_path.exists():
        print(f"[!] notes.md already exists — skipping template creation")
    else:
        notes_content = NOTES_TEMPLATE.format(
            platform_upper=platform.upper(),
            machine_title=machine.title(),
            date=datetime.now().strftime("%Y-%m-%d"),
            difficulty=difficulty.title(),
            target_ip=target_ip,
            my_ip=my_ip,
        )
        notes_path.write_text(notes_content)
        print(f"[+] Created: {notes_path}")

    # Nmap scans
    allports_file = machine_dir / "nmap_allports.txt"
    services_file = machine_dir / "nmap_services.txt"

    open_ports = run_nmap_allports(target_ip, allports_file)

    services_output = ""
    if open_ports:
        services_output = run_nmap_services(target_ip, open_ports, services_file)

    # Inject port findings into notes
    if services_output:
        service_lines = parse_services(services_output)
        if service_lines:
            old_section = "## Open Ports & Services\n<!-- filled during recon -->"
            new_section = "## Open Ports & Services\n" + "\n".join(service_lines)
            updated = notes_path.read_text().replace(old_section, new_section)
            notes_path.write_text(updated)
            print(f"[+] Port findings written to notes.md")

    # Git commit scaffold
    print("[*] Committing scaffold to git...")
    files_to_add = [str(machine_dir)]
    subprocess.run(["git", "-C", str(CTF_BASE), "add"] + files_to_add, check=True)
    subprocess.run(
        ["git", "-C", str(CTF_BASE), "commit",
         "-m", f"init: {platform}/{machine} — scaffold + nmap"],
        check=True
    )
    print("[+] Committed.")

    print(f"""
[+] MACHINE READY: {machine.upper()} ({platform.upper()})
  Target:   {target_ip}
  My IP:    {my_ip}
  Dir:      {machine_dir}
  Notes:    {notes_path}
  Allports: {allports_file}
  Services: {services_file}

[*] NEXT: Review nmap output, then start enumeration.
  cat {services_file}
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="HTB/THM machine setup automation")
    parser.add_argument("--machine", required=True, help="Machine name (e.g. cap, lame, blue)")
    parser.add_argument("--ip", required=True, help="Target IP address")
    parser.add_argument("--platform", default="htb", choices=["htb", "thm"])
    parser.add_argument("--difficulty", default="easy", choices=["easy", "medium", "hard", "insane"])
    args = parser.parse_args()

    # Validate IP
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", args.ip):
        print(f"[ERROR] Invalid IP: {args.ip}")
        sys.exit(1)

    create_machine(
        machine=args.machine.lower(),
        target_ip=args.ip,
        platform=args.platform,
        difficulty=args.difficulty,
    )


if __name__ == "__main__":
    main()
