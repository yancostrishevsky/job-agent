from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobFetcher, BaseJobParser, FetchResult, JobSource
from app.sources.common import clean_text, parse_iso_datetime


@dataclass(frozen=True, slots=True)
class GreenhouseFetcher(BaseJobFetcher):
    board_token: str
    label: str
    timeout_seconds: float = 20.0

    def fetch(self) -> FetchResult:
        response = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs",
            params={"content": "true"},
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source="greenhouse",
            source_label=self.label,
            payload=response.text,
            metadata={"board_token": self.board_token},
        )


class GreenhouseParser(BaseJobParser):
    def parse(self, result: FetchResult) -> list[JobPosting]:
        payload = json.loads(result.payload)
        jobs_raw = payload.get("jobs", [])
        if not isinstance(jobs_raw, list):
            return []

        postings: list[JobPosting] = []
        for item in jobs_raw:
            if not isinstance(item, dict):
                continue

            absolute_url = item.get("absolute_url")
            if not isinstance(absolute_url, str) or not absolute_url.strip():
                continue

            location = item.get("location")
            if isinstance(location, dict):
                location_name = clean_text(location.get("name"))
            else:
                location_name = clean_text(location if isinstance(location, str) else "")

            metadata = {
                "board_token": result.metadata["board_token"],
            }
            for key in ("updated_at", "requisition_id"):
                value = item.get(key)
                if value is not None:
                    metadata[key] = str(value)

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=absolute_url.strip(),
                    title=clean_text(item.get("title") if isinstance(item.get("title"), str) else "Untitled"),
                    company=clean_text(result.metadata["board_token"]),
                    location=location_name or "Unknown",
                    description=clean_text(item.get("content") if isinstance(item.get("content"), str) else ""),
                    seniority=clean_text(item.get("metadata", [{}])[0].get("value") if isinstance(item.get("metadata"), list) and item.get("metadata") else ""),
                    source_job_id=str(item.get("id")) if item.get("id") is not None else None,
                    posted_at=parse_iso_datetime(
                        item.get("updated_at") if isinstance(item.get("updated_at"), str) else None
                    ),
                    metadata=metadata,
                )
            )
        return postings


@dataclass(slots=True)
class GreenhouseSource(JobSource):
    board_token: str
    label: str
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        self._fetcher = GreenhouseFetcher(
            board_token=self.board_token,
            label=self.label,
            timeout_seconds=self.timeout_seconds,
        )
        self._parser = GreenhouseParser()

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(
                f"Warning: Greenhouse source '{self.board_token}' failed: {exc}. Continuing."
            )
            return []

    def source_name(self) -> str:
        return self.label
