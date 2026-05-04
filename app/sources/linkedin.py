from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.models import JobPosting
from app.sources.base import FetchResult
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.common import absolute_url, clean_text, soup_from_html


class LinkedInSource(BroadMarketJobSource):
    """Best-effort LinkedIn listing scraper (opt-in; may return empty).

    Notes:
    - LinkedIn frequently blocks automated access and may require authentication.
    - This adapter is intentionally disabled by default and must be explicitly enabled
      via the JOB_AGENT_ENABLE_LINKEDIN_SCRAPING environment variable.
    """

    source = "linkedin"

    def __init__(
        self,
        *,
        search_url: str,
        label: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(search_url=search_url, label=label, timeout_seconds=timeout_seconds)

    def fetch_jobs(self) -> list[JobPosting]:
        enabled = os.getenv("JOB_AGENT_ENABLE_LINKEDIN_SCRAPING", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            print(
                "Warning: LinkedIn source is disabled by default. "
                "Set JOB_AGENT_ENABLE_LINKEDIN_SCRAPING=true to enable (may still yield 0 results)."
            )
            return []
        return super().fetch_jobs()

    def discover_listing_urls(self, session) -> list[str]:
        _ = session
        return [self.search_url]

    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        soup = soup_from_html(result.payload)
        candidates: list[ListingCandidate] = []
        seen: set[str] = set()

        cards = soup.select(
            "div.base-card, li[data-occludable-job-id], li .base-card, article.job-search-card"
        )
        for card in cards:
            anchor = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            href = self._canonical_job_url(
                absolute_url(result.metadata["url"], anchor.get("href") if anchor else None)
            )
            if not href or href in seen:
                continue
            seen.add(href)

            title = clean_text(
                (
                    card.select_one("h3.base-search-card__title, h3, [class*='job-title']")
                    or anchor
                ).get_text(" ", strip=True)
                if (card.select_one("h3.base-search-card__title, h3, [class*='job-title']") or anchor)
                else ""
            ) or "Untitled"
            company_node = card.select_one(
                "h4.base-search-card__subtitle, a.hidden-nested-link, [class*='company-name']"
            )
            location_node = card.select_one(
                "span.job-search-card__location, [class*='job-search-card__location'], [class*='location']"
            )
            description_node = card.select_one(
                ".base-search-card__metadata, .base-search-card__snippet, [class*='description']"
            )
            candidates.append(
                ListingCandidate(
                    url=href,
                    title=title,
                    company=clean_text(
                        company_node.get_text(" ", strip=True) if company_node else "Unknown"
                    ),
                    location=clean_text(
                        location_node.get_text(" ", strip=True) if location_node else "Unknown"
                    ),
                    description=clean_text(
                        description_node.get_text(" ", strip=True) if description_node else ""
                    ),
                    metadata={
                        "search_url": result.metadata["url"],
                        "discovered_via": "listing",
                    },
                )
            )

        if candidates:
            return candidates

        anchors = soup.select("a[href*='/jobs/view/'], a[href*='linkedin.com/jobs/view']")
        for a in anchors:
            href = self._canonical_job_url(absolute_url(result.metadata["url"], a.get("href")))
            if not href or href in seen:
                continue
            seen.add(href)
            title = clean_text(a.get_text(" ", strip=True)) or "Untitled"
            candidates.append(
                ListingCandidate(
                    url=href,
                    title=title,
                    company="Unknown",
                    location="Unknown",
                    metadata={"search_url": result.metadata["url"], "discovered_via": "listing"},
                )
            )

        return candidates

    def parse_job_detail(self, candidate: ListingCandidate, result: FetchResult) -> JobPosting:
        soup = soup_from_html(result.payload)
        schema = self._extract_jobposting_schema(soup)
        title_node = soup.select_one("h1, .top-card-layout__title, [data-test-job-title]")
        company_node = soup.select_one(
            "a.topcard__org-name-link, span.topcard__flavor, .top-card-layout__card a"
        )
        location_node = soup.select_one(".topcard__flavor--bullet, .top-card-layout__first-subline span")
        description_node = soup.select_one(
            ".show-more-less-html__markup, .description__text, main, article"
        )

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
                    self._schema_nested_string(
                        schema, "jobLocation", "address", "addressLocality"
                    )
                    or self._schema_nested_string(
                        schema, "jobLocation", "address", "addressRegion"
                    )
                    or self._schema_nested_string(
                        schema, "jobLocation", "address", "addressCountry"
                    )
                )
            )
            or candidate.location,
            description=clean_text(
                description_node.get_text(" ", strip=True)
                if description_node
                else self._html_to_text(self._schema_string(schema, "description"))
            ),
            metadata=candidate.metadata,
        )

    def fallback_job_posting(self, candidate: ListingCandidate) -> JobPosting | None:
        if candidate.company in {"", "Unknown"} and candidate.location in {"", "Unknown"}:
            return None
        return super().fallback_job_posting(candidate)

    def _canonical_job_url(self, url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        match = re.search(r"/jobs/view/(\d+)", path)
        if match:
            path = f"/jobs/view/{match.group(1)}/"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

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
