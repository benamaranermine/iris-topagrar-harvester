
"""Extract and validate geographic clues from article text."""

import re
import unicodedata
import json
import time
from pathlib import Path

import requests

# Known place names relevant to German agricultural news.
# This is a conservative starter list, not a complete gazetteer.
KNOWN_PLACES = {
    "deutschland": "Deutschland",
    "schleswig-holstein": "Schleswig-Holstein",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "nrw": "Nordrhein-Westfalen",
    "norddeutschland": "Norddeutschland",
    "bayern": "Bayern",
    "löbau": "Löbau",
    "loebau": "Löbau",
    "staufen": "Staufen",
    "sosberg": "Sosberg",
    "hofbieber": "Hofbieber",
    "neustadt-glewe": "Neustadt-Glewe",
    "minnesota": "Minnesota",
    "alabama": "Alabama",
    "kansas": "Kansas",
    "frankreich": "Frankreich",
    "ukraine": "Ukraine",
    "china": "China",
    "europa": "Europa",
    "großbritannien": "Großbritannien",
    "grossbritannien": "Großbritannien",
    "usa": "USA",
}


COORDINATE_PATTERN = re.compile(
    r"(?P<lat>-?\d{1,2}\.\d+)\s*[,;/]\s*"
    r"(?P<lon>-?\d{1,3}\.\d+)"
)


def normalize_place_name(value):
    """Normalize a place name for case-insensitive matching."""
    value = unicodedata.normalize("NFKC", value or "")
    return value.strip().casefold()


def validate_coordinates(latitude, longitude):
    """Check whether latitude and longitude are in valid ranges."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False

    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def extract_coordinates(text):
    """Extract the first valid decimal latitude/longitude pair."""
    if not text:
        return None

    for match in COORDINATE_PATTERN.finditer(text):
        latitude = float(match.group("lat"))
        longitude = float(match.group("lon"))

        if validate_coordinates(latitude, longitude):
            return latitude, longitude

    return None


def extract_place_mentions(text):
    """
    Find mentions matching the known-place list.

    Unknown capitalized words are deliberately ignored to reduce
    false positives from German nouns and sentence capitalization.
    """
    if not text:
        return []

    found = []

    # Match longer place names first to avoid partial matches.
    for key, display_name in sorted(
        KNOWN_PLACES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            rf"(?<!\w){re.escape(key)}(?!\w)",
            re.IGNORECASE,
        )

        if pattern.search(text) and display_name not in found:
            found.append(display_name)

    return found


def resolve_location(title, summary=""):
    """Return geographic clues without inventing coordinates."""
    text = f"{title or ''} {summary or ''}"

    coordinates = extract_coordinates(text)
    places = extract_place_mentions(text)

    if coordinates:
        status = "coordinates_found"
    elif places:
        status = "place_mention_unresolved"
    else:
        status = "unresolved"

    return {
        "location_text": "; ".join(places) if places else None,
        "coordinates": coordinates,
        "status": status,
    }
    
"""Geocode a place name using the Nominatim service."""

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "geocode_cache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "IRIS-SIG-33 educational research project"


def geocode_place(place_name):
    """
    Return (longitude, latitude) for a place, or None.

    Results are cached to avoid repeating requests.
    A returned coordinate identifies the matched place, not
    necessarily the location of a farm.
    """
    if not place_name:
        return None

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    key = normalize_place_name(place_name)

    if key in cache:
        return tuple(cache[key]) if cache[key] else None

    # Respect the public service's low request rate.
    time.sleep(1.1)

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": place_name,
                "format": "jsonv2",
                "limit": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            coordinates = None
        else:
            latitude = float(results[0]["lat"])
            longitude = float(results[0]["lon"])

            if validate_coordinates(latitude, longitude):
                coordinates = [longitude, latitude]
            else:
                coordinates = None

    except (requests.RequestException, ValueError, KeyError, TypeError):
        # Do not cache temporary service or network errors.
        return None

    cache[key] = coordinates
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return tuple(coordinates) if coordinates else None

