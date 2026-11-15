# Runbook: Delegating Long-Running Jobs to Oracle Cloud VM

This runbook provides the operational procedure for handing off long-running scrapers, multi-year clerk backfills, large-scale entity resolution models, and heavy data transformations from a local machine to the **Oracle Cloud VM** (`svc-ai`).

---

## 1. When to Delegate (Eligibility Matrix)

| Workflow Characteristics | Local Mac Execution | Delegate to Oracle VM | Rationale |
| :--- | :---: | :---: | :--- |
| **Duration < 15 minutes** (e.g. quick test, single day scrape) | ✅ **Yes** | ❌ No | Low overhead, instant feedback loop. |
| **Duration > 30 minutes** (e.g. multi-year backfill) | ❌ No | ✅ **Yes** | Prevents interruption from laptop sleep, lid closing, or Wi-Fi roaming. |
| **Rate-Limited Continuous Crawling** (WebSocket RPC, polite jitter) | ❌ No | ✅ **Yes** | 24/7 dedicated network uptime with stationary IP address. |
| **High Memory / I/O Footprint** (> 8 GB RAM, multi-million record joins) | ❌ No | ✅ **Yes** | Utilizes the VM's 24 GB RAM and dedicated 4 OCPU Ampere A1 cores. |
| **Nightly Production Ingestion & Scoring** | ❌ No | ✅ **Yes** | Orchestrated via crontab on the VM. |

---

## 2. Infrastructure & Environment Reference

* **Public IP (Direct):** `155.248.205.250`
* **Private Mesh (Tailscale):** `100.75.240.71`
* **User:** `ubuntu`
* **SSH Key:** `~/.ssh/id_oci`
* **Repository Paths on VM:**
  * Standards: `/home/ubuntu/rel-repo-standards`
  * Collin Ingestion: `/home/ubuntu/rel-svc-collin-data`
  * Denton Ingestion: `/home/ubuntu/rel-svc-denton-data`
  * MLS Ingestion: `/home/ubuntu/rel-svc-mls-data`
  * Analytical Core: `/home/ubuntu/rel-aly-works`
* **Python Virtual Environments:** Managed via `uv`, located in `.venv/bin/python` inside each repo.

---

## 3. Step-by-Step Handoff Procedure

### Step 1: Cleanly Stop Any Running Local Worker
If the script is already running locally on your laptop:
```bash
# Gracefully send SIGTERM so the active batch finishes and commits to SQLite
kill -TERM <LOCAL_PID>

# Verify process stopped
ps -p <LOCAL_PID> || echo "Cleanly stopped"

# Flush SQLite WAL pages
sqlite3 data/county.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Step 2: Push Code Updates & Pull on VM
Always maintain exact Git parity. Never copy code files via `scp`:
```bash
# 1. Commit and push on local
git add -A
git commit -m "feat/fix: update pipeline parameters or client logic"
git push origin main

# 2. Pull on Oracle VM
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "cd ~/rel-svc-denton-data && git pull origin main"
```

### Step 3: Export & Merge Progress Delta (Zero Data Loss)
If your local process completed partial work (e.g. 19 completed chunks), transfer only the progress delta:
```bash
# 1. Export locally to a compact transfer SQLite DB
python3 -c '
import sqlite3
con_src = sqlite3.connect("data/denton_county.db")
con_dst = sqlite3.connect("data/progress_delta.db")

# Create schema and copy completed chunks & records
schema_c = con_src.execute("SELECT sql FROM sqlite_master WHERE name=\"raw_clerk_chunks\"").fetchone()[0]
schema_r = con_src.execute("SELECT sql FROM sqlite_master WHERE name=\"clerk_records\"").fetchone()[0]
con_dst.execute(schema_c); con_dst.execute(schema_r)

chunks = con_src.execute("SELECT * FROM raw_clerk_chunks WHERE chunk_id LIKE \"RP_2024%\"").fetchall()
con_dst.executemany("INSERT INTO raw_clerk_chunks VALUES (?,?,?,?,?)", chunks)

records = con_src.execute("SELECT * FROM clerk_records WHERE recorded_date LIKE \"2024%\"").fetchall()
con_dst.executemany("INSERT INTO clerk_records VALUES (" + ",".join(["?"]*len(records[0])) + ")", records)

con_dst.commit()
'

