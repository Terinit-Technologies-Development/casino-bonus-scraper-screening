"""Scrape a small set of bonus rows and structure their terms with Gemini."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

from src.gemini_client import (
    BONUS_TERM_FIELDS,
    MODEL_ID,
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    extract_bonus_terms,
)

SOURCE_URL = "https://betproof.co.za/casino-bonuses-south-africa/"
ROBOTS_URL = urljoin(SOURCE_URL, "/robots.txt")
USER_AGENT = (
    "CasinoBonusScraperScreeningTest/1.0 "
    "(+https://github.com/Terinit-Technologies-Development/"
    "casino-bonus-scraper-screening)"
)
TARGET_CASINOS = ("PlayaBets", "Springbok Casino", "Thunderbolt Casino")
OUTPUT_PATH = Path(__file__).resolve().parent / "docs" / "bonuses.json"
REQUEST_TIMEOUT = (5, 25)


class ScraperError(RuntimeError):
    """Raised when source data or generated output fails validation."""


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        }
    )
    return session


def _load_allowed_robots(session: requests.Session) -> RobotFileParser:
    """Fetch robots.txt and fail closed if permission cannot be established."""
    try:
        response = session.get(
            ROBOTS_URL,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ScraperError("Could not retrieve robots.txt; refusing to scrape.") from exc

    if response.status_code != 200:
        raise ScraperError(
            f"robots.txt returned HTTP {response.status_code}; refusing to scrape."
        )

    robots = RobotFileParser(ROBOTS_URL)
    robots.parse(response.text.splitlines())
    if not robots.can_fetch(USER_AGENT, SOURCE_URL):
        raise ScraperError("robots.txt disallows the comparison page; refusing to scrape.")
    return robots


def _fetch_source_html(session: requests.Session, robots: RobotFileParser) -> str:
    delay = robots.crawl_delay(USER_AGENT)
    if delay is None:
        delay = robots.crawl_delay("*")
    if delay:
        time.sleep(delay)

    try:
        response = session.get(
            SOURCE_URL,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ScraperError("The approved comparison page could not be fetched.") from exc

    if 300 <= response.status_code < 400:
        raise ScraperError(
            f"The comparison page redirected (HTTP {response.status_code}); "
            "redirects are not followed by this scraper."
        )
    if response.status_code != 200:
        raise ScraperError(f"The comparison page returned HTTP {response.status_code}.")
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        raise ScraperError("The comparison page response was not HTML.")
    return response.text


def parse_target_rows(html: str, source_url: str = SOURCE_URL) -> list[dict[str, str]]:
    """Read selected rows from the server-rendered comparison table."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(".bonus-table-wrap table")
    if table is None:
        raise ScraperError("Could not find the comparison table (.bonus-table-wrap table).")

    table_rows = table.find_all("tr")
    if not table_rows:
        raise ScraperError("The comparison table has no rows.")

    header_cells = table_rows[0].find_all(["th", "td"], recursive=False)
    headers = [" ".join(cell.get_text(" ", strip=True).lower().split()) for cell in header_cells]
    required_headers = ("casino", "bonus", "wagering", "min deposit")
    if any(header not in headers for header in required_headers):
        raise ScraperError("The comparison table is missing a required column.")
    indexes = {header: headers.index(header) for header in required_headers}

    targets = {name.casefold(): name for name in TARGET_CASINOS}
    found: dict[str, dict[str, str]] = {}
    for row in table_rows[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) < len(headers):
            continue

        casino_name = cells[indexes["casino"]].get_text(" ", strip=True)
        casino_name = re.sub(r"\s+Play\s*→\s*$", "", casino_name, flags=re.IGNORECASE).strip()
        canonical_name = targets.get(casino_name.casefold())
        if canonical_name is None:
            continue
        if canonical_name in found:
            raise ScraperError(f"The source table contains duplicate rows for {canonical_name}.")

        values = {
            "casino": canonical_name,
            "source_bonus": cells[indexes["bonus"]].get_text(" ", strip=True),
            "source_wagering": cells[indexes["wagering"]].get_text(" ", strip=True),
            "source_minimum_deposit": cells[indexes["min deposit"]].get_text(" ", strip=True),
            "source_url": source_url,
        }
        if any(not values[field] for field in ("source_bonus", "source_wagering", "source_minimum_deposit")):
            raise ScraperError(f"The source row for {canonical_name} has an empty required term.")
        found[canonical_name] = values

    missing = [name for name in TARGET_CASINOS if name not in found]
    if missing:
        raise ScraperError("Required casino rows missing from the source: " + ", ".join(missing))
    if len(found) != 3:
        raise ScraperError("Expected exactly three distinct casino rows.")
    return [found[name] for name in TARGET_CASINOS]


def _currency_amounts(text: str) -> list[str]:
    amounts = re.findall(r"(?i)\bR\s*([\d,]+(?:\.\d{1,2})?)", text)
    return [amount.replace(",", "").replace(" ", "") for amount in amounts]


def _percentages(text: str) -> list[str]:
    values = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", text)
    return [value.rstrip("0").rstrip(".") if "." in value else value for value in values]


