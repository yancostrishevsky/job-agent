from __future__ import annotations

from app.models import CandidateProfile, JobPosting
from app.sources.base import JobSource


class DummySource(JobSource):
    """A minimal source adapter with hardcoded postings for v0 development."""

    def fetch_jobs(self, profile: CandidateProfile) -> list[JobPosting]:
        # `profile` is accepted for future adapters; DummySource ignores it.
        _ = profile

        return [
            JobPosting(
                url="https://example.com/jobs/ml-junior-krakow-001",
                title="Junior Machine Learning Engineer",
                company="Krakow AI Labs",
                location="Krakow, Poland",
                level="Junior",
                description=(
                    "Looking for a junior ML engineer focused on machine learning and deep learning. "
                    "Research-driven work using Python, PyTorch, and evaluation pipelines."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/ml-intern-remote-002",
                title="ML Research Intern (Deep Learning)",
                company="Nova Research",
                location="Remote",
                level="Internship",
                description=(
                    "We are seeking an internship for deep learning research. "
                    "Topics include AI, research, and model development in Python with TensorFlow."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/ai-engineer-remote-003",
                title="AI Engineer (NLP)",
                company="Prism Technologies",
                location="Remote (EU)",
                level="Junior",
                description=(
                    "Build NLP features with AI and machine learning. "
                    "Requirements: Python and TensorFlow; experience with deep learning is a plus."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/ds-intern-krakow-004",
                title="Intern - Data Science & ML",
                company="Vistula Labs",
                location="Krakow, Poland",
                level="Internship",
                description=(
                    "Internship for ML projects: data science, machine learning, and research experiments. "
                    "Stack: Python, PyTorch, and model training."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/junior-research-krakow-005",
                title="Junior ML Researcher",
                company="Agora Research",
                location="Krakow, Poland",
                level="Junior",
                description=(
                    "Join our research group working on machine learning and deep learning. "
                    "We use Python, PyTorch, and publish research findings."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/ai-cv-junior-remote-006",
                title="Junior AI Engineer - Computer Vision",
                company="Lumen AI",
                location="Remote",
                level="Junior",
                description=(
                    "Deep learning and computer vision using PyTorch and TensorFlow. "
                    "Python-first engineering with strong AI and research fundamentals."
                ),
            ),
            # Non-matching examples (excluded keywords / location / missing domain keywords)
            JobPosting(
                url="https://example.com/jobs/senior-ml-remote-007",
                title="Senior Machine Learning Engineer",
                company="OldTown Systems",
                location="Remote",
                level="Senior",
                description=(
                    "Senior role working on AI and deep learning with Python and PyTorch."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/lead-ds-krakow-008",
                title="Lead Data Scientist (AI)",
                company="Argo Analytics",
                location="Krakow, Poland",
                level="Lead",
                description=(
                    "Lead position focused on machine learning and AI with Python."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/python-backend-warsaw-009",
                title="Backend Python Developer",
                company="WebCloud",
                location="Warsaw, Poland",
                level="Junior",
                description=(
                    "Backend developer for APIs and databases. "
                    "Python required; knowledge of REST, SQL, and testing."
                ),
            ),
            JobPosting(
                url="https://example.com/jobs/manager-ml-remote-010",
                title="Project Manager - Machine Learning",
                company="Orchid Ventures",
                location="Remote",
                level="Manager",
                description=(
                    "Manager role overseeing machine learning projects. "
                    "Include Python and ML keywords, but this position is managerial."
                ),
            ),
        ]

