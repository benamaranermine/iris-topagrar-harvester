
-- IRIS-SIG-33: staging data quality checks

-- 1. Total number of records
SELECT COUNT(*) AS total_records
FROM iris_staging.signal_ingest;

-- 2. Duplicate source identifiers (expected: zero rows)
SELECT source, source_id, COUNT(*) AS occurrences
FROM iris_staging.signal_ingest
GROUP BY source, source_id
HAVING COUNT(*) > 1;

-- 3. Missing mandatory fields
SELECT
    COUNT(*) FILTER (WHERE source IS NULL) AS missing_source,
    COUNT(*) FILTER (WHERE source_id IS NULL OR source_id = '') AS missing_source_id,
    COUNT(*) FILTER (WHERE title IS NULL OR title = '') AS missing_title,
    COUNT(*) FILTER (WHERE source_url IS NULL OR source_url = '') AS missing_source_url
FROM iris_staging.signal_ingest;

-- 4. Signal classification counts
SELECT signal_type, COUNT(*) AS records
FROM iris_staging.signal_ingest
GROUP BY signal_type
ORDER BY records DESC;

-- 5. Publication dates missing
SELECT COUNT(*) AS missing_publication_dates
FROM iris_staging.signal_ingest
WHERE published_at IS NULL;

-- 6. Records with unresolved geographic information
SELECT COUNT(*) AS missing_geometry
FROM iris_staging.signal_ingest
WHERE geom IS NULL;

-- 7. Confirm geometry reference system and type
SELECT
    ST_SRID(geom) AS srid,
    GeometryType(geom) AS geometry_type,
    COUNT(*) AS records
FROM iris_staging.signal_ingest
WHERE geom IS NOT NULL
GROUP BY ST_SRID(geom), GeometryType(geom);
