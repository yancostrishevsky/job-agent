import json

from app.config.loader import SourceDefinition
from app.sources.ashby import AshbyParser
from app.sources.base import FetchResult
from app.sources.broad_market import ListingCandidate
from app.sources.greenhouse import GreenhouseParser
from app.sources.lever import LeverParser
from app.sources.linkedin import LinkedInSource
from app.sources.nofluffjobs import NoFluffJobsSource
from app.sources.pracuj import PracujSource
from app.sources.registry import build_sources
from app.sources.theprotocol import TheProtocolSource


def test_greenhouse_parser_smoke() -> None:
    parser = GreenhouseParser()
    payload = json.dumps(
        {
            "jobs": [
                {
                    "id": 101,
                    "title": "ML Intern",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                    "location": {"name": "Krakow"},
                    "content": "Python and ML",
                    "updated_at": "2026-04-29T12:00:00Z",
                }
            ]
        }
    )
    result = parser.parse(
        FetchResult(
            source="greenhouse",
            source_label="Greenhouse",
            payload=payload,
            metadata={"board_token": "acme"},
        )
    )

    assert len(result) == 1
    assert result[0].company == "acme"
    assert result[0].location == "Krakow"


def test_lever_parser_smoke() -> None:
    parser = LeverParser()
    payload = json.dumps(
        [
            {
                "id": "abc",
                "text": "Junior AI Engineer",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "description": "Python NLP",
                "createdAt": 1714473600000,
                "categories": {
                    "location": "Remote, Poland",
                    "commitment": "Internship",
                    "team": "AI",
                },
            }
        ]
    )
    result = parser.parse(
        FetchResult(
            source="lever",
            source_label="Lever",
            payload=payload,
            metadata={"handle": "acme", "format": "json"},
        )
    )

    assert len(result) == 1
    assert result[0].employment_type == "Internship"
    assert result[0].category == "AI"


def test_ashby_parser_smoke() -> None:
    parser = AshbyParser(company_name="Ashby")
    payload = json.dumps(
        {
            "jobs": [
                {
                    "jobPostingId": "123",
                    "title": "Machine Learning Intern",
                    "location": "Krakow, Poland",
                    "team": "AI",
                    "department": "Engineering",
                    "isListed": True,
                    "descriptionPlain": "Python, ML, and evaluation work.",
                    "publishedAt": "2026-04-29T12:00:00Z",
                    "employmentType": "Intern",
                    "workplaceType": "Hybrid",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/123",
                    "applyUrl": "https://jobs.ashbyhq.com/acme/123/apply",
                }
            ]
        }
    )
    result = parser.parse(
        FetchResult(
            source="ashby",
            source_label="Ashby",
            payload=payload,
            metadata={"job_board_name": "acme"},
        )
    )

    assert len(result) == 1
    assert result[0].company == "Ashby"
    assert result[0].source_job_id == "123"
    assert result[0].employment_type == "Intern"
    assert result[0].category == "AI"


def test_pracuj_sitemap_and_listing_parsers() -> None:
    source = PracujSource(
        search_url="https://it.pracuj.pl/praca?kw=ml",
        label="Pracuj",
        sitemap_urls=["https://it.pracuj.pl/sitemap-jobs.xml"],
    )
    sitemap_candidates = source.parse_listing_cards(
        FetchResult(
            source="pracuj",
            source_label="Pracuj",
            payload="""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://it.pracuj.pl/oferta/ml-intern,oferta,1000000</loc></url>
              <url><loc>https://it.pracuj.pl/oferta/junior-ai,oferta,2000000</loc></url>
            </urlset>
            """,
            metadata={"url": "https://it.pracuj.pl/sitemap-jobs.xml"},
        )
    )
    listing_candidates = source.parse_listing_cards(
        FetchResult(
            source="pracuj",
            source_label="Pracuj",
            payload="""
            <a href="/oferta/ml-intern,oferta,1000000" data-test="link-offer">
              <h2 data-test="offer-title">ML Intern</h2>
              <h4 data-test="text-company-name">Acme</h4>
              <span data-test="offer-badge-location">Krakow</span>
            </a>
            """,
            metadata={"url": "https://it.pracuj.pl/praca?kw=ml"},
        )
    )

    assert len(sitemap_candidates) == 2
    assert sitemap_candidates[0].metadata["discovered_via"] == "sitemap"
    assert listing_candidates[0].title == "ML Intern"
    assert listing_candidates[0].company == "Acme"


