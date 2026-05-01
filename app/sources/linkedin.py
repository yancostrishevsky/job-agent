from __future__ import annotations

import os

from app.models import JobPosting
from app.sources.base import FetchResult
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.common import absolute_url, clean_text, soup_from_html


class LinkedInSource(BroadMarketJobSource):
    """Best-effort LinkedIn listing scraper (opt-in; may return empty).

    Notes:
    - LinkedIn frequently blocks automated access and may require authentication.
    - This adapter is intentionally disabled by default and must be explicitly enabled
      via the JOB_AGENT_ENABLE_LINKEDIN_SCRAPING environment variable.
    """

    source = "linkedin"

    def __init__(
        self,
        *,
        search_url: str,
        label: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(search_url=search_url, label=label, timeout_seconds=timeout_seconds)

    def fetch_jobs(self) -> list[JobPosting]:
        enabled = os.getenv("JOB_AGENT_ENABLE_LINKEDIN_SCRAPING", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            print(
                "Warning: LinkedIn source is disabled by default. "
                "Set JOB_AGENT_ENABLE_LINKEDIN_SCRAPING=true to enable (may still yield 0 results)."
            )
            return []
        return super().fetch_jobs()

    def discover_listing_urls(self, session) -> list[str]:
        return [self.search_url]

    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        soup = soup_from_html(result.payload)
        anchors = soup.select("a[href*='/jobs/view/'], a[href*='linkedin.com/jobs/view']")
        candidates: list[ListingCandidate] = []
        seen: set[str] = set()

        for a in anchors:
            href = absolute_url(result.metadata["url"], a.get("href"))
            if not href or href in seen:
                continue
            seen.add(href)

            title = clean_text(a.get_text(" ", strip=True)) or "Untitled"
            candidates.append(
                ListingCandidate(
                    url=href,
                    title=title,
                    company="Unknown",
                    location="Unknown",
                    metadata={"search_url": result.metadata["url"], "discovered_via": "listing"},
                )
            )

        return candidates

    def parse_job_detail(self, candidate: ListingCandidate, result: FetchResult) -> JobPosting:
        soup = soup_from_html(result.payload)
        title_node = soup.select_one("h1, .top-card-layout__title, [data-test-job-title]")
        company_node = soup.select_one(
            "a.topcard__org-name-link, span.topcard__flavor, .top-card-layout__card a"
        )
        location_node = soup.select_one(".topcard__flavor--bullet, .top-card-layout__first-subline span")
        description_node = soup.select_one(
            ".show-more-less-html__markup, .description__text, main, article"
        )

        return JobPosting(
            source=self.source,
            source_label=self.label,
            url=candidate.url,
            title=clean_text(title_node.get_text(" ", strip=True) if title_node else candidate.title),
            company=clean_text(
                company_node.get_text(" ", strip=True) if company_node else candidate.company
            ),
            location=clean_text(
                location_node.get_text(" ", strip=True) if location_node else candidate.location
            ),
            description=clean_text(
                description_node.get_text(" ", strip=True) if description_node else candidate.description
            ),
            metadata=candidate.metadata,
        )

