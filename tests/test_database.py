
"""Tests for database persistence and upsert behavior."""

from unittest.mock import MagicMock

from src import database


def test_save_records_executes_upsert_for_repeated_article(monkeypatch):
    """Repeated saves use the same source ID and an SQL upsert."""
    cursor = MagicMock()

    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value = cursor_context

    monkeypatch.setattr(
        database,
        "get_connection",
        lambda: connection,
    )

    record = {
        "source": "topagrar",
        "source_id": "test-article-001",
        "title": "Test dairy farm article",
        "published_at": None,
        "source_url": "https://example.com/test-article-001",
        "summary": "Test article used to verify upsert behavior.",
        "signal_type": "dairy_livestock_risk",
        "location_text": "Sosberg",
        "coordinates": (7.3, 50.1),  # longitude, latitude
        "location_status": "place_geocoded",
    }

    first_result = database.save_records([record])
    second_result = database.save_records([record])

    assert first_result == 1
    assert second_result == 1

    # Each invocation executes one SQL statement.
    assert cursor.execute.call_count == 2

    first_sql, first_params = cursor.execute.call_args_list[0].args
    second_sql, second_params = cursor.execute.call_args_list[1].args

    # Verify that PostgreSQL will update a matching source/source_id pair.
    assert "ON CONFLICT (source, source_id)" in first_sql
    assert "DO UPDATE SET" in first_sql
    assert second_sql == first_sql

    # Both attempts identify the same article.
    assert first_params[0:2] == ("topagrar", "test-article-001")
    assert second_params[0:2] == first_params[0:2]

    # Longitude must precede latitude in the PostGIS point construction.
    assert first_params[8:12] == (7.3, 50.1, 7.3, 50.1)
