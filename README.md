# IT Infrastructure & Applications Documentation (IT-APPS-DOCS)

Welcome to the **IT-APPS-DOCS** repository. This repository serves as the central knowledge base, automation hub, and configuration repository for IT infrastructure services, identity management, log monitoring, backups, and hypervisor management.

---

## 📚 Repository Structure & Overview

### 📖 Documentation Guides

| File | Category | Description |
| :--- | :--- | :--- |
| 🔐 [freeipa_docs.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/freeipa_docs.md) | Identity & Access | FreeIPA setup, LDAP/Kerberos configuration, group sync policies, and user administration. |
| ⚡ [semaphore_docs.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/semaphore_docs.md) | Ansible Automation | Ansible Semaphore deployment, web UI task runner configuration, and playbook integration. |
| 🐉 [komodo_docs.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/komodo_docs.md) | Container Orchestration | Komodo stack deployment, multi-node container management, and access control integration. |
| 📊 [log_monitoring_docs.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/log_monitoring_docs.md) | Observability | Centralized logging stack architecture (Grafana, Loki, Vector/Promtail) and dashboard usage. |
| 💾 [borg_docs.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/borg_docs.md) | Backup & Recovery | BorgBackup repository setup, deduplication strategy, automated schedules, and restore procedures. |
| 🌐 [Network-Interface-Driver-OpnSense.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/Network-Interface-Driver-OpnSense.md) | Networking | OPNsense firewall network interface driver installation and tuning notes. |
| 🔧 [potential_NIC_PVE3_fix.md](file:///c:/Users/sadok/Desktop/it-apps-docs-main/potential_NIC_PVE3_fix.md) | Hypervisor Fixes | Hardware and driver workaround guide for Network Interface Cards on Proxmox VE (PVE3). |

---

### ⚙️ Automation Scripts (`scripts/`)

Located in the [`scripts/`](file:///c:/Users/sadok/Desktop/it-apps-docs-main/scripts) directory:

- **`gitlab-ipa-sync-v2.py`**: Synchronizes FreeIPA users and group memberships with GitLab over API/LDAP.
- **`gitlab_ipa_sync.py`**: Legacy synchronization script for FreeIPA and GitLab.
- **`komodo_ipa_group_sync.py`**: Automatically syncs FreeIPA user groups into Komodo authorization roles.
- **`delete_unused_vms.sh`**: Bash script to detect and prune decommissioned or idle Virtual Machines on Proxmox VE.
- **`ufw_docker_management.sh`**: Manages UFW firewall rules to properly control Docker port exposures and network isolation.

---

### 📈 Grafana Dashboards (`grafana_dashboards/`)

Located in the [`grafana_dashboards/`](file:///c:/Users/sadok/Desktop/it-apps-docs-main/grafana_dashboards) directory:

- **`container_logs_exporter_v3.json`**: Primary Grafana dashboard template for real-time container log exploration and filtering via Loki.
- **`contaner_logs_explorer_v2.json`** & **`container_logs_explorer.json`**: Legacy and fallback dashboard revisions.

---

## 🛠️ Quick Start & Usage

### 1. Running Sync Scripts
Ensure Python 3 is installed along with required dependencies (e.g., `requests`, `python-ldap` if applicable):

```bash
# Sync FreeIPA groups with GitLab
python3 scripts/gitlab-ipa-sync-v2.py

# Sync FreeIPA groups with Komodo
python3 scripts/komodo_ipa_group_sync.py
```

### 2. Managing Firewall Rules for Docker
Run the UFW management script with necessary privileges:

```bash
chmod +x scripts/ufw_docker_management.sh
sudo ./scripts/ufw_docker_management.sh
```

### 3. Importing Grafana Dashboards
1. Open your Grafana web application.
2. Navigate to **Dashboards** -> **Import**.
3. Upload `grafana_dashboards/container_logs_exporter_v3.json` or paste the JSON contents.

---

## 🤝 Maintenance & Contributing

When making updates to infrastructure procedures or adding new automation tools:
1. Update or create the relevant markdown documentation file.
2. Ensure any new scripts added to `scripts/` are well-commented and executable.
3. Update this `README.md` to reflect new tools or documentation additions.
