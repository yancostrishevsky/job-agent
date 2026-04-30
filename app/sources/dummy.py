from __future__ import annotations

from app.models import JobPosting
from app.sources.base import JobSource


class DummySource(JobSource):
    """Development-only source used as a deterministic local fallback."""

    def fetch_jobs(self) -> list[JobPosting]:
        return [
            JobPosting(
                source="dummy",
                source_label="Dummy Seed Source",
                url="https://example.com/jobs/ml-junior-krakow-001",
                title="Junior Machine Learning Engineer",
                company="Krakow AI Labs",
                location="Krakow, Poland",
                seniority="Junior",
                description=(
                    "Looking for a junior ML engineer focused on machine learning and deep learning. "
                    "Research-driven work using Python, PyTorch, and evaluation pipelines."
                ),
            ),
            JobPosting(
                source="dummy",
                source_label="Dummy Seed Source",
                url="https://example.com/jobs/ml-intern-remote-002",
                title="ML Research Intern (Deep Learning)",
                company="Nova Research",
                location="Remote",
                seniority="Internship",
                description=(
                    "We are seeking an internship for deep learning research. "
                    "Topics include AI, research, and model development in Python with TensorFlow."
                ),
            ),
        ]
