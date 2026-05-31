#!/usr/bin/env python3
"""
report_gen.py — AI-powered CTF writeup generator for GP Singh
Usage: python3 report_gen.py --machine <name> --platform htb|thm
Reads notes.md from the machine folder, generates full writeup + LinkedIn post
"""

import argparse
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error


CTF_BASE = Path.home() / "ctf"
TOOLS_DIR = Path.home() / "tools"
CLAW_CORE = "100.126.22.55"
OLLAMA_URL = f"http://{CLAW_CORE}:11434/api/generate"
OLLAMA_MODEL = "hermes3:70b"
HERMES_LOG = CTF_BASE / "HERMES_LOG.md"


def read_shared_context() -> str:
    """Read HERMES_LOG.md to give Hermes project context."""
    if HERMES_LOG.exists():
        return HERMES_LOG.read_text()
    return ""


def append_hermes_log(entry: str) -> None:
    """Append a timestamped entry to HERMES_LOG.md under Hermes Work Log."""
    if not HERMES_LOG.exists():
        return
    content = HERMES_LOG.read_text()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"\n### {timestamp} — {entry}\n"
    insert_after = "## Hermes Work Log\n<!-- Hermes appends entries here after every generation task -->"
    content = content.replace(insert_after, insert_after + log_entry)
    HERMES_LOG.write_text(content)


def read_notes(machine_name: str, platform: str) -> str:
    """Read notes.md from the machine directory."""
    machine_dir = CTF_BASE / platform / "active" / machine_name
    completed_dir = CTF_BASE / platform / "completed" / machine_name

    notes_path = None
    for d in [machine_dir, completed_dir]:
        candidate = d / "notes.md"
        if candidate.exists():
            notes_path = candidate
            machine_dir = d
            break

    if not notes_path:
        print(f"[ERROR] No notes.md found for {machine_name}")
        print(f"  Checked: {machine_dir}/notes.md")
        print(f"  Checked: {completed_dir}/notes.md")
        sys.exit(1)

    return notes_path.read_text(), machine_dir


def call_ollama(prompt: str) -> str:
    """Call Ollama on claw-core via urllib."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"content-type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["response"]
    except urllib.error.URLError as e:
        print(f"[ERROR] Ollama call failed: {e}")
        print(f"  Is claw-core ({CLAW_CORE}) reachable via Tailscale?")
        sys.exit(1)


def generate_writeup(notes: str, machine_name: str, platform: str) -> str:
    """Generate a full technical writeup from notes."""
    shared_context = read_shared_context()
    prompt = f"""You are Hermes, the AI assistant for GP Singh's cybersecurity lab.

SHARED PROJECT CONTEXT:
{shared_context}

---
You are writing a cybersecurity CTF writeup for {machine_name} on {platform.upper()}.

Author: GP Singh (cybersecurity analyst building toward OSCP)
GitHub: PyHackSecGP

Here are the raw notes from the session:

---
{notes}
---

Generate a complete, professional writeup in Markdown with these sections:

# {machine_name} — {platform.upper()} Writeup

## Overview
Brief summary of the machine, difficulty, key techniques used.

## Reconnaissance
Document the initial scanning and discovery phase with exact commands and key findings.

## Enumeration
Detail the service enumeration, directory busting, credential hunting etc.

## Initial Foothold
Explain the vulnerability found and how it was exploited. Include exact commands.

## Privilege Escalation
Walk through the privesc path with commands and explanation of WHY it worked.

## Flags
- User flag: [redacted for published writeup]
- Root flag: [redacted for published writeup]

## Key Takeaways
3-5 bullet points of what was learned. Reference CVEs or techniques by name (e.g. CVE-XXXX, MITRE ATT&CK TXX.XXX).

## Tools Used
List all tools with one-line descriptions.

Write it so a junior analyst can follow along and LEARN, not just repeat steps.
Be technically precise. Explain the reasoning at each step.
"""
    return call_ollama(prompt)


def generate_linkedin_post(notes: str, machine_name: str, platform: str) -> str:
    """Generate a short LinkedIn post for the win."""
    shared_context = read_shared_context()
    prompt = f"""You are Hermes, GP Singh's lab AI. Project context:
{shared_context[:500]}

Write a LinkedIn post for GP Singh who just rooted {machine_name} on {platform.upper()}.

Raw notes:
{notes[:1000]}

