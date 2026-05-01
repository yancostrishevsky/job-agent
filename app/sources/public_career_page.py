from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.models import JobPosting
from app.sources.base import FetchResult, JobSource, RequestsHTMLFetcher
from app.sources.common import clean_text, parse_iso_datetime, soup_from_html


@dataclass(frozen=True, slots=True)
class PublicCareerPageConfig:
    url: str
    label: str
    company_name: str | None = None


class PublicCareerPageParser:
    """Best-effort parser for schema.org JobPosting JSON-LD blocks."""

    def parse(self, result: FetchResult, *, company_hint: str | None = None) -> list[JobPosting]:
        soup = soup_from_html(result.payload)
        scripts = soup.select("script[type='application/ld+json']")

        postings: list[dict[str, Any]] = []
        for script in scripts:
            raw = script.get_text(strip=True)
            if not raw:
                continue
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                continue
            postings.extend(self._extract_jobposting_nodes(decoded))

        jobs: list[JobPosting] = []
        for node in postings:
            url = clean_text(self._string(node.get("url"))) or result.metadata.get("url", "")
            title = clean_text(self._string(node.get("title"))) or "Untitled"

            company = clean_text(
                self._string(self._nested(node, "hiringOrganization", "name"))
                or self._string(self._nested(node, "hiringOrganization", "@id"))
                or company_hint
            ) or "Unknown"

            location = clean_text(
                self._string(self._nested(node, "jobLocation", "address", "addressLocality"))
                or self._string(self._nested(node, "jobLocation", "address", "addressRegion"))
                or self._string(self._nested(node, "jobLocation", "address", "addressCountry"))
                or self._string(node.get("jobLocation"))
            ) or "Unknown"

            description = clean_text(self._string(node.get("description")))
            posted_at = parse_iso_datetime(self._string(node.get("datePosted")))
            employment_type = clean_text(self._string(node.get("employmentType"))) or None
            source_job_id = clean_text(self._string(self._nested(node, "identifier", "value"))) or None

            if not url:
                continue

            jobs.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=url,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    employment_type=employment_type,
                    source_job_id=source_job_id,
                    posted_at=posted_at,
                    metadata={**result.metadata, "parsed_via": "jsonld"},
                )
            )

        deduped: list[JobPosting] = []
        seen: set[str] = set()
        for job in jobs:
            key = str(job.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(job)
        return deduped

    def _extract_jobposting_nodes(self, decoded: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(decoded, list):
            for item in decoded:
                nodes.extend(self._extract_jobposting_nodes(item))
            return nodes

        if not isinstance(decoded, dict):
            return nodes

        graph = decoded.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                nodes.extend(self._extract_jobposting_nodes(item))

        type_value = decoded.get("@type")
        if isinstance(type_value, str) and type_value.lower() == "jobposting":
            nodes.append(decoded)
        elif isinstance(type_value, list) and any(
            isinstance(item, str) and item.lower() == "jobposting" for item in type_value
        ):
            nodes.append(decoded)

        return nodes

    def _nested(self, obj: Any, *keys: str) -> Any:
        current: Any = obj
        for key in keys:
            if isinstance(current, list):
                current = current[0] if current else None
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        if isinstance(current, list):
            return current[0] if current else None
        return current

    def _string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)


class PublicCareerPageSource(JobSource):
    """Scrape a public company careers page that embeds JSON-LD JobPosting data."""

    source = "public_career_page"

    def __init__(
        self,
        *,
        url: str,
        label: str,
        company_name: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._config = PublicCareerPageConfig(url=url, label=label, company_name=company_name)
        self._fetcher = RequestsHTMLFetcher(
            source=self.source,
            source_label=label,
            url=url,
            timeout_seconds=timeout_seconds,
        )
        self._parser = PublicCareerPageParser()

    def fetch_jobs(self) -> list[JobPosting]:
        result = self._fetcher.fetch()
        return self._parser.parse(result, company_hint=self._config.company_name)

    def source_name(self) -> str:
        return self._config.label

