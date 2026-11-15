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

---

## 5. Protocol: Delegating Long-Running & Heavy Jobs to Oracle VM

To ensure 24/7 continuous execution, prevent laptop sleep/battery dropouts, and leverage the cloud VM's dedicated 24 GB RAM and 4 OCPU, any job meeting the eligibility criteria below **must be delegated to the Oracle Cloud VM**.

### 5.1 Eligibility Criteria for VM Delegation
A job should run on the Oracle Cloud VM rather than local development when:
1. **Duration > 30 minutes**: Multi-month/multi-year clerk backfills, historical MLS snapshots, or statewide tax ingestion.
2. **Rate-Limited Continuous Crawling**: Jobs requiring polite randomized pauses ($1.5\text{s} - 3.2\text{s}$) over hours/days that would be corrupted or cancelled if local Wi-Fi drops or a laptop lid closes.
3. **High Memory / I/O Footprint**: Statewide entity resolution (e.g., Texas Comptroller 3.5M franchise taxpayers), graph clustering, or cross-county geospatial polygon joins requiring large in-memory hash tables.
4. **Nightly Production Cadence**: Scheduled daily ingestion or motivation stacking runs.

### 5.2 Server Access & Endpoints
* **Public IP (Direct):** `ubuntu@155.248.205.250`
* **Private Mesh (Tailscale):** `ubuntu@100.75.240.71`
* **SSH Key:** `~/.ssh/id_oci`
* **Python Runtime:** `.venv/bin/python` under each `/home/ubuntu/rel-*` repository (managed via `uv`).

### 5.3 Delegation Protocol (Standard Operating Procedure)

1. **Local Checkpoint & Flush:**
   If the job is already running locally, terminate it cleanly so in-flight transactions commit:
   ```bash
   kill -TERM <PID>
   sqlite3 data/county.db "PRAGMA wal_checkpoint(TRUNCATE);"
   ```

2. **Code Alignment (Pure Git Pull):**
   Ensure any scraper bug fixes or client improvements are committed and pushed to `main`, then pulled onto the VM:
   ```bash
   git commit -am "fix(extract): resilient connection handling"
   git push origin main
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "cd ~/rel-svc-denton-data && git pull origin main"
   ```

3. **Delta State Transfer (Zero Data Loss):**
   Export newly completed chunks/records from the local database into a transfer SQLite file and merge into the VM database:
   ```bash
   scp -i ~/.ssh/id_oci data/progress_delta.db ubuntu@155.248.205.250:~/rel-svc-denton-data/data/
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "python3 -c '
   import sqlite3
   con = sqlite3.connect(\"data/denton_county.db\")
   con.execute(\"ATTACH \\\"data/progress_delta.db\\\" AS delta\")
   con.execute(\"INSERT OR REPLACE INTO main.raw_clerk_chunks SELECT * FROM delta.raw_clerk_chunks\")
   con.execute(\"INSERT OR REPLACE INTO main.clerk_records SELECT * FROM delta.clerk_records\")
   con.commit()
   '"
   ```

4. **Detached Background Execution:**
   Always launch detached using `nohup` with redirected `stdin` (`< /dev/null`) so the SSH session terminates cleanly without blocking or orphaning the process:
   ```bash
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 'nohup /home/ubuntu/rel-svc-denton-data/.venv/bin/python /home/ubuntu/rel-svc-denton-data/run_clerk.py \
       --start 2024-01-01 --end 2025-12-31 --chunk-days 7 --no-distress \
       > /home/ubuntu/rel-svc-denton-data/data/clerk_backfill.log 2>&1 < /dev/null &'
   ```

5. **Remote Observability:**
   Inspect live progress without interfering with execution:
   ```bash
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "tail -f ~/rel-svc-denton-data/data/clerk_backfill.log"
   ```

6. **Post-Completion Synchronization:**
   When the remote backfill finishes, trigger post-processing on the VM (e.g. `scripts/link_denton_clerk_records.py`), checkpoint WAL, and sync the finalized SQLite database back to the local workspace if needed.
