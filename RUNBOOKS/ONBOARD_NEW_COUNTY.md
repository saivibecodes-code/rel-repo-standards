# Runbook: Onboarding a New County Ingestion Microservice

This runbook provides the step-by-step procedure for scaffolding and integrating a new county into the `rel-*` platform (e.g. `rel-svc-tarrant-data` or `rel-svc-dallas-data`).

---

## 1. Naming & Scaffolding Convention

* **Repository Name:** `rel-svc-<county>-data` (e.g., `rel-svc-tarrant-data`)
* **Database Name:** `data/<county>_county.db` (e.g., `data/tarrant_county.db`)
* **County Code:** Standardized uppercase identifier (e.g., `'TARRANT'`, `'DALLAS'`)

### Directory Layout
```
rel-svc-<county>-data/
├── pyproject.toml
├── .gitignore                      # Must include data/, *.db, *.DAT, *.zip
├── README.md
├── Makefile
├── run_all.py                      # Master pipeline entrypoint
├── deploy/
│   └── sync_to_vm.sh               # Pure git pull deployment
├── src/
│   ├── extract/
│   │   ├── cad_downloader.py       # CAD bulk download or API client
│   │   ├── tax_collector.py        # Delinquent tax account collector
│   │   └── clerk_collector.py      # Deed/lien scraper with rate-limiting
│   ├── transform/
│   │   ├── cad_parser.py           # Normalizer to canonical parcel_master
│   │   └── raw_loader.py           # SQLite database schema initializer
│   └── common/
│       └── universal_id.py         # SHA256 UniversalID generator
└── tests/
```

---

## 2. Ingestion Checklist

### Step 1: CAD Property Roll Extraction
* Locate the appraisal district's public data portal (e.g. Tarrant Appraisal District TAD exports, Dallas CAD open data).
* Download the annual tax roll or bulk parcel file.
* Parse into canonical `parcel_master` table adhering to [`DATA_CONTRACTS.md`](file:///Users/sai/Github/rel-repo-standards/DATA_CONTRACTS.md).
* Compute `universal_id` for every record using `generate_universal_id('<COUNTY>', prop_id)`.

### Step 2: County Clerk Public Records Integration
* Identify the vendor portal (Tyler Technologies PublicSearch, Kofile QuickSearch, TexasFile, County Clerk search).
* Build an async client:
  - If Tyler PublicSearch: Implement WebSocket RPC `@kofile/FETCH_DOCUMENTS/v4`.
  - If HTML Form portal: Use Playwright or headless HTTP requests with browser headers.
* Implement 7-day resumable chunking with `raw_clerk_chunks`.
* Apply polite jitter ($1.8\text{s} - 3.2\text{s}$ per batch request) and inter-chunk rest ($4\text{s} - 8\text{s}$).

### Step 3: Fast Set-Based Resolution
* Implement 3-pass set-based SQL resolution to populate `clerk_records.matched_universal_id` against `parcel_master`.
* Never perform row-by-row queries across CAD parcels.

### Step 4: Delinquent Tax Collection
* Extract or scrape the county tax assessor-collector delinquent tax rolls.
* Persist to `raw_tax_delinquent_accounts` or `tax_delinquency` and resolve against `parcel_master`.

### Step 5: Downstream Connector Integration
* Open [rel-aly-works/src/connectors/](file:///Users/sai/Github/rel-aly-works/src/connectors/) in `rel-aly-works`.
* Add a new county connector class `TarrantCountyConnector` pointing to `../rel-svc-tarrant-data/data/tarrant_county.db`.
* Register in `motivation_engine.py` to fold the new county into cross-county motivation stacking.

### Step 6: Oracle VM Deployment & Crontab
* Clone repo to `/home/ubuntu/rel-svc-<county>-data` on Oracle VM.
* Run `uv sync` to configure `.venv`.
* Add daily cron entry prior to `rel-aly-works` execution (e.g. 06:00 UTC).