# 2. SCP transfer DB to VM
scp -i ~/.ssh/id_oci data/progress_delta.db ubuntu@155.248.205.250:~/rel-svc-denton-data/data/

# 3. Merge on VM
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "python3 -c '
import sqlite3
con = sqlite3.connect(\"/home/ubuntu/rel-svc-denton-data/data/denton_county.db\")
con.execute(\"ATTACH \\\"/home/ubuntu/rel-svc-denton-data/data/progress_delta.db\\\" AS delta\")
con.execute(\"INSERT OR REPLACE INTO main.raw_clerk_chunks SELECT * FROM delta.raw_clerk_chunks\")
con.execute(\"INSERT OR REPLACE INTO main.clerk_records SELECT * FROM delta.clerk_records\")
con.commit()
'"

# 4. Clean up temporary transfer DB
rm -f data/progress_delta.db
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "rm -f ~/rel-svc-denton-data/data/progress_delta.db"
```

### Step 4: Launch Detached Runner on Oracle VM
To prevent SSH from hanging or terminating the process when your local terminal closes, **you must disconnect stdin/stdout/stderr**:
```bash
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 'nohup /home/ubuntu/rel-svc-denton-data/.venv/bin/python /home/ubuntu/rel-svc-denton-data/run_clerk.py \
    --start 2024-01-01 --end 2025-12-31 --chunk-days 7 --no-distress \
    > /home/ubuntu/rel-svc-denton-data/data/clerk_backfill.log 2>&1 < /dev/null &'
```

---

## 4. Monitoring & Observability Commands

### View Live Streaming Logs:
```bash
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "tail -f -n 50 ~/rel-svc-denton-data/data/clerk_backfill.log"
```

### Inspect Process Status & CPU/RAM Usage:
```bash
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "ps -eo pid,%cpu,%mem,vsz,rss,stat,start,time,command | grep run_clerk.py | grep -v grep"
```

### Check Database Progress & Chunk Count:
```bash
ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "python3 -c '
import sqlite3
con = sqlite3.connect(\"/home/ubuntu/rel-svc-denton-data/data/denton_county.db\")
c = con.execute(\"SELECT COUNT(*) FROM clerk_records\").fetchone()[0]
done = con.execute(\"SELECT COUNT(*) FROM raw_clerk_chunks WHERE status=\\\"COMPLETED\\\"\").fetchone()[0]
print(f\"Total Clerk Records: {c:,} | Completed Chunks: {done}\")
'"
```

---

## 5. Post-Completion Handoff & Synchronization

When the background process completes:

1. **Run Post-Processing Linking on VM:**
   ```bash
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "cd ~/rel-svc-denton-data && .venv/bin/python scripts/link_denton_clerk_records.py"
   ```

2. **Truncate WAL on VM:**
   ```bash
   ssh -i ~/.ssh/id_oci ubuntu@155.248.205.250 "sqlite3 /home/ubuntu/rel-svc-denton-data/data/denton_county.db 'PRAGMA wal_checkpoint(TRUNCATE);'"
   ```

3. **Sync Final Database to Local Workspace:**
   ```bash
   rsync -avzP -e "ssh -i ~/.ssh/id_oci" \
       ubuntu@155.248.205.250:/home/ubuntu/rel-svc-denton-data/data/denton_county.db \
       /Users/sai/Github/rel-svc-denton-data/data/denton_county.db
   ```

---

## 6. Common Pitfalls & Solutions

1. **SSH Session Hangs on Launch:**
   * *Cause:* `nohup` keeps stdin attached to the SSH terminal.
   * *Fix:* Always redirect stdin from `/dev/null` (`< /dev/null &`).

2. **Database Locked (`sqlite3.OperationalError: database is locked`):**
   * *Cause:* Two competing processes attempting concurrent writes, or journal mode set to `DELETE` instead of `WAL`.
   * *Fix:* Ensure WAL mode is active: `PRAGMA journal_mode=WAL;`, and verify only one backfill runner is active (`ps aux | grep run_clerk`).

3. **Tyler PublicSearch WebSocket Disconnects:**
   * *Cause:* Idle socket timeout or server-side cookie expiration during multi-hour jobs.
   * *Fix:* Enforce session refresh with exponential backoff retries (`fetch_documents_with_retry` in `src/extract/clerk_client.py`).
