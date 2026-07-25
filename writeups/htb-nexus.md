# HTB: Nexus — Easy Linux

**Platform:** Hack The Box
**Difficulty:** Easy
**Category:** Web Exploitation / Linux Privilege Escalation
**Date completed:** July 2026

## Why I picked this one

I'm doing weekend HTB boxes alongside my weekday PortSwigger/Juice Shop rotation
as part of a 12-week AppSec lab plan, and I wanted something that would exercise
the same muscles I use during the week at my day job doing Bugcrowd triage —
reading an application's attack surface the way an attacker would, not just
running a scanner and calling it done. Nexus turned out to be a perfect fit:
nothing about it required exotic exploit dev, but every step required actually
paying attention.

## My process

**Recon.** Standard full port sweep first, which turned up just two open
ports — SSH and HTTP. The HTTP port redirected to a domain name I hadn't seen
before, so the first real step was adding it to my hosts file and looking at
what was actually being served. A quick vhost fuzz (ffuf, filtering out the
default response size) turned up two more subdomains that weren't linked
anywhere from the main site — one running a self-hosted git server, one
running an internal-looking business application. Neither of those would have
shown up if I'd stopped at "what does the homepage link to."

**The git server was the real way in.** It had public repository browsing
enabled, and one repo turned out to be infrastructure-as-code for standing up
the business app via Docker. The current `.env` file in that repo had its
sensitive value blanked — but I checked the commit history out of habit
(`git log -p`), and an earlier commit had the real value still sitting there.
This is the single most reusable lesson from the whole box for me: **removing
a secret in a new commit does not remove it from the repository.** The
history is still fully readable by anyone who can clone it. If a secret ever
touches a commit, the only real fix is rotating it — rewriting history is a
band-aid at best.

**Credential reuse got me into the CMS.** That leaked password worked
directly against the admin login of the business application once I paired
it with an email address I found from a completely different piece of public
recon (a careers/job posting page had listed a hiring manager's email — a
nice reminder that OSINT on a target isn't just technical infrastructure, it's
also just reading the website like a human would).

**The CMS itself was running a version affected by a recently disclosed,
authenticated RCE.** The vulnerability lived in a file-upload feature (an
email composer that let you attach files) — the frontend only checked file
extensions, so the fix was: rename the payload to an allowed extension,
upload it, and use Burp Suite to intercept the request in-flight and rename
it back to an executable extension before forwarding. This is a pattern
I've now seen in more than one context, both in labs and in real submissions
I've triaged — client-side extension validation is essentially decorative if
you can touch the raw request.

**On the box, a second leaked credential got me further.** The CMS's own
config file (readable once I had code execution as the web server user) had
a *different* password than the one I'd found in the git server — a proper
one for the actual application database. That password, tried against SSH,
logged me straight into a real user account. Two separate instances of
credential reuse in one chain, which really drove home how much a single
compromised secret can cascade if password policies (or just habits) don't
enforce uniqueness per service.

**Privilege escalation was the most interesting part technically.** Enumerating
scheduled jobs turned up a systemd timer running a Python script as root every
minute or so. The script's job was mundane — sync files from specially-flagged
"template" git repositories into a staging directory — but the way it built
destination paths was the bug: it took the file path exactly as reported by
`git ls-tree` and joined it onto the staging directory with no validation that
the result stayed inside that directory. Normally, Git's own CLI refuses to let
you create a tracked file with `../` in its path — but that protection lives in
the porcelain commands, not in the raw object format. By constructing the tree
and blob objects directly (writing the compressed, hashed objects straight into
`.git/objects` and pointing a branch ref at the resulting commit), I could
create a "file" whose path was a traversal sequence, which Git happily
accepted since I bypassed the CLI checks entirely. The sync script then joined
that untrusted, traversal-laden path onto its staging directory and wrote
straight through to a sensitive location outside of it — running as root, that
turned into an arbitrary file write with root privileges, which was enough to
plant a way back in as root.

## What I actually learned (the reusable part)

- **Grep git history, not just the working tree, when hunting for secrets.**
  `git log -p | grep -i` on cloned repos is now a permanent part of my recon
  checklist, not an afterthought.
- **Password reuse compounds.** One leaked credential rarely stays contained
  to the service it was found for — always try it broadly (SSH, admin panels,
  git hosting, anything).
- **`os.path.join()` / path-joining functions in general do not sanitize `..`
  sequences.** If any component of a joined path can be influenced by
  something outside your direct control — even something that feels "trusted"
  like an internal git repo — the resulting path needs to be canonicalized
  and verified to still be inside the intended directory before it's touched.
  I now specifically look for this pattern when reviewing file-handling code
  during triage, because it's an easy one to miss in a code review that's
  scanning for the "obvious" injection points.
- **Client-side upload validation is not validation.** Anything enforced only
  in the browser needs a server-side equivalent, full stop.

## Tools used

`nmap`, `ffuf`, `curl`, Burp Suite (proxy + repeater), `git`, a small custom
Python script to construct raw git objects, `ssh`, `nc`.
