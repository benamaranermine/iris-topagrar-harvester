# IRIS-SIG-33 — TopAgrar RSS Harvester

## 1. Project Overview

IRIS-SIG-33 is a Python-based data collection pipeline that retrieves agricultural news articles from TopAgrar, analyzes their content, identifies potential signs of dairy and livestock farming distress, extracts geographic information, and stores the results in PostgreSQL with PostGIS support.

The project focuses on identifying two categories of signals:

- **Explicit distress:** Indicators such as farm closures, insolvency, liquidation, or cessation of agricultural activities.
- **Economic or structural risk:** Indicators such as rising production costs, falling milk prices, feed shortages, and financial pressure on agricultural businesses.

The collected data is stored in the `iris_staging.signal_ingest` table for further analysis and geographic exploration.

## 2. Main Features

- Fetches articles from the TopAgrar RSS feed.
- Parses RSS/Atom entries and extracts article metadata.
- Detects duplicate articles within a feed.
- Classifies articles using keyword-based rules.
- Extracts recognized place names and geographic coordinates.
- Geocodes selected locations using OpenStreetMap Nominatim.
- Stores geographic points in PostGIS using the EPSG:25832 coordinate reference system.
- Uses PostgreSQL upserts to avoid duplicate database records.
- Handles HTTP errors, malformed feeds, missing fields, and database errors.
- Supports local configuration through environment variables.
- Provides a foundation for automated tests and data-quality validation.

## 3. Technology Stack

- **Python** — data collection and processing.
- **feedparser** — RSS/Atom parsing.
- **Requests** — HTTP requests.
- **python-dotenv** — environment configuration.
- **PostgreSQL 16** — relational database.
- **PostGIS 3.4** — spatial data storage and processing.
- **psycopg** — PostgreSQL connectivity.
- **pytest** — automated testing.
- **OpenStreetMap Nominatim** — geographic lookup.

## 4. Project Structure

The project is organized as follows:

```text
iris-topagrar-harvester/
├── src/
│   ├── __init__.py
│   ├── harvester.py
│   ├── locations.py
│   ├── database.py
│   └── main.py
├── tests/
│   └── ...
├── data/
│   └── geocode_cache.json
├── sql/
│   └── ...
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

The `tests/` and `sql/` directories may contain additional files depending on the final implementation.

## 5. Requirements

Before running the project, install the following:

- Python.
- PostgreSQL 16.
- PostGIS 3.4 installed in the PostgreSQL 16 instance.
- Git, if version control is required.

The database connection details must match the PostgreSQL instance used by the project.

## 6. Installation

### Step 1 — Clone or open the project

Navigate to the project directory:

```powershell
cd C:\Users\dell\Documents\iris-topagrar-harvester
```

### Step 2 — Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use the following command for the current terminal session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Step 3 — Install Python dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The dependencies should include the packages used by the project, such as `feedparser`, `requests`, `python-dotenv`, `psycopg`, and `pytest`.

## 7. Environment Configuration

Create a local `.env` file in the project root. Use `.env.example` as a template.

Example configuration:

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5434
DATABASE_NAME=iris
DATABASE_USER=postgres
DATABASE_PASSWORD=replace_me
RSS_URL=https://www.topagrar.com/top_agrar_online-10090692.xml
```

Replace the example database credentials with the values configured on your own machine.

**Security requirements:**

- Never commit `.env` to Git.
- Never publish real database passwords.
- Keep `.env.example` limited to placeholder values.
- Ensure `.env` is listed in `.gitignore`.

## 8. RSS Source

The project uses the following RSS feed:

`https://www.topagrar.com/top_agrar_online-10090692.xml`

The originally specified endpoint, `https://www.topagrar.com/rss`, did not provide a usable RSS feed during implementation. The alternative endpoint above returned a valid feed and was therefore selected.

The feed URL can be changed through the `RSS_URL` environment variable.

## 9. Database Setup

Connect to the `iris` database using pgAdmin or `psql`.

Enable PostGIS and create the staging schema and table:

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

The unique constraint on `(source, source_id)` enables the pipeline to update an existing article instead of inserting a duplicate.

## 10. Running the Harvester

Make sure PostgreSQL is running and the `.env` configuration is correct.

From the project root, activate the virtual environment and run:

```powershell
python -m src.main
```

The pipeline performs the following operations:

1. Retrieves the RSS feed.
2. Parses the available articles.
3. Classifies articles using keyword-based rules.
4. Identifies and geocodes selected locations.
5. Saves the article records to PostgreSQL.
6. Displays a summary of the collection process.

Example console output:

```text
Récupération du flux RSS TopAgrar...
Articles récupérés : 100
Signaux de détresse explicite : 0
Articles présentant un risque : 7
Géolocalisation des lieux détectés...
Lieux géocodés : 4
Lieux non résolus : 96
Enregistrement dans PostgreSQL...
Articles traités en base de données : 100
Collecte terminée.
```

