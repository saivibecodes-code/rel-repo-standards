#!/usr/bin/env bash
# ==============================================================================
# rel-* Ecosystem Health Check and Database Audit Script
# ==============================================================================
set -euo pipefail

BASE_DIR="${1:-/home/ubuntu}"

echo "=============================================================================="
echo "  AUDITING REL-* PLATFORM DATABASES & INTEGRITY"
echo "  Base Directory: ${BASE_DIR}"
echo "=============================================================================="

audit_db() {
    local db_path="$1"
    local name="$2"

    if [ -f "$db_path" ]; then
        echo -e "\n[*] Database: ${name} (${db_path})"
        local size
        size=$(du -h "$db_path" | cut -f1)
        echo "    Size: ${size}"

        python3 -c "
import sqlite3
try:
    con = sqlite3.connect('${db_path}')
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
    print('    Tables (' + str(len(tables)) + '): ' + ', '.join(tables))
    for t in ['parcel_master', 'clerk_records', 'distress_stacked_leads', 'raw_clerk_chunks']:
        if t in tables:
            cnt = cur.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
            print(f'      - {t}: {cnt:,} records')
    con.close()
except Exception as e:
    print('    Error querying db:', e)
"
    else
        echo -e "\n[!] Database NOT found: ${db_path}"
    fi
}

audit_db "${BASE_DIR}/rel-svc-denton-data/data/denton_county.db" "Denton County Data"
audit_db "${BASE_DIR}/rel-svc-collin-data/data/collin_county.db" "Collin County Data"
audit_db "${BASE_DIR}/rel-aly-works/data/distress_leads.db" "Analytical Motivation Leads"

echo -e "\n=============================================================================="
echo "  AUDIT COMPLETE"
echo "=============================================================================="