def _multipliers(text: str) -> list[str]:
    values = re.findall(r"(?i)\b(\d+(?:\.\d+)?)\s*x\b", text)
    return [value.rstrip("0").rstrip(".") if "." in value else value for value in values]


def _labelled_multiplier_facts(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Capture common category labels with their adjacent multiplier."""
    category_patterns = (
        ("sports", r"\bsports?\b"),
        ("casino", r"\bcasino\b"),
        ("free bet", r"\bfree[\s-]+bets?\b"),
        ("spins", r"\bspins?\b"),
        ("deposit", r"\bdeposits?\b"),
        ("games", r"\bgames?\b"),
    )
    facts: list[tuple[str, tuple[str, ...]]] = []
    for segment in re.split(r"\s*(?:/|;|\|)\s*", text):
        match = re.search(r"(?i)\b(\d+(?:\.\d+)?)\s*x\b", segment)
        if match is None:
            continue
        multiplier = match.group(1)
        if "." in multiplier:
            multiplier = multiplier.rstrip("0").rstrip(".")
        categories = tuple(
            name for name, pattern in category_patterns if re.search(pattern, segment, re.IGNORECASE)
        )
        facts.append((multiplier, categories))
    return sorted(facts)


def validate_extracted_terms(
    source_row: dict[str, str], extracted: dict[str, str]
) -> dict[str, str]:
    """Reject omissions or model-invented numeric terms before writing public JSON."""
    required = set(BONUS_TERM_FIELDS)
    if set(extracted) != required:
        raise ScraperError(f"Gemini returned an unexpected field set for {source_row['casino']}.")
    if any(not isinstance(extracted[field], str) or not extracted[field].strip() for field in required):
        raise ScraperError(f"Gemini returned an empty or non-text field for {source_row['casino']}.")

    if sorted(_currency_amounts(extracted["welcome_bonus"])) != sorted(
        _currency_amounts(source_row["source_bonus"])
    ):
        raise ScraperError(f"Gemini welcome-bonus amounts did not match the source for {source_row['casino']}.")
    if sorted(_percentages(extracted["welcome_bonus"])) != sorted(
        _percentages(source_row["source_bonus"])
    ):
        raise ScraperError(f"Gemini welcome-bonus percentages did not match the source for {source_row['casino']}.")
    if sorted(_multipliers(extracted["wagering_requirement_multiplier"])) != sorted(
        _multipliers(source_row["source_wagering"])
    ):
        raise ScraperError(f"Gemini wagering multipliers did not match the source for {source_row['casino']}.")
    source_wagering_facts = _labelled_multiplier_facts(source_row["source_wagering"])
    if any(categories for _, categories in source_wagering_facts) and (
        _labelled_multiplier_facts(extracted["wagering_requirement_multiplier"])
        != source_wagering_facts
    ):
        raise ScraperError(f"Gemini wagering category labels did not match the source for {source_row['casino']}.")
    if sorted(_currency_amounts(extracted["minimum_deposit"])) != sorted(
        _currency_amounts(source_row["source_minimum_deposit"])
    ):
        raise ScraperError(f"Gemini minimum deposit did not match the source for {source_row['casino']}.")

    return {field: extracted[field].strip() for field in BONUS_TERM_FIELDS}


def _new_gemini_client() -> genai.Client:
    env_file = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_file, override=False)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured locally.")
    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        raise GeminiConfigurationError(
            f"Could not initialize the Gemini client ({type(exc).__name__})."
        ) from exc


def run_scraper(
    *,
    output_path: Path = OUTPUT_PATH,
    session: requests.Session | None = None,
    client: genai.Client | None = None,
) -> dict[str, Any]:
    """Fetch the approved page, invoke Gemini for each row, validate, and write JSON."""
    active_session = session if session is not None else _new_session()
    gemini = client if client is not None else _new_gemini_client()

    robots = _load_allowed_robots(active_session)
    html = _fetch_source_html(active_session, robots)
    source_rows = parse_target_rows(html)

    casinos: list[dict[str, str]] = []
    for row in source_rows:
        terms = (
            f"Welcome bonus: {row['source_bonus']}\n"
            f"Wagering requirement: {row['source_wagering']}\n"
            f"Minimum deposit: {row['source_minimum_deposit']}"
        )
        extracted = extract_bonus_terms(terms, client=gemini, model=MODEL_ID)
        validated = validate_extracted_terms(row, extracted)
        casinos.append(
            {
                "casino": row["casino"],
                **validated,
                "source_url": row["source_url"],
            }
        )

    names = [casino["casino"] for casino in casinos]
    if len(casinos) != 3 or len(set(names)) != 3 or tuple(names) != TARGET_CASINOS:
        raise ScraperError("Final validation failed: expected exactly the three configured casinos.")

    dataset: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "model": MODEL_ID,
        "casinos": casinos,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return dataset


def main() -> int:
    try:
        dataset = run_scraper()
    except (ScraperError, GeminiConfigurationError, GeminiRequestError, GeminiResponseError) as exc:
        print(f"Scraper failed: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {len(dataset['casinos'])} casino records with {MODEL_ID}.")
    print(f"Output: {OUTPUT_PATH.relative_to(Path(__file__).resolve().parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
