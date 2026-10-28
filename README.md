# IRIS-SIG-33 — TopAgrar RSS Harvester

## 1. Project Overview

IRIS-SIG-33 is a Python-based data collection pipeline that retrieves agricultural news from TopAgrar, analyzes article content, identifies potential signs of dairy and livestock farming distress, extracts geographic information, and stores the results in PostgreSQL with PostGIS support.

The pipeline looks for two categories of signals:

- **Explicit distress:** Indicators such as farm closures, insolvency, liquidation, or cessation of agricultural activities.
- **Economic or structural risk:** Indicators such as rising production costs, falling milk prices, feed shortages, and financial pressure on agricultural businesses.

Collected records are stored in the `iris_staging.signal_ingest` table for further analysis and geographic exploration.

## 2. Main Features

- Fetches articles from a configurable TopAgrar RSS feed.
- Parses RSS/Atom entries and extracts article metadata.
- Skips entries missing required fields and removes duplicate entries within a feed.
- Classifies articles using keyword-based rules.
- Extracts recognized place names and geographic coordinates.
- Geocodes selected locations using OpenStreetMap Nominatim.
- Stores point geometries in PostGIS using SRID 25832.
- Uses PostgreSQL upserts to avoid duplicate database records.
- Handles HTTP errors, invalid or empty feeds, and database errors.
- Loads local configuration from a `.env` file.
- Includes automated tests for date normalization, classification, feed parsing, duplicates, and feed errors.

## 3. Technology Stack

- **Python** — data collection and processing.
- **feedparser** — RSS/Atom parsing.
- **Requests** — HTTP requests.
- **python-dotenv** — environment configuration.
- **psycopg** — PostgreSQL connectivity.
- **PostgreSQL 16** — relational database.
- **PostGIS 3.4** — spatial data storage and processing.
- **pytest** — automated testing.
- **OpenStreetMap Nominatim** — geographic lookup.

## 4. Project Structure

The main project files include:

```text
iris-topagrar-harvester/
├── src/
│   ├── __init__.py
│   ├── harvester.py
│   ├── locations.py
│   ├── database.py
│   └── main.py
├── tests/
│   └── test_harvester.py
├── data/
│   └── geocode_cache.json
├── sql/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

The local `.env` file is created on each developer's machine and must not be committed. The `data/` and `sql/` directories may contain additional project-specific files.

## 5. Requirements

Before running the project, install or configure:

- Python compatible with the project dependencies.
- PostgreSQL 16.
- PostGIS 3.4 installed in the PostgreSQL 16 instance.
- Git, if you are cloning or using version control.

The database settings in `.env` must match the PostgreSQL instance being used.

## 6. Installation

### Step 1 — Open the project

If the repository is already on your computer, navigate to its root directory:

```powershell
cd C:\Users\dell\Documents\iris-topagrar-harvester
```

If you are setting up a fresh copy, clone the repository and then enter its directory:

```powershell
git clone https://github.com/benamaranermine/iris-topagrar-harvester.git
cd iris-topagrar-harvester
```

### Step 2 — Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, allow scripts for the current terminal session only and activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Step 3 — Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 7. Environment Configuration

Create a local `.env` file in the project root using `.env.example` as a template.

Example configuration:

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5434
DATABASE_NAME=iris
DATABASE_USER=postgres
DATABASE_PASSWORD=replace_me
RSS_URL=https://www.topagrar.com/top_agrar_online-10090692.xml
```

Replace the example values with the settings for your own database. The port shown above (`5434`) is the port used in the development environment documented for this project; use your actual PostgreSQL port if it differs.

**Security requirements:**

- Never commit `.env` to Git.
- Never publish a real database password.
- Keep `.env.example` limited to placeholder values.
- Ensure `.env` is listed in `.gitignore`.

## 8. RSS Source

The configured feed is:

`https://www.topagrar.com/top_agrar_online-10090692.xml`

During implementation, the originally specified endpoint, `https://www.topagrar.com/rss`, did not provide a usable RSS feed. The alternative endpoint above was selected for testing the pipeline.

The feed URL can be changed using the `RSS_URL` environment variable. Feed availability and article contents may change over time.

## 9. Database Setup

Connect to the `iris` database using `psql` or pgAdmin. Run the following SQL in that database to enable PostGIS and create the staging schema and table:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS iris_staging;

