# FreeIPA + Self-Service Password + LDAP Sync

---

## Table of Contents

1. [FreeIPA Server](#1-freeipa-server)
   - [Option A — Native Install (dnf)](#option-a--native-install-dnf)
   - [Option B — Docker Container](#option-b--docker-container)
2. [Self-Service Password Portal](#2-self-service-password-portal)
3. [LDAP Sync](#3-ldap-sync)

---

## 1. FreeIPA Server

FreeIPA is a full identity management stack — it bundles a **389 Directory Server** (LDAP), **MIT Kerberos**, and a **PKI/CA** into a single container. That's why `--privileged` is mandatory: it needs real kernel-level access that normal containers don't get.

---

### Option A — Native Install (dnf)

**Prerequisites:**

- Set the hostname before installing.

```bash
# Set the hostname
sudo hostnamectl set-hostname ipa.asteroidea.co

# Add hosts entry (replace IP with your VM's actual IP)
echo "20.0.1.176  ipa.asteroidea.co  ipa" | sudo tee -a /etc/hosts

# Verify
hostname -f        # must return ipa.asteroidea.co
ping -c1 ipa.asteroidea.co
```

**Install and run:**

```bash
sudo dnf install -y freeipa-server freeipa-server-dns

sudo ipa-server-install \
  --realm=ASTEROIDEA.CO \
  --domain=asteroidea.co \
  --hostname=ipa.asteroidea.co \
  --ds-password='<DS_PASSWORD>' \
  --admin-password='<ADMIN_PASSWORD>' \
  --unattended \
  --no-ntp \
  --skip-mem-check
```

- `--no-ntp` — skips the built-in Chrony setup. Keep the host clock accurate.
- `--skip-mem-check` — bypasses the RAM requirement check.

**Open firewall ports after install:**

FreeIPA's installer does not always add firewalld rules automatically. Add them explicitly:

```bash
sudo firewall-cmd --add-service=freeipa-ldap --permanent
sudo firewall-cmd --add-service=freeipa-ldaps --permanent
sudo firewall-cmd --add-service=https --permanent
sudo firewall-cmd --add-service=http --permanent
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-services
```

**Access the UI:**

Navigate to `https://ipa.asteroidea.co` from a browser. The client machine must also resolve the hostname — add the same hosts entry, or create a DNS host override in OPNsense under **Services → Unbound DNS → Host Overrides**.

---

### Option B — Docker Container (not stable)

```bash
sudo docker run -it \
  --name freeipa-server \
  --hostname ipa.asteroidea.com \
  --privileged \
  -v /opt/freeipa-data:/data \
  -p 80:80 \
  -p 443:443 \
  -p 389:389 \
  -p 636:636 \
  -p 88:88 \
  -p 464:464 \
  -p 88:88/udp \
  -p 464:464/udp \
  freeipa/freeipa-server:almalinux-10 \
  ipa-server-install \
    --realm=ASTEROIDEA.COM \
    --domain=asteroidea.com \
    --hostname=ipa.asteroidea.com \
    --ds-password='<DS_PASSWORD>' \
    --admin-password='<ADMIN_PASSWORD>' \
    --unattended \
    --no-ntp
```

- `--hostname ipa.asteroidea.com` — FreeIPA hardcodes this into every certificate and Kerberos principal it generates at install time. It must match what clients use to reach it, otherwise TLS and Kerberos break.
- `-v /opt/freeipa-data:/data` — persists the entire identity server (LDAP database, CA, Kerberos keys) across container restarts. Without this, everything is wiped on restart.
- `--no-ntp` — skips the built-in Chrony setup since the host manages time sync.
- Ports `88` and `464` (TCP + UDP) — Kerberos authentication and the `kpasswd` service. Both need TCP and UDP because Kerberos uses UDP for small packets and falls back to TCP for larger ones.

---

## 2. Self-Service Password Portal

SSP allows users to reset their FreeIPA password via a web interface without admin intervention. It talks to FreeIPA over LDAP and sends reset tokens by email through a Postfix relay.

### docker-compose.yml

```yaml
version: "3.8"
services:
  self-service-password:
    image: ltbproject/self-service-password
    container_name: self-service-password
    ports:
      - "8081:80"
    volumes:
      - ./config.inc.local.php:/var/www/conf/config.inc.local.php:ro
    restart: unless-stopped


```

### config.inc.local.php

```php
<?php
# ── LDAP / FreeIPA ────────────────────────────────────────────────────────────
$ldap_url    = "ldap://20.0.0.42:389";
$ldap_binddn = "uid=admin,cn=users,cn=accounts,dc=asteroidea,dc=co";
$ldap_bindpw = 'Asteroidea4711$%!';
$ldap_base   = "cn=users,cn=accounts,dc=asteroidea,dc=co";
# ── Security ──────────────────────────────────────────────────────────────────
$keyphrase  = "uG/dWCYb8GVW9x9K4VrdHRP3vTD4S3DBzbllUTa0i3I=";
$use_tokens = true;
# ── Mail ──────────────────────────────────────────────────────────────────────
$mail_from           = "XXXXXXX@gmail.com";
$mail_protocol       = "smtp";
$mail_smtp_host      = "smtp.gmail.com";
$mail_smtp_port      = 587;
$mail_smtp_auth      = true;
$mail_smtp_user      = "XXXXXXX@gmail.com";
$mail_smtp_pass      = "XXXXXXXXXXXXXXXXXXXXXXXXX";
$mail_smtp_secure    = "tls";
$mail_smtp_autotls   = true;
$mail_smtp_debug     = 4;
# ── URLs ──────────────────────────────────────────────────────────────────────
$reset_url = "http://20.0.0.42:8081";
$baseurl   = "http://20.0.0.42:8081";
?>
```

- `ldap://freeipa-server:389` — uses the container name instead of an IP. Docker's internal DNS resolves it as long as both containers are on `ipa-net`. More reliable than a hardcoded IP which can change on restart.
- `$use_tokens = true` + `$keyphrase` — SSP generates a one-time token, signs it with the keyphrase, and emails a reset link to the user. The keyphrase must stay constant across restarts — if it changes, any in-flight reset tokens become invalid.
- `$reset_url` and `$baseurl` — must point to the externally reachable address of SSP so that the token links in emails actually work for the user clicking them.
- `$smtp_debug = 4` — logs the full SMTP session to container logs. Useful during setup, set to `0` in production.

---

## 3. LDAP Sync

To integrate FreeIPA with an external service via LDAP, use the following settings:

### Connection

| Field | Value |
|---|---|
| Base DN | `cn=accounts,dc=asteroidea,dc=com` |
| User Attribute | `uid` |
| Server | `ipa.asteroidea.com` |
| Port | `389` |
| Mode | `LDAP` (plain) or `LDAPS` (port 636) |

> **Note:** The server must be resolvable from the client host. If DNS isn't configured, use the IP directly. Docker container names are not resolvable outside the Docker network.

### Bind / Sync

| Field | Value |
|---|---|
| Bind DN | `uid=admin,cn=users,cn=accounts,dc=asteroidea,dc=com` |
| Bind Password | `<ADMIN_PASSWORD>` |
| User Filter | `(objectClass=posixAccount)` |
| Group Filter | `(&(objectClass=groupOfNames)(cn=*))` |
| User Classes | `inetOrgPerson, posixAccount` |
| Group Classes | `groupOfNames, posixGroup` |
| Email Attribute | `mail` |
| Group Name Attribute | `cn` |

- `uid` is the login attribute in FreeIPA — not `sAMAccountName`, which is Active Directory only.
- `(objectClass=posixAccount)` limits the sync to real user accounts, skipping service entries.
- After syncing, users are not automatically granted access — roles and permissions must still be assigned explicitly in the target service.