from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MACRO_QUERY = (
    '(gold OR "Federal Reserve" OR FOMC OR inflation OR "interest rates" OR '
    'dollar OR treasury OR war OR sanctions OR recession)'
)
ANALYST_QUERY = (
    '("gold outlook" OR "gold forecast" OR "gold analysis" OR "XAUUSD analysis" OR '
    '"precious metals outlook" OR "gold technical analysis")'
)
FLOW_QUERY = (
    '("central bank gold" OR "gold ETF" OR "gold demand" OR "gold reserves" OR '
    '"COMEX gold" OR "gold futures" OR "safe haven gold")'
)
NEWS_QUERIES = (
    ("ข่าวตลาด", MACRO_QUERY),
    ("นักวิเคราะห์", ANALYST_QUERY),
    ("ข้อมูลตลาด", FLOW_QUERY),
)
OFFICIAL_RSS = (
    ("https://www.federalreserve.gov/feeds/press_monetary.xml", "Federal Reserve"),
    ("https://www.federalreserve.gov/feeds/speeches.xml", "Federal Reserve speeches"),
    ("https://www.bls.gov/feed/bls_latest.rss", "US BLS"),
    ("https://www.ecb.europa.eu/rss/press.html", "ECB"),
    ("https://www.cftc.gov/RSS/RSSGP/rssgp.xml", "US CFTC"),
    ("https://www.bis.org/doclist/all_pressrels.rss", "BIS"),
    ("https://www.bis.org/doclist/cbspeeches.rss", "Central-bank speeches"),
)

ANALYST_DOMAINS = (
    "gold.org", "kitco.com", "fxstreet.com", "cmegroup.com", "lbma.org.uk",
    "ing.com", "saxo", "ig.com", "marketpulse.com", "dailyfx.com",
)
RELEVANT_TERMS = (
    "gold", "precious metal", "federal reserve", "fomc", "interest rate", "inflation",
    "consumer price", "producer price", "employment", "payroll", "dollar", "treasury",
    "central bank", "monetary policy", "commodity", "futures", "geopolit", "sanction",
)

BULLISH_PHRASES = {
    "rate cut": 2, "dovish": 2, "dollar falls": 2, "dollar weakens": 2,
    "weaker dollar": 2, "lower yields": 2, "safe-haven demand": 2,
    "safe haven demand": 2, "central bank buying": 2, "etf inflows": 2,
    "yields fall": 2, "yield falls": 2, "recession": 1, "banking crisis": 2,
    "geopolitical tensions": 1, "war escalates": 2, "military strike": 1, "missile attack": 1,
    "new sanctions": 1, "gold rises": 1, "gold gains": 1,
}
BEARISH_PHRASES = {
    "rate hike": -2, "hawkish": -2, "dollar rises": -2, "dollar strengthens": -2,
    "stronger dollar": -2, "higher yields": -2, "etf outflows": -2,
    "profit taking": -1, "easing tensions": -1,
    "yields rise": -2, "yield rises": -2, "strong jobs": -1,
    "inflation cools": -1, "ceasefire": -1, "peace deal": -1,
    "gold falls": -1, "gold drops": -1,
}
HIGH_IMPACT = (
    "fomc", "federal reserve", "powell", "cpi", "ppi", "pce", "payroll", "nonfarm",
    "unemployment", "war", "attack", "sanctions", "central bank", "geopolitical",
)


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    domain: str
    source_country: str
    category: str = "ข่าวตลาด"


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
    return NewsMood(score, high_impact, articles[:10], summary)


def _category_for_domain(domain: str, fallback: str) -> str:
    normalized = domain.lower()
    if any(marker in normalized for marker in ANALYST_DOMAINS):
        return "นักวิเคราะห์/วิจัย"
    return fallback


def _diversify(articles: list[NewsItem], limit: int = 18) -> list[NewsItem]:
    """Deduplicate headlines and stop one publisher dominating the signal."""
    buckets = {"ทางการ": [], "นักวิเคราะห์/วิจัย": [], "นักวิเคราะห์": [], "ข้อมูลตลาด": [], "ข่าวตลาด": []}
    seen_titles: set[str] = set()
    for article in articles:
        key = " ".join(article.title.lower().split())
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        buckets.setdefault(article.category, []).append(article)

    selected: list[NewsItem] = []
    domain_counts: dict[str, int] = {}
    order = ("ทางการ", "นักวิเคราะห์/วิจัย", "นักวิเคราะห์", "ข้อมูลตลาด", "ข่าวตลาด")
    while len(selected) < limit and any(buckets.values()):
        progressed = False
        for category in order:
            bucket = buckets.get(category, [])
            while bucket:
                article = bucket.pop(0)
                domain = article.domain.lower()
                if domain_counts.get(domain, 0) >= 2:
                    continue
                selected.append(article)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


class GlobalNewsClient:
    def __init__(self, cache_seconds: int = 300) -> None:
        self.cache_seconds = cache_seconds
        self._cached: NewsMood | None = None
        self._cached_at = 0.0

    def fetch(self) -> NewsMood:
        if self._cached and time.monotonic() - self._cached_at < self.cache_seconds:
            return self._cached
        articles: list[NewsItem] = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self._fetch_gdelt, query, category): category
                for category, query in NEWS_QUERIES
            }
            futures[executor.submit(self._fetch_official_feeds)] = "ทางการ"
            for future in as_completed(futures):
                try:
                    articles.extend(future.result())
                except (requests.RequestException, ValueError, ET.ParseError):
                    continue
        articles = _diversify(articles)
        if not articles:
            if self._cached:
                return self._cached
            raise RuntimeError("ไม่พบข่าวจากแหล่งหลักหรือแหล่งสำรอง")
        self._cached = analyze_headlines(articles)
        self._cached_at = time.monotonic()
        return self._cached

    @staticmethod
    def _fetch_gdelt(query: str = MACRO_QUERY, category: str = "ข่าวตลาด") -> list[NewsItem]:
        response = requests.get(
            GDELT_URL,
            params={
                "query": query, "mode": "ArtList", "maxrecords": 40,
                "timespan": "12h", "sort": "DateDesc", "format": "json",
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
            domain = str(article.get("domain", "unknown"))
            articles.append(NewsItem(
                title=title,
                url=str(article.get("url", "")),
                domain=domain,
                source_country=str(article.get("sourcecountry", "")),
                category=_category_for_domain(domain, category),
            ))
            if len(articles) >= 20:
                break
        return articles

    @staticmethod
    def _fetch_official_feeds() -> list[NewsItem]:
        articles: list[NewsItem] = []
        for feed_url, source_name in OFFICIAL_RSS:
            try:
                response = requests.get(
                    feed_url,
                    headers={"User-Agent": "GoldGuideBot/1.0 (news reader)"},
                    timeout=15,
                )
                response.raise_for_status()
                root = ET.fromstring(response.content)
                entries = root.findall(".//item") or root.findall(".//{*}entry")
                for item in entries[:10]:
                    title = (item.findtext("title") or item.findtext("{*}title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    if not link:
                        link_node = item.find("{*}link")
                        link = str(link_node.get("href", "")) if link_node is not None else ""
                    normalized = title.lower()
                    if title and any(term in normalized for term in RELEVANT_TERMS):
                        articles.append(NewsItem(
                            title=title,
                            url=link,
                            domain=urlparse(link or feed_url).netloc,
                            source_country=source_name,
                            category="ทางการ",
                        ))
            except (requests.RequestException, ET.ParseError):
                continue
        return articles[:24]