Guidelines:
- 150-200 words max
- Open with the win, not "I'm excited to share"
- Mention 1-2 specific techniques used (real ones from the notes)
- Connect it to real-world security relevance
- End with a call to action (link to full writeup on GitHub/Medium)
- Hashtags at end: #cybersecurity #ethicalhacking #{platform} #infosec #pentesting
- Tone: confident, technical, not cringe
- No generic phrases like "hard work pays off"

Just write the post text, nothing else.
"""
    return call_ollama(prompt)


def generate_medium_intro(writeup: str, machine_name: str) -> str:
    """Generate Medium-ready intro paragraph."""
    prompt = f"""Write a 2-paragraph Medium article introduction for this CTF writeup about {machine_name}.

Writeup content:
{writeup[:500]}

Make it engaging for a security audience. First paragraph: hook with what makes this machine interesting.
Second paragraph: what the reader will learn. No fluff. Under 100 words total.
"""
    return call_ollama(prompt)


def move_to_completed(machine_dir: Path, platform: str, machine_name: str) -> Path:
    """Move machine folder from active to completed."""
    completed = CTF_BASE / platform / "completed" / machine_name
    completed.parent.mkdir(parents=True, exist_ok=True)
    if "active" in str(machine_dir):
        machine_dir.rename(completed)
        print(f"[+] Moved to completed: {completed}")
        return completed
    return machine_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-powered CTF writeup generator")
    parser.add_argument("--machine", required=True, help="Machine name (e.g. lame, blue)")
    parser.add_argument("--platform", default="htb", choices=["htb", "thm"], help="Platform")
    parser.add_argument("--complete", action="store_true", help="Move machine to completed/")
    parser.add_argument("--no-push", action="store_true", help="Skip git push")
    args = parser.parse_args()

    machine = args.machine.lower()
    platform = args.platform

    print(f"[*] Generating writeup for {machine} ({platform.upper()})")
    print(f"[*] Using Ollama on claw-core ({CLAW_CORE}) — model: {OLLAMA_MODEL}")

    print("[*] Reading notes...")
    notes, machine_dir = read_notes(machine, platform)

    print("[*] Generating writeup (this takes ~60s on hermes3:70b)...")
    writeup = generate_writeup(notes, machine, platform)

    print("[*] Generating LinkedIn post...")
    linkedin = generate_linkedin_post(notes, machine, platform)

    print("[*] Generating Medium intro...")
    medium_intro = generate_medium_intro(writeup, machine)

    # Save everything
    timestamp = datetime.now().strftime("%Y-%m-%d")
    writeup_dir = CTF_BASE / "writeups" / "drafts"
    writeup_dir.mkdir(parents=True, exist_ok=True)

    writeup_path = writeup_dir / f"{timestamp}-{platform}-{machine}.md"
    linkedin_path = writeup_dir / f"{timestamp}-{platform}-{machine}-linkedin.txt"
    medium_path = writeup_dir / f"{timestamp}-{platform}-{machine}-medium-intro.txt"

    writeup_path.write_text(writeup)
    linkedin_path.write_text(linkedin)
    medium_path.write_text(f"MEDIUM INTRO:\n\n{medium_intro}\n\n---\nFULL WRITEUP BELOW:\n\n{writeup}")

    # Log Hermes work to shared context file
    append_hermes_log(
        f"Generated writeup + LinkedIn + Medium intro for {platform.upper()}/{machine}\n"
        f"  Files: {writeup_path.name}, {linkedin_path.name}, {medium_path.name}"
    )

    print(f"\n[+] DONE")
    print(f"  Writeup:   {writeup_path}")
    print(f"  LinkedIn:  {linkedin_path}")
    print(f"  Medium:    {medium_path}")

    if args.complete:
        machine_dir = move_to_completed(machine_dir, platform, machine)

    if not args.no_push:
        print("\n[*] Committing to GitHub...")
        subprocess.run(
            ["git", "-C", str(CTF_BASE), "add", "."],
            check=True
        )
        subprocess.run(
            ["git", "-C", str(CTF_BASE), "commit",
             "-m", f"writeup: {platform}/{machine} — {timestamp}"],
            check=True
        )
        subprocess.run(
            ["git", "-C", str(CTF_BASE), "push"],
            check=True
        )
        print("[+] Pushed to GitHub")

    print("\n[*] NEXT STEPS:")
    print(f"  1. Review writeup: cat {writeup_path}")
    print(f"  2. Post to Medium with the intro in {medium_path}")
    print(f"  3. Post to LinkedIn: {linkedin_path}")


if __name__ == "__main__":
    main()
