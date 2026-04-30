import json

from app.sources.base import FetchResult
from app.sources.greenhouse import GreenhouseParser
from app.sources.lever import LeverParser
from app.sources.nofluffjobs import NoFluffJobsParser
from app.sources.pracuj import PracujParser
from app.sources.theprotocol import TheProtocolParser


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


def test_html_parsers_smoke() -> None:
    pracuj = PracujParser().parse(
        FetchResult(
            source="pracuj",
            source_label="Pracuj",
            payload="""
            <a href="/oferta/ml-intern" data-test="link-offer">
              <h2>ML Intern</h2>
              <h4>Acme</h4>
              <span data-test="offer-badge-location">Krakow</span>
            </a>
            """,
            metadata={"url": "https://it.pracuj.pl/praca"},
        )
    )
    nfj = NoFluffJobsParser().parse(
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
    protocol = TheProtocolParser().parse(
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

    assert pracuj[0].title == "ML Intern"
    assert nfj[0].company == "Acme"
    assert protocol[0].location == "Krakow"
