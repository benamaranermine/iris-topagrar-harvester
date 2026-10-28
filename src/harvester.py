
"""Fetch, parse and classify TopAgrar RSS articles."""

import os
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

from src.locations import resolve_location


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_RSS_URL = (
    "https://www.topagrar.com/top_agrar_online-10090692.xml"
)


# Explicit evidence of closure, insolvency, or cessation of activity.
DISTRESS_TERMS = (
    "insolvenz",
    "insolvent",
    "zahlungsunfähig",
    "zahlungsunfaehig",
    "liquidation",
    "liquidiert",
    "hofaufgabe",
    "betriebsaufgabe",
    "betriebsschließung",
    "betriebsschliessung",
    "schließung des betriebs",
    "schliessung des betriebs",
    "aufgabe des betriebs",
    "aufgegeben",
    "gibt auf",
    "geben auf",
    "pleite",
    "bankrott",
    "zwangsversteigerung",
    "farm closure",
    "farm liquidation",
    "bankruptcy",
)

# Terms indicating dairy or livestock farming.
FARM_TERMS = (
    "milch",
    "milchvieh",
    "milchbetrieb",
    "milchbauer",
    "milchbauern",
    "milchkuh",
    "milchkühe",
    "milchkuehe",
    "milchproduktion",
    "rinderhaltung",
    "rinderbetrieb",
    "rinder",
    "viehhaltung",
    "viehbetrieb",
    "viehhalter",
    "tierhaltung",
    "landwirtschaftsbetrieb",
    "landwirt",
    "landwirte",
    "bauernhof",
    "bauernhöfe",
    "bauernhoefe",
    "dairy",
    "livestock",
    "farm",
)

# Economic or structural risk indicators, not proof of closure.
RISK_TERMS = (
    "unter druck",
    "existenzbedroht",
    "existenz bedroht",
    "existenzgefährdet",
    "existenzgefaehrdet",
    "verlieren glauben an zukunft",
    "wirtschaftliche schwierigkeiten",
    "finanzielle schwierigkeiten",
    "steigende kosten",
    "kostensteigerung",
    "futterengpass",
    "futterengpässe",
    "futterknappheit",
    "futtermangel",
    "futterkosten",
    "trockenheit",
    "dürre",
    "duerre",
    "milchpreis",
    "milchpreise",
    "zukunft der betriebe",
    "zukunft der höfe",
    "zukunft der hoefe",
    "economic pressure",
        "preisdruck",
    "preise geben nach",
    "geben weiter nach",
    "gewinn sinkt",
    "gewinnrückgang",
    "schuldenabbau",
    "kosten nicht gedeckt",
    "kostendeckende milchpreise",
    "futterversorgung angespannt",
    "proteinversorgung angespannt",
    "wirtschaftlich unter druck",
    "financial difficulties",
)


def normalize_date(value):
    """Convert a publication date to ISO-8601, or return None."""
    if not value:
        return None

    try:
        date = parsedate_to_datetime(value)

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        return date.isoformat()

    except (TypeError, ValueError, OverflowError):
        return None


def classify_signal(title, summary=""):
    """
    Classify an article as explicit distress, risk, or no signal.

    Explicit distress takes precedence over general risk indicators.
    Keyword matching is a screening heuristic, not a factual verdict.
    """
    text = f"{title or ''} {summary or ''}".casefold()

    has_farm_context = any(
        term in text for term in FARM_TERMS
    )

    if not has_farm_context:
        return None

    if any(term in text for term in DISTRESS_TERMS):
        return "dairy_livestock_distress"

    if any(term in text for term in RISK_TERMS):
        return "dairy_livestock_risk"

    return None


def is_relevant_signal(title, summary=""):
    """
    Return True only for explicit livestock or dairy distress signals.

    Risk-only articles return False.
    """
    return (
        classify_signal(title, summary)
        == "dairy_livestock_distress"
    )


def parse_feed(xml_content):
    """Parse RSS/Atom XML and return normalized article records."""
    parsed = feedparser.parse(xml_content)

    if parsed.bozo and not parsed.entries:
        raise ValueError(
            "Invalid or unreadable RSS/Atom feed: "
            f"{parsed.bozo_exception}"
        )

    records = []
    seen_ids = set()

    for entry in parsed.entries:
        link = entry.get("link")
        source_id = entry.get("id") or link
        title = (entry.get("title") or "").strip()
        summary = (entry.get("summary") or "").strip()

        # Skip entries without the minimum required information.
        if not source_id or not title or not link:
            continue

        # Remove duplicate articles within the same feed.
        if source_id in seen_ids:
            continue

        seen_ids.add(source_id)

        signal_type = classify_signal(title, summary)

        # Extract place mentions and any explicit coordinates.
        location = resolve_location(title, summary)

        records.append(
            {
                "source": "topagrar",
                "source_id": source_id,
                "title": title,
                "published_at": normalize_date(
                    entry.get("published")
                ),
                "source_url": link,
                "summary": summary,
                "signal_type": signal_type,
                "location_text": location.get("location_text"),
                "coordinates": location.get("coordinates"),
                "geometry": None,
                "location_status": location.get(
                    "status", "unresolved"
                ),
                "risk_context": (
                    signal_type == "dairy_livestock_risk"
                ),
            }
        )

    return records


def fetch_feed(url=None, timeout=20):
    """Download and parse the configured RSS/Atom feed."""
    url = url or os.getenv("RSS_URL") or DEFAULT_RSS_URL

    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "IRIS-SIG-33 research harvester/1.0"
        },
    )
    response.raise_for_status()

    records = parse_feed(response.content)

    if not records:
        raise ValueError(
            "The feed returned no usable article records."
        )

    return records


if __name__ == "__main__":
    articles = fetch_feed()
    print(f"Articles récupérés : {len(articles)}")
    print(
        "Signaux de détresse explicite : "
        f"{sum(r['signal_type'] == 'dairy_livestock_distress' for r in articles)}"
    )
    print(
        "Articles présentant un risque : "
        f"{sum(r['signal_type'] == 'dairy_livestock_risk' for r in articles)}"
    )
