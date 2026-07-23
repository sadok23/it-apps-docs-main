# Log Monitoring with Grafana

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Monitoring VM Setup](#1-monitoring-vm-setup)
- [Docker Servers Setup](#2-docker-servers-setup)
- [Adding Dashboards to Grafana](#3-adding-dashboards-to-grafana)

---

## Overview

This guide covers setting up centralized log monitoring using **Promtail**, **Loki**, and **Grafana**.

| Component | Role |
|-----------|------|
| **Promtail** | Reads container logs, adds labels, and ships them to Loki via HTTP. Must be installed on each server. |
| **Loki** | Ingests, stores, and indexes logs based on their labels. |
| **Grafana** | Connects to Loki as a data source, queries logs using LogQL, and displays them in dashboards. |

---

## Architecture

```
Docker Server #1        Docker Server #2        Docker Server #3
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│   Promtail   │        │   Promtail   │        │   Promtail   │
└──────┬───────┘        └──────┬───────┘        └──────┬───────┘
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Monitoring VM     │
                    │  ┌───────────────┐  │
                    │  │     Loki      │  │
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │    Grafana    │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

---

## 1. Monitoring VM Setup

### Installing Loki and Grafana

Create a `docker-compose.yml` file on the monitoring VM:

```yaml
version: "3.8"
services:
  loki:
    restart: unless-stopped
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yml:/etc/loki/local-config.yaml
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml

  grafana:
    restart: unless-stopped
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SMTP_ENABLED=true
      - GF_SMTP_HOST=smtp.gmail.com:587
      - GF_SMTP_USER=you@gmail.com
      - GF_SMTP_PASSWORD=your_app_password
      - GF_SMTP_FROM_ADDRESS=you@gmail.com
      - GF_SMTP_FROM_NAME=Grafana Alerts

volumes:
  loki-data:
  grafana-data:
```

> ⚠️ **Note:** A Loki config file must be created and accessible before running the containers. Set the SMTP environment variables if you want Grafana alerts via email.

---

### Loki Config File

Create `loki-config.yml` in the same directory:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /loki

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  tsdb_shipper:
    active_index_directory: /loki/tsdb-index
    cache_location: /loki/tsdb-cache
  filesystem:
    directory: /loki/chunks

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  retention_period: 7d

compactor:
  working_directory: /loki/compactor
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem
```

> 💡 **Tips:**
> - Set `retention_period` if you want automatic log deletion
> - Set `object_store` to `filesystem` when storing logs locally

---

### Linking Grafana with Loki

1. Access the Grafana UI at `http://<host-ip>:3000`
2. Navigate to **Connections → Data Sources → Add new Data Source**
3. Select **Loki**
4. Set the URL to `http://<host-ip>:3100`
5. Click **Save and Test**

---

## 2. Docker Servers Setup

### Installing Promtail

On each Docker server, create a `docker-compose.yml`:

```yaml
version: "3.8"
services:
  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    user: root
    volumes:
      - /var/log:/var/log
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - ./promtail-config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped
```

> ⚠️ **Note:** The Promtail config file must be created and accessible before running the container.

---

### Promtail Config File

Create `promtail-config.yml` on each Docker server:

```yaml
clients:
  - url: http://20.0.0.41:3100/loki/api/v1/push
scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(promtail|loki|grafana)'
        action: drop
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container_name'
      - source_labels: ['__meta_docker_container_image']
        target_label: 'container_image'
      - target_label: 'host'
        replacement: '${HOST_LABEL}'
      - source_labels: ['__meta_docker_container_image']
        target_label: 'image'
      - source_labels: ['__meta_docker_network_name']
        target_label: 'network'
      - source_labels: ['__meta_docker_container_label_com_docker_compose_project']
        target_label: 'stack'
        action: replace
      - source_labels: ['__meta_docker_container_label_product']
        target_label: 'product'
        action: replace
    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            time: time
      - timestamp:
          format: RFC3339Nano
          source: time
      - labels:
          stream:
      - regex:
          expression: '(?i)x-request-id:\s*(?P<x_request_id>\S+)'
          source: output
      - labels:
          x_request_id:
      - output:
          source: output
```

#### `clients`

Where Promtail sends logs. Replace `20.0.0.41` with your monitoring VM's IP. All logs collected on this server will be HTTP-POSTed to this endpoint in batches.

#### `docker_sd_configs` — Service Discovery

Promtail connects to the Docker socket to automatically discover all running containers. Every 5 seconds it checks for new or removed containers and updates what it's tailing — no manual config needed when you add or remove containers.

#### `relabel_configs` — Filtering and Labeling

Relabeling runs on every discovered container before any logs are read. It has two jobs: decide which containers to ignore, and attach labels to the ones that are kept.

Containers named `promtail`, `loki`, or `grafana` are dropped to avoid noise and circular ingestion. Each remaining rule copies a piece of Docker metadata into a Loki label — these labels are how you filter and search logs in Grafana.

| Label | Source | What it gives you |
|---|---|---|
| `container_name` | Container name | Filter logs by a specific container |
| `container_image` | Image name | See which image a container is running |
| `host` | `${HOST_LABEL}` env var | Identify which server the log came from |
| `network` | Docker network name | Filter by Docker network |
| `stack` | Compose project label | Group all containers in a Compose stack |
| `product` | Custom `product` label | Group by app if you set this label in your Compose files |

The `host` label deserves special attention — `${HOST_LABEL}` is an environment variable you set when starting Promtail (e.g. `HOST_LABEL=docker-server-1`). Since all servers ship to the same Loki instance, this is the only way to tell them apart in Grafana.

#### `pipeline_stages` — Log Processing

Pipeline stages run on each log line after it's collected, before it's sent to Loki.

**JSON parsing** — Docker logs are wrapped in a JSON envelope. This extracts the actual log message (`log`), whether it came from stdout or stderr (`stream`), and the original timestamp (`time`). Without this, you'd see the raw JSON wrapper instead of the log message.

**Timestamp** — Uses the timestamp from the original log line rather than the time Promtail received it. This keeps log ordering accurate even if there's a delay in shipping.

**Stream label** — Promotes `stream` (stdout/stderr) to a Loki label so you can filter by it in queries.

**Request ID extraction** — Scans each log line for an `X-Request-ID` HTTP header value and, if found, promotes it to a label. This lets you trace a single request across multiple services by filtering on `x_request_id` in Grafana. Remove these two stages if your services don't produce request IDs.

**Output** — Sets the final log line stored in Loki to the extracted `output` field (the clean log message), discarding the JSON envelope entirely.

---

## 3. Adding Dashboards to Grafana

In Grafana, go to **Dashboards → New → Import**. You can import a dashboard in two ways:

**Option A — Import by ID** — Browse [grafana.com/dashboards](https://grafana.com/grafana/dashboards/), find a dashboard you want, copy its numeric ID (e.g. `13639`), paste it into the ID field, and click **Load**. Grafana fetches the dashboard definition directly from the community library.

**Option B — Import by JSON** — If you have a dashboard exported from another Grafana instance or downloaded manually, paste the full JSON into the **Import via panel json** text area and click **Load**.

After loading by either method, select your Loki data source from the dropdown and click **Import**.

> 💡 This gives you a ready-to-use dashboard with little to no manual configuration.