from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from app.models import CandidateProfile, JobPosting
from app.sources.base import JobSource


@dataclass(frozen=True, slots=True)
class LeverSource(JobSource):
    """
    Adapter for Lever public postings.

    Primary source is Lever's public Postings API (JSON).
    If JSON can't be parsed, it falls back to a public XML feed.
    """

    handle: str
    timeout_seconds: float = 15.0
    page_limit: int = 100
    max_pages: int = 50  # safety cap

    def source_name(self) -> str:
        return f"Lever:{self.handle}"

    def _json_list_url(self, skip: int) -> str:
        return (
            f"https://api.lever.co/v0/postings/{self.handle}"
            f"?mode=json&skip={skip}&limit={self.page_limit}"
        )

    def _xml_feed_url(self) -> str:
        # Common public feed location for Lever-hosted job sites.
        return f"https://jobs.lever.co/{self.handle}/rss"

    def _to_iso8601_from_millis(self, millis: object) -> str | None:
        if millis is None:
            return None
        try:
            ms_int = int(millis)
        except (TypeError, ValueError):
            return None
        try:
            return dt.datetime.fromtimestamp(ms_int / 1000, tz=dt.timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None

    def _parse_json_jobs(self, jobs: object) -> list[JobPosting]:
        if not isinstance(jobs, list):
            return []

        results: list[JobPosting] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue

            source_job_id = item.get("id")
            source_job_id_str = (
                str(source_job_id).strip() if source_job_id is not None else None
            )

            title = item.get("text") if isinstance(item.get("text"), str) else ""
            categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}

            location = categories.get("location")
            location_str = location.strip() if isinstance(location, str) and location.strip() else "Unknown"

            commitment = categories.get("commitment")
            commitment_str = (
                commitment.strip() if isinstance(commitment, str) and commitment.strip() else None
            )

            department = categories.get("department")
            team = categories.get("team")
            category_value = department if isinstance(department, str) and department.strip() else team
            category_str = category_value.strip() if isinstance(category_value, str) and category_value.strip() else None

            apply_url = item.get("applyUrl")
            apply_url_str = (
                apply_url.strip()
                if isinstance(apply_url, str) and apply_url.strip()
                else None
            )

            hosted_url = item.get("hostedUrl")
            hosted_url_str = (
                hosted_url.strip()
                if isinstance(hosted_url, str) and hosted_url.strip()
                else None
            )

            url = apply_url_str or hosted_url_str
            if not url:
                continue  # without URL we can't deduplicate reliably

            description = item.get("description")
            description_str = description if isinstance(description, str) else ""

            posted_at = self._to_iso8601_from_millis(item.get("createdAt"))

            results.append(
                JobPosting(
                    url=url,
                    title=title.strip() or "Untitled",
                    company=self.handle,
                    location=location_str,
                    level=commitment_str or "Unknown",
                    description=description_str,
                    source_job_id=source_job_id_str,
                    posted_at=posted_at,
                    category=category_str,
                    commitment=commitment_str,
                )
            )

        return results

    def _parse_xml_jobs(self, xml_text: str) -> list[JobPosting]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        # RSS (item) vs Atom (entry)
        nodes = root.findall(".//item")
        if not nodes:
            nodes = root.findall(".//entry")

        results: list[JobPosting] = []
        for node in nodes:
            # Helper: find element text by local tag name (handles namespaces).
            def _find_text(*tag_candidates: str) -> str | None:
                for cand in tag_candidates:
                    found = node.find(f".//{cand}")
                    if found is not None and found.text and found.text.strip():
                        return found.text.strip()
                    # Namespace-tolerant search: compare tag suffix.
                    for child in node.iter():
                        if child.tag.endswith(cand) and child.text and child.text.strip():
                            return child.text.strip()
                return None

            title = _find_text("title") or ""
            link = _find_text("link", "guid") or ""

            # Lever feeds often only provide the job link; use it as apply URL fallback.
            url = link if link else None

            description = _find_text("description")
            if description is None:
                description = _find_text("content:encoded", "encoded")
            description_str = description or ""

            location = _find_text("location")
            location_str = location or "Unknown"

            commitment = _find_text("commitment")
            commitment_str = commitment.strip() if isinstance(commitment, str) and commitment.strip() else None

            category = _find_text("category")
            category_str = category.strip() if isinstance(category, str) and category.strip() else None

            source_job_id = _find_text("guid", "id")
            source_job_id_str = source_job_id.strip() if isinstance(source_job_id, str) and source_job_id.strip() else None

            posted_at = _find_text("pubDate", "updated", "published")

            if not url:
                continue

            results.append(
                JobPosting(
                    url=url,
                    title=title.strip() or "Untitled",
                    company=self.handle,
                    location=location_str.strip() if isinstance(location_str, str) else "Unknown",
                    level=commitment_str or "Unknown",
                    description=description_str,
                    source_job_id=source_job_id_str,
                    posted_at=posted_at,
                    category=category_str,
                    commitment=commitment_str,
                )
            )

        return results

    def _fetch_json_jobs(self) -> list[JobPosting]:
        results: list[JobPosting] = []
        skip = 0
        pages = 0

        while pages < self.max_pages:
            url = self._json_list_url(skip=skip)
            try:
                resp = requests.get(
                    url,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as e:
                print(
                    f"Warning: Could not fetch Lever jobs for handle '{self.handle}': {e}. Skipping."
                )
                return []

            if resp.status_code == 429:
                print(
                    f"Warning: Lever rate limited while fetching '{self.handle}' (HTTP 429). Skipping."
                )
                return []

            if resp.status_code != 200:
                print(
                    f"Warning: Lever handle '{self.handle}' returned HTTP {resp.status_code}. Skipping."
                )
                return []

            try:
                jobs_json = resp.json()
            except ValueError:
                # JSON not available for this handle; fall back to XML.
                return self._fetch_xml_jobs()

            parsed = self._parse_json_jobs(jobs_json)
            if not parsed:
                # Handle might not expose JSON in practice; try XML/RSS fallback once.
                xml_results = self._fetch_xml_jobs()
                if xml_results:
                    return xml_results
                break

            results.extend(parsed)
            skip += self.page_limit
            pages += 1

            if len(parsed) < self.page_limit:
                break

        return results

    def _fetch_xml_jobs(self) -> list[JobPosting]:
        feed_url = self._xml_feed_url()
        try:
            resp = requests.get(
                feed_url,
                headers={"Accept": "application/xml"},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            return self._parse_xml_jobs(resp.text)
        except requests.RequestException as e:
            print(
                f"Warning: Could not fetch Lever XML feed for handle '{self.handle}': {e}. Skipping."
            )
            return []

    def fetch_jobs(self, profile: CandidateProfile) -> list[JobPosting]:
        _ = profile  # rule-based filtering is applied later
        return self._fetch_json_jobs()

