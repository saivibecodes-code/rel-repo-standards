# Runbook: Disaster Recovery & Database Synchronization

This runbook covers database recovery, safe out-of-band backups, and WAL synchronization.

---

## 1. The Strict Zero-Data Git Rule

* **Code is tracked in Git.**
* **Data is NEVER tracked in Git.**
* If a repository's database is accidentally deleted or corrupted, Git cannot restore it. Recovery relies on out-of-band SQLite database backups.

---

## 2. Safe Database Copying & WAL Checkpointing

SQLite in WAL mode splits data across three files:
* `database.db` (The main database file)
* `database.db-wal` (Write-Ahead Log containing recent uncommitted/unmerged pages)
* `database.db-shm` (Shared-memory index for the WAL)

### Mandatory Checkpoint Procedure
Before copying or syncing any SQLite database to another machine or backup store, **always force a WAL checkpoint to truncate and flush all WAL frames into the main `.db` file**:

```python
import sqlite3

def checkpoint_db(db_path: str):
    conn = sqlite3.connect(db_path)
    # TRUNCATE checkpoints all frames and shrinks WAL to 0 bytes
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.close()
    print(f"[✓] Checkpointed and truncated WAL for {db_path}")
```

Once checkpointed, only `database.db` needs to be copied.

---

## 3. Cross-Machine Syncing via `rsync`

To transfer a compiled database between your local development machine and the Oracle Cloud VM:

### Local $\rightarrow$ Oracle VM:
```bash
# 1. Truncate WAL locally
sqlite3 data/denton_county.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 2. Rsync directly over SSH with compression and progress
rsync -avzP -e "ssh -i ~/.ssh/id_oci" \
    data/denton_county.db \
    ubuntu@100.75.240.71:/home/ubuntu/rel-svc-denton-data/data/denton_county.db
```

### Oracle VM $\rightarrow$ Local:
```bash
# 1. Truncate WAL on VM
ssh -i ~/.ssh/id_oci ubuntu@100.75.240.71 \
    "sqlite3 /home/ubuntu/rel-svc-denton-data/data/denton_county.db 'PRAGMA wal_checkpoint(TRUNCATE);'"

# 2. Rsync to local
rsync -avzP -e "ssh -i ~/.ssh/id_oci" \
    ubuntu@100.75.240.71:/home/ubuntu/rel-svc-denton-data/data/denton_county.db \
    data/denton_county.db
```

---

## 4. Recovering from Interrupted Scrapes or Corrupted Tables

If an unexpected crash or network partition occurs during a backfill:

1. **Verify Integrity:**
   ```sql
   PRAGMA integrity_check;
   ```
   * If `ok`, the database is healthy.
2. **Examine Last Chunk in `raw_clerk_chunks`:**
   ```sql
   SELECT chunk_id, status, last_attempt 
   FROM raw_clerk_chunks 
   ORDER BY last_attempt DESC 
   LIMIT 5;
   ```
3. **Reset Stuck Chunks:**
   If a chunk is stuck in `'IN_PROGRESS'`:
   ```sql
   UPDATE raw_clerk_chunks 
   SET status = 'PENDING' 
   WHERE status = 'IN_PROGRESS';
   ```
4. **Re-run the Scraper:**
   Re-running `run_clerk.py` will automatically pick up where it left off.
