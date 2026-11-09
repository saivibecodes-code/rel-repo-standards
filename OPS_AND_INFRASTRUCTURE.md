# Operations, Infrastructure & Deployment Standards

This document outlines the deployment topography, server configurations, automated crontab execution, and deployment procedures for the `rel-*` platform.

---

## 1. Oracle Cloud VM Infrastructure

Production pipelines run on an Oracle Cloud Infrastructure (OCI) Compute Instance:

* **Host Alias / IP:** `ubuntu@100.75.240.71` (Tailscale private mesh IP)
* **Architecture:** Ampere A1 (ARM64 / aarch64)
* **Operating System:** Ubuntu 22.04 LTS
* **Specs:** 4 OCPU, 24 GB RAM, 200 GB NVMe Storage
* **Python Runtime:** Python 3.10 via `uv` (`~/.local/share/uv/python/cpython-3.10-linux-aarch64-gnu/bin/python3.10`)
* **Base Directory:** `/home/ubuntu/`

### Directory Layout on VM
```
/home/ubuntu/
├── rel-repo-standards/          # Ecosystem documentation, runbooks, and linting
├── rel-svc-collin-data/         # Collin County Ingestion microservice
│   ├── .venv/
│   ├── data/collin_county.db    # Collin SQLite database (WAL)
│   └── logs/
├── rel-svc-denton-data/         # Denton County Ingestion microservice
│   ├── .venv/
│   ├── data/denton_county.db    # Denton SQLite database (WAL)
│   └── logs/
├── rel-svc-mls-data/            # MLS Ingestion microservice
│   ├── .venv/
│   ├── data/mls_data.db
│   └── logs/
└── rel-aly-works/               # Analytical Core & Downstream Intelligence
    ├── .venv/
    ├── data/distress_leads.db   # Canonical cross-county leads
    └── logs/
```

---

## 2. Automated Crontab Schedule

The ingestion and analytical pipelines run daily on an orchestrated schedule:

```cron
# ==============================================================================
# rel-* Real Estate Intelligence Daily Orchestration Pipeline (UTC)
# ==============================================================================

# 1. Denton County Ingestion (Tax Assessor + Clerk Recordings)
30 06 * * * cd /home/ubuntu/rel-svc-denton-data && .venv/bin/python3 run_all.py >> logs/cron_denton.log 2>&1

# 2. Collin County Ingestion (CAD Parcels + Deeds & Liens)
00 07 * * * cd /home/ubuntu/rel-svc-collin-data && .venv/bin/python3 run_all.py >> logs/cron_collin.log 2>&1

# 3. Analytical Synthesis Core (Motivation Stacking & Parity Reports)
30 07 * * * /home/ubuntu/svc-repo-standards/ops/bin/run_pipeline.sh rel-aly-works >> /home/ubuntu/rel-aly-works/logs/cron_analytics.log 2>&1
```

* **Sequencing Rationale:** Upstream county ingestion microservices run first (06:30 – 07:00 UTC). Once county databases are updated with the latest recordings, the downstream analytical core triggers at 07:30 UTC to synthesize motivation leads and refresh localized reports.

---

## 3. Pure Git Pull Deployment Workflow

All deployments from local development to the Oracle VM execute strictly via **pure Git pull over SSH deploy keys**.

### Requirements
* No `rsync` or `scp` for source code files. Code state on the VM must exactly match `origin/main`.
* Each repository has a dedicated deploy script (`deploy/sync_to_vm.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="ubuntu@100.75.240.71"
REMOTE_DIR="/home/ubuntu/rel-aly-works"
SSH_KEY="$HOME/.ssh/id_oci"

ssh -i "$SSH_KEY" "$REMOTE_HOST" "
    cd $REMOTE_DIR
    git fetch origin main
    git pull origin main
    git log -1 --oneline
"
```

---

## 4. Strict Zero Data in Git Rule

Under no circumstances may database files, binary dumps, or archives be committed to Git:
1. Every repo must ignore `data/`, `*.db`, `*.sqlite*`, `*.DAT`, `*.zip`, `*.tar.gz`, `*.parquet`.
2. Initial database hydration or cross-machine syncing must occur out-of-band via SSH `rsync`:
   ```bash
   rsync -avzP -e "ssh -i ~/.ssh/id_oci" /local/path/data/county.db ubuntu@100.75.240.71:/remote/path/data/county.db
   ```
3. SQLite WAL Checkpoint: Always run `PRAGMA wal_checkpoint(TRUNCATE);` before copying a database file to ensure zero unflushed WAL pages.
