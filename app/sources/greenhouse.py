from __future__ import annotations

from dataclasses import dataclass

import requests

from app.models import CandidateProfile, JobPosting
from app.sources.base import JobSource


@dataclass(frozen=True, slots=True)
class GreenhouseSource(JobSource):
    """
    Adapter for Greenhouse Job Board API (public, read-only).

    Fetches published jobs in JSON (no HTML scraping).
    """

    board_token: str
    timeout_seconds: float = 15.0

    def source_name(self) -> str:
        return f"Greenhouse:{self.board_token}"

    def _get_company_name(self) -> str:
        # Best-effort: a second API call for board metadata to get the org name.
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}"
        try:
            resp = requests.get(url, timeout=self.timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except requests.RequestException:
            pass
        return self.board_token

    def fetch_jobs(self, profile: CandidateProfile) -> list[JobPosting]:
        _ = profile  # unused (adapter uses only public job board JSON)

        jobs_url = (
            f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
        )
        try:
            resp = requests.get(
                jobs_url,
                params={"content": "true"},
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            if resp.status_code != 200:
                print(
                    f"Warning: Greenhouse token '{self.board_token}' returned HTTP {resp.status_code}. Skipping.",
                )
                return []

            data = resp.json()
        except requests.RequestException as e:
            print(
                f"Warning: Could not fetch Greenhouse jobs for token '{self.board_token}': {e}. Skipping."
            )
            return []
        except ValueError as e:
            print(
                f"Warning: Greenhouse jobs response for token '{self.board_token}' was not valid JSON: {e}. Skipping."
            )
            return []

        company = self._get_company_name()
        jobs_raw = data.get("jobs", [])
        if not isinstance(jobs_raw, list):
            return []

        results: list[JobPosting] = []
        for item in jobs_raw:
            if not isinstance(item, dict):
                continue

            absolute_url = item.get("absolute_url")
            if not isinstance(absolute_url, str) or not absolute_url.strip():
                continue  # without URL we can't deduplicate

            title = item.get("title") if isinstance(item.get("title"), str) else ""
            location_obj = item.get("location")
            location_name = ""
            if isinstance(location_obj, dict) and isinstance(location_obj.get("name"), str):
                location_name = location_obj["name"]
            elif isinstance(location_obj, str):
                location_name = location_obj

            content = item.get("content")
            description = content if isinstance(content, str) else ""

            updated_at = item.get("posted_at") or item.get("updated_at")
            posted_at = updated_at if isinstance(updated_at, str) else None

            source_job_id = item.get("id") or item.get("internal_job_id")
            source_job_id_str = (
                str(source_job_id) if source_job_id is not None and source_job_id != "" else None
            )

            results.append(
                JobPosting(
                    url=absolute_url.strip(),
                    title=title.strip() or "Untitled",
                    company=company,
                    location=location_name.strip() or "Unknown",
                    level="Unknown",
                    description=description,
                    source_job_id=source_job_id_str,
                    posted_at=posted_at,
                )
            )

        return results

