
"""Tests for geographic processing in the harvesting pipeline."""

from src.main import process_locations


def test_process_locations_preserves_and_reorders_source_coordinates(
    monkeypatch,
):
    """Article coordinates are converted to (longitude, latitude)."""
    records = [
        {
            "location_text": None,
            "coordinates": (50.5, 8.5),  # latitude, longitude
            "location_status": "coordinates_found",
        }
    ]

    def unexpected_geocode(_place):
        raise AssertionError("Geocoding should not be called")

    monkeypatch.setattr(
        "src.main.geocode_place",
        unexpected_geocode,
    )

    stats = process_locations(records)

    assert records[0]["coordinates"] == (8.5, 50.5)
    assert records[0]["location_status"] == "coordinates_found"
    assert stats["accepted"] == 1


def test_process_locations_rejects_invalid_coordinates():
    """Invalid latitude values must not be accepted."""
    records = [
        {
            "location_text": None,
            "coordinates": (95.0, 8.5),  # invalid latitude
            "location_status": "coordinates_found",
        }
    ]

    stats = process_locations(records)

    assert records[0]["coordinates"] is None
    assert records[0]["location_status"] == "invalid_coordinates"
    assert stats["invalid_coordinates"] == 1


def test_process_locations_geocodes_approved_place(monkeypatch):
    """An approved place can be geocoded without a live network request."""
    records = [
        {
            "location_text": "Sosberg",
            "coordinates": None,
            "location_status": "place_mention_unresolved",
        }
    ]

    monkeypatch.setattr(
        "src.main.geocode_place",
        lambda _place: (7.3, 50.1),  # longitude, latitude
    )

    stats = process_locations(records)

    assert records[0]["coordinates"] == (7.3, 50.1)
    assert records[0]["location_status"] == "place_geocoded"
    assert stats["accepted"] == 1
