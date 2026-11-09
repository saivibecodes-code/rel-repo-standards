# Canonical Data Contracts & Schema Specifications

This document defines the strict, cross-county data contracts implemented by all `rel-*` repositories.

---

## 1. Universal Property Identifier (`UniversalID`)

All real estate properties across all Texas counties are addressed by a canonical, human-readable, deterministic identifier derived from the 5-digit Federal Information Processing Standard (FIPS) county code and the sanitized CAD property account number:

$$\text{UniversalID} = \text{FIPS} + \text{"\_"} + \text{CLEAN\_PROP\_ID}$$

### Standard Texas FIPS Reference
| County | FIPS Code | Example CAD Prop ID | Canonical Universal ID |
| :--- | :--- | :--- | :--- |
| **Collin** | `48085` | `821` | `48085_821` |
| **Denton** | `48121` | `100` | `48121_100` |
| **Dallas** | `48113` | `000001234567` | `48113_000001234567` |
| **Tarrant** | `48439` | `01234567` | `48439_01234567` |

### Python Implementation (`rel_core.universal_id`)
```python
import re

COUNTY_FIPS_MAP = {
    "COLLIN": "48085",
    "DENTON": "48121",
    "DALLAS": "48113",
    "TARRANT": "48439",
    "ROCKWALL": "48397",
    "KAUFMAN": "48257",
}

def generate_universal_id(county_or_fips: str, raw_prop_id: str | int) -> str:
    """Generate canonical Universal Property ID in '{fips}_{prop_id}' format."""
    clean_county = str(county_or_fips).strip().upper()
    fips = clean_county if clean_county.isdigit() and len(clean_county) == 5 else COUNTY_FIPS_MAP.get(clean_county, clean_county)
    clean_id = re.sub(r"[^A-Za-z0-9]", "", str(raw_prop_id)).strip()
    return f"{fips}_{clean_id}"
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
Materialized cross-county table containing stacked distress signals, debt/auction metrics, and calculated motivation scores (identical across Collin and Denton databases).

```sql
CREATE TABLE IF NOT EXISTS distress_stacked_leads (
    universal_id            TEXT PRIMARY KEY,       -- e.g. '48085_821', '48121_100'
    county_fips             TEXT NOT NULL,          -- '48085', '48121'
    county_name             TEXT NOT NULL,          -- 'Collin', 'Denton'
    prop_id                 TEXT NOT NULL,          -- County CAD property ID
    geo_id                  TEXT,                   -- Geographic GIS ID
    situs_address           TEXT NOT NULL,          -- Physical property street address
    situs_city              TEXT,                   -- Physical city
    situs_zip               TEXT,                   -- Physical 5-digit zip
    owner_name              TEXT,                   -- Primary owner of record
    owner_address           TEXT,                   -- Mailing street address
    market_value            REAL DEFAULT 0,         -- CAD total market value
    year_built              INTEGER,                -- Year of construction
    living_area_sqft        REAL,                   -- Heated/cooled living area
    homestead_flag          INTEGER DEFAULT 0,      -- 1 if primary homestead
    is_absentee             INTEGER DEFAULT 0,      -- 1 if mailing address differs from situs
    has_pre_foreclosure     INTEGER DEFAULT 0,      -- 1 if Notice of Default / Trustee Sale filed
    notice_date             TEXT,                   -- Date of foreclosure notice (YYYY-MM-DD)
    auction_date            TEXT,                   -- Scheduled auction date (YYYY-MM-DD)
    default_amount          REAL,                   -- Unpaid mortgage default balance
    has_auction_scheduled   INTEGER DEFAULT 0,      -- 1 if active auction scheduled
    has_delinquent_tax      INTEGER DEFAULT 0,      -- 1 if ad valorem taxes delinquent
    delinquent_tax_due      REAL DEFAULT 0,         -- Total unpaid delinquent taxes ($)
    oldest_delinquent_year  INTEGER,                -- Earliest unpaid tax year
    suit_number             TEXT,                   -- Delinquent tax court suit docket #
    has_tax_lawsuit         INTEGER DEFAULT 0,      -- 1 if formal tax lawsuit filed
    has_probate             INTEGER DEFAULT 0,      -- 1 if probate or affidavit of heirship filed
    is_unsettled_estate     INTEGER DEFAULT 0,      -- 1 if active probate without deed distribution
    ocr_deceased_name       TEXT,                   -- Deceased party extracted via OCR
    ocr_date_of_death       TEXT,                   -- Date of death (YYYY-MM-DD)
    heirship_filing_date    TEXT,                   -- Filing date of heirship affidavit
    distress_count          INTEGER NOT NULL,       -- Overlapping distress factors count
    motivation_score        INTEGER NOT NULL,       -- Normalized score (0 - 100)
    priority_tier           TEXT NOT NULL,          -- 'URGENT', 'HIGH', 'MEDIUM', 'WATCHLIST'
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_leads_uid ON distress_stacked_leads(universal_id);
CREATE INDEX IF NOT EXISTS idx_leads_score ON distress_stacked_leads(motivation_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_distress ON distress_stacked_leads(distress_count DESC);
CREATE INDEX IF NOT EXISTS idx_leads_tier ON distress_stacked_leads(priority_tier);
CREATE INDEX IF NOT EXISTS idx_leads_zip ON distress_stacked_leads(situs_zip);
```

---

### 2.4. `active_mls_listings`
Normalized listing table persisted in `data/mls_listings.db` by `rel-svc-mls-data`.

```sql
CREATE TABLE IF NOT EXISTS active_mls_listings (
    mls_id                  TEXT PRIMARY KEY,       -- Portal or MLS listing ID
    address                 TEXT NOT NULL,          -- Normalized street address
    city                    TEXT,                   -- Physical city
    state                   TEXT DEFAULT 'TX',      -- State code
    zip_code                TEXT,                   -- 5-digit zip
    price                   REAL,                   -- Current asking price
    beds                    REAL,                   -- Bedroom count
    baths                   REAL,                   -- Bathroom count
    sqft                    REAL,                   -- Heated square footage
    price_per_sqft          REAL,                   -- Price per square foot
    lot_size_sqft           REAL,                   -- Lot size in sqft
    year_built              INTEGER,                -- Year built
    hoa_fee_monthly         REAL DEFAULT 0,         -- Monthly HOA dues
    days_on_market          INTEGER,                -- Days on market (DOM)
    status                  TEXT,                   -- 'Active', 'Pending', 'Price Change'
    property_type           TEXT,                   -- Raw property type code
    property_type_name      TEXT,                   -- 'Single Family Residential', 'Townhouse'
    latitude                REAL,                   -- WGS84 latitude
    longitude               REAL,                   -- WGS84 longitude
    url                     TEXT,                   -- Portal listing URL
    matched_universal_id    TEXT,                   -- Linked CAD Universal ID (FIPS_PropID)
    cad_market_value        REAL DEFAULT 0,         -- Matched CAD appraisal market value
    discount_vs_cad         REAL DEFAULT 0,         -- (cad_market_value - price)
    discount_pct            REAL DEFAULT 0,         -- Percentage discount vs CAD
    is_active               INTEGER DEFAULT 1,      -- 1 if active, 0 if off-market
    scraped_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mls_matched_uid ON active_mls_listings(matched_universal_id);
CREATE INDEX IF NOT EXISTS idx_mls_price ON active_mls_listings(price);
CREATE INDEX IF NOT EXISTS idx_mls_dom ON active_mls_listings(days_on_market);
CREATE INDEX IF NOT EXISTS idx_mls_status ON active_mls_listings(status);
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
