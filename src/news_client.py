from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERY = (
    '(gold OR "Federal Reserve" OR FOMC OR inflation OR "interest rates" OR '
    'dollar OR treasury OR war OR sanctions OR recession)'
)
OFFICIAL_RSS = (
    "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "https://www.bls.gov/feed/bls_latest.rss",
    "https://www.ecb.europa.eu/rss/press.html",
)

BULLISH_PHRASES = {
    "rate cut": 2, "dovish": 2, "dollar falls": 2, "dollar weakens": 2,
    "yields fall": 2, "yield falls": 2, "recession": 1, "banking crisis": 2,
    "war escalates": 2, "military strike": 1, "missile attack": 1,
    "new sanctions": 1, "gold rises": 1, "gold gains": 1,
}
BEARISH_PHRASES = {
    "rate hike": -2, "hawkish": -2, "dollar rises": -2, "dollar strengthens": -2,
    "yields rise": -2, "yield rises": -2, "strong jobs": -1,
    "inflation cools": -1, "ceasefire": -1, "peace deal": -1,
    "gold falls": -1, "gold drops": -1,
}
HIGH_IMPACT = ("fomc", "federal reserve", "powell", "cpi", "pce", "payroll", "war", "attack")


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    domain: str
    source_country: str


@dataclass(frozen=True)
class NewsMood:
    score: int
    high_impact: bool
    articles: list[NewsItem]
    summary: str


def analyze_headlines(articles: list[NewsItem]) -> NewsMood:
    raw_score = matched_up = matched_down = 0
    high_impact = False
    for article in articles:
        normalized = article.title.lower()
        article_score = sum(weight for phrase, weight in BULLISH_PHRASES.items() if phrase in normalized)
        article_score += sum(weight for phrase, weight in BEARISH_PHRASES.items() if phrase in normalized)
        raw_score += max(-3, min(3, article_score))
        matched_up += article_score > 0
        matched_down += article_score < 0
        high_impact = high_impact or any(term in normalized for term in HIGH_IMPACT)
    score = max(-3, min(3, raw_score))
    if score >= 2:
        summary = f"ข่าวหนุนทอง ({matched_up} หัวข้อบวก/{matched_down} หัวข้อลบ)"
    elif score <= -2:
        summary = f"ข่าวกดดันทอง ({matched_up} หัวข้อบวก/{matched_down} หัวข้อลบ)"
    else:
        summary = f"ข่าวยังผสมกัน ({matched_up} หัวข้อบวก/{matched_down} หัวข้อลบ)"
    return NewsMood(score, high_impact, articles[:5], summary)


class GlobalNewsClient:
    def __init__(self, cache_seconds: int = 300) -> None:
        self.cache_seconds = cache_seconds
        self._cached: NewsMood | None = None
        self._cached_at = 0.0

    def fetch(self) -> NewsMood:
        if self._cached and time.monotonic() - self._cached_at < self.cache_seconds:
            return self._cached
        try:
            articles = self._fetch_gdelt()
        except (requests.RequestException, ValueError):
            if self._cached:
                return self._cached
            articles = self._fetch_official_feeds()
        if not articles:
            raise RuntimeError("ไม่พบข่าวจากแหล่งหลักหรือแหล่งสำรอง")
        self._cached = analyze_headlines(articles)
        self._cached_at = time.monotonic()
        return self._cached

    @staticmethod
    def _fetch_gdelt() -> list[NewsItem]:
        response = requests.get(
            GDELT_URL,
            params={
                "query": QUERY, "mode": "ArtList", "maxrecords": 25,
                "timespan": "6h", "sort": "DateDesc", "format": "json",
            },
            headers={"User-Agent": "GoldGuideBot/1.0"},
            timeout=25,
        )
        response.raise_for_status()
        articles: list[NewsItem] = []
        seen: set[str] = set()
        for article in response.json().get("articles", []):
            title = str(article.get("title", "")).strip()
            key = title.lower()
            if not title or key in seen:
                continue
            seen.add(key)
            articles.append(NewsItem(
                title=title,
                url=str(article.get("url", "")),
                domain=str(article.get("domain", "unknown")),
                source_country=str(article.get("sourcecountry", "")),
            ))
            if len(articles) >= 12:
                break
        return articles

    @staticmethod
    def _fetch_official_feeds() -> list[NewsItem]:
        articles: list[NewsItem] = []
        for feed_url in OFFICIAL_RSS:
            try:
                response = requests.get(
                    feed_url,
                    headers={"User-Agent": "GoldGuideBot/1.0 (news reader)"},
                    timeout=15,
                )
                response.raise_for_status()
                root = ET.fromstring(response.content)
                for item in root.findall(".//item")[:5]:
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    if title:
                        articles.append(NewsItem(
                            title=title,
                            url=link,
                            domain=urlparse(link or feed_url).netloc,
                            source_country="Official",
                        ))
            except (requests.RequestException, ET.ParseError):
                continue
        return articles[:12]
