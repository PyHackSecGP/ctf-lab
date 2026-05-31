#!/usr/bin/env python3
"""
htb_complete.py — Post-root automation for GP Singh
Usage: python3 htb_complete.py --machine <name> [--platform htb|thm]
                                [--user-flag <flag>] [--root-flag <flag>]
                                [--no-push]

Updates notes with flags, calls report_gen, moves to completed/, commits + pushes.
"""

import argparse
import subprocess
import sys
import re
from datetime import datetime
from pathlib import Path


CTF_BASE = Path.home() / "ctf"
TOOLS_DIR = CTF_BASE / "tools"


def find_machine_dir(machine: str, platform: str) -> Path:
    """Find machine dir in active/ or completed/."""
    for state in ["active", "completed"]:
        path = CTF_BASE / platform / state / machine
        if path.exists():
            return path
    print(f"[ERROR] Machine dir not found: {platform}/active/{machine}")
    print(f"  Create it first with: python3 htb_start.py --machine {machine} --ip <IP>")
    sys.exit(1)


def update_flags(notes_path: Path, user_flag: str | None, root_flag: str | None) -> None:
    """Write flags into notes.md if provided."""
    if not (user_flag or root_flag):
        return

    content = notes_path.read_text()

    if user_flag:
        content = re.sub(r"(- user\.txt:).*", f"\\1 {user_flag}", content)
        print(f"[+] User flag written to notes")

    if root_flag:
        content = re.sub(r"(- root\.txt:).*", f"\\1 {root_flag}", content)
        print(f"[+] Root flag written to notes")

    notes_path.write_text(content)


def run_report_gen(machine: str, platform: str, no_push: bool) -> None:
    """Call report_gen.py to generate writeup, move to completed, commit."""
    cmd = [
        "python3", str(TOOLS_DIR / "report_gen.py"),
        "--machine", machine,
        "--platform", platform,
        "--complete",
    ]
    if no_push:
        cmd.append("--no-push")

    print("[*] Running report_gen.py...")
    result = subprocess.run(cmd, cwd=str(CTF_BASE))
    if result.returncode != 0:
        print("[!] report_gen.py failed — check output above")
        print(f"    You can retry: python3 {TOOLS_DIR}/report_gen.py --machine {machine} --platform {platform} --complete")
        sys.exit(1)


def check_claw_core_reachable() -> bool:
    """Quick ping check on Ollama port."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "3",
             "http://100.126.22.55:11434/api/tags"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def print_publish_checklist(machine: str, platform: str) -> None:
    """Print post-root publishing steps."""
    date = datetime.now().strftime("%Y-%m-%d")
    writeup_path = CTF_BASE / "writeups" / "drafts" / f"{date}-{platform}-{machine}.md"
    linkedin_path = CTF_BASE / "writeups" / "drafts" / f"{date}-{platform}-{machine}-linkedin.txt"

    print(f"""
╔══════════════════════════════════════════════╗
║  {machine.upper()} ROOTED — POST-ROOT CHECKLIST
╚══════════════════════════════════════════════╝

1. Review writeup draft:
   cat {writeup_path}

2. Polish + publish to Medium:
   - Add screenshots if you have them
   - Cross-link to GitHub repo

3. Post LinkedIn:
   cat {linkedin_path}

4. GitHub: already pushed (check above)

5. Update HTB profile + add to your portfolio

REMEMBER: 1 machine daily. Keep the streak.
""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-root automation for HTB/THM")
    parser.add_argument("--machine", required=True, help="Machine name")
    parser.add_argument("--platform", default="htb", choices=["htb", "thm"])
    parser.add_argument("--user-flag", help="User flag hash")
    parser.add_argument("--root-flag", help="Root flag hash")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    args = parser.parse_args()

    machine = args.machine.lower()
    platform = args.platform

    print(f"[*] Completing {machine.upper()} ({platform.upper()})")

    machine_dir = find_machine_dir(machine, platform)
    notes_path = machine_dir / "notes.md"

    if not notes_path.exists():
        print(f"[ERROR] notes.md not found at {notes_path}")
        sys.exit(1)

    # Write flags to notes
    update_flags(notes_path, args.user_flag, args.root_flag)

    # Check claw-core reachable before starting long LLM call
    print("[*] Checking claw-core reachability...")
    if not check_claw_core_reachable():
        print("[!] claw-core not reachable at 100.126.22.55:11434")
        print("    Is Tailscale connected? Is Ollama running on claw-core?")
        print("    Skipping writeup generation — run report_gen.py manually later:")
        print(f"    python3 {TOOLS_DIR}/report_gen.py --machine {machine} --platform {platform} --complete")

        # Still move to completed and commit
        completed_dir = CTF_BASE / platform / "completed" / machine
        completed_dir.parent.mkdir(parents=True, exist_ok=True)
        if "active" in str(machine_dir):
            machine_dir.rename(completed_dir)
            print(f"[+] Moved to completed: {completed_dir}")

        subprocess.run(["git", "-C", str(CTF_BASE), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(CTF_BASE), "commit",
             "-m", f"complete: {platform}/{machine} — rooted"],
            check=True
        )
        if not args.no_push:
            subprocess.run(["git", "-C", str(CTF_BASE), "push"], check=True)
        return

    print("[+] claw-core reachable")

    # Generate writeup via report_gen
    run_report_gen(machine, platform, args.no_push)

    print_publish_checklist(machine, platform)


if __name__ == "__main__":
    main()