def test_pracuj_detail_parser_uses_jsonld_fallback() -> None:
    source = PracujSource(
        search_url="https://it.pracuj.pl/praca?kw=ml",
        label="Pracuj",
    )
    candidate = source.parse_listing_cards(
        FetchResult(
            source="pracuj",
            source_label="Pracuj",
            payload="""
            <article data-test="section-offer">
              <a href="/oferta/ml-intern,oferta,1000000" data-test="link-offer">
                <h2 data-test="offer-title">ML Intern</h2>
                <h4 data-test="text-company-name">Acme</h4>
                <span data-test="offer-badge-location">Krakow</span>
              </a>
            </article>
            """,
            metadata={"url": "https://it.pracuj.pl/praca?kw=ml"},
        )
    )[0]
    job = source.parse_job_detail(
        candidate,
        FetchResult(
            source="pracuj",
            source_label="Pracuj",
            payload="""
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "JobPosting",
              "title": "ML Intern",
              "description": "<p>Python and ML</p>",
              "employmentType": "Internship",
              "identifier": {"value": "job-123"},
              "hiringOrganization": {"name": "Acme"},
              "jobLocation": {"address": {"addressLocality": "Krakow"}}
            }
            </script>
            """,
            metadata={"url": "https://it.pracuj.pl/oferta/ml-intern,oferta,1000000"},
        ),
    )

    assert job.company == "Acme"
    assert job.location == "Krakow"
    assert job.employment_type == "Internship"
    assert job.source_job_id == "job-123"


def test_linkedin_parser_preserves_listing_metadata_and_canonical_url() -> None:
    source = LinkedInSource(
        search_url="https://www.linkedin.com/jobs/search/?keywords=ml",
        label="LinkedIn",
    )
    candidates = source.parse_listing_cards(
        FetchResult(
            source="linkedin",
            source_label="LinkedIn",
            payload="""
            <div class="base-card">
              <a class="base-card__full-link"
                 href="https://pl.linkedin.com/jobs/view/1234567890?trackingId=abc">
              </a>
              <h3 class="base-search-card__title">Junior ML Engineer</h3>
              <h4 class="base-search-card__subtitle">Acme</h4>
              <span class="job-search-card__location">Krakow</span>
            </div>
            """,
            metadata={"url": "https://www.linkedin.com/jobs/search/?keywords=ml"},
        )
    )

    assert len(candidates) == 1
    assert candidates[0].url == "https://pl.linkedin.com/jobs/view/1234567890/"
    assert candidates[0].company == "Acme"
    assert candidates[0].location == "Krakow"


def test_linkedin_detail_parser_uses_jsonld_when_html_is_sparse() -> None:
    source = LinkedInSource(
        search_url="https://www.linkedin.com/jobs/search/?keywords=ml",
        label="LinkedIn",
    )
    job = source.parse_job_detail(
        ListingCandidate(
            url="https://pl.linkedin.com/jobs/view/1234567890/",
            title="Junior ML Engineer",
            company="Acme",
            location="Krakow",
        ),
        FetchResult(
            source="linkedin",
            source_label="LinkedIn",
            payload="""
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "JobPosting",
              "title": "Junior ML Engineer",
              "description": "<p>Python, NLP, and LLM evaluation</p>",
              "hiringOrganization": {"name": "Acme"},
              "jobLocation": {"address": {"addressLocality": "Krakow"}}
            }
            </script>
            """,
            metadata={"url": "https://pl.linkedin.com/jobs/view/1234567890/"},
        ),
    )

    assert job.company == "Acme"
    assert job.location == "Krakow"
    assert "LLM evaluation" in job.description


def test_broad_market_fixture_parsers_smoke() -> None:
    nfj_source = NoFluffJobsSource(
        search_url="https://nofluffjobs.com/pl/jobs?criteria=keyword%3Dml",
        label="NFJ",
    )
    protocol_source = TheProtocolSource(
        search_url="https://theprotocol.it/praca?keyword=ml",
        label="The Protocol",
    )

    nfj_candidates = nfj_source.parse_listing_cards(
        FetchResult(
            source="nofluffjobs",
            source_label="NFJ",
            payload="""
            <a href="/pl/job/junior-ml-engineer">
              <h3>Junior ML Engineer</h3>
              <span data-cy="listing-item-company-name">Acme</span>
              <span data-cy="listing-item-city">Remote</span>
            </a>
            """,
            metadata={"url": "https://nofluffjobs.com/pl/jobs"},
        )
    )
    protocol_candidates = protocol_source.parse_listing_cards(
        FetchResult(
            source="theprotocol",
            source_label="The Protocol",
            payload="""
            <article>
              <a href="/praca/ml-role">
                <h2>AI Engineer</h2>
                <span class="company">Acme</span>
                <span class="location">Krakow</span>
              </a>
            </article>
            """,
            metadata={"url": "https://theprotocol.it/praca"},
        )
    )

    assert nfj_candidates[0].company == "Acme"
    assert protocol_candidates[0].location == "Krakow"


def test_registry_builds_public_career_page_and_linkedin_sources() -> None:
    sources = build_sources(
        [
            SourceDefinition(
                type="public_career_page",
                enabled=True,
                label="Public Careers",
                config={
                    "url": "https://example.com/careers",
                    "company_name": "Example Co",
                },
            ),
            SourceDefinition(
                type="linkedin",
                enabled=True,
                label="LinkedIn Search",
                config={
                    "search_url": "https://www.linkedin.com/jobs/search/?keywords=ml",
                },
            ),
        ]
    )

    assert len(sources) == 2
    assert sources[0].source_name() == "Public Careers"
    assert sources[1].source_name() == "LinkedIn Search"
