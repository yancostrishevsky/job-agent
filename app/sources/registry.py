from __future__ import annotations

from app.config import SourceDefinition
from app.sources.ashby import AshbySource
from app.sources.base import JobSource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.linkedin import LinkedInSource
from app.sources.nofluffjobs import NoFluffJobsSource
from app.sources.pracuj import PracujSource
from app.sources.public_career_page import PublicCareerPageSource
from app.sources.theprotocol import TheProtocolSource


def build_sources(definitions: list[SourceDefinition]) -> list[JobSource]:
    sources: list[JobSource] = []

    for definition in definitions:
        if not definition.enabled:
            continue

        if definition.type == "greenhouse":
            for token in definition.config.get("board_tokens", []):
                if token:
                    sources.append(
                        GreenhouseSource(
                            board_token=token,
                            label=f"{definition.label}: {token}",
                        )
                    )
            continue

        if definition.type == "lever":
            for handle in definition.config.get("handles", []):
                if handle:
                    sources.append(
                        LeverSource(
                            handle=handle,
                            label=f"{definition.label}: {handle}",
                        )
                    )
            continue

        if definition.type == "ashby":
            for job_board_name in definition.config.get("job_board_names", []):
                if job_board_name:
                    sources.append(
                        AshbySource(
                            job_board_name=job_board_name,
                            label=f"{definition.label}: {job_board_name}",
                            company_name=definition.config.get("company_name"),
                            include_compensation=bool(
                                definition.config.get("include_compensation", False)
                            ),
                        )
                    )
            continue

        if definition.type == "pracuj":
            search_url = definition.config.get("search_url")
            if isinstance(search_url, str) and search_url:
                sitemap_urls = definition.config.get("sitemap_urls", [])
                sources.append(
                    PracujSource(
                        search_url=search_url,
                        label=definition.label,
                        sitemap_urls=sitemap_urls if isinstance(sitemap_urls, list) else None,
                    )
                )
            continue

        if definition.type == "nofluffjobs":
            search_url = definition.config.get("search_url")
            if isinstance(search_url, str) and search_url:
                sources.append(
                    NoFluffJobsSource(search_url=search_url, label=definition.label)
                )
            continue

        if definition.type == "theprotocol":
            search_url = definition.config.get("search_url")
            if isinstance(search_url, str) and search_url:
                sources.append(
                    TheProtocolSource(search_url=search_url, label=definition.label)
                )
            continue

        if definition.type == "public_career_page":
            url = definition.config.get("url")
            if isinstance(url, str) and url:
                sources.append(
                    PublicCareerPageSource(
                        url=url,
                        label=definition.label,
                        company_name=definition.config.get("company_name"),
                    )
                )
            continue

        if definition.type == "linkedin":
            search_url = definition.config.get("search_url")
            if isinstance(search_url, str) and search_url:
                sources.append(
                    LinkedInSource(search_url=search_url, label=definition.label)
                )

    return sources
