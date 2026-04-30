from __future__ import annotations

from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobParser, FetchResult, JobSource, RequestsHTMLFetcher
from app.sources.common import absolute_url, clean_text, soup_from_html


class TheProtocolParser(BaseJobParser):
    def parse(self, result: FetchResult) -> list[JobPosting]:
        soup = soup_from_html(result.payload)
        postings: list[JobPosting] = []
        cards = soup.select("a[href*='/praca/'], article a")
        seen_urls: set[str] = set()

        for card in cards:
            href = absolute_url(result.metadata["url"], card.get("href"))
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            title_node = card.select_one("h2, h3") or card
            company_node = card.select_one("[class*='company'], [class*='employer']")
            location_node = card.select_one("[class*='location'], [class*='city']")
            tags = [
                clean_text(node.get_text(" ", strip=True))
                for node in card.select("[class*='tag'], [class*='badge']")
            ]

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=href,
                    title=clean_text(title_node.get_text(" ", strip=True)) or "Untitled",
                    company=clean_text(
                        company_node.get_text(" ", strip=True) if company_node else "Unknown"
                    ),
                    location=clean_text(
                        location_node.get_text(" ", strip=True) if location_node else "Unknown"
                    ),
                    metadata={
                        "search_url": result.metadata["url"],
                        "tags": ", ".join(tag for tag in tags if tag),
                    },
                )
            )
        return postings


@dataclass(slots=True)
class TheProtocolSource(JobSource):
    search_url: str
    label: str
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self._fetcher = RequestsHTMLFetcher(
            source="theprotocol",
            source_label=self.label,
            url=self.search_url,
            timeout_seconds=self.timeout_seconds,
        )
        self._parser = TheProtocolParser()

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError) as exc:
            print(
                f"Warning: The Protocol source '{self.label}' failed: {exc}. Continuing."
            )
            return []

    def source_name(self) -> str:
        return self.label