CREATE TABLE IF NOT EXISTS iris_staging.signal_ingest (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'topagrar',
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    source_url TEXT NOT NULL,
    summary TEXT,
    signal_type TEXT,
    location_text TEXT,
    geom geometry(Point, 25832),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    location_status TEXT,
    CONSTRAINT signal_ingest_source_id_unique
        UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS signal_ingest_published_at_idx
    ON iris_staging.signal_ingest (published_at);

CREATE INDEX IF NOT EXISTS signal_ingest_signal_type_idx
    ON iris_staging.signal_ingest (signal_type);

CREATE INDEX IF NOT EXISTS signal_ingest_geom_idx
    ON iris_staging.signal_ingest USING GIST (geom);
```

The unique constraint on `(source, source_id)` allows the pipeline to update an existing article instead of inserting a duplicate.

## 10. Running the Harvester

Make sure PostgreSQL is running and the `.env` file is configured correctly. From the project root, activate the virtual environment and run:

```powershell
python -m src.main
```

The pipeline:

1. Retrieves the RSS feed.
2. Parses available articles.
3. Classifies articles using keyword-based rules.
4. Identifies and attempts to geocode selected locations.
5. Saves article records to PostgreSQL.
6. Prints a summary of the run.

### Example output from the latest verified run

```text
Fetching the TopAgrar RSS feed...
Articles retrieved: 100
Explicit distress signals: 0
Articles indicating risk: 7
Geocoding detected locations...
Locations successfully geocoded: 4
Unresolved place mentions: 20
Articles without a recognized location: 76
Saving records to PostgreSQL...
Articles processed in the database: 100
Harvest completed successfully.
```

These figures describe one run and may change as the feed changes. They are not the same as cumulative counts stored in the database.

## 11. Signal Classification

The pipeline uses keyword-based rules to classify articles.

| Signal type | Description |
|---|---|
| `dairy_livestock_distress` | Explicit indicators of farm closure, insolvency, liquidation, or cessation of activity. |
| `dairy_livestock_risk` | Indicators of economic pressure or structural risk affecting dairy or livestock farming. |
| `NULL` | No signal detected by the current classification rules. |

Explicit distress takes precedence over general risk indicators.

Keyword matching is a screening method. A detected keyword does not prove that a farm is distressed, and an article without a detected keyword is not necessarily irrelevant. Results should be validated before they are used for operational or policy decisions.

## 12. Geographic Processing

The pipeline extracts recognized place names and looks up selected locations using OpenStreetMap Nominatim.

Geographic results are stored in the `geom` column as PostGIS `POINT` geometries with SRID 25832 (ETRS89 / UTM zone 32N).

The `location_status` field records the outcome of location processing. Current stored statuses include:

- `place_geocoded` — a selected location was geocoded and stored as a spatial point.
- `place_mention_unresolved` — a place was mentioned but could not be resolved to an accepted point.
- `unresolved` — no usable location was identified.

Only selected, sufficiently specific locations are eligible for geocoding. Broad regions, ambiguous place mentions, and locations outside the project's geographic filter are not automatically converted into spatial points.

**Important limitations:**

- A town's coordinates represent the town or geocoding result, not necessarily the precise location of a farm.
- EPSG:25832 is appropriate only for locations within its intended geographic area. The current geographic filter is approximate and is not an official boundary.
- Nominatim should be used responsibly, with an appropriate request frequency and a descriptive User-Agent. Cached results can reduce repeated requests.

## 13. Data Validation Queries

Run these SQL queries against the `iris` database to review stored data.

### Total records and signal classifications

```sql
SELECT
    COUNT(*) AS total_articles,
    COUNT(DISTINCT (source, source_id)) AS unique_articles,
    COUNT(*) FILTER (
        WHERE signal_type = 'dairy_livestock_distress'
    ) AS distress_signals,
    COUNT(*) FILTER (
        WHERE signal_type = 'dairy_livestock_risk'
    ) AS risk_signals,
    COUNT(*) FILTER (
        WHERE signal_type IS NULL
    ) AS articles_without_signal
FROM iris_staging.signal_ingest;
```

### Check for duplicate source records

```sql
SELECT
    source,
    source_id,
    COUNT(*) AS record_count
FROM iris_staging.signal_ingest
GROUP BY source, source_id
HAVING COUNT(*) > 1;
```

Expected result: zero rows.

### Check required fields and timestamps

```sql
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (
        WHERE title IS NULL OR BTRIM(title) = ''
    ) AS missing_titles,
    COUNT(*) FILTER (
        WHERE source_id IS NULL OR BTRIM(source_id) = ''
    ) AS missing_source_ids,
    COUNT(*) FILTER (
        WHERE source_url IS NULL OR BTRIM(source_url) = ''
    ) AS missing_source_urls,
    COUNT(*) FILTER (WHERE ingested_at IS NULL) AS missing_ingested_at,
    COUNT(*) FILTER (WHERE updated_at IS NULL) AS missing_updated_at
FROM iris_staging.signal_ingest;
```

### Check geographic coverage

```sql
SELECT
    location_status,
    COUNT(*) AS article_count,
    COUNT(*) FILTER (WHERE geom IS NOT NULL) AS records_with_geometry
FROM iris_staging.signal_ingest
GROUP BY location_status
ORDER BY article_count DESC;
```

### Check geometry type, validity, and SRID

```sql
SELECT
    COUNT(*) AS geometry_count,
    COUNT(*) FILTER (WHERE ST_IsValid(geom)) AS valid_geometries,
    COUNT(*) FILTER (WHERE GeometryType(geom) = 'POINT') AS point_geometries,
    COUNT(*) FILTER (WHERE ST_SRID(geom) = 25832) AS geometries_in_epsg_25832
FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL;
```

### Review detected signals

```sql
SELECT
    title,
    published_at,
    signal_type,
    location_text,
    location_status,
    source_url
FROM iris_staging.signal_ingest
WHERE signal_type IN (
    'dairy_livestock_distress',
    'dairy_livestock_risk'
)
ORDER BY published_at DESC NULLS LAST;
```

## 14. Verified Test and Database Results

The following results were observed in the development environment on 2026-10-28. Database counts can change after later ingestion runs.

### Automated tests

Command:

```powershell
python -m pytest -v
```

Result:

- Tests collected: **14**
- Passed: **14**
- Failed: **0**
- Execution time: **0.25 seconds**

The tests cover date normalization, distress and risk classification, feed parsing, duplicate handling, invalid feeds, HTTP errors, empty feeds, and entries missing required fields. These tests use test fixtures and mocked HTTP responses; they do not establish that the live feed will always be available.

### Database checks

| Check | Verified result |
|---|---:|
| PostgreSQL server version | 16.15 |
| PostGIS version | 3.4.2 |
| Total stored records | 117 |
| Distinct `(source, source_id)` pairs | 117 |
| Duplicate source-identifier pairs | 0 |
| Records missing titles | 0 |
| Records missing source URLs | 0 |
| Records missing source IDs | 0 |
| Records missing `ingested_at` | 0 |
| Records missing `updated_at` | 0 |
| Stored geometries | 4 |
| Valid stored geometries | 4 |
| Stored point geometries using SRID 25832 | 4 |

The geometry metadata was also verified as `POINT` with SRID `25832`. The table contains 13 columns, including the PostGIS `geom` column.

### Stored classifications

At the time of validation, the database contained:

| Classification | Records |
|---|---:|
| No signal (`NULL`) | 107 |
| `dairy_livestock_risk` | 10 |
| `dairy_livestock_distress` | 0 |
| **Total** | **117** |

The latest run processed 100 articles and identified 7 risk signals and 0 explicit distress signals. These latest-run results differ from the cumulative database counts because the database contains previously stored records as well.

### Stored location statuses

The database location-status check returned:

| Location status | Records | Records with geometry |
|---|---:|---:|
| `unresolved` | 89 | 0 |
| `place_mention_unresolved` | 24 | 0 |
| `place_geocoded` | 4 | 4 |
| **Total** | **117** | **4** |

Only 4 of the 117 stored records had geometry at the time of this check. Location coverage is therefore a known limitation and should be considered when interpreting spatial results.

### Idempotency check

The database contained 117 records before and after rerunning the pipeline. The distinct `(source, source_id)` count remained 117, with zero duplicate pairs. This verifies idempotent behavior for the feed snapshot and database state tested; it does not guarantee that every future feed or database failure scenario is covered.

## 15. Reliability and Idempotency

The pipeline uses the unique constraint on `(source, source_id)` together with PostgreSQL `ON CONFLICT` handling. Reprocessing an article with the same source identifier should update its existing record rather than create another row.

Feed content and article counts can change between runs. The number of records processed in a run may therefore differ from the total number of records already stored in the database.

## 16. Known Limitations

- Classification is keyword-based and can produce false positives or false negatives.
- The feed may not include every relevant article or every historical article.
- Article counts and signal counts can change between runs.
- Place-name extraction relies on a predefined set of recognized locations.
- Some locations remain unresolved or are too broad for precise geocoding.
- A geocoded place does not necessarily identify the exact farm discussed.
- The EPSG:25832 geographic filter is approximate.
- Only a small portion of the currently stored records has a geometry.
- Keyword detection alone does not establish actual farm closure or financial distress.
- Live RSS, HTTP, database, and geocoding services may be temporarily unavailable.
- Automated tests use fixtures and mocks for feed behavior; a passing test suite does not guarantee that external services will remain available.

## 17. Error Handling and Quality Reporting

The harvester raises errors when an HTTP request fails, a feed cannot be parsed into usable records, or a feed contains no usable article records. Database errors should also be treated as failed ingestion rather than successful completion.

Useful quality indicators for each run include:

- Number of articles retrieved.
- Number of unique articles processed.
- Number of explicit distress signals.
- Number of risk signals.
- Number of successfully geocoded locations.
- Number of unresolved place mentions.
- Number of articles without a recognized location.
- Number of records inserted or updated.
- Any feed, geocoding, or database errors.

The current console output reports unresolved place mentions separately from articles without a recognized location. Database location-status totals are cumulative and should not be interpreted as the counts for a single run.

## 18. Security

- Keep database credentials in the local `.env` file.
- Do not commit `.env` or expose real passwords in logs, screenshots, or documentation.
- Use `.env.example` to document required environment variables with placeholder values.
- Do not bypass website access restrictions when retrieving source material.
