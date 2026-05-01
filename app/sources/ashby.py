from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from app.models import JobPosting
from app.sources.base import BaseJobFetcher, BaseJobParser, FetchResult, JobSource
from app.sources.common import clean_text, parse_iso_datetime


@dataclass(frozen=True, slots=True)
class AshbyFetcher(BaseJobFetcher):
    job_board_name: str
    label: str
    timeout_seconds: float = 20.0
    include_compensation: bool = False

    def fetch(self) -> FetchResult:
        response = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.job_board_name}",
            params={"includeCompensation": str(self.include_compensation).lower()},
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return FetchResult(
            source="ashby",
            source_label=self.label,
            payload=response.text,
            metadata={"job_board_name": self.job_board_name},
        )


class AshbyParser(BaseJobParser):
    def __init__(self, company_name: str | None = None) -> None:
        self.company_name = company_name

    def parse(self, result: FetchResult) -> list[JobPosting]:
        payload = json.loads(result.payload)
        jobs_raw = payload.get("jobs", [])
        if not isinstance(jobs_raw, list):
            return []

        postings: list[JobPosting] = []
        for item in jobs_raw:
            if not isinstance(item, dict):
                continue
            if item.get("isListed") is False:
                continue

            job_url = item.get("jobUrl") or item.get("applyUrl")
            if not isinstance(job_url, str) or not job_url.strip():
                continue

            location = clean_text(item.get("location") if isinstance(item.get("location"), str) else "")
            workplace_type = clean_text(
                item.get("workplaceType") if isinstance(item.get("workplaceType"), str) else ""
            )
            if workplace_type and workplace_type.lower() not in location.lower():
                location = f"{location} ({workplace_type})" if location else workplace_type

            metadata: dict[str, str] = {"job_board_name": result.metadata["job_board_name"]}
            for key in ("department", "team", "employmentType", "workplaceType", "applyUrl"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    metadata[key] = value.strip()

            postings.append(
                JobPosting(
                    source=result.source,
                    source_label=result.source_label,
                    url=job_url.strip(),
                    title=clean_text(
                        item.get("title") if isinstance(item.get("title"), str) else "Untitled"
                    ),
                    company=self.company_name or clean_text(result.metadata["job_board_name"]),
                    location=location or "Unknown",
                    description=clean_text(
                        item.get("descriptionPlain")
                        if isinstance(item.get("descriptionPlain"), str)
                        else item.get("descriptionHtml")
                        if isinstance(item.get("descriptionHtml"), str)
                        else ""
                    ),
                    seniority=clean_text(
                        item.get("employmentType") if isinstance(item.get("employmentType"), str) else ""
                    ) or None,
                    employment_type=clean_text(
                        item.get("employmentType") if isinstance(item.get("employmentType"), str) else ""
                    ) or None,
                    category=clean_text(
                        item.get("team")
                        if isinstance(item.get("team"), str)
                        else item.get("department")
                        if isinstance(item.get("department"), str)
                        else ""
                    ) or None,
                    source_job_id=clean_text(
                        item.get("id")
                        if isinstance(item.get("id"), str)
                        else item.get("jobPostingId")
                        if isinstance(item.get("jobPostingId"), str)
                        else ""
                    ) or None,
                    posted_at=parse_iso_datetime(
                        item.get("publishedAt") if isinstance(item.get("publishedAt"), str) else None
                    ),
                    metadata=metadata,
                )
            )
        return postings


@dataclass(slots=True)
class AshbySource(JobSource):
    job_board_name: str
    label: str
    company_name: str | None = None
    timeout_seconds: float = 20.0
    include_compensation: bool = False

    def __post_init__(self) -> None:
        self._fetcher = AshbyFetcher(
            job_board_name=self.job_board_name,
            label=self.label,
            timeout_seconds=self.timeout_seconds,
            include_compensation=self.include_compensation,
        )
        self._parser = AshbyParser(company_name=self.company_name)

    def fetch_jobs(self) -> list[JobPosting]:
        try:
            return self._parser.parse(self._fetcher.fetch())
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"Warning: Ashby source '{self.job_board_name}' failed: {exc}. Continuing.")
            return []

    def source_name(self) -> str:
        return self.label
