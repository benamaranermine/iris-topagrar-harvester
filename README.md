# IRIS-SIG-33 — TopAgrar Structural Change & Land Market Harvester

## 1. Project Overview

IRIS-SIG-33 is a Python ingestion pipeline that retrieves agricultural news articles from TopAgrar, screens their content for possible dairy and livestock farming distress, extracts geographic context when available, and stores traceable staging records in PostgreSQL with PostGIS support.

The assignment objective is to identify regional dairy farm liquidations and structural distress in livestock production. The pipeline distinguishes between:

- **Explicit distress** — possible farm closure, insolvency, liquidation, or cessation of agricultural activity.
- **Economic or structural risk** — possible pressure from production costs, milk prices, feed shortages, or other livestock-sector conditions.

Records are stored in `iris_staging.signal_ingest` for further validation and analysis. Keyword-based signals are screening indicators; they do not prove that a specific farm is distressed.

## 2. Features

- Configurable RSS feed URL through an environment variable.
- RSS/Atom parsing and extraction of source identifiers, titles, publication dates, URLs, summaries, and location text when available.
- Skipping entries with missing required fields and removing duplicate identifiers within a feed response.
- Keyword-based classification into explicit distress, structural risk, or no detected signal.
- Validation and normalization of geographic coordinates.
- Geocoding of selected place names using OpenStreetMap Nominatim.
- Storage of accepted point geometries in PostGIS using SRID 25832.
- Idempotent database writes using a unique key on `(source, source_id)` and PostgreSQL `ON CONFLICT ... DO UPDATE`.
- Visible handling of HTTP errors, unusable or empty feeds, invalid coordinates, and database failures.
- Automated tests using local fixtures and mocked external/database interactions.
- SQL queries for checking record uniqueness, required fields, signal classifications, and spatial data quality.

## 3. Technology Stack

- **Python** — ingestion and processing.
- **feedparser** — RSS/Atom parsing.
- **Requests** — HTTP requests.
- **python-dotenv** — local environment configuration.
- **psycopg** — PostgreSQL connectivity.
- **PostgreSQL 16** — relational staging database.
- **PostGIS 3.4** — spatial data support.
- **pytest** — automated tests.
- **OpenStreetMap Nominatim** — lookup of selected place names.

## 4. Project Structure

```text
iris-topagrar-harvester/
├── src/
│   ├── __init__.py
│   ├── harvester.py
│   ├── locations.py
│   ├── database.py
│   └── main.py
├── tests/
│   ├── fixtures/
│   ├── test_database.py
│   ├── test_harvester.py
│   └── test_pipeline.py
├── data/
│   └── geocode_cache.json
├── sql/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

The local `.env` file is created on each machine and must not be committed. The `data/` and `sql/` directories may contain local cache and SQL resources used by the project.

## 5. Requirements

Before running the application, install or configure:

- Python compatible with the dependencies in `requirements.txt`.
- PostgreSQL 16.
- PostGIS 3.4 enabled in the target PostgreSQL database.
- Git, if you are cloning the repository.

The database connection values in `.env` must match your own PostgreSQL instance.

## 6. Installation

### Step 1 — Clone or open the repository

For a fresh checkout:

```powershell
git clone https://github.com/benamaranermine/iris-topagrar-harvester.git
cd iris-topagrar-harvester
```

If the project is already on your machine, open the project directory instead.

### Step 2 — Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation scripts, allow scripts only for the current terminal session and activate again:

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

Create a local `.env` file in the project root using `.env.example` as the template. For example:

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5434
DATABASE_NAME=iris
DATABASE_USER=postgres
DATABASE_PASSWORD=replace_me
RSS_URL=https://www.topagrar.com/top_agrar_online-10090692.xml
```

Replace these example settings with the values for your machine. `5434` is the port used in the development environment for this project; use your actual PostgreSQL port if it differs.

**Credentials and repository hygiene:**

- Never commit `.env` or publish a real database password.
- Keep `.env.example` limited to placeholder values.
- Ensure `.env` is listed in `.gitignore`.
- Do not include real credentials in screenshots, logs, or documentation.

## 8. RSS Source and Endpoint Notes

The feed configured for development is:

`https://www.topagrar.com/top_agrar_online-10090692.xml`

The assignment specified `https://www.topagrar.com/rss`. During implementation, that endpoint did not provide a usable RSS response in the development checks, so the alternative feed above was used to develop and test the RSS/Atom ingestion pattern. The configured feed can be changed with `RSS_URL`.

Feed availability, format, article counts, and publication dates can change. Verify source accessibility and dates at runtime; this README does not guarantee that the live endpoint will always be available or contain the same records. The implementation uses normal HTTP requests and does not attempt to bypass access restrictions.

