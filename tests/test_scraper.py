from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scraper import (
    ROBOTS_URL,
    SOURCE_URL,
    ScraperError,
    _fetch_source_html,
    _load_allowed_robots,
    parse_target_rows,
    run_scraper,
    validate_extracted_terms,
)


TABLE_HTML = """
<div class="bonus-table-wrap">
  <table>
    <thead><tr><th>Casino</th><th>Bonus</th><th>Wagering</th><th>Min Deposit</th><th>Clearable?</th><th>Licence</th></tr></thead>
    <tbody>
      <tr><td>Thunderbolt Casino Play →</td><td>Up to R10,000 (4 coupons)</td><td>30x</td><td>R25</td><td>No</td><td>Offshore</td></tr>
      <tr><td>PlayaBets Play →</td><td>100% up to R3,000</td><td>6x</td><td>R10</td><td>Yes</td><td>MER</td></tr>
      <tr><td>Springbok Casino Play →</td><td>R250 no-deposit + up to R11,500 (3 deposits)</td><td>30x</td><td>R25</td><td>No</td><td>Offshore</td></tr>
      <tr><td>Betway South Africa Play →</td><td>R1,000 sports + R2,000 casino</td><td>3x sports / 30x casino</td><td>R5</td><td>Yes</td><td>WCGRB</td></tr>
    </tbody>
  </table>
</div>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str, content_type: str = "text/plain"):
        self.status_code = status_code
        self.text = text
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, page_response: FakeResponse | None = None):
        self.page_response = page_response or FakeResponse(200, TABLE_HTML, "text/html; charset=utf-8")
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        assert kwargs["allow_redirects"] is False
        self.calls.append(url)
        if url == ROBOTS_URL:
            return FakeResponse(200, "User-agent: *\nAllow: /\nDisallow: /go/\n")
        assert url == SOURCE_URL
        return self.page_response


class FakeGeminiModels:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        prompt = str(kwargs["contents"])
        if "100% up to R3,000" in prompt:
            terms = {
                "welcome_bonus": "100% up to R3,000",
                "wagering_requirement_multiplier": "6x",
                "minimum_deposit": "R10",
            }
        elif "R250 no-deposit + up to R11,500 (3 deposits)" in prompt:
            terms = {
                "welcome_bonus": "R250 no-deposit + up to R11,500 (3 deposits)",
                "wagering_requirement_multiplier": "30x",
                "minimum_deposit": "R25",
            }
        else:
            terms = {
                "welcome_bonus": "Up to R10,000 (4 coupons)",
                "wagering_requirement_multiplier": "30x",
                "minimum_deposit": "R25",
            }
        return SimpleNamespace(text=json.dumps(terms))


def test_parse_target_rows_returns_exact_three_in_configured_order() -> None:
    rows = parse_target_rows(TABLE_HTML)

    assert [row["casino"] for row in rows] == [
        "PlayaBets",
        "Springbok Casino",
        "Thunderbolt Casino",
    ]
    assert rows[0]["source_bonus"] == "100% up to R3,000"
    assert rows[0]["source_wagering"] == "6x"
    assert rows[0]["source_minimum_deposit"] == "R10"
    assert all(row["source_url"].startswith("https://betproof.co.za/") for row in rows)


def test_parse_fails_if_a_required_casino_is_missing() -> None:
    html = TABLE_HTML.replace(
        '<tr><td>Springbok Casino Play →</td><td>R250 no-deposit + up to R11,500 (3 deposits)</td><td>30x</td><td>R25</td><td>No</td><td>Offshore</td></tr>',
        "",
    )

    with pytest.raises(ScraperError, match="Springbok Casino"):
        parse_target_rows(html)


def test_model_extraction_must_preserve_source_values() -> None:
    source_row = {
        "casino": "Betway South Africa",
        "source_bonus": "R1,000 sports + R2,000 casino",
        "source_wagering": "3x sports / 30x casino",
        "source_minimum_deposit": "R5",
    }
    extracted = {
        "welcome_bonus": "R1,000 sports bonus + R2,000 casino bonus",
        "wagering_requirement_multiplier": "3x sports / 30x casino",
        "minimum_deposit": "R5",
    }

    result = validate_extracted_terms(source_row, extracted)
    assert result["wagering_requirement_multiplier"] == "3x sports / 30x casino"


def test_model_cannot_collapse_distinct_wagering_categories() -> None:
    source_row = {
        "casino": "Betway South Africa",
        "source_bonus": "R1,000 sports + R2,000 casino",
        "source_wagering": "3x sports / 30x casino",
        "source_minimum_deposit": "R5",
    }
    extracted = {
        "welcome_bonus": "R1,000 sports bonus + R2,000 casino bonus",
        "wagering_requirement_multiplier": "30x",
        "minimum_deposit": "R5",
    }

    with pytest.raises(ScraperError, match="multipliers did not match"):
        validate_extracted_terms(source_row, extracted)


def test_model_cannot_swap_wagering_category_labels() -> None:
    source_row = {
        "casino": "Betway South Africa",
        "source_bonus": "R1,000 sports + R2,000 casino",
        "source_wagering": "3x sports / 30x casino",
        "source_minimum_deposit": "R5",
    }
    extracted = {
        "welcome_bonus": "R1,000 sports bonus + R2,000 casino bonus",
        "wagering_requirement_multiplier": "3x casino / 30x sports",
        "minimum_deposit": "R5",
    }

    with pytest.raises(ScraperError, match="category labels did not match"):
        validate_extracted_terms(source_row, extracted)


def test_model_cannot_invent_a_deposit_amount() -> None:
    source_row = {
        "casino": "PlayaBets",
        "source_bonus": "100% up to R3,000",
        "source_wagering": "6x",
        "source_minimum_deposit": "R10",
    }
    extracted = {
        "welcome_bonus": "100% up to R3,000",
        "wagering_requirement_multiplier": "6x",
        "minimum_deposit": "R20",
    }

    with pytest.raises(ScraperError, match="minimum deposit did not match"):
        validate_extracted_terms(source_row, extracted)


def test_scraper_uses_gemini_for_each_row_and_writes_validated_json(tmp_path: Path) -> None:
    session = FakeSession()
    gemini_models = FakeGeminiModels()
    output_path = tmp_path / "docs" / "bonuses.json"

    dataset = run_scraper(
        output_path=output_path,
        session=session,  # type: ignore[arg-type]
        client=SimpleNamespace(models=gemini_models),  # type: ignore[arg-type]
    )

    assert session.calls == [ROBOTS_URL, SOURCE_URL]
    assert len(gemini_models.calls) == 3
    assert all(call["model"] == "gemini-3.5-flash-lite" for call in gemini_models.calls)
    assert [casino["casino"] for casino in dataset["casinos"]] == [
        "PlayaBets",
        "Springbok Casino",
        "Thunderbolt Casino",
    ]
    assert json.loads(output_path.read_text(encoding="utf-8")) == dataset


def test_scraper_fails_closed_when_robots_disallows_source() -> None:
    class DisallowSession(FakeSession):
        def get(self, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append(url)
            return FakeResponse(200, "User-agent: *\nDisallow: /\n")

    session = DisallowSession()

    with pytest.raises(ScraperError, match="robots.txt disallows"):
        _load_allowed_robots(session)  # type: ignore[arg-type]

    assert session.calls == [ROBOTS_URL]


def test_scraper_does_not_follow_source_redirects() -> None:
    session = FakeSession(FakeResponse(302, "", "text/html"))
    robots = _load_allowed_robots(session)  # type: ignore[arg-type]

    with pytest.raises(ScraperError, match="redirected"):
        _fetch_source_html(session, robots)  # type: ignore[arg-type]

    assert session.calls == [ROBOTS_URL, SOURCE_URL]
