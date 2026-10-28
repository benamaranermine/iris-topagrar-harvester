
"""Run the IRIS-SIG-33 RSS harvesting pipeline."""

from src.harvester import fetch_feed
from src.database import save_records
from src.locations import geocode_place, validate_coordinates


# Only specific towns are eligible for geocoding.
# Broad regions and countries are deliberately excluded.
PRECISE_PLACES = {
    "sosberg": "Sosberg, Rhineland-Palatinate, Germany",
    "hofbieber": "Hofbieber, Hesse, Germany",
    "neustadt-glewe": (
        "Neustadt-Glewe, Mecklenburg-Vorpommern, Germany"
    ),
    "staufen": (
        "Staufen im Breisgau, Baden-Württemberg, Germany"
    ),
    "löbau": "Löbau, Saxony, Germany",
}

# Approximate geographic filter used by this project.
MIN_LONGITUDE = 6.0
MAX_LONGITUDE = 12.0
MIN_LATITUDE = 47.0
MAX_LATITUDE = 55.0


def inside_target_region(longitude, latitude):
    """Return whether a point is inside the configured target area."""
    return (
        MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
        and MIN_LATITUDE <= latitude <= MAX_LATITUDE
    )


def process_locations(records):
    """
    Validate article coordinates and geocode recognized place names.

    Coordinates extracted from article text arrive as (latitude, longitude).
    geocode_place() returns (longitude, latitude).

    All accepted coordinates are normalized to (longitude, latitude)
    before they are passed to the database layer.
    """
    stats = {
        "accepted": 0,
        "unresolved_place": 0,
        "no_location": 0,
        "invalid_coordinates": 0,
        "outside_region": 0,
    }

    for record in records:
        source_coordinates = record.get("coordinates")

        # Reset the field before validating the original coordinates.
        record["coordinates"] = None
        rejected_status = None

        # First, validate coordinates extracted directly from the article.
        if source_coordinates is not None:
            try:
                if len(source_coordinates) != 2:
                    raise ValueError(
                        "Expected a latitude/longitude pair"
                    )

                latitude = float(source_coordinates[0])
                longitude = float(source_coordinates[1])

            except (TypeError, ValueError, IndexError, OverflowError):
                rejected_status = "invalid_coordinates"
                stats["invalid_coordinates"] += 1

            else:
                if not validate_coordinates(latitude, longitude):
                    rejected_status = "invalid_coordinates"
                    stats["invalid_coordinates"] += 1

                elif not inside_target_region(longitude, latitude):
                    rejected_status = (
                        "coordinates_outside_target_region"
                    )
                    stats["outside_region"] += 1

                else:
                    record["coordinates"] = (longitude, latitude)
                    record["location_status"] = "coordinates_found"
                    stats["accepted"] += 1
                    continue

        place = record.get("location_text")

        if not place:
            record["location_status"] = (
                rejected_status or "unresolved"
            )
            stats["no_location"] += 1
            continue

        # Multiple place names are ambiguous.
        if ";" in place:
            record["location_status"] = (
                rejected_status or "place_mention_unresolved"
            )
            stats["unresolved_place"] += 1
            continue

        # Geocode only locations on the approved list.
        query = PRECISE_PLACES.get(place.strip().casefold())

        if not query:
            record["location_status"] = (
                rejected_status or "place_mention_unresolved"
            )
            stats["unresolved_place"] += 1
            continue

        coordinates = geocode_place(query)

        if coordinates is None:
            record["location_status"] = (
                rejected_status or "place_mention_unresolved"
            )
            stats["unresolved_place"] += 1
            continue

        # geocode_place() returns (longitude, latitude).
        try:
            if len(coordinates) != 2:
                raise ValueError(
                    "Expected a longitude/latitude pair"
                )

            longitude = float(coordinates[0])
            latitude = float(coordinates[1])

        except (TypeError, ValueError, IndexError, OverflowError):
            record["location_status"] = "invalid_coordinates"
            stats["invalid_coordinates"] += 1
            stats["unresolved_place"] += 1
            continue

        if not validate_coordinates(latitude, longitude):
            record["location_status"] = "invalid_coordinates"
            stats["invalid_coordinates"] += 1
            stats["unresolved_place"] += 1

        elif not inside_target_region(longitude, latitude):
            record["location_status"] = (
                "coordinates_outside_target_region"
            )
            stats["outside_region"] += 1
            stats["unresolved_place"] += 1

        else:
            record["coordinates"] = (longitude, latitude)
            record["location_status"] = "place_geocoded"
            stats["accepted"] += 1

    return stats


def main():
    """Fetch, classify, locate, and persist TopAgrar articles."""
    print("Fetching the TopAgrar RSS feed...")

    try:
        records = fetch_feed()

        distress_signals = [
            record
            for record in records
            if record["signal_type"] == "dairy_livestock_distress"
        ]

        risk_signals = [
            record
            for record in records
            if record["signal_type"] == "dairy_livestock_risk"
        ]

        print(f"Articles retrieved: {len(records)}")
        print(f"Explicit distress signals: {len(distress_signals)}")
        print(f"Articles indicating risk: {len(risk_signals)}")

        print("Processing geographic information...")
        stats = process_locations(records)

        print(
            "Locations with accepted coordinates: "
            f"{stats['accepted']}"
        )
        print(
            f"Unresolved place mentions: "
            f"{stats['unresolved_place']}"
        )
        print(
            "Articles without a recognized location: "
            f"{stats['no_location']}"
        )
        print(
            "Rejected invalid coordinates: "
            f"{stats['invalid_coordinates']}"
        )
        print(
            "Coordinates outside target region: "
            f"{stats['outside_region']}"
        )

        print("Saving records to PostgreSQL...")
        saved = save_records(records)

        print(f"Articles processed in the database: {saved}")
        print("Harvest completed successfully.")

    except Exception as error:
        print(f"Error during harvesting: {error}")
        raise


if __name__ == "__main__":
    main()
