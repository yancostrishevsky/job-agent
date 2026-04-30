from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobFetcher, BaseJobParser, FetchResult, JobSource
from app.sources.common import clean_text, parse_unix_millis


@dataclass(frozen=True, slots=True)
class LeverFetcher(BaseJobFetcher):
    handle: str
    label: str
    timeout_seconds: float = 20.0
    page_limit: int = 100

    def fetch(self) -> FetchResult:
        response = requests.get(
            f"https://api.lever.co/v0/postings/{self.handle}",
            params={"mode": "json", "limit": self.page_limit},
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source="lever",
            source_label=self.label,
            payload=response.text,
            metadata={"handle": self.handle, "format": "json"},
        )


@dataclass(frozen=True, slots=True)
class LeverRSSFetcher(BaseJobFetcher):
    handle: str
    label: str
    timeout_seconds: float = 20.0

    def fetch(self) -> FetchResult:
        response = requests.get(
            f"https://jobs.lever.co/{self.handle}/rss",
            headers={"Accept": "application/xml"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source="lever",
            source_label=self.label,
            payload=response.text,
            metadata={"handle": self.handle, "format": "rss"},
        )


class LeverParser(BaseJobParser):
    def parse(self, result: FetchResult) -> list[JobPosting]:
        if result.metadata.get("format") == "rss":
            return self._parse_rss(result)
        return self._parse_json(result)

    def _parse_json(self, result: FetchResult) -> list[JobPosting]:
        payload = json.loads(result.payload)
        if not isinstance(payload, list):
            return []

        postings: list[JobPosting] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
            url = item.get("hostedUrl") or item.get("applyUrl")
            if not isinstance(url, str) or not url.strip():
                continue

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=url.strip(),
                    title=clean_text(item.get("text") if isinstance(item.get("text"), str) else "Untitled"),
                    company=clean_text(result.metadata["handle"]),
                    location=clean_text(categories.get("location") if isinstance(categories.get("location"), str) else "") or "Unknown",
                    description=clean_text(item.get("description") if isinstance(item.get("description"), str) else ""),
                    seniority=clean_text(categories.get("commitment") if isinstance(categories.get("commitment"), str) else "") or None,
                    employment_type=clean_text(categories.get("commitment") if isinstance(categories.get("commitment"), str) else "") or None,
                    category=clean_text(categories.get("team") if isinstance(categories.get("team"), str) else "") or None,
                    source_job_id=str(item.get("id")) if item.get("id") is not None else None,
                    posted_at=parse_unix_millis(item.get("createdAt")),
                    metadata={"handle": result.metadata["handle"]},
                )
            )
        return postings

    def _parse_rss(self, result: FetchResult) -> list[JobPosting]:
        root = ET.fromstring(result.payload)
        nodes = root.findall(".//item") or root.findall(".//entry")
        postings: list[JobPosting] = []
        for node in nodes:
            title = clean_text(self._find_text(node, "title") or "Untitled")
            url = clean_text(self._find_text(node, "link") or self._find_text(node, "guid"))
            if not url:
                continue
            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=url,
                    title=title,
                    company=clean_text(result.metadata["handle"]),
                    location=clean_text(self._find_text(node, "location")) or "Unknown",
                    description=clean_text(
                        self._find_text(node, "description")
                        or self._find_text(node, "content:encoded")
                    ),
                    seniority=clean_text(self._find_text(node, "commitment")) or None,
                    employment_type=clean_text(self._find_text(node, "commitment")) or None,
                    category=clean_text(self._find_text(node, "category")) or None,
                    source_job_id=clean_text(self._find_text(node, "guid")) or None,
                    metadata={"handle": result.metadata["handle"]},
                )
            )
        return postings

    def _find_text(self, node: ET.Element, tag_name: str) -> str | None:
        direct = node.find(f".//{tag_name}")
        if direct is not None and direct.text:
            return direct.text
        for child in node.iter():
            if child.tag.endswith(tag_name) and child.text:
                return child.text
        return None


@dataclass(slots=True)
class LeverSource(JobSource):
    handle: str
    label: str
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self._fetcher = LeverFetcher(
            handle=self.handle,
            label=self.label,
            timeout_seconds=self.timeout_seconds,
        )
        self._rss_fetcher = LeverRSSFetcher(
            handle=self.handle,
            label=self.label,
            timeout_seconds=self.timeout_seconds,
        )
        self._parser = LeverParser()

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError, ET.ParseError) as exc:
            try:
                return self._parser.parse(self._rss_fetcher.fetch())
            except (requests.RequestException, ValueError, ET.ParseError) as fallback_exc:
                print(
                    f"Warning: Lever source '{self.handle}' failed: {exc}; RSS fallback also failed: {fallback_exc}. Continuing."
                )
                return []

    def source_name(self) -> str:
        return self.label
