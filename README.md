# rel-repo-standards

> **The Single Source of Truth for Architecture, Data Contracts, Scraper Engineering, Operational Runbooks, and Knowledge across the `rel-*` Real Estate Intelligence Ecosystem.**

---

## 1. Mission & Ecosystem Map

The `rel-*` suite is an autonomous, cross-county off-market real estate intelligence engine operating across North Texas (Collin, Denton, and regional DFW). It ingests public CAD property rolls, tax delinquency rolls, county clerk deed & lien filings, probate heirships, and MLS listings to score and rank properties under a **multi-factor motivation stacking model**.

```
                           UPSTREAM SOURCES
   [ Collin CAD & Tax ]   [ Denton CAD & Tyler PublicSearch ]   [ NTREIS MLS Data ]
            │                              │                             │
            ▼                              ▼                             ▼
┌──────────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│  rel-svc-collin-data │       │  rel-svc-denton-data │       │   rel-svc-mls-data   │
│ (County Ingestion)   │       │ (County Ingestion)   │       │ (Listings & Comps)   │
└──────────┬───────────┘       └──────────┬───────────┘       └──────────┬───────────┘
           │ `collin_county.db`           │ `denton_county.db`           │ `mls_data.db`
           └──────────────────────┬───────┴──────────────────────────────┘
                                  ▼
                     ┌──────────────────────────┐
                     │      rel-aly-works       │
                     │  (Analytical Core & GIS) │
                     └────────────┬─────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    ▼                             ▼                             ▼
[ Motivation Engine ]    [ Localized ISD / Zip ]      [ Geospatial Enriched ]
(Stacked Distress Leads) (Market Trends & Parity)    (GeoJSON & Map Exports)
```

### The Repositories

