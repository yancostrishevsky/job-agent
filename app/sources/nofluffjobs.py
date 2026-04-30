from __future__ import annotations

from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobParser, FetchResult, JobSource, RequestsHTMLFetcher
from app.sources.common import absolute_url, clean_text, soup_from_html


class NoFluffJobsParser(BaseJobParser):
    def parse(self, result: FetchResult) -> list[JobPosting]:
        soup = soup_from_html(result.payload)
        postings: list[JobPosting] = []

        cards = soup.select("a.posting-list-item, a[href*='/job/'], a[href*='/pl/job/']")
        seen_urls: set[str] = set()
        for card in cards:
            href = absolute_url(result.metadata["url"], card.get("href"))
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            title_node = card.select_one("h3, h2, [class*='posting-title']")
            company_node = card.select_one("[class*='company'], [data-cy='listing-item-company-name']")
            location_node = card.select_one("[class*='location'], [data-cy='listing-item-city']")
            salary_node = card.select_one("[class*='salary']")

            metadata: dict[str, str] = {"search_url": result.metadata["url"]}
            if salary_node:
                metadata["salary"] = clean_text(salary_node.get_text(" ", strip=True))

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=href,
                    title=clean_text(title_node.get_text(" ", strip=True) if title_node else "Untitled"),
                    company=clean_text(company_node.get_text(" ", strip=True) if company_node else "Unknown"),
                    location=clean_text(location_node.get_text(" ", strip=True) if location_node else "Unknown"),
                    metadata=metadata,
                )
            )
        return postings


@dataclass(slots=True)
class NoFluffJobsSource(JobSource):
    search_url: str
    label: str
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self._fetcher = RequestsHTMLFetcher(
            source="nofluffjobs",
            source_label=self.label,
            url=self.search_url,
            timeout_seconds=self.timeout_seconds,
        )
        self._parser = NoFluffJobsParser()

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError) as exc:
            print(
                f"Warning: No Fluff Jobs source '{self.label}' failed: {exc}. Continuing."
            )
            return []

    def source_name(self) -> str:
        return self.label
