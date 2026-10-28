
from unittest.mock import Mock

import pytest
import requests

from src.harvester import (
    classify_signal,
    fetch_feed,
    is_relevant_signal,
    normalize_date,
    parse_feed,
)


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TopAgrar test feed</title>
    <item>
      <title>Milchviehbetrieb meldet Insolvenz</title>
      <link>https://example.com/article-1</link>
      <guid>article-1</guid>
      <pubDate>Mon, 26 Oct 2026 10:00:00 +0000</pubDate>
      <description>Ein Milchbetrieb ist betroffen.</description>
    </item>
    <item>
      <title>Neue Technik für Landwirte</title>
      <link>https://example.com/article-2</link>
      <guid>article-2</guid>
      <pubDate>Mon, 26 Oct 2026 11:00:00 +0000</pubDate>
      <description>Ein Bericht über neue Technik.</description>
    </item>
    <item>
      <title>Milchviehbetrieb meldet Insolvenz</title>
      <link>https://example.com/article-1</link>
      <guid>article-1</guid>
      <pubDate>Mon, 26 Oct 2026 10:00:00 +0000</pubDate>
      <description>Duplikat.</description>
    </item>
  </channel>
</rss>
""".encode("utf-8")


def test_normalize_date_valid():
    result = normalize_date("Mon, 26 Oct 2026 10:00:00 +0000")
    assert result == "2026-10-26T10:00:00+00:00"


def test_normalize_date_missing_or_invalid():
    assert normalize_date(None) is None
    assert normalize_date("not a date") is None


def test_relevant_dairy_distress_article():
    assert is_relevant_signal(
        "Milchviehbetrieb meldet Insolvenz",
        "Ein Milchbetrieb ist betroffen.",
    )


def test_unrelated_article_is_not_relevant():
    assert not is_relevant_signal(
        "Neue Technik für Landwirte",
        "Ein Bericht über neue Technik.",
    )


def test_parse_feed_and_remove_duplicates():
    records = parse_feed(SAMPLE_FEED)

    assert len(records) == 2
    assert records[0]["source"] == "topagrar"
    assert records[0]["source_id"] == "article-1"
    assert records[0]["signal_type"] == "dairy_livestock_distress"
    assert records[1]["signal_type"] is None
    assert records[0]["geometry"] is None


def test_invalid_feed_raises_error():
    with pytest.raises(ValueError):
        parse_feed(b"<this is not valid RSS")


def test_fetch_feed_uses_http_response(monkeypatch):
    response = Mock()
    response.content = SAMPLE_FEED
    response.raise_for_status.return_value = None

    request_mock = Mock(return_value=response)
    monkeypatch.setattr("src.harvester.requests.get", request_mock)

    records = fetch_feed("https://example.com/feed.xml")

    assert len(records) == 2
    request_mock.assert_called_once()
    response.raise_for_status.assert_called_once()


def test_classify_explicit_distress():
    assert classify_signal(
        "Milchviehbetrieb meldet Insolvenz"
    ) == "dairy_livestock_distress"


def test_classify_structural_risk():
    assert classify_signal(
        "Niederländische Viehhalter verlieren Glauben an Zukunft"
    ) == "dairy_livestock_risk"


def test_classify_feed_shortage_as_risk():
    assert classify_signal(
        "Wie Milchkuhhalter Futterengpässe rechtzeitig abfedern können"
    ) == "dairy_livestock_risk"


def test_unrelated_article_has_no_signal():
    assert classify_signal(
        "Neue Technik für Landwirte",
        "Ein Bericht über neue Technik.",
    ) is None


def test_fetch_feed_raises_http_error(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 Not Found"
    )

    monkeypatch.setattr(
        "src.harvester.requests.get",
        Mock(return_value=response),
    )

    with pytest.raises(requests.exceptions.HTTPError):
        fetch_feed("https://example.com/missing-feed.xml")


def test_fetch_feed_raises_error_for_empty_feed(monkeypatch):
    response = Mock()
    response.content = b"""<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Empty test feed</title>
      </channel>
    </rss>
    """
    response.raise_for_status.return_value = None

    monkeypatch.setattr(
        "src.harvester.requests.get",
        Mock(return_value=response),
    )

    with pytest.raises(ValueError, match="no usable article records"):
        fetch_feed("https://example.com/empty-feed.xml")


def test_parse_feed_skips_entries_missing_required_fields():
    feed = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Incomplete test feed</title>
        <item>
          <title>Article without a link</title>
          <guid isPermaLink="false">missing-link</guid>
        </item>
        <item>
          <link>https://example.com/missing-title</link>
          <guid>missing-title</guid>
        </item>
        <item>
          <title>Article without an identifier</title>
          <link>https://example.com/missing-id</link>
        </item>
        <item>
          <title>Valid dairy article</title>
          <link>https://example.com/valid-article</link>
          <guid>valid-article</guid>
        </item>
      </channel>
    </rss>
    """

    records = parse_feed(feed)

    assert len(records) == 2

    titles = {record["title"] for record in records}

    assert "Article without a link" not in titles
    assert "Article without an identifier" in titles
    assert "Valid dairy article" in titles

    fallback_record = next(
        record
        for record in records
        if record["title"] == "Article without an identifier"
    )
    assert fallback_record["source_id"] == "https://example.com/missing-id"
