from __future__ import annotations

from app.models import JobPosting
from app.sources.base import FetchResult
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.common import absolute_url, clean_text, soup_from_html


class NoFluffJobsSource(BroadMarketJobSource):
    source = "nofluffjobs"

    def discover_listing_urls(self, session) -> list[str]:
        _ = session
        return [self.search_url]

    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        soup = soup_from_html(result.payload)
        cards = soup.select("a.posting-list-item, a[href*='/job/'], a[href*='/pl/job/']")
        candidates: list[ListingCandidate] = []
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

            candidates.append(
                ListingCandidate(
                    url=href,
                    title=clean_text(title_node.get_text(" ", strip=True) if title_node else "Untitled"),
                    company=clean_text(company_node.get_text(" ", strip=True) if company_node else "Unknown"),
                    location=clean_text(location_node.get_text(" ", strip=True) if location_node else "Unknown"),
                    metadata=metadata,
                )
            )
        return candidates

    def parse_job_detail(
        self,
        candidate: ListingCandidate,
        result: FetchResult,
    ) -> JobPosting:
        soup = soup_from_html(result.payload)
        description_node = soup.select_one("[class*='description'], [data-cy='JobOfferPage']")
        description = clean_text(
            description_node.get_text(" ", strip=True) if description_node else candidate.description
        )
        return JobPosting(
            source=self.source,
            source_label=self.label,
            url=candidate.url,
            title=candidate.title,
            company=candidate.company,
            location=candidate.location,
            description=description,
            metadata=candidate.metadata,
        )
