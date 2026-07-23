# Komodo — Documentation

> Container management platform with a Core + Periphery agent architecture.

---

## Table of Contents

1. [Installation](#1-installation)
   - [Download Compose Files](#11-download-compose-files)
   - [Compose File](#12-compose-file)
   - [Environment File](#13-environment-file)
   - [Start the Stack](#14-start-the-stack)
2. [Variables & Secrets](#2-variables--secrets)
   - [Plain Variables](#21-plain-variables)
   - [Secret Variables](#22-secret-variables)
   - [Using Variables in Stacks](#23-using-variables-in-stacks)
3. [Providers](#3-providers)
   - [Via the UI](#31-via-the-ui)
   - [Via `config.toml`](#32-via-configtoml)
4. [Stack Templates](#4-stack-templates)
   - [Create a Template](#41-create-a-template)
   - [Deploy a Stack from a Template](#42-deploy-a-stack-from-a-template)
5. [Groups & Permissions](#5-groups--permissions)
   - [Permission Levels](#51-permission-levels)
   - [Create a Group](#52-create-a-group)
   - [Assign Users to a Group](#53-assign-users-to-a-group)
   - [Grant Resource Permissions to a Group](#54-grant-resource-permissions-to-a-group)
6. [Periphery Agents](#6-periphery-agents)
   - [Create an Onboarding Key](#61-create-an-onboarding-key)
   - [Install Periphery on a Remote Host](#62-install-periphery-on-a-remote-host)
7. [Resource Sync](#7-resource-sync)
   - [How It Works](#71-how-it-works)
   - [Create a Resource Sync](#72-create-a-resource-sync)
   - [Stack TOML Example](#73-stack-toml-example)
   - [Triggering a Sync](#74-triggering-a-sync)
8. [GitLab CI Integration](#8-gitlab-ci-integration)
   - [Approach A — GitLab Webhook](#81-approach-a--gitlab-webhook-simple-limited)
   - [Approach B — GitLab CI with Komodo API Calls](#82-approach-b--gitlab-ci-with-komodo-api-calls-flexible-no-ui-required)

---

## 1. Installation

### 1.1 Download Compose Files

Pull both the compose and environment files into a local `komodo/` directory:

```bash
wget -P komodo https://raw.githubusercontent.com/moghtech/komodo/main/compose/ferretdb.compose.yaml && \
  wget -P komodo https://raw.githubusercontent.com/moghtech/komodo/main/compose/compose.env
```

This gives you:

```
komodo/
├── ferretdb.compose.yaml   # Core + FerretDB (MongoDB-compatible) stack
└── compose.env             # Environment variable overrides
```

---

### 1.2 Compose File

> Paste your `ferretdb.compose.yaml` content below.

```yaml
###################################
# 🦎 KOMODO COMPOSE - FERRETDB 🦎 #
###################################
## This compose file will deploy:
##   1. Postgres + FerretDB Mongo adapter (https://www.ferretdb.com)
##   2. Komodo Core
##   3. Komodo Periphery
services:
  postgres:
    # 🚨 Pin to a specific version. Updates can be breaking.
    # https://github.com/FerretDB/documentdb/pkgs/container/postgres-documentdb
    image: ghcr.io/ferretdb/postgres-documentdb
    labels:
      komodo.skip: # Prevent Komodo from stopping with StopAllContainers
    restart: unless-stopped
    # ports:
    #   - 5432:5432
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: ${KOMODO_DATABASE_USERNAME}
      POSTGRES_PASSWORD: ${KOMODO_DATABASE_PASSWORD}
      POSTGRES_DB: postgres

  ferretdb:
    # 🚨 Pin to a specific version. Updates can be breaking.
    # https://github.com/FerretDB/FerretDB/pkgs/container/ferretdb
    image: ghcr.io/ferretdb/ferretdb
    labels:
      komodo.skip: # Prevent Komodo from stopping with StopAllContainers
    restart: unless-stopped
    depends_on:
      - postgres
    # ports:
    #   - 27017:27017
    volumes:
      - ferretdb-state:/state
    environment:
      FERRETDB_POSTGRESQL_URL: postgres://${KOMODO_DATABASE_USERNAME}:${KOMODO_DATABASE_PASSWORD}@postgres:5432/postgres

  core:
    image: ghcr.io/moghtech/komodo-core:${COMPOSE_KOMODO_IMAGE_TAG:-2}
    init: true
    restart: unless-stopped
    depends_on:
      - ferretdb
    ports:
      - 9120:9120
    env_file: ./compose.env
    environment:
      KOMODO_DATABASE_ADDRESS: ferretdb:27017
    volumes:
      ## Attach the Core / Periphery communication keys
      - keys:/config/keys
      ## Store dated backups of the database - https://komo.do/docs/setup/backup
      - ${COMPOSE_KOMODO_BACKUPS_PATH}:/backups
      ## Store sync files on server
      # - /path/to/syncs:/syncs
      ## Optionally mount a custom core.config.toml
      # - /path/to/core.config.toml:/config/config.toml
      ## Optionally mount custom root CA certificate to trust
      # - /path/to/root_ca.crt:/usr/local/share/ca-certificates/root_ca.crt

  ## Deploy Periphery container using this block,
  ## or deploy the Periphery binary with systemd using
  ## https://github.com/moghtech/komodo/tree/main/scripts
  periphery:
    image: ghcr.io/moghtech/komodo-periphery:${COMPOSE_KOMODO_IMAGE_TAG:-2}
    init: true
    restart: unless-stopped
    depends_on:
      - core
    env_file: ./compose.env
    volumes:
      ## Attach the Core / Periphery communication keys
      - keys:/config/keys
      ## Mount external docker socket
      - /var/run/docker.sock:/var/run/docker.sock
      ## Allow Periphery to see processes outside of container
      - /proc:/proc
      ## Specify the Periphery agent root directory.
      ## All your configs / repos must be children of this directory for Periphery to be able to see it.
      ## Must be the same inside and outside the container,
      ## or docker will get confused. See https://github.com/moghtech/komodo/discussions/180.
      ## Default: /etc/komodo.
      - ${PERIPHERY_ROOT_DIRECTORY:-/etc/komodo}:${PERIPHERY_ROOT_DIRECTORY:-/etc/komodo}
      ## Optionally mount a custom periphery.config.toml
      # - /path/to/periphery.config.toml:/config/config.toml
      ## Optionally mount custom root CA certificate to trust
      # - /path/to/root_ca.crt:/usr/local/share/ca-certificates/root_ca.crt

volumes:
  # Postgres
  postgres-data:
  # FerretDB
  ferretdb-state:
  # Core / Periphery
  keys:
```

---

### 1.3 Environment File

> Paste your `compose.env` content below.

```env
####################################
# 🦎 KOMODO COMPOSE - VARIABLES 🦎 #
####################################

## These compose variables can be used with all Komodo deployment options.
## Pass these variables to the compose up command using `--env-file komodo/compose.env`.
## Additionally, they are passed to both Komodo Core and Komodo Periphery with `env_file: ./compose.env`,
## so you can pass any additional environment variables to Core / Periphery directly in this file as well.

## Follows "major.minor.patch" semver.
COMPOSE_KOMODO_IMAGE_TAG="2"
## Store dated database backups on the host - https://komo.do/docs/setup/backup
COMPOSE_KOMODO_BACKUPS_PATH=/etc/komodo/backups

## DB credentials
KOMODO_DATABASE_USERNAME=admin
KOMODO_DATABASE_PASSWORD=admin

## Set your time zone for schedules
## https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TZ=Etc/UTC

#=-------------------------=#
#= Komodo Core Environment =#
#=-------------------------=#

## Full variable list + descriptions are available here:
## 🦎 https://github.com/moghtech/komodo/blob/main/config/core.config.toml 🦎

## Note. Secret variables also support `${VARIABLE}_FILE` syntax to pass docker compose secrets.
## Docs: https://docs.docker.com/compose/how-tos/use-secrets/#examples

## Used for Oauth / Webhook url suggestion.
KOMODO_HOST=https://example.komodo.com
## Displayed in the browser tab.
KOMODO_TITLE=Komodo

## Allow Periphery to connect via generated public key
KOMODO_PERIPHERY_PUBLIC_KEY=file:/config/keys/periphery.pub

## Enable login with username + password.
KOMODO_LOCAL_AUTH=true
## Set the initial admin username created upon first launch.
## Comment out to disable initial user creation,
## and create first user using signup button.
KOMODO_INIT_ADMIN_USERNAME=admin
## Set the initial admin password
KOMODO_INIT_ADMIN_PASSWORD=changeme

## Create a first Server with a custom name.
## Usually the system hostname is good.
KOMODO_FIRST_SERVER_NAME=Local

## Make execute buttons just double-click, rather than the full confirmation dialog.
KOMODO_DISABLE_CONFIRM_DIALOG=false

## Disable creating the default Procedures on first startup.
KOMODO_DISABLE_INIT_RESOURCES=false

## Used to auth incoming webhooks. Alt: KOMODO_WEBHOOK_SECRET_FILE
KOMODO_WEBHOOK_SECRET=a_random_secret
## Used to generate jwt. Alt: KOMODO_JWT_SECRET_FILE
KOMODO_JWT_SECRET=a_random_jwt_secret
## Time to live for jwt tokens.
## Options: 1-hr, 12-hr, 1-day, 3-day, 1-wk, 2-wk
KOMODO_JWT_TTL="1-day"

## Rate Komodo polls your servers for
## status / container status / system stats / alerting.
## Options: 1-sec, 5-sec, 15-sec, 1-min, 5-min, 15-min
## Default: 15-sec
KOMODO_MONITORING_INTERVAL="15-sec"
## Interval at which to poll Resources for any updated / automated actions.
## Options: 5-min, 15-min, 1-hr, 2-hr, 6-hr, 12-hr, 1-day
## Default: 1-hr
KOMODO_RESOURCE_POLL_INTERVAL="1-hr"

## Disable new user signups.
KOMODO_DISABLE_USER_REGISTRATION=false
## All new logins are auto enabled
KOMODO_ENABLE_NEW_USERS=false
## Disable non-admins from creating new resources.
KOMODO_DISABLE_NON_ADMIN_CREATE=false
## Allows all users to have Read level access to all resources.
KOMODO_TRANSPARENT_MODE=false

## OIDC Login
KOMODO_OIDC_ENABLED=false
## Must reachable from Komodo Core container
# KOMODO_OIDC_PROVIDER=https://oidc.provider.internal/application/o/komodo
## Change the host to one reachable by users (optional if it is the same as above).
## DO NOT include the `path` part of the URL.
# KOMODO_OIDC_REDIRECT_HOST=https://oidc.provider.external
## Your OIDC client id
# KOMODO_OIDC_CLIENT_ID= # Alt: KOMODO_OIDC_CLIENT_ID_FILE
## Your OIDC client secret.
## If your provider supports PKCE flow, this can be ommitted.
# KOMODO_OIDC_CLIENT_SECRET= # Alt: KOMODO_OIDC_CLIENT_SECRET_FILE
## Make usernames the full email.
## Note. This does not work for all OIDC providers.
# KOMODO_OIDC_USE_FULL_EMAIL=true
## Add additional trusted audiences for token claims verification.
## Supports comma separated list, and passing with _FILE (for compose secrets).
# KOMODO_OIDC_ADDITIONAL_AUDIENCES=abc,123 # Alt: KOMODO_OIDC_ADDITIONAL_AUDIENCES_FILE

## Github Oauth
KOMODO_GITHUB_OAUTH_ENABLED=false
# KOMODO_GITHUB_OAUTH_ID= # Alt: KOMODO_GITHUB_OAUTH_ID_FILE
# KOMODO_GITHUB_OAUTH_SECRET= # Alt: KOMODO_GITHUB_OAUTH_SECRET_FILE

## Google Oauth
KOMODO_GOOGLE_OAUTH_ENABLED=false
# KOMODO_GOOGLE_OAUTH_ID= # Alt: KOMODO_GOOGLE_OAUTH_ID_FILE
# KOMODO_GOOGLE_OAUTH_SECRET= # Alt: KOMODO_GOOGLE_OAUTH_SECRET_FILE

## Aws - Used to launch Builder instances.
KOMODO_AWS_ACCESS_KEY_ID= # Alt: KOMODO_AWS_ACCESS_KEY_ID_FILE
KOMODO_AWS_SECRET_ACCESS_KEY= # Alt: KOMODO_AWS_SECRET_ACCESS_KEY_FILE

## Prettier logging with empty lines between logs
KOMODO_LOGGING_PRETTY=false
## More human readable logging of startup config (multi-line)
KOMODO_PRETTY_STARTUP_CONFIG=false

#=------------------------------=#
#= Komodo Periphery Environment =#
#=------------------------------=#

## Full variable list + descriptions are available here:
## 🦎 https://github.com/moghtech/komodo/blob/main/config/periphery.config.toml 🦎

## Point Periphery to Core for connection
PERIPHERY_CORE_ADDRESS=ws://core:9120
## Use the same name as KOMODO_FIRST_SERVER_NAME to connect
PERIPHERY_CONNECT_AS=${KOMODO_FIRST_SERVER_NAME}
## Use the public key generated by Core.
PERIPHERY_CORE_PUBLIC_KEYS=file:/config/keys/core.pub

## Specify the root directory used by Periphery agent.
## All your compose files and repos need to be inside this directory
## for Periphery to interact with them.
## - ROOT_DIRECTORY (/etc/komodo)
## --- ./stacks
## ------ ./my_stack_1
## ------ ./my_stack_2
## --- ./repos
## ------ ./my_repo_1
PERIPHERY_ROOT_DIRECTORY=/etc/komodo

## Specify whether to disable the terminals feature
## and disallow remote shell access (inside the Periphery container).
PERIPHERY_DISABLE_TERMINALS=false
## Specify whether to disable the container exec / attach features
## and disallow container remote shell access.
PERIPHERY_DISABLE_CONTAINER_TERMINALS=false

## If the disk size is overreporting, can use one of these to
## whitelist / blacklist the disks to filter them, whichever is easier.
## Accepts comma separated list of paths.
## Usually whitelisting just /etc/hostname gives correct size.
PERIPHERY_INCLUDE_DISK_MOUNTS=/etc/hostname
# PERIPHERY_EXCLUDE_DISK_MOUNTS=/snap,/etc/repos

## Prettier logging with empty lines between logs
PERIPHERY_LOGGING_PRETTY=false
## More human readable logging of startup config (multi-line)
PERIPHERY_PRETTY_STARTUP_CONFIG=false
```

---

### 1.4 Start the Stack

```bash
docker compose -p komodo \
  -f komodo/ferretdb.compose.yaml \
  --env-file komodo/compose.env \
  up -d
```

Komodo Core will be accessible on the port defined in `compose.env` (default: `9120`).

---

## 2. Variables & Secrets

Komodo has a built-in variable store that lets you define key-value pairs and reference them across all stacks — either as plain environment variables or as masked secrets.

### 2.1 Plain Variables

Navigate to **Settings → Variables** and click **New Variable**.

| Field | Description |
|---|---|
| **Name** | The key used to reference the variable (e.g. `DOMAIN`) |
| **Value** | The plain-text value |
| **Secret** | Leave unchecked |

Plain variables are visible in the UI and are suitable for non-sensitive configuration such as domain names, image tags, or replica counts.

---

### 2.2 Secret Variables

Same flow as above, but check the **Secret** toggle before saving.

- The value is stored encrypted and **never displayed again** in the UI after creation.
- Secrets are injected at deploy time and do not appear in stack logs or the API response.
- Suitable for: API keys, passwords, tokens, TLS certificates.

> **Tip:** You can edit a secret's value at any time; only the value field is re-encrypted — the name reference in stacks stays intact.

---

### 2.3 Using Variables in Stacks

Reference any variable (plain or secret) inside a stack's compose body using the `[[VAR_NAME]]` interpolation syntax:

```yaml
services:
  app:
    image: myapp:latest
    environment:
      - DOMAIN=[[DOMAIN]]
      - DB_PASSWORD=[[DB_PASSWORD]]   # secret variable
      - API_KEY=[[API_KEY]]           # secret variable
```

Komodo resolves `[[...]]` references server-side before sending the compose file to the Periphery agent — the raw values are never stored in Git or visible in the UI stack view.

---

## 3. Providers

Providers connect Komodo to external Git hosts or container registries so it can pull compose files and images without storing credentials inline.

### 3.1 Via the UI

1. Go to **Settings → Providers**.
2. Click **New Provider** and choose the type:
   - **Git Provider** — GitHub, GitLab, Gitea, Bitbucket, etc.
   - **Registry** — Docker Hub, GHCR, a private registry.
3. Fill in the required fields:
   - **Domain** — e.g. `github.com` or `registry.example.com`
   - **Username** — your account or bot username
   - **Token / Password** — use a personal access token (PAT) with the minimum required scopes (`read:packages`, `contents:read`, etc.)
4. Save. The provider becomes selectable in stack and build configurations.

---

### 3.2 Via `config.toml`

Providers can also be declared statically in Komodo Core's configuration file, which is useful for GitOps or automated deployments.

```toml
[[git_provider]]
domain   = "github.com"
https    = true
username = "your-bot-user"
token    = "ghp_..."

[[git_provider]]
domain   = "gitlab.example.com"
https    = true
username = "ci-bot"
token    = "glpat-..."

[[registry]]
domain   = "ghcr.io"
username = "your-bot-user"
token    = "ghp_..."
```

> **Note:** Tokens in `config.toml` are read at startup. Prefer the UI secret store or environment variable injection to avoid committing tokens to version control.

---

## 4. Stack Templates

Stack templates let you define a parameterized compose spec once and reuse it to spin up multiple stacks without duplication.

### 4.1 Create a Template

1. Navigate to **Stacks → New or Existing Stack**.
2. Modify the yaml of your template.
3. Press the Template Switch on the top of the screen.
4. Click **Save**. The template is now available for any stack deployment.

---

### 4.2 Deploy a Stack from a Template

1. Go to **Stacks → New Stack**.
2. Under **Source**, select **Template** and pick your saved template from the dropdown.
3. Select the **Server** (Periphery agent) to deploy to.
4. Click **Deploy**.

> You can also update the template later — existing stacks that were created from it are independent copies and won't be affected unless you re-deploy.

---

## 5. Groups & Permissions

Groups let you manage access control at scale. Instead of granting permissions to individual users, you assign users to groups and then grant those groups access to specific resources at a defined permission level.

### 5.1 Permission Levels

Komodo has four permission levels that can be assigned to a group on a per-resource basis (e.g. a specific Stack, Server, or Repo).

**None** means no access at all — the resource won't even appear in the UI for members of that group.

**Read** is view-only. Members can see the resource, its configuration, logs, and current status, but cannot make any changes or trigger any actions. Good for auditors and stakeholders who just need visibility.

**Execute** includes everything Read allows, plus the ability to trigger actions such as deploying, starting, stopping, restarting, running procedures, and pulling images. Members still cannot edit the resource's configuration. This is the right level for operators who run deployments but shouldn't be able to change settings.

**Write** is full control. It includes everything Execute allows, plus the ability to edit configuration, rename, and delete the resource. Treat this as ownership — reserve it for team leads or automation accounts.

Permission levels are cumulative, so Execute always implies Read. If a user belongs to multiple groups, they inherit the highest level any of those groups grants them on a given resource.

---

### 5.2 Create a Group

1. Navigate to **Settings → Groups**.
2. Click **New Group**.
3. Give the group a descriptive name (e.g. `ops-team`, `read-only-auditors`, `deploy-bots`).
4. Click **Save**.

---

### 5.3 Assign Users to a Group

1. Open the group from **Settings → Groups**.
2. Under the **Members** tab, click **Add User**.
3. Search for and select the user(s) to add.
4. Click **Save**.

> Users can belong to multiple groups. Their effective permission on any resource is the highest level granted by any of their groups.

---

### 5.4 Grant Resource Permissions to a Group

Permissions are granted per resource, not globally. You can set a group's access level on any individual Stack, Server, Build, Repo, or Procedure.

1. Open the resource you want to control (e.g. **Stacks → my-stack**).
2. Go to the **Permissions** tab of that resource.
3. Click **Add Group Permission**.
4. Select the group from the dropdown.
5. Choose the permission level: **Read**, **Execute**, or **Write**.
6. Click **Save**.

Repeat for each resource the group should have access to. Resources that have no explicit group permission remain invisible to group members (equivalent to **None**).

> **Note:** Admin users bypass all group-level permission checks and have full access to every resource regardless of group membership.

---

## 6. Periphery Agents

Periphery is the lightweight agent that runs on each managed host. Core communicates with it over a secure WebSocket connection to manage containers, pull images, and stream logs.

### 6.1 Create an Onboarding Key

Onboarding keys allow a new Periphery agent to register itself with Core without requiring you to pre-configure it manually on the Core side.

1. In the UI, go to **Settings → Onboarding Keys**.
2. Click **New Onboarding Key**.
3. Set an optional **Expiry** (recommended: short TTL for one-time use).
4. Copy the generated key — it starts with `O-`.

> Once a Periphery successfully registers, the key is consumed and cannot be reused (depending on your Core config). Revoke unused keys after deployment.

---

### 6.2 Install Periphery on a Remote Host

SSH into the target host and run the official setup script, passing the Core address, the hostname to register as, and the onboarding key:

```bash
curl -sSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py \
  | python3 - \
  --core-address="https://<core-address>" \
  --connect-as="$(hostname)" \
  --onboarding-key="O-..."
```

| Flag | Description |
|---|---|
| `--core-address` | Full HTTPS URL of your Komodo Core instance |
| `--connect-as` | Name the agent registers under in the UI (defaults to hostname) |
| `--onboarding-key` | The `O-...` key generated in step 6.1 |

Once registered, you can target this server in stack deployments, resource monitoring, and terminal access directly from the Komodo UI.

## 7. Resource Sync

Resource Sync allows you to define Komodo resources — Stacks, Builds, Repos, Procedures, and more — as TOML files stored in a Git repository. Komodo periodically polls the repo and reconciles the live state with the declared configuration, giving you a GitOps-style workflow for your entire infrastructure.

### 7.1 How It Works

When a Sync is triggered (manually or on schedule), Komodo:

1. Clones or pulls the configured repo branch.
2. Parses all `.toml` resource files found under the specified path.
3. **Creates** resources that exist in the files but not in Core.
4. **Updates** resources whose configuration has drifted from the file.
5. Optionally **deletes** resources that exist in Core but have been removed from the files (only if `delete_unmanaged` is enabled).

Resources managed by a Sync display a **Sync** badge in the UI and their configuration becomes read-only there — the source of truth is always the repo.

---

### 7.2 Create a Resource Sync

1. Navigate to **Settings → Resource Syncs**.
2. Click **New Resource Sync**.
3. Fill in the fields:

| Field | Description |
|---|---|
| **Name** | Identifier for this sync (e.g. `infra-gitops`) |
| **Git Provider** | The provider configured in Section 3 |
| **Repo** | e.g. `your-org/komodo-resources` |
| **Branch** | e.g. `main` |
| **Resource Path** | Path inside the repo to scan for `.toml` files (e.g. `./resources`) |
| **Delete Unmanaged** | If enabled, removes Core resources not present in the repo |

4. Click **Save**, then click **Sync** to perform the first reconciliation.

---

### 7.3 Stack TOML Example

Each resource type has its own TOML schema. Below is a complete example for a **Stack** resource — the most commonly synced type:

```toml
[[stack]]
name = "my-app"

[stack.config]
server = "my-server"           # Name of the Periphery agent to deploy to

# ── Environment ──────────────────────────────────
# Written to .env before `compose up`. Supports [[VAR]] interpolation.
environment = """
APP_ENV = production
DB_HOST = db
DB_PASS = [[DB_PASSWORD]]   # interpolated from Komodo variable/secret
LOG_LEVEL = info
"""



# ── Lifecycle flags ───────────────────────────────
auto_pull              = true   # `compose pull` before deploy
destroy_before_deploy  = false  # run `compose down` before `compose up`
run_build              = false  # run `docker compose build` before up
skip_secret_interp     = false  # set true to disable [[VAR]] substitution

# ── Update polling ───────────────────────────────
poll_for_updates           = true   # poll images for updates
auto_update                = true   # redeploy automatically when updates found
auto_update_all_services   = false  # if true, redeploys whole stack (not just changed services)

# ── Alerting ──────────────────────────────────────
send_alerts = true


# ── Ignore services ───────────────────────────────
# These service names won't affect stack health status
ignore_services = ["db-migrate", "init"]

# ── Extra compose args ────────────────────────────
extra_args       = ["--remove-orphans"]
build_extra_args = ["--no-cache"]          # only used if run_build = true



# ── Webhook ───────────────────────────────────────
webhook_enabled      = true
webhook_force_deploy = false   # if true, always DeployStack (skips diff check)
webhook_secret       = ""      # leave empty to use global default

## Option A: Inline compose body
compose_contents = """
services:
  app:
    image: ghcr.io/my-org/my-app:[[APP_VERSION]]
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=[[DATABASE_URL]]
      - API_KEY=[[API_KEY]]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.my-app.rule=Host(`[[DOMAIN]]`)"

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: [[DB_PASSWORD]]
      POSTGRES_DB: appdb

volumes:
  db-data:
"""

## Option B: Pull compose file from a Git repo instead of inlining it
# git_provider = "github.com"
# repo          = "my-org/my-app"
# branch        = "main"
# compose_path  = "./docker/compose.yaml"

## Run this stack on a fixed schedule (optional)
# run_order = 1                # Lower numbers deploy first when syncing multiple stacks

## Extra environment injected on top of the compose file (optional)
# environment = [
#   { variable = "LOG_LEVEL", value = "info" },
# ]
```

> **Tip:** Variable interpolation (`[[VAR_NAME]]`) works exactly the same inside synced TOML files as it does in stacks configured through the UI — Komodo resolves them server-side at deploy time using the values stored in **Settings → Variables**.

---



### 7.4 Triggering a Sync

| Method | How |
|---|---|
| **Manual** | Open the Sync in the UI and click **Sync Now** |
| **Webhook** | Configure a push webhook on your Git host pointing to `https://<core>/sync/<sync-name>/webhook` using your `KOMODO_WEBHOOK_SECRET` |
| **Schedule** | Set `KOMODO_RESOURCE_POLL_INTERVAL` in `compose.env` (see Section 1.3) — Core will re-sync on every poll cycle |

> **Note:** The webhook approach is recommended for production — it ensures Core converges within seconds of a commit rather than waiting for the next poll interval.

## 8. GitLab CI Integration
 
Komodo does not have a native GitLab CI integration, but you can connect the two in one of two ways — each with different trade-offs around simplicity and flexibility.
 
---
 
### 8.1 Approach A — GitLab Webhook (Simple, Limited)
 
GitLab can send a webhook to Komodo after a pipeline succeeds, which triggers a stack deploy or a resource sync. This is the simplest setup and requires no scripting, but it has one important limitation: **Komodo must already know about the resource before the webhook fires**, and you cannot pass pipeline-generated values (such as a dynamic image tag built from the branch name or commit SHA) through the webhook payload — Komodo ignores the body and simply triggers whatever action is configured on its end.
 
#### When to use it
 
- Your image tag is static or stored as a Komodo variable that you update separately.
- You only need Komodo to re-pull and redeploy on every push to a branch.
- You want the minimum possible configuration.
#### Setup
 
**In Komodo:**
 
1. Make sure the Stack (or Resource Sync) you want to trigger already exists in the UI.
2. Note the webhook URL for that resource — it follows the pattern:
   ```
   https://<core-address>/stack/<stack-name>/webhook
   ```
   For a Resource Sync it is:
   ```
   https://<core-address>/sync/<sync-name>/webhook
   ```
3. Specify the webhook secret.
**In GitLab:**
 
1. Go to your project → **Settings → Webhooks**.
2. Click **Add new webhook**.
3. Set the **URL** to the Komodo webhook URL above.
4. Under **Secret token**, paste your webhook secret.
5. Under **Trigger**, check **Pipeline events** (fires after a pipeline finishes).
6. Optionally restrict to specific branches using the **Branch filter** field.
7. Click **Save**.
From this point on, every successful pipeline on the configured branch will fire the webhook and Komodo will redeploy the stack using whichever image tag is currently set in its variable store.
 
#### Limitation — no dynamic variables
 
Because Komodo reads the webhook only as a trigger signal, there is no way to pass a value like `IMAGE_TAG=abc123` from the pipeline into the deploy. If your image tag changes per commit, Komodo will redeploy with whatever `[[APP_VERSION]]` is currently set to in **Settings → Variables** — not necessarily the tag that was just built.
 
 
---
### 8.2 Approach B — GitLab CI with Komodo API Calls (Flexible, No UI Required)
 
Instead of relying on webhooks, your pipeline calls the Komodo HTTP API directly. This lets you pass any runtime value — branch name, commit SHA, registry tag — into Komodo as part of the same pipeline that built the image. The trade-off is that it requires a Komodo API key and a few extra `curl` calls in your `.gitlab-ci.yml`.
 
#### Prerequisites
 
- A Komodo API key pair (`API_KEY` + `API_SECRET`). Generate one under **Settings → API Keys**.
- Store both values as **masked CI/CD variables** in GitLab: **Settings → CI/CD → Variables**.
| GitLab Variable | Value |
|---|---|
| `KOMODO_URL` | `https://your-komodo-core-address` |
| `KOMODO_API_KEY` | Your Komodo API key |
| `KOMODO_API_SECRET` | Your Komodo API secret |
 
#### How authentication works
 
Every Komodo API request must include an `X-Api-Key` and `X-Api-Secret` header pair. There are no OAuth flows or token exchanges — just pass the key and secret directly on each request.
 
#### Full `.gitlab-ci.yml` example
 
```yaml
stages:
  - build
  - deploy
 
# ─── Stage 1: Build & Push ────────────────────────────────────────────────────
build:
  stage: build
  image: docker:26
  script:
    - docker login $REGISTRY -u $NEXUS_USER -p $NEXUS_PASS
    - docker build -t $REGISTRY/myapp:$CI_COMMIT_REF_SLUG .
    - docker push $REGISTRY/myapp:$CI_COMMIT_REF_SLUG
  only:
    - main
 
# ─── Stage 2: Deploy ──────────────────────────────────────────────────────────
deploy:
  stage: deploy
  image: alpine:latest
  needs: ["build"]
  before_script:
    - apk add --no-cache curl jq
  script:
    - |
      IMAGE_TAG="$CI_COMMIT_REF_SLUG"
      echo "==> Deploying tag: $IMAGE_TAG"
 
      # ── 1. Check if stack exists ──
      EXISTING=$(curl -s -X POST "${KOMODO_URL}/read" \
        -H "Content-Type: application/json" \
        -H "X-Api-Key: ${KOMODO_API_KEY}" \
        -H "X-Api-Secret: ${KOMODO_API_SECRET}" \
        -d "{\"type\": \"GetStack\", \"params\": {\"stack\": \"${STACK_NAME}\"}}")
 
      STACK_ID=$(echo "$EXISTING" | jq -r '._id["$oid"] // empty')
 
      # ── 2. Create or Update ──
      if [ -z "$STACK_ID" ]; then
        echo "==> Stack not found, creating..."
        RESPONSE=$(jq -n \
          --rawfile compose myapp.compose.yml \
          --arg name "$STACK_NAME" \
          --arg server "$SERVER_NAME" \
          --arg image_tag "$IMAGE_TAG" \
          '{
            "type": "CreateStack",
            "params": {
              "name": $name,
              "config": {
                "server": $server,
                "file_contents": $compose,
                "environment": ("IMAGE_TAG=" + $image_tag)
              }
            }
          }' | curl -s -X POST "${KOMODO_URL}/write" \
            -H "Content-Type: application/json" \
            -H "X-Api-Key: ${KOMODO_API_KEY}" \
            -H "X-Api-Secret: ${KOMODO_API_SECRET}" \
            -d @-)
      else
        echo "==> Stack exists, updating IMAGE_TAG only..."
 
        EXISTING_ENV=$(echo "$EXISTING" | jq -r '.config.environment // ""')
        MERGED_ENV=$(printf '%s' "$EXISTING_ENV" \
          | { grep -v '^IMAGE_TAG=' || true; echo "IMAGE_TAG=${IMAGE_TAG}"; })
 
        RESPONSE=$(jq -n \
          --arg id "$STACK_ID" \
          --arg env "$MERGED_ENV" \
          '{
            "type": "UpdateStack",
            "params": {
              "id": $id,
              "config": {
                "environment": $env
              }
            }
          }' | curl -s -X POST "${KOMODO_URL}/write" \
            -H "Content-Type: application/json" \
            -H "X-Api-Key: ${KOMODO_API_KEY}" \
            -H "X-Api-Secret: ${KOMODO_API_SECRET}" \
            -d @-)
      fi
 
      echo "==> Write response: $RESPONSE"
      echo "$RESPONSE" | jq -e '._id' > /dev/null || { echo "ERROR: Create/Update failed"; exit 1; }
 
      # ── 3. Deploy ──
      echo "==> Deploying..."
      DEPLOY=$(curl -s -X POST "${KOMODO_URL}/execute" \
        -H "Content-Type: application/json" \
        -H "X-Api-Key: ${KOMODO_API_KEY}" \
        -H "X-Api-Secret: ${KOMODO_API_SECRET}" \
        -d "{\"type\": \"DeployStack\", \"params\": {\"stack\": \"${STACK_NAME}\"}}")
 
      echo "==> Deploy response: $DEPLOY"
      echo "$DEPLOY" | jq -e '._id' > /dev/null || { echo "ERROR: Deploy failed"; exit 1; }
 
      echo "==> Done. Tag: ${IMAGE_TAG}"
```
 
#### What each job does
 
`build` logs into your Nexus registry, builds the image tagged with `$CI_COMMIT_REF_SLUG` (the sanitised branch name), and pushes it.
 
`deploy` runs after `build` and handles the full Komodo lifecycle in a single script: it checks whether the stack already exists via `GetStack`, creates it with `CreateStack` (passing `myapp.compose.yml` as the compose file and `IMAGE_TAG` as an environment variable) if it doesn't, or updates only the `IMAGE_TAG` environment variable on the existing stack via `UpdateStack` if it does. Either way it finishes by calling `DeployStack` to roll out the new image. The job exits with an error if any API response is missing the expected `._id` field.
 
---