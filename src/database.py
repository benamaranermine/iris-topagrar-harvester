
"""PostgreSQL persistence for the IRIS-SIG-33 harvester."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def get_connection():
    """Open a PostgreSQL connection using the project's .env settings."""
    required = (
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
        "DATABASE_USER",
        "DATABASE_PASSWORD",
    )

    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            "Missing database settings in .env: "
            + ", ".join(missing)
        )

    return psycopg.connect(
        host=os.getenv("DATABASE_HOST"),
        port=int(os.getenv("DATABASE_PORT")),
        dbname=os.getenv("DATABASE_NAME"),
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASSWORD"),
        connect_timeout=10,
    )


def save_records(records):
    """
    Insert or update articles in PostgreSQL.

    Coordinates are expected as (longitude, latitude) in EPSG:4326.
    PostGIS transforms them to EPSG:25832.
    Records are uniquely identified by (source, source_id).
    """
    if not records:
        return 0

    sql = """
        INSERT INTO iris_staging.signal_ingest (
            source,
            source_id,
            title,
            published_at,
            source_url,
            summary,
            signal_type,
            location_text,
            geom,
            location_status
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            CASE
                WHEN %s::double precision IS NOT NULL
                 AND %s::double precision IS NOT NULL
                THEN ST_Transform(
                    ST_SetSRID(
                        ST_MakePoint(
                            %s::double precision,
                            %s::double precision
                        ),
                        4326
                    ),
                    25832
                )
                ELSE NULL
            END,
            %s
        )
        ON CONFLICT (source, source_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            published_at = EXCLUDED.published_at,
            source_url = EXCLUDED.source_url,
            summary = EXCLUDED.summary,
            signal_type = EXCLUDED.signal_type,
            location_text = EXCLUDED.location_text,
            geom = EXCLUDED.geom,
            location_status = EXCLUDED.location_status,
            updated_at = NOW();
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            for record in records:
                coordinates = record.get("coordinates")

                longitude = None
                latitude = None

                if coordinates and len(coordinates) == 2:
                    longitude, latitude = coordinates

                    # Reject invalid longitude/latitude values.
                    try:
                        longitude = float(longitude)
                        latitude = float(latitude)

                        if not (
                            -180 <= longitude <= 180
                            and -90 <= latitude <= 90
                        ):
                            longitude = None
                            latitude = None
                    except (TypeError, ValueError):
                        longitude = None
                        latitude = None

                location_status = record.get("location_status")

                if longitude is not None and latitude is not None:
                    location_status = "place_geocoded"
                elif not location_status:
                    location_status = (
                        "place_mention_unresolved"
                        if record.get("location_text")
                        else "unresolved"
                    )

                cur.execute(
                    sql,
                    (
                        record["source"],
                        record["source_id"],
                        record["title"],
                        record.get("published_at"),
                        record["source_url"],
                        record.get("summary"),
                        record.get("signal_type"),
                        record.get("location_text"),
                        longitude,
                        latitude,
                        longitude,
                        latitude,
                        location_status,
                    ),
                )

    return len(records)
