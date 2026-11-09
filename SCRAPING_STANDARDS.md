# Scraping Standards & Anti-Bot Etiquette

This document establishes mandatory engineering rules for building and running county portal web scrapers across the `rel-*` platform.

---

## 1. The Polite Scraper Philosophy

Public government portals (County Clerks, District Clerks, Appraisal Districts) provide vital public data under the Texas Public Information Act. However, aggressive, unthrottled scrapers risk degrading public services, incurring Cloudflare/WAF IP bans, or tripping CAPTCHA verification challenges.

**Mandatory Rule:** All scrapers must behave identically to a polite human browsing the site.

---

## 2. Core Operational Rules

### 2.1. Randomized Uniform Jitter
* **Never use fixed sleep intervals** (e.g. `time.sleep(2.0)`). Fixed intervals create distinct frequency spikes detectable by WAF behavioral anomaly models.
* **Always use randomized uniform jitter:**
  ```python
  import random
  import time

  # Pacing between individual page/batch requests
  delay = random.uniform(1.8, 3.2)
  time.sleep(delay)
  ```

### 2.2. Human Batch Sizing
* Set page/batch requests to standard UI pagination sizes ($\le 100$ records per request).
* Requesting 1,000+ records in a single payload triggers backend memory limits and flags automated scrapers.

### 2.3. Inter-Chunk Pauses
* When iterating across historical date intervals (e.g. 7-day windows), introduce an extended resting pause between intervals:
  ```python
  chunk_rest = random.uniform(4.0, 8.0)
  time.sleep(chunk_rest)
  ```

### 2.4. Headless Session Recycling
* WebSocket sessions (e.g., Tyler PublicSearch `@kofile/FETCH_DOCUMENTS/v4`) and HTTP cookies expire or degrade after extended continuous polling.
* Scrapers must gracefully recycle session tokens and cookie headers every 15–20 completed chunks.

---

## 3. Resumable Chunking Protocol

Every bulk extraction job must be partitionable into small, discrete, idempotent chunks tracked in the `raw_clerk_chunks` table:

```
[ Chunk 1: Jan 1 - Jan 7 ]  ==> Status: COMPLETED (3,240 docs)
[ Chunk 2: Jan 8 - Jan 14 ] ==> Status: COMPLETED (2,890 docs)
[ Chunk 3: Jan 15 - Jan 21 ]==> Status: IN_PROGRESS (1,500 docs)  <-- If interrupted,
                                                                       resumes here!
```

### Partition Algorithm
1. Break target date ranges into 7-day windows.
2. Query `SELECT chunk_id FROM raw_clerk_chunks WHERE status = 'COMPLETED'`.
3. Filter out completed chunks. Only process pending chunks.
4. Support `--reverse` flag to allow backwards crawling (fetching the freshest records first before backfilling historical records).

---

## 4. Set-Based SQL Resolution vs. Row-by-Row Loops

### The Trap: $O(N \times M)$ Row-by-Row Lookups
In early iterations, scrapers attempted to match incoming clerk documents to parcels by running a query for each document:
```python
# ANTI-PATTERN: DO NOT DO THIS
for doc in fetched_docs:
    cursor.execute(
        "SELECT universal_id FROM parcel_master WHERE last_deed_instrument LIKE ?",
        (f"%{doc['inst_number']}%",)
    )
```
* With 381,000 parcels in `parcel_master` and 200 documents per batch, this forced **38,000,000 row scans per batch**, pegging CPU at 100% and causing scrapers to grind to a halt.

### The Standard: 3-Pass Set-Based Resolution
All scrapers must ingest raw documents directly into the database first, create indexes, and execute set-based SQL `JOIN` updates:

```sql
-- Pass 1: Exact instrument number join
UPDATE clerk_records
SET matched_universal_id = (
    SELECT pm.universal_id
    FROM parcel_master pm
    WHERE pm.last_deed_instrument = clerk_records.instrument_number
    LIMIT 1
)
WHERE matched_universal_id IS NULL AND instrument_number IS NOT NULL;

-- Pass 2: Cleaned instrument number join (strip leading zeros / prefixes)
UPDATE clerk_records
SET matched_universal_id = (
    SELECT pm.universal_id
    FROM parcel_master pm
    WHERE LTRIM(pm.last_deed_instrument, '0') = LTRIM(clerk_records.instrument_number, '0')
    LIMIT 1
)
WHERE matched_universal_id IS NULL AND instrument_number IS NOT NULL;
```
* **Result:** Execution time dropped from 35 seconds per batch to **0.024 seconds** across 100,000+ records.
