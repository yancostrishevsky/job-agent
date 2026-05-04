from __future__ import annotations

from app.models import JobPosting
from app.sources.base import FetchResult
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.common import absolute_url, clean_text, soup_from_html


class TheProtocolSource(BroadMarketJobSource):
    source = "theprotocol"

    def discover_listing_urls(self, session) -> list[str]:
        _ = session
        return [self.search_url]

    def parse_listing_cards(self, result: FetchResult) -> list[ListingCandidate]:
        soup = soup_from_html(result.payload)
        cards = soup.select("a[href*='/praca/'], article a")
        candidates: list[ListingCandidate] = []
        seen_urls: set[str] = set()

        for card in cards:
            href = absolute_url(result.metadata["url"], card.get("href"))
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            title_node = card.select_one("h2, h3") or card
            company_node = card.select_one("[class*='company'], [class*='employer']")
            location_node = card.select_one("[class*='location'], [class*='city']")
            tags = [
                clean_text(node.get_text(" ", strip=True))
                for node in card.select("[class*='tag'], [class*='badge']")
            ]
            candidates.append(
                ListingCandidate(
                    url=href,
                    title=clean_text(title_node.get_text(" ", strip=True)) or "Untitled",
                    company=clean_text(
                        company_node.get_text(" ", strip=True) if company_node else "Unknown"
                    ),
                    location=clean_text(
                        location_node.get_text(" ", strip=True) if location_node else "Unknown"
                    ),
                    metadata={
                        "search_url": result.metadata["url"],
                        "tags": ", ".join(tag for tag in tags if tag),
                    },
                )
            )
        return candidates

    def parse_job_detail(
        self,
        candidate: ListingCandidate,
        result: FetchResult,
    ) -> JobPosting:
        soup = soup_from_html(result.payload)
        description_node = soup.select_one("article, [class*='description'], main")
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