## 9. Database Setup

Connect to the target database (named `iris` in the development environment) using `psql` or pgAdmin. Run the following SQL if the schema and table have not already been created:

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

The unique constraint on `(source, source_id)` is essential for idempotent ingestion. If the table already exists, verify that the unique constraint is present; `CREATE TABLE IF NOT EXISTS` does not modify an existing table's definition.

## 10. Running the Harvester

Ensure PostgreSQL is running and `.env` is configured. From the project root, activate `.venv` and run:

```powershell
python -m src.main
```

The pipeline fetches the feed, parses article records, applies classification rules, processes location information, saves records to PostgreSQL, and prints a run summary. The program raises an error when a required processing step fails rather than reporting a failed run as successful.

### Latest observed run output

The following output was reported by a local run on October 28, 2026. Feed data and output counts may change on subsequent runs.

```text
Fetching the TopAgrar RSS feed...
Articles retrieved: 100
Explicit distress signals: 0
Articles indicating risk: 7
Processing geographic information...
Locations with accepted coordinates: 4
Unresolved place mentions: 21
Articles without a recognized location: 75
Rejected invalid coordinates: 0
Coordinates outside target region: 1
Saving records to PostgreSQL...
Articles processed in the database: 100
Harvest completed successfully.
```

These figures describe that particular execution. They are not the same as cumulative counts stored in the database.

## 11. Signal Classification

The classifier uses keyword-based rules over article titles and summaries, together with farming-domain terms, to screen for potential signals.

| Signal type | Meaning |
|---|---|
| `dairy_livestock_distress` | Possible explicit distress, such as farm closure, insolvency, liquidation, or cessation of activity. |
| `dairy_livestock_risk` | Possible economic or structural risk affecting dairy or livestock farming. |
| `NULL` | No signal detected by the configured keyword rules. |

Explicit distress takes precedence over general risk indicators. The classification is heuristic. A positive match is not proof of farm distress, and an article that does not match the configured vocabulary may still be relevant. Results should be reviewed before operational or policy use.

## 12. Geographic Processing and Assumptions

Locations are extracted from article content when possible and selected place names may be looked up with OpenStreetMap Nominatim. Accepted coordinates are transformed from WGS 84 (EPSG:4326) into the target spatial reference system, EPSG:25832 (ETRS89 / UTM zone 32N), before being stored in the `geom` column.

Coordinates passed from the location-processing stage to the database layer use `(longitude, latitude)` order. Coordinates obtained from article text may initially be represented as `(latitude, longitude)` and must be normalized before persistence. Invalid coordinates and points outside the configured geographic filter are not stored as accepted geometries.

The current approximate geographic filter is:

- Longitude: 6.0 to 12.0 degrees.
- Latitude: 47.0 to 55.0 degrees.

This is an implementation-specific filter, not an official administrative or operational boundary. It excludes some areas, including parts of Germany, so it should be reviewed if broader geographic coverage is required.

The `location_status` field describes the location-processing outcome. Statuses used by the current pipeline include:

- `coordinates_found` — coordinates extracted from article content were validated and accepted.
- `place_geocoded` — an approved place name was geocoded and the point was accepted.
- `invalid_coordinates` — supplied coordinate values failed validation.
- `coordinates_outside_target_region` — a point was outside the configured geographic filter.
- `place_mention_unresolved` — a place was mentioned but could not be resolved to an accepted point.
- `unresolved` — no usable location was identified.

Only selected, sufficiently specific place names are eligible for geocoding. A geocoded town or settlement represents the geocoding result, not necessarily the precise position of a farm. Nominatim should be used responsibly, with a descriptive User-Agent, appropriate request frequency, and caching where available.

## 13. Data Validation Queries

Run these queries against the database used by the application.

### Total records and classifications

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
    COUNT(*) FILTER (WHERE signal_type IS NULL) AS articles_without_signal
FROM iris_staging.signal_ingest;
```

### Check duplicate source records

```sql
SELECT source, source_id, COUNT(*) AS record_count
FROM iris_staging.signal_ingest
GROUP BY source, source_id
HAVING COUNT(*) > 1;
```

Expected result: zero rows.

### Check required fields and timestamps

```sql
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE title IS NULL OR BTRIM(title) = '') AS missing_titles,
    COUNT(*) FILTER (WHERE source_id IS NULL OR BTRIM(source_id) = '') AS missing_source_ids,
    COUNT(*) FILTER (WHERE source_url IS NULL OR BTRIM(source_url) = '') AS missing_source_urls,
    COUNT(*) FILTER (WHERE ingested_at IS NULL) AS missing_ingested_at,
    COUNT(*) FILTER (WHERE updated_at IS NULL) AS missing_updated_at
