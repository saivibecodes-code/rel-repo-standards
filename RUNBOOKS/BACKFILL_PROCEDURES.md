# Runbook: Historical Backfill Procedures

This runbook documents how to execute large-scale historical backfills across county clerk and tax systems safely without triggering anti-bot gates or crashing memory.

---

## 1. Pre-Flight Preparation

1. **Verify Database Disk Space:**
   Ensure at least 5 GB of free NVMe space on the host (local machine or Oracle VM):
   ```bash
   df -h /home/ubuntu
   ```
2. **Ensure WAL Mode Active:**
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   ```
3. **Verify Chunk Partition Table Exists:**
   ```sql
   SELECT count(*) FROM raw_clerk_chunks;
   ```

---

## 2. Executing Polite Backfill

Always invoke the backfill runner with polite rate limiting and date chunking:

```bash
# Example: Backfill Denton County for full year 2026
.venv/bin/python3 run_clerk.py \
    --start 2026-01-01 \
    --end 2026-08-31 \
    --reverse \
    --delay-min 1.8 \
    --delay-max 3.2 \
    --batch-size 100 \
    --chunk-days 7
```

### Parameter Explanations:
* `--reverse`: Crawls backwards from latest records to oldest records. This guarantees that if the process is stopped early, you have already captured the newest and most relevant recordings.
* `--delay-min 1.8 --delay-max 3.2`: Enforces randomized human-like jitter between requests.
* `--batch-size 100`: Polite UI pagination size that does not stress the upstream server.
* `--chunk-days 7`: Segments the extraction into 7-day resumable checkpoints.

---

## 3. Running Detached on Oracle VM

For long-running backfills (>1 hour), always execute detached under `nohup`:

```bash
mkdir -p logs
nohup .venv/bin/python3 run_clerk.py \
    --start 2026-01-01 \
    --end 2026-08-31 \
    --reverse \
    --delay-min 1.8 \
    --delay-max 3.2 \
    --batch-size 100 > logs/clerk_backfill.log 2>&1 &
```

### Monitoring Detached Run:
```bash
# Monitor live output
tail -f logs/clerk_backfill.log

# Check running process
ps aux | grep run_clerk

# Check database record count
sqlite3 data/denton_county.db "SELECT count(*) FROM clerk_records;"
```

---

## 4. Interruptions & Resuming

If a backfill is interrupted (network drop, server restart, or process killed):
1. **Zero Data Loss:** All completed 7-day chunks are recorded as `'COMPLETED'` in `raw_clerk_chunks`.
2. **Instant Resume:** Re-launching the exact same command will query `raw_clerk_chunks`, skip every completed chunk, and immediately resume from the exact interrupted chunk.
