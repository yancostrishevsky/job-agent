from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

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
        discovered = [self.search_url]
        discovered.extend(self.sitemap_urls)
        discovered.extend(self._discover_sitemaps_from_robots(session))
        if len(discovered) == 1:
            discovered.extend(self.DEFAULT_SITEMAP_URLS)

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
        schema = self._extract_jobposting_schema(soup)
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
            title=clean_text(
                title_node.get_text(" ", strip=True) if title_node else self._schema_string(schema, "title")
            )
            or candidate.title,
            company=clean_text(
                company_node.get_text(" ", strip=True)
                if company_node
                else self._schema_nested_string(schema, "hiringOrganization", "name")
            )
            or candidate.company,
            location=clean_text(
                location_node.get_text(" ", strip=True)
                if location_node
                else (
                    self._schema_nested_string(schema, "jobLocation", "address", "addressLocality")
                    or self._schema_nested_string(schema, "jobLocation", "address", "addressRegion")
                    or self._schema_nested_string(schema, "jobLocation", "address", "addressCountry")
                )
            )
            or candidate.location,
            description=clean_text(
                description_node.get_text(" ", strip=True)
                if description_node
                else self._html_to_text(self._schema_string(schema, "description"))
            ),
            seniority=clean_text(
                seniority_node.get_text(" ", strip=True)
                if seniority_node
                else candidate.metadata.get("seniority", "")
            ) or None,
            employment_type=clean_text(
                employment_type_node.get_text(" ", strip=True)
                if employment_type_node
                else (
                    candidate.metadata.get("employment_type", "")
                    or self._schema_string(schema, "employmentType")
                )
            ) or None,
            source_job_id=(
                candidate.metadata.get("source_job_id")
                or self._schema_nested_string(schema, "identifier", "value")
            ),
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
        cards = soup.select(
            "[data-test='section-offer'], article[data-test='section-offer'], "
            "a[data-test='link-offer'], a[href*='/oferta/'], article a[href*='/oferta/']"
        )
        candidates: list[ListingCandidate] = []
        seen_urls: set[str] = set()
        for card in cards:
            link_node = card if card.name == "a" else card.select_one("a[href*='/oferta/']")
            href = absolute_url(result.metadata["url"], link_node.get("href") if link_node else None)
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            title_node = card.select_one("[data-test='offer-title'], h2, h3")
            company_node = card.select_one(
                "[data-test='text-company-name'], [data-test='offer-company-name'], h4"
            )
            location_node = card.select_one(
                "[data-test='offer-badge-location'], [data-test='text-regionName'], "
                "[data-test='offer-badge-description']"
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

    def _extract_jobposting_schema(self, soup) -> dict[str, Any]:
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.get_text(strip=True)
            if not raw:
                continue
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                continue
            jobposting = self._find_jobposting_node(decoded)
            if jobposting is not None:
                return jobposting
        return {}

    def _find_jobposting_node(self, payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, list):
            for item in payload:
                match = self._find_jobposting_node(item)
                if match is not None:
                    return match
            return None
        if not isinstance(payload, dict):
            return None
        node_type = payload.get("@type")
        if isinstance(node_type, str) and node_type.lower() == "jobposting":
            return payload
        if isinstance(node_type, list) and any(
            isinstance(item, str) and item.lower() == "jobposting" for item in node_type
        ):
            return payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                match = self._find_jobposting_node(item)
                if match is not None:
                    return match
        return None

    def _schema_nested_string(self, payload: dict[str, Any], *keys: str) -> str | None:
        current: Any = payload
        for key in keys:
            if isinstance(current, list):
                current = current[0] if current else None
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return self._schema_value_to_string(current)

    def _schema_string(self, payload: dict[str, Any], key: str) -> str | None:
        return self._schema_value_to_string(payload.get(key))

    def _schema_value_to_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            value = value[0] if value else None
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return None
        return str(value)

    def _html_to_text(self, value: str | None) -> str:
        if not value:
            return ""
        return clean_text(soup_from_html(value).get_text(" ", strip=True))