FROM iris_staging.signal_ingest;
```

### Check location status and spatial coverage

```sql
SELECT
    location_status,
    COUNT(*) AS article_count,
    COUNT(*) FILTER (WHERE geom IS NOT NULL) AS records_with_geometry
FROM iris_staging.signal_ingest
GROUP BY location_status
ORDER BY article_count DESC;
```

### Check geometry validity, type, and SRID

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

## 14. Automated Tests and Latest Validation Results

### Automated test suite

Run from the project root:

```powershell
python -m pytest -v
```

Latest observed result on October 28, 2026:

- Tests collected: **18**
- Passed: **18**
- Failed: **0**
- Reported duration: **0.36 seconds**

The test suite covers date normalization, signal classification, feed parsing, in-feed duplicate handling, malformed or empty feeds, HTTP errors, missing required fields, location-coordinate normalization, invalid coordinates, geocoding of an approved place, and the database upsert query.

The database upsert test uses a mocked connection. It verifies that repeated calls for the same `(source, source_id)` execute the expected `ON CONFLICT ... DO UPDATE` query; it does not independently prove database behavior against a live PostgreSQL server. The SQL validation below is a separate check against the actual development database.

### Latest observed PostgreSQL/PostGIS validation

The following values were returned by the latest database validation run on October 28, 2026:

| Check | Result |
|---|---:|
| PostgreSQL version previously verified in the development environment | 16.15 |
| PostGIS version previously verified in the development environment | 3.4.2 |
| Total stored records | 118 |
| Distinct `(source, source_id)` pairs | 118 |
| Duplicate rows, calculated as total minus distinct pairs | 0 |
| Rows with a non-null geometry | 4 |
| Valid EPSG:25832 point geometries | 4 |

All four geometries present in that query were valid points with SRID 25832. Only 4 of 118 stored records had geometry, so geographic coverage remains a significant limitation.

### Rerun / idempotency evidence

A previous local rerun check showed the total row count remaining at 117 before and after rerunning the harvester, with 117 unique source-identifier pairs and zero duplicate pairs. A later validation, after additional ingestion, reported 118 total rows, 118 distinct source-identifier pairs, and zero duplicates. Since the live feed can change, compare counts immediately before and after a rerun to verify whether the current feed snapshot adds any new records.

## 15. Reliability and Idempotency

The staging table's unique constraint on `(source, source_id)` and the database layer's `ON CONFLICT ... DO UPDATE` statement are intended to make ingestion repeatable. A record with an existing source identifier should update the corresponding row rather than create a duplicate.

The number of articles retrieved during a run may differ from the cumulative database row count. Feed updates, changed article availability, and previously stored records explain why these counts should not be treated as interchangeable.

## 16. Known Limitations

- Classification depends on configured keywords and can produce false positives or false negatives.
- The feed may not contain every relevant article or historical article.
- Source availability, response format, and article counts can change over time.
- Location extraction depends on a predefined list of recognized place names.
- Some location mentions remain unresolved or too broad for precise geocoding.
- A geocoded place does not necessarily represent the exact farm location.
- The approximate longitude/latitude filter excludes some locations that could otherwise be relevant.
- Only a small proportion of the current database records has a geometry.
- Keyword matches alone do not establish actual farm closure or financial distress.
- The automated database test mocks persistence; real database constraints and geometry should continue to be checked with SQL validation.
- Live RSS, HTTP, PostgreSQL, and geocoding services can be temporarily unavailable.

## 17. Error Handling and Quality Reporting

The harvester reports failures when HTTP requests fail, no usable article records are returned, or processing and database operations raise exceptions. The command-line entry point prints an error and re-raises the exception so that a failed execution does not appear to have completed successfully.

Useful per-run quality indicators include:

- Number of articles retrieved.
- Number of explicit distress and risk signals.
- Number of accepted coordinates.
- Number of unresolved place mentions.
- Number of articles without a recognized location.
- Number of invalid coordinates rejected.
- Number of coordinates outside the configured target region.
- Number of records processed for persistence.
- Feed, geocoding, or database errors.

Run-level figures describe one feed response; database validation queries describe cumulative stored data.

## 18. Security and Responsible Access

- Keep real database credentials in the local `.env` file, not in source code.
- Do not commit `.env` or publish passwords.
- Use only authorized public source access and do not bypass site access restrictions.
- Follow the source website's terms and applicable usage restrictions.
- Use OpenStreetMap Nominatim responsibly and include suitable attribution where required.
- Avoid storing more article content than is necessary for the assignment's ingestion and traceability needs.
