# Canonical Data Contracts & Schema Specifications

This document defines the strict, cross-county data contracts implemented by all `rel-*` repositories.

---

## 1. Universal Property Identifier (`UniversalID`)

All real estate properties across all Texas counties are addressed by a deterministic, collision-resistant 16-character hexadecimal identifier derived from the SHA-256 hash of the normalized county code and property account number:

$$\text{UniversalID} = \text{SHA256}(\text{COUNTY\_CODE} + \text{"\_"} + \text{CLEAN\_PROP\_ID})[:16]$$

### Python Implementation
```python
import hashlib
import re

def generate_universal_id(county_code: str, raw_prop_id: str | int) -> str:
    """Generate deterministic 16-character Universal Property ID.
    
    Args:
        county_code: Standardized 2-letter or 3-letter county code (e.g. 'COLLIN', 'DENTON', 'TARRANT', 'DALLAS')
        raw_prop_id: The county appraisal district property or account number
    """
    clean_id = re.sub(r"[^A-Za-z0-9]", "", str(raw_prop_id)).upper()
    key = f"{county_code.strip().upper()}_{clean_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
```

---

## 2. Canonical Tables

### 2.1. `parcel_master`
The central registry of real property parcels within a county appraisal district.

```sql
CREATE TABLE IF NOT EXISTS parcel_master (
    universal_id        TEXT PRIMARY KEY,
    county_id           TEXT NOT NULL,          -- e.g. 'DENTON', 'COLLIN'
    prop_id             TEXT NOT NULL,          -- CAD internal property / quick-ref ID
    account_number      TEXT,                   -- Geo ID / Account Number
    owner_name          TEXT,                   -- Primary owner of record
    owner_address       TEXT,                   -- Mailing street address
    owner_city          TEXT,                   -- Mailing city
    owner_state         TEXT,                   -- Mailing 2-letter state code
    owner_zip           TEXT,                   -- Mailing 5-digit zip code
    situs_address       TEXT,                   -- Physical property street address
    situs_city          TEXT,                   -- Physical city
    situs_zip           TEXT,                   -- Physical zip code
    legal_description   TEXT,                   -- Formal plat legal description
    property_use_code   TEXT,                   -- Property class (e.g. 'A1', 'B1', 'C1')
    property_type       TEXT,                   -- 'RESIDENTIAL', 'COMMERCIAL', 'VACANT', 'AG'
    appraised_val       NUMERIC DEFAULT 0,      -- CAD appraised total value
    market_val          NUMERIC DEFAULT 0,      -- CAD market valuation
    assessed_val        NUMERIC DEFAULT 0,      -- CAD assessed valuation (after exemptions)
    improvement_val     NUMERIC DEFAULT 0,      -- Value of structures
    land_val            NUMERIC DEFAULT 0,      -- Value of raw land
    year_built          INTEGER,                -- Primary structure construction year
    living_area_sqft    NUMERIC,                -- Gross heated/cooled living square footage
    land_area_acres     NUMERIC,                -- Total lot size in acres
    homestead_flag      INTEGER DEFAULT 0,      -- 1 if primary residence homestead exemption active
    school_district     TEXT,                   -- ISD name (e.g. 'FRISCO ISD', 'PLANO ISD')
    latitude            REAL,                   -- WGS84 latitude coordinate
    longitude           REAL,                   -- WGS84 longitude coordinate
    last_deed_date      TEXT,                   -- Most recent recorded transfer date (YYYY-MM-DD)
    last_deed_instrument TEXT,                  -- Instrument number of last deed
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pm_prop_id ON parcel_master(prop_id);
CREATE INDEX IF NOT EXISTS idx_pm_situs_zip ON parcel_master(situs_zip);
CREATE INDEX IF NOT EXISTS idx_pm_isd ON parcel_master(school_district);
CREATE INDEX IF NOT EXISTS idx_pm_deed_inst ON parcel_master(last_deed_instrument);
CREATE INDEX IF NOT EXISTS idx_pm_homestead ON parcel_master(homestead_flag);
CREATE INDEX IF NOT EXISTS idx_pm_owner ON parcel_master(owner_name);
```

---

### 2.2. `clerk_records`
Public recordings from the County Clerk (deeds, deeds of trust, liens, probates, foreclosures).

