# Casino Bonus Scraper Screening

Foundation for the screening project and a later, separately tracked portfolio evolution. The current Pass 0R work prepares repository, Gemini and static-hosting configuration only.

**Not implemented yet:** scraper, website, and generated casino data. No production JSON is manually maintained.

## Planned stack

- Python 3.11+ for the local scraper and Gemini calls.
- Requests + BeautifulSoup for the approved comparison page.
- Google's official `google-genai` SDK for structured extraction.
- Static HTML, CSS and JavaScript served by Vercel from `docs/`.
- The Gemini key is used locally by Python only; it must never be placed in frontend code, generated JSON, Vercel settings, or Git.

## Runtime and hosting boundary

The scraper is invoked manually on the owner's machine. It calls Gemini locally using `GEMINI_API_KEY`, validates the response, and writes `docs/bonuses.json`. The generated JSON is committed to GitHub with the source update; Vercel deploys only the static contents of `docs/` and serves the page and JSON. Vercel does not run or schedule the scraper and has no API, serverless function, database, or other backend for this project.

## Local setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` locally. Alternatively, set that environment variable in your shell. Never commit `.env`.
4. Run offline checks with `python -m pytest -q`.

The synthetic Gemini diagnostic is skipped until a key is configured. It uses synthetic text, not casino scraping evidence. Check Google AI Studio's project/model quota before running it; no paid API access is intended.

## Milestones

- **Milestone 1 — screening:** implement and verify only the required scraper, data, and mobile-readable site in the assessment window.
- **Milestone 2 — portfolio:** any enhancements happen after the screening and are recorded separately; they must not be represented as screening-time work.

See `docs/process/` for objective execution evidence, decisions, and validation results. Applicant-owned written responses are intentionally out of scope.
