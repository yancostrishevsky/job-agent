from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field

import requests

from app.models import JobPosting
from app.sources.base import FetchResult, JobSource


DEFAULT_BROWSER_HEADERS = {
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
}


@dataclass(frozen=True, slots=True)
class ListingCandidate:
    url: str
    title: str = "Untitled"
    company: str = "Unknown"
    location: str = "Unknown"
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class BroadMarketJobSource(JobSource):
    """Reusable fetch/discovery pattern for broad-market portals."""

    source: str = "broad-market"

    def __init__(
        self,
        search_url: str,
        label: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.search_url = search_url
        self.label = label
        self.timeout_seconds = timeout_seconds

    def fetch_jobs(self) -> list[JobPosting]:
        session = self._build_session()
        jobs: list[JobPosting] = []

        for listing_url in self.discover_listing_urls(session):
            try:
                listing_result = self.fetch_listing_page(session, listing_url)
                candidates = self.parse_listing_cards(listing_result)
            except requests.RequestException as exc:
                self._log_http_warning("listing discovery", listing_url, exc)
                continue
            except ValueError as exc:
                print(f"Warning: {self.label} listing parse failed for {listing_url}: {exc}.")
                continue

            for candidate in candidates:
                try:
                    detail_result = self.fetch_job_detail(session, candidate)
                    jobs.append(self.parse_job_detail(candidate, detail_result))
                except requests.RequestException as exc:
                    self._log_http_warning("job detail", candidate.url, exc)
                    fallback = self.fallback_job_posting(candidate)
                    if fallback is not None:
                        jobs.append(fallback)
                except ValueError as exc:
                    print(f"Warning: {self.label} detail parse failed for {candidate.url}: {exc}.")
                    fallback = self.fallback_job_posting(candidate)
                    if fallback is not None:
                        jobs.append(fallback)

        deduped: list[JobPosting] = []
        seen_urls: set[str] = set()
        for job in jobs:
            job_url = str(job.url)
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            deduped.append(job)
        return deduped

    def source_name(self) -> str:
        return self.label

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(DEFAULT_BROWSER_HEADERS)
        self.prepare_session(session)
        return session

    def prepare_session(self, session: requests.Session) -> None:
        """Allow a source to warm up cookies or set portal-specific headers."""

    @abstractmethod
    def discover_listing_urls(self, session: requests.Session) -> list[str]:
        """Return listing or sitemap URLs that can yield candidate job URLs."""

    def fetch_listing_page(
        self,
        session: requests.Session,
        listing_url: str,
    ) -> FetchResult:
        response = session.get(listing_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return FetchResult(
            source=self.source,
            source_label=self.label,
            payload=response.text,
            metadata={"url": listing_url},
        )

    @abstractmethod
    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        """Parse one listing/sitemap page into candidate jobs."""

    def fetch_job_detail(
        self,
        session: requests.Session,
        candidate: ListingCandidate,
    ) -> FetchResult:
        response = session.get(candidate.url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return FetchResult(
            source=self.source,
            source_label=self.label,
            payload=response.text,
            metadata={"url": candidate.url, **candidate.metadata},
        )

    @abstractmethod
    def parse_job_detail(
        self,
        candidate: ListingCandidate,
        result: FetchResult,
    ) -> JobPosting:
        """Parse one job detail page into a shared JobPosting."""

    def fallback_job_posting(self, candidate: ListingCandidate) -> JobPosting | None:
        if not candidate.url:
            return None
        return JobPosting(
            source=self.source,
            source_label=self.label,
            url=candidate.url,
            title=candidate.title,
            company=candidate.company,
            location=candidate.location,
            description=candidate.description,
            metadata=candidate.metadata,
        )

    def _log_http_warning(
        self,
        stage: str,
        url: str,
        exc: requests.RequestException,
    ) -> None:
        response = getattr(exc, "response", None)
        if response is not None:
            status = response.status_code
            if status in {403, 429} or status >= 500:
                print(
                    f"Warning: {self.label} {stage} HTTP {status} for {url}. Continuing."
                )
                return
        print(f"Warning: {self.label} {stage} failed for {url}: {exc}. Continuing.")
