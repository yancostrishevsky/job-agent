from __future__ import annotations

from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobFetcher, BaseJobParser, FetchResult, JobSource
from app.sources.common import absolute_url, clean_text, soup_from_html


class PracujParser(BaseJobParser):
    def parse(self, result: FetchResult) -> list[JobPosting]:
        soup = soup_from_html(result.payload)
        postings: list[JobPosting] = []

        cards = soup.select("a[data-test='link-offer'], a.tiles_c8yvgfl, a[href*='/oferta/']")
        seen_urls: set[str] = set()
        for card in cards:
            href = absolute_url(result.metadata["url"], card.get("href"))
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            title = clean_text(
                card.get("aria-label")
                or (card.select_one("[data-test='offer-title']") or card.select_one("h2, h3")).get_text(" ", strip=True)
                if (card.select_one("[data-test='offer-title']") or card.select_one("h2, h3"))
                else ""
            )
            company = clean_text(
                (card.select_one("[data-test='text-company-name']") or card.select_one("h4, span")).get_text(" ", strip=True)
                if (card.select_one("[data-test='text-company-name']") or card.select_one("h4, span"))
                else "Unknown"
            )
            location = clean_text(
                (card.select_one("[data-test='offer-badge-description']") or card.select_one("[data-test='offer-badge-location']") or card.select_one("div, span")).get_text(" ", strip=True)
                if (card.select_one("[data-test='offer-badge-description']") or card.select_one("[data-test='offer-badge-location']") or card.select_one("div, span"))
                else "Unknown"
            )

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=href,
                    title=title or "Untitled",
                    company=company or "Unknown",
                    location=location or "Unknown",
                    metadata={"search_url": result.metadata["url"]},
                )
            )
        return postings


@dataclass(frozen=True, slots=True)
class PracujFetcher(BaseJobFetcher):
    search_url: str
    label: str
    timeout_seconds: float = 20.0

    def fetch(self) -> FetchResult:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://it.pracuj.pl/",
        }
        session = requests.Session()
        session.headers.update(headers)

        # Warm up the session first; Pracuj often rejects bare one-shot requests.
        try:
            session.get("https://it.pracuj.pl/", timeout=self.timeout_seconds)
        except requests.RequestException:
            pass

        response = session.get(
            self.search_url,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source="pracuj",
            source_label=self.label,
            payload=response.text,
            metadata={"url": self.search_url},
        )


@dataclass(slots=True)
class PracujSource(JobSource):
    search_url: str
    label: str
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self._fetcher = PracujFetcher(
            search_url=self.search_url,
            label=self.label,
            timeout_seconds=self.timeout_seconds,
        )
        self._parser = PracujParser()

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError) as exc:
            print(f"Warning: Pracuj source '{self.label}' failed: {exc}. Continuing.")
            return []

    def source_name(self) -> str:
        return self.label