```sql
CREATE TABLE IF NOT EXISTS clerk_records (
    doc_id               TEXT PRIMARY KEY,       -- County doc identifier
    instrument_number    TEXT,                   -- Official recording instrument number
    doc_type             TEXT NOT NULL,          -- Formal recorded document type
    recorded_date        TEXT NOT NULL,          -- YYYY-MM-DD
    grantor              TEXT,                   -- Transferor / Mortgagor / Debtor
    grantee              TEXT,                   -- Transferee / Mortgagee / Creditor
    subdivision          TEXT,                   -- Platted subdivision name
    lot                  TEXT,                   -- Platted lot
    block                TEXT,                   -- Platted block
    legal_description    TEXT,                   -- Text legal description
    doc_url              TEXT,                   -- Direct document link if available
    matched_universal_id TEXT,                   -- Linked parcel Universal ID (or NULL)
    is_deed              INTEGER DEFAULT 0,      -- 1 if Warranty Deed / Transfer
    is_mortgage          INTEGER DEFAULT 0,      -- 1 if Deed of Trust
    is_distress_lien     INTEGER DEFAULT 0,      -- 1 if HOA, Abstract of Judgment, Tax, Mechanic's Lien
    is_probate_heirship  INTEGER DEFAULT 0,      -- 1 if Affidavit of Heirship or Probate Docket
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clerk_inst ON clerk_records(instrument_number);
CREATE INDEX IF NOT EXISTS idx_clerk_type ON clerk_records(doc_type);
CREATE INDEX IF NOT EXISTS idx_clerk_date ON clerk_records(recorded_date);
CREATE INDEX IF NOT EXISTS idx_clerk_grantor ON clerk_records(grantor);
CREATE INDEX IF NOT EXISTS idx_clerk_grantee ON clerk_records(grantee);
CREATE INDEX IF NOT EXISTS idx_clerk_distress ON clerk_records(is_distress_lien);
CREATE INDEX IF NOT EXISTS idx_clerk_probate ON clerk_records(is_probate_heirship);
CREATE INDEX IF NOT EXISTS idx_clerk_matched ON clerk_records(matched_universal_id);
```

---

### 2.3. `distress_stacked_leads`
Materialized cross-county table containing stacked distress signals and calculated motivation scores.

```sql
CREATE TABLE IF NOT EXISTS distress_stacked_leads (
    lead_id              TEXT PRIMARY KEY,       -- Derived hash of universal_id + generation_date
    universal_id         TEXT NOT NULL,          -- References parcel_master(universal_id)
    county               TEXT NOT NULL,          -- 'COLLIN', 'DENTON', etc.
    prop_id              TEXT NOT NULL,          -- County CAD property ID
    situs_address        TEXT NOT NULL,
    situs_city           TEXT,
    situs_zip            TEXT,
    school_district      TEXT,
    market_val           NUMERIC DEFAULT 0,
    motivation_score     INTEGER NOT NULL,       -- Calculated score (0 - 100)
    distress_count       INTEGER NOT NULL,       -- Number of overlapping distress signals
    is_probate           INTEGER DEFAULT 0,      -- Heirship / Probate record detected
    is_hoa_lien          INTEGER DEFAULT 0,      -- HOA Assessment lien filed
    is_tax_delinquent    INTEGER DEFAULT 0,      -- CAD / Assessor unpaid delinquent taxes
    is_absentee          INTEGER DEFAULT 0,      -- Non-homestead + mailing zip != situs zip
    is_foreclosure       INTEGER DEFAULT 0,      -- Lis pendens or Notice of Trustee Sale
    is_judgment_lien     INTEGER DEFAULT 0,      -- Abstract of Judgment or State/Federal tax lien
    latest_distress_date TEXT,                   -- Most recent filing date (YYYY-MM-DD)
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_uid ON distress_stacked_leads(universal_id);
CREATE INDEX IF NOT EXISTS idx_leads_score ON distress_stacked_leads(motivation_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_distress ON distress_stacked_leads(distress_count DESC);
CREATE INDEX IF NOT EXISTS idx_leads_zip ON distress_stacked_leads(situs_zip);
```

---

### 2.4. `raw_clerk_chunks`
Resumable chunk checkpoint table tracking scraper progress.

```sql
CREATE TABLE IF NOT EXISTS raw_clerk_chunks (
    chunk_id      TEXT PRIMARY KEY,              -- e.g. 'RP_20260101_20260107'
    department    TEXT NOT NULL,                 -- e.g. 'RP' (Real Property)
    start_date    TEXT NOT NULL,                 -- YYYY-MM-DD
    end_date      TEXT NOT NULL,                 -- YYYY-MM-DD
    total_docs    INTEGER DEFAULT 0,             -- Total records returned by portal
    status        TEXT NOT NULL,                 -- 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'
    last_attempt  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunk_status ON raw_clerk_chunks(status);
```
