
"""Run the IRIS-SIG-33 RSS harvesting pipeline."""

from src.harvester import fetch_feed
from src.database import save_records
from src.locations import geocode_place


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


def main():
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

        print("Geocoding detected locations...")

        geocoded_count = 0
        unresolved_place_count = 0
        no_location_count = 0

        for record in records:
            place = record.get("location_text")

            # Clear previous coordinates so invalid or outdated
            # geometries are not retained during database updates.
            record["coordinates"] = None

            if not place:
                record["location_status"] = "unresolved"
                no_location_count += 1
                continue

            # Multiple place names are ambiguous.
            if ";" in place:
                record["location_status"] = (
                    "place_mention_unresolved"
                )
                unresolved_place_count += 1
                continue

            # Only geocode selected, sufficiently specific towns.
            query = PRECISE_PLACES.get(place.casefold())

            if not query:
                record["location_status"] = (
                    "place_mention_unresolved"
                )
                unresolved_place_count += 1
                continue

            coordinates = geocode_place(query)

            if coordinates:
                longitude, latitude = coordinates

                # Approximate geographic filter for UTM zone 32N.
                if (
                    6 <= longitude <= 12
                    and 47 <= latitude <= 55
                ):
                    record["coordinates"] = (
                        longitude,
                        latitude,
                    )
                    record["location_status"] = "place_geocoded"
                    geocoded_count += 1
                else:
                    record["location_status"] = (
                        "place_mention_unresolved"
                    )
                    unresolved_place_count += 1
            else:
                record["location_status"] = (
                    "place_mention_unresolved"
                )
                unresolved_place_count += 1

        print(f"Locations successfully geocoded: {geocoded_count}")
        print(f"Unresolved place mentions: {unresolved_place_count}")
        print(f"Articles without a recognized location: {no_location_count}")

        print("Saving records to PostgreSQL...")
        saved = save_records(records)

        print(f"Articles processed in the database: {saved}")
        print("Harvest completed successfully.")

    except Exception as error:
        print(f"Error during harvesting: {error}")
        raise


if __name__ == "__main__":
    main()
