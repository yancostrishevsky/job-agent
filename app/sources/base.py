from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from app.models import JobPosting


@dataclass(frozen=True, slots=True)
class FetchResult:
    source: str
    source_label: str
    payload: str
    metadata: dict[str, str]


class BaseJobFetcher(ABC):
    """Network layer for a source adapter."""

    @abstractmethod
    def fetch(self) -> FetchResult:
        """Fetch raw source payload."""


class BaseJobParser(ABC):
    """Parsing layer that maps raw payloads into shared job models."""

    @abstractmethod
    def parse(self, result: FetchResult) -> list[JobPosting]:
        """Parse raw source payload into normalized jobs."""


class JobSource(ABC):
    """Adapter interface composed of a fetcher and parser."""

    @abstractmethod
    def fetch_jobs(self) -> list[JobPosting]:
        """Fetch and parse source jobs."""

    def source_name(self) -> str:
        """Human-readable source identifier used in exports."""

        return self.__class__.__name__


class RequestsHTMLFetcher(BaseJobFetcher):
    """Minimal requests-based fetcher for HTML listing pages."""

    def __init__(
        self,
        source: str,
        source_label: str,
        url: str,
        timeout_seconds: float = 20.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._source = source
        self._source_label = source_label
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._headers = headers or {
            "User-Agent": "job-agent/1.0 (+https://example.local)"
        }

    def fetch(self) -> FetchResult:
        response = requests.get(
            self._url,
            headers=self._headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source=self._source,
            source_label=self._source_label,
            payload=response.text,
            metadata={"url": self._url},
        )
