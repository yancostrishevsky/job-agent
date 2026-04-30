from __future__ import annotations

from app.config import SourceDefinition
from app.sources.base import JobSource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.nofluffjobs import NoFluffJobsSource
from app.sources.pracuj import PracujSource
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

        if definition.type == "pracuj":
            search_url = definition.config.get("search_url")
            if isinstance(search_url, str) and search_url:
                sources.append(PracujSource(search_url=search_url, label=definition.label))
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

    return sources
