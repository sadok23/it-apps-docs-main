# Borg Backup Server (BBS) — Operations Guide

BBS is a self-hosted web application for centrally managing BorgBackup across multiple Linux machines. A lightweight agent runs on each client, polls the BBS server for tasks, and backs up over SSH. No inbound connections to clients are required — works behind firewalls and NAT.

---
## Architecture Overview

```
Backup Client #1         Backup Client #2         Backup Client #3
  (Linux VM)              (Linux VM)               (Docker Server)
   ┌──────────┐           ┌──────────┐            ┌──────────┐
   │ Borg CLI │           │ Borg CLI │            │ Borg CLI │
   │ Agent    │           │ Agent    │            │ Agent    │
   └──────┬───┘           └──────┬───┘            └──────┬───┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                                 |
                                 │
                    ╔════════════▼═════════════╗
                    ║   Borg Backup Server     ║
                    ║ (Docker Container)       ║
                    ║ ┌─────────────────────┐  ║
                    ║ │ Web UI (Port 8080)  │  ║
                    ║ └─────────────────────┘  ║
                    ║                          ║
                    ╚══════════════════════════╝
                            │
                  ┌─────────▼──────────┐
                  │ TrueNAS 
                  │             (NFS)  │
                  └────────────────────┘
```

## Table of Contents

1. [Installation (Docker)](#1-installation-docker)
2. [Adding a Client](#2-adding-a-client)
3. [Setting Up Storage (Repository)](#3-setting-up-storage-repository)
4. [Creating a Backup Plan](#4-creating-a-backup-plan)
5. [Database Backups (PostgreSQL)](#5-database-backups-postgresql)
6. [Restoring a Database](#6-restoring-a-database)
7. [Restoring Files](#7-restoring-files)

## 1. Installation (Docker)

The recommended way to run BBS is via Docker Compose. Save this as `docker-compose.yml` or deploy it via Komodo:

```yaml
networks:
  traefik:
    external: true

services:
  bbs:
    image: marcpope/borgbackupserver:latest
    container_name: bbs
    ports:
      - "8086:80"   # Web UI
      - "2222:22"   # SSH for agent connections
    environment:
      - APP_URL=http://<YOUR_HOST_IP>:8086
      - SSH_PORT=2222
      - TZ=Africa/Tunis
    volumes:
      - /opt/data/bbs-data:/var/bbs
      - nfs-backups:/mnt/storage
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.borg.rule=Host(`borg.yourdomain.com`)"
      - "traefik.http.routers.borg.entrypoints=web,websecure"
      - "traefik.http.services.borg.loadbalancer.server.port=80"
    restart: unless-stopped
    networks:
      - traefik

volumes:
  nfs-backups:
    driver: local
    driver_opts:
      type: nfs
      o: addr=<NFS_SERVER_IP>,nfsvers=4,soft,timeo=30,retrans=3
      device: ":/mnt/your-pool"
```

After starting, get the auto-generated admin credentials:

```bash
docker compose logs bbs
```

Open the web UI and complete the setup wizard.

---

## 2. Adding a Client

A **client** is any machine you want to back up. BBS uses a lightweight Python agent installed on the client.

### Step 1 — Create the client in BBS

1. Go to **Clients** → **Add Client**
2. Enter a name 
3. Click **Create Client**
4. Copy the install command shown on the next screen

### Step 2 — Install the agent on the client machine

SSH into the client and run the install command copied from BBS:

```bash
curl -s https://borg.yourdomain.com/get-agent | sudo bash -s -- \
  --server https://borg.yourdomain.com \
  --key YOUR_API_KEY
```

The installer will:
- Install BorgBackup if not present
- Create the agent config at `/etc/bbs-agent/config.ini`
- Register the agent as a systemd service
- Exchange SSH keys with the BBS server

### Step 3 — Verify the agent is running

```bash
sudo systemctl status bbs-agent
```

The client status in BBS should change from **Setup** (blue) to **Online** (green) within a minute.


---

## 3. Setting Up Storage (Repository)

Before creating backup plans, you need a repository — the storage location where Borg archives are kept.

1. Go to **Repositories** → **Add Repository**
2. Choose **Local Storage** (NFS mount inside the container) or **Remote SSH**
3. Give it a name and point it to your storage path (e.g. `/mnt/storage`)
4. Save — BBS will initialize the Borg repository automatically

---

## 4. Creating a Backup Plan

A backup plan defines **what** to back up, **where** to store it, and **when** to run.

1. Go to the client detail page → **Backup Plans** → **Add Plan**
2. Configure:
   - **Name**: e.g. `daily-full`
   - **Directories**: paths to back up (e.g. `/home`, `/etc`, `/var/backups`)
   - **Repository**: select the repo created above
   - **Schedule**: cron expression (e.g. `0 2 * * *` for 2am daily)
   - **Retention**: e.g. keep 7 daily, 4 weekly, 3 monthly
3. Save the plan

To trigger a backup manually: open the plan → click **Run Now**.

---

## 5. Database Backups (PostgreSQL)

BBS has a built-in PostgreSQL plugin that automatically dumps the database before each backup run.

### Prerequisites

Install `postgresql-client` on the client machine (provides `pg_dump` without a full server):

```bash
sudo apt install postgresql-client -y
```

### Step 1 — Enable the plugin

1. Go to client detail page → **Plugins** tab
2. Toggle **PostgreSQL Backup** to enabled

### Step 2 — Add a configuration

Click **Add Configuration** and fill in:

| Field | Value |
|---|---|
| Configuration Name | e.g. `postgres-main` |
| Database Host | IP of the machine running PostgreSQL (not `localhost` if it's in Docker) |
| Port | `5432` |
| Username | `admin` (or your DB user) |
| Password | your DB password |
| Databases | `all` or comma-separated list e.g. `borgtest,appdb` |
| Dump Directory | `/var/backups/postgresql` |

Click **Save Configuration**.

### Step 3 — Test the plugin

On the Plugins tab, click **Test** next to the configuration. Monitor the result in **Queue**. A successful test means BBS connected to PostgreSQL and created dump files in the dump directory.

### Step 4 — Attach to a backup plan

1. Edit your backup plan
2. In the **Plugins** section, select the PostgreSQL configuration from the dropdown
3. Make sure the dump directory (`/var/backups/postgresql`) is included in the plan's directory list
4. Save

### How it works

When a backup job runs:
1. BBS agent runs `pg_dump` for each configured database → saves `.dump` files to the dump directory
2. Borg archives the dump directory along with any other configured paths
3. The dump files are stored inside the Borg archive, deduplicated and compressed

---

## 6. Restoring a Database

1. Go to client detail → **Restore** tab
2. Find the archive to restore from (archives with DB dumps show a database icon)
3. Click **Restore Database**
4. Fill in the target PostgreSQL credentials (can be a different server)
5. Select which databases to restore
6. Click **Restore**

BBS automatically:
- Extracts the dump files from the Borg archive
- Creates a safety backup of the current database before overwriting
- Runs `pg_restore` against the target server

---

## 7. Restoring Files

1. Go to client detail → **Restore** tab
2. Select an archive
3. Browse the file tree and select files or directories to restore
4. Choose a restore destination
5. Click **Restore**

---