| Repository | Responsibility | Output Database / Artifacts | Deployment Target |
| :--- | :--- | :--- | :--- |
| [**`rel-repo-standards`**](https://github.com/saivibecodes-code/rel-repo-standards) | Ecosystem blueprint, canonical schemas, scraping etiquette, operational runbooks, and linting tools. | Architectural specs, validation CLI scripts. | Local & Oracle VM |
| [**`rel-aly-works`**](https://github.com/saivibecodes-code/rel-aly-works) | Downstream analytical engine, motivation stacking scoring, ISD/ZCTA localized intelligence, GIS spatial queries, and reporting exports. | `data/distress_leads.db`, GeoJSON summaries, executive CLI reports. | Oracle VM (`07:30 UTC`) |
| [**`rel-svc-denton-data`**](https://github.com/saivibecodes-code/rel-svc-denton-data) | Denton County CAD property master, tax delinquent accounts, and Tyler PublicSearch WebSocket RPC historical recordings. | `data/denton_county.db` | Oracle VM (`06:30 UTC`) |
| [**`rel-svc-collin-data`**](https://github.com/saivibecodes-code/rel-svc-collin-data) | Collin County CAD parcel rolls, tax assessor delinquencies, and clerk lien/deed records. | `data/collin_county.db` | Oracle VM (`07:00 UTC`) |
| [**`rel-svc-mls-data`**](https://github.com/saivibecodes-code/rel-svc-mls-data) | Real-time and historical MLS listing ingestion (days on market, status changes, absorption, price drops). | `data/mls_data.db` | Oracle VM |

---

## 2. Core Architectural Principles

1. **Strict Zero Data in Git Policy:**
   * Git tracks code, test fixtures, operational scripts, and minimal status metadata (`monitoring/last_success.json`).
   * Databases (`*.db`, `*.sqlite*`), raw archives (`*.DAT`, `*.zip`, `*.tar.gz`), and bulky CSV/Parquet files **must never be committed to Git**.
   * Large databases are synced out-of-band via SSH `rsync` or cloud object storage.

2. **Microservice Separation (Extract/Persist vs. Analytical Synthesis):**
   * `rel-svc-*` microservices are **county-bound extractors**. Their only job is to extract raw records, normalize them to canonical schemas, resolve Universal IDs, and persist them into their local SQLite database. They do **not** perform cross-county analytics.
   * `rel-aly-works` is the **consumer and aggregator**. It reads normalized databases, applies the cross-county Motivation Stacking Engine, merges geographic boundaries (ISD, City, ZCTA), and exports final actionable intelligence.

3. **Deterministic Universal Property Identifiers:**
   * Every parcel across all counties has a globally unique, immutable 16-character hexadecimal identifier:
     $$\text{UniversalID} = \text{SHA256}(\text{COUNTY\_ID} + \text{"\_"} + \text{CLEAN\_PROP\_ID})[:16]$$
   * Guarantees collision-free cross-county joins.

4. **Polite, Non-Suspicious Scraping Protocols:**
   * Public county portals must be scraped with randomized jitter ($1.8\text{s} - 3.2\text{s}$), UI-sized batch pagination ($\le 100$ records), inter-chunk pauses ($4\text{s} - 8\text{s}$), and headless session token rotation.
   * Every scraper must be fully resumable via partition chunk tables (`raw_clerk_chunks`).

5. **Set-Based SQL Resolution over Row-by-Row Loops:**
   * Never execute unindexed $O(N)$ row-by-row queries across 380,000+ parcels. Always compile batch lookups into set-based indexed SQL `JOIN`s or `UPDATE ... FROM` passes.

---

## 3. Repository Documentation Map

* [**`ARCHITECTURE.md`**](file:///Users/sai/Github/rel-repo-standards/ARCHITECTURE.md) — Detailed pipeline topography, data lifecycle, and technology choices.
* [**`DATA_CONTRACTS.md`**](file:///Users/sai/Github/rel-repo-standards/DATA_CONTRACTS.md) — Canonical SQLite schemas (`parcel_master`, `clerk_records`, `distress_stacked_leads`, `raw_clerk_chunks`).
* [**`MOTIVATION_SCORING.md`**](file:///Users/sai/Github/rel-repo-standards/MOTIVATION_SCORING.md) — Distress signal weights, probate urgency, HOA lien threat levels, and stacking formulas.
* [**`SCRAPING_STANDARDS.md`**](file:///Users/sai/Github/rel-repo-standards/SCRAPING_STANDARDS.md) — WebSocket RPC handling, anti-bot mitigation, polite rate limiting, and date chunking.
* [**`OPS_AND_INFRASTRUCTURE.md`**](file:///Users/sai/Github/rel-repo-standards/OPS_AND_INFRASTRUCTURE.md) — Oracle Cloud VM specifications, SSH deploy keys, cron matrix, and pure Git pull deployment.

### Runbooks (`RUNBOOKS/`)

* [**`ONBOARD_NEW_COUNTY.md`**](file:///Users/sai/Github/rel-repo-standards/RUNBOOKS/ONBOARD_NEW_COUNTY.md) — Complete guide to scaffolding and adding a new county extractor (`rel-svc-tarrant-data`, `rel-svc-dallas-data`).
* [**`BACKFILL_PROCEDURES.md`**](file:///Users/sai/Github/rel-repo-standards/RUNBOOKS/BACKFILL_PROCEDURES.md) — How to safely execute multi-month/multi-year historical backfills.
* [**`SMOKE_TESTS_AND_HEALTHCHECKS.md`**](file:///Users/sai/Github/rel-repo-standards/RUNBOOKS/SMOKE_TESTS_AND_HEALTHCHECKS.md) — Verifying end-to-end pipeline health on local and cloud VM.
* [**`DISASTER_RECOVERY.md`**](file:///Users/sai/Github/rel-repo-standards/RUNBOOKS/DISASTER_RECOVERY.md) — Point-in-time recovery, WAL checkpoints, and cross-machine syncing.

---

## 4. Quickstart & Verification Tools

This repository contains standalone verification scripts to ensure that all `rel-*` repositories adhere to the ecosystem standards.

```bash
# Clone the repository standards
git clone https://github.com/saivibecodes-code/rel-repo-standards.git
cd rel-repo-standards

# Install dev dependencies
uv sync

# Run the structural compliance linter across all sibling repos
uv run python checks/check_repo_structure.py

# Verify database schemas and data contract compliance
uv run python checks/check_db_integrity.py /path/to/denton_county.db
```
