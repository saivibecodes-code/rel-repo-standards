# Runbook: Smoke Tests & Health Checks

This runbook outlines how to verify pipeline integrity, database consistency, and microservice health across local and cloud environments.

---

## 1. Automated Smoke Test on Oracle VM

The standard execution harness on the Oracle VM is `ops/bin/run_pipeline.sh`:

```bash
# SSH into Oracle VM
ssh -i ~/.ssh/id_oci ubuntu@100.75.240.71

# Execute smoke test on rel-aly-works
/home/ubuntu/svc-repo-standards/ops/bin/run_pipeline.sh rel-aly-works

# Check pipeline exit status
echo $?
```

* **Expected Output:** `Pipeline completed successfully` (Return Code: 0).
* **Artifacts Generated:** `monitoring/last_success.json` updated with timestamp and execution summary.

---

## 2. Database Health Audits

Run the standalone database auditor to verify table counts and foreign key linkages:

```bash
# Run database integrity check
uv run python checks/check_db_integrity.py /home/ubuntu/rel-svc-denton-data/data/denton_county.db
```

### Manual SQL Health Checks:

```sql
-- 1. Check total parcels & homestead percentage
SELECT 
    count(*) AS total_parcels,
    SUM(CASE WHEN homestead_flag = 1 THEN 1 ELSE 0 END) AS homestead_count,
    ROUND(AVG(market_val), 0) AS avg_market_val
FROM parcel_master;

-- 2. Check total recorded deeds, mortgages, and distress filings
SELECT 
    doc_type, 
    count(*) AS total_docs,
    SUM(CASE WHEN matched_universal_id IS NOT NULL THEN 1 ELSE 0 END) AS matched_to_cad
FROM clerk_records
GROUP BY doc_type
ORDER BY total_docs DESC
LIMIT 15;

-- 3. Check for orphan Universal IDs in distress leads
SELECT count(*) 
FROM distress_stacked_leads 
WHERE universal_id NOT IN (SELECT universal_id FROM parcel_master);
-- Expected: 0 orphans
```

---

## 3. Structural Repository Linter

To verify that all `rel-*` repositories follow standard conventions (`.gitignore` zero-data rule, `pyproject.toml`, `deploy/sync_to_vm.sh`, etc.):

```bash
uv run python checks/check_repo_structure.py
```