These figures are an example from a previous run. Results may change as the RSS feed is updated.

## 11. Signal Classification

The pipeline uses keyword-based rules to classify articles.

| Signal type | Description |
|---|---|
| `dairy_livestock_distress` | Explicit indicators of farm closure, insolvency, liquidation, or cessation of activity. |
| `dairy_livestock_risk` | Indicators of economic pressure or structural risk affecting dairy or livestock farming. |
| `NULL` | No signal detected by the current classification rules. |

Explicit distress takes precedence over general risk indicators.

Keyword matching is a screening method. A detected keyword does not prove that a farm is distressed, and an article without a detected keyword is not necessarily irrelevant. Results should be validated before being used for operational or policy decisions.

## 12. Geographic Processing

The pipeline extracts recognized place names and looks up selected locations using OpenStreetMap Nominatim.

Geographic results are stored in the `geom` column as PostGIS points with SRID 25832 (ETRS89 / UTM zone 32N).

The `location_status` field records the outcome of location processing. Current statuses include:

- `place_geocoded` — a selected location was geocoded and stored as a spatial point.
- `place_mention_unresolved` — a place was mentioned but could not be resolved to an accepted point.
- `unresolved` — no usable location was identified.

Only selected, sufficiently specific locations are eligible for geocoding. Broad regions, ambiguous place mentions, and locations outside the project's geographic filter are not automatically converted into spatial points.

**Important limitation:** A town's coordinates represent the town or geocoding result, not necessarily the precise location of a farm. EPSG:25832 is appropriate only for locations within its intended geographic area. The current geographic filter is approximate and should not be treated as an official boundary.

Nominatim requests should be used responsibly, with appropriate request frequency and a descriptive User-Agent. Cached results help avoid unnecessary repeated requests.

## 13. Data Validation Queries

### Total articles and classification counts

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

The expected result is zero rows.

### Check geographic coverage

```sql
SELECT
    location_status,
    COUNT(*) AS article_count
FROM iris_staging.signal_ingest
GROUP BY location_status
ORDER BY article_count DESC;
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

### Check spatial reference IDs

```sql
SELECT
    ST_SRID(geom) AS srid,
    COUNT(*) AS geometry_count
FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL
GROUP BY ST_SRID(geom);
```

The expected SRID for stored geometries is `25832`.

## 14. Testing

Run the automated test suite from the project root:

```powershell
python -m pytest -v
```

Tests should cover feed parsing, date normalization, classification rules, duplicate handling, malformed feeds, missing fields, HTTP errors, location extraction, and database persistence.

Where possible, tests should use mocked HTTP responses and a test database or mocked database connection rather than depending on live external services.

## 15. Reliability and Idempotency

The pipeline uses the unique constraint on `(source, source_id)` together with PostgreSQL `ON CONFLICT` handling.

Consequently, running the harvester repeatedly should update existing records for the same source identifier rather than creating duplicate rows.

Article metadata, classification results, location information, and geometry can be updated when the same article is processed again.

## 16. Known Limitations

- Classification is based on keywords and may produce false positives or false negatives.
- The feed may not contain every relevant article or every historical article.
- The number of articles can change between runs.
- Place-name extraction relies on a predefined list of recognized locations.
- Some locations remain unresolved or are too broad for precise geocoding.
- A geocoded place does not necessarily identify the exact farm discussed.
- The EPSG:25832 geographic filter is approximate.
- Keyword detection alone does not establish actual farm closure or financial distress.
- Live RSS and geocoding services may be temporarily unavailable.

These limitations should be considered when interpreting results.

## 17. Error Handling and Quality Reporting

The harvester raises errors when an HTTP request fails, the feed cannot be parsed into usable records, or the database operation fails. The main entry point displays an error message and propagates the exception so that failures are visible.

For each run, the following indicators are useful for quality reporting:

- Number of articles retrieved.
- Number of unique articles processed.
- Number of explicit distress signals.
- Number of risk signals.
- Number of successfully geocoded locations.
- Number of unresolved place mentions.
- Number of articles with no recognized location.
- Number of records inserted or updated.
- Any feed, geocoding, or database errors.

The current console output groups all records without accepted coordinates under “Lieux non résolus.” For a more precise report, distinguish records with an unresolved place mention from records in which no location was detected.

## 18. License and Data Sources

Article metadata is collected from the TopAgrar RSS feed. Geographic lookups use OpenStreetMap Nominatim.

Respect the source websites' terms of use, applicable access restrictions, and attribution requirements. This repository does not reproduce the full content of articles beyond the fields needed for the project.

---

**Project:** IRIS-SIG-33 — TopAgrar RSS Harvester  
**Purpose:** Agricultural news collection, distress-signal screening, and geographic data staging.
