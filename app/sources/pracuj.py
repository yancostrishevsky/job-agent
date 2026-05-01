from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from app.models import JobPosting
from app.sources.base import FetchResult
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.common import absolute_url, clean_text, soup_from_html


class PracujSource(BroadMarketJobSource):
    source = "pracuj"
    DEFAULT_ROBOTS_URLS = ("https://it.pracuj.pl/robots.txt", "https://www.pracuj.pl/robots.txt")
    DEFAULT_SITEMAP_URLS = (
        "https://it.pracuj.pl/sitemap.xml",
        "https://www.pracuj.pl/sitemap.xml",
    )

    def __init__(
        self,
        search_url: str,
        label: str,
        timeout_seconds: float = 20.0,
        sitemap_urls: list[str] | None = None,
    ) -> None:
        super().__init__(search_url=search_url, label=label, timeout_seconds=timeout_seconds)
        self.sitemap_urls = sitemap_urls or []

    def prepare_session(self, session: requests.Session) -> None:
        session.headers.update({"Referer": "https://it.pracuj.pl/"})
        try:
            session.get("https://it.pracuj.pl/", timeout=self.timeout_seconds)
        except requests.RequestException:
            pass

    def discover_listing_urls(self, session: requests.Session) -> list[str]:
        discovered = list(self.sitemap_urls)
        discovered.extend(self._discover_sitemaps_from_robots(session))
        if not discovered:
            discovered.extend(self.DEFAULT_SITEMAP_URLS)
        discovered.append(self.search_url)

        ordered: list[str] = []
        seen: set[str] = set()
        for url in discovered:
            if not url or url in seen:
                continue
            seen.add(url)
            ordered.append(url)
        return ordered

    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        if result.metadata["url"].endswith(".xml") or result.payload.lstrip().startswith("<?xml"):
            return self._parse_sitemap_candidates(result)
        return self._parse_listing_candidates(result)

    def parse_job_detail(
        self,
        candidate: ListingCandidate,
        result: FetchResult,
    ) -> JobPosting:
        soup = soup_from_html(result.payload)
        title_node = soup.select_one("h1, [data-test='text-positionName']")
        company_node = soup.select_one("[data-test='text-employerName'], [class*='employer']")
        location_node = soup.select_one("[data-test='offer-badge-location'], [class*='location']")
        seniority_node = soup.select_one("[data-test='sections-benefit-expander'] li, [class*='seniority']")
        employment_type_node = soup.select_one(
            "[data-test='sections-benefit-expander'] li:nth-of-type(2)"
        )
        description_node = soup.select_one("main, article, [data-test='text-benefits']")

        return JobPosting(
            source=self.source,
            source_label=self.label,
            url=candidate.url,
            title=clean_text(title_node.get_text(" ", strip=True) if title_node else candidate.title),
            company=clean_text(company_node.get_text(" ", strip=True) if company_node else candidate.company),
            location=clean_text(location_node.get_text(" ", strip=True) if location_node else candidate.location),
            description=clean_text(
                description_node.get_text(" ", strip=True) if description_node else candidate.description
            ),
            seniority=clean_text(
                seniority_node.get_text(" ", strip=True)
                if seniority_node
                else candidate.metadata.get("seniority", "")
            ) or None,
            employment_type=clean_text(
                employment_type_node.get_text(" ", strip=True)
                if employment_type_node
                else candidate.metadata.get("employment_type", "")
            ) or None,
            metadata=candidate.metadata,
        )

    def _discover_sitemaps_from_robots(self, session: requests.Session) -> list[str]:
        urls: list[str] = []
        for robots_url in self.DEFAULT_ROBOTS_URLS:
            try:
                response = session.get(robots_url, timeout=self.timeout_seconds)
                response.raise_for_status()
            except requests.RequestException:
                continue
            for line in response.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url:
                        urls.extend(self._expand_sitemap_reference(session, sitemap_url))
        return urls

    def _expand_sitemap_reference(
        self,
        session: requests.Session,
        sitemap_url: str,
    ) -> list[str]:
        try:
            response = session.get(sitemap_url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException:
            return [sitemap_url]

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return [sitemap_url]

        locs = [self._xml_text(node) for node in root.iter() if node.tag.endswith("loc")]
        child_sitemaps = [loc for loc in locs if loc.endswith(".xml")]
        jobish_urls = [
            loc for loc in locs if "/oferta/" in loc or "/praca/" in loc or "/job/" in loc
        ]
        if child_sitemaps:
            return child_sitemaps
        if jobish_urls:
            return [sitemap_url]
        return [sitemap_url]

    def _parse_sitemap_candidates(self, result: FetchResult) -> list[ListingCandidate]:
        try:
            root = ET.fromstring(result.payload)
        except ET.ParseError as exc:
            raise ValueError(f"invalid sitemap XML: {exc}") from exc

        candidates: list[ListingCandidate] = []
        for url_node in root.iter():
            if not url_node.tag.endswith("url"):
                continue
            loc_text = ""
            for child in list(url_node):
                if child.tag.endswith("loc") and child.text:
                    loc_text = child.text.strip()
                    break
            if not loc_text:
                continue
            if "/oferta/" not in loc_text and "/praca/" not in loc_text:
                continue
            candidates.append(
                ListingCandidate(url=loc_text, metadata={"discovered_via": "sitemap"})
            )
        return candidates

    def _parse_listing_candidates(self, result: FetchResult) -> list[ListingCandidate]:
        soup = soup_from_html(result.payload)
        cards = soup.select("a[data-test='link-offer'], a[href*='/oferta/'], article a[href*='/oferta/']")
        candidates: list[ListingCandidate] = []
        seen_urls: set[str] = set()
        for card in cards:
            href = absolute_url(result.metadata["url"], card.get("href"))
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            title_node = card.select_one("[data-test='offer-title'], h2, h3")
            company_node = card.select_one("[data-test='text-company-name'], h4, span")
            location_node = card.select_one(
                "[data-test='offer-badge-location'], [data-test='offer-badge-description'], div, span"
            )
            candidates.append(
                ListingCandidate(
                    url=href,
                    title=clean_text(title_node.get_text(" ", strip=True) if title_node else "Untitled"),
                    company=clean_text(company_node.get_text(" ", strip=True) if company_node else "Unknown"),
                    location=clean_text(location_node.get_text(" ", strip=True) if location_node else "Unknown"),
                    metadata={"search_url": result.metadata["url"], "discovered_via": "listing"},
                )
            )
        return candidates

    def _xml_text(self, node: ET.Element) -> str:
        return node.text.strip() if node.text else ""
