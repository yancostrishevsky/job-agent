from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import CandidateProfile, JobPosting


class JobSource(ABC):
    """Adapter interface for job providers (scrapers, APIs, feeds, etc.)."""

    @abstractmethod
    def fetch_jobs(self, profile: CandidateProfile) -> list[JobPosting]:
        """Fetch job postings for the given candidate profile."""

    def source_name(self) -> str:
        """
        Human-readable source identifier used in exports.

        Subclasses can override this to include configuration details (e.g. token).
        """

        return self.__class__.__name__

