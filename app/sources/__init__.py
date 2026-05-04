"""Job sources for fetching job postings."""
from app.sources.ashby import AshbySource
from app.sources.base import (
    BaseJobFetcher,
    BaseJobParser,
    FetchResult,
    JobSource,
    RequestsHTMLFetcher,
)
from app.sources.broad_market import BroadMarketJobSource, ListingCandidate
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.linkedin import LinkedInSource
from app.sources.nofluffjobs import NoFluffJobsSource
from app.sources.pracuj import PracujSource
from app.sources.public_career_page import PublicCareerPageSource
from app.sources.registry import build_sources
from app.sources.theprotocol import TheProtocolSource

__all__ = [
    "AshbySource",
    "BaseJobFetcher",
    "BaseJobParser",
    "BroadMarketJobSource",
    "FetchResult",
    "GreenhouseSource",
    "JobSource",
    "LeverSource",
    "LinkedInSource",
    "ListingCandidate",
    "NoFluffJobsSource",
    "PracujSource",
    "PublicCareerPageSource",
    "RequestsHTMLFetcher",
    "TheProtocolSource",
    "build_sources",
]
