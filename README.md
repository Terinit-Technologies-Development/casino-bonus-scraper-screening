# Casino Bonus Scraper Screening

A small, local Python scraper that uses Gemini to structure source-page bonus terms, plus a vanilla static page that displays the generated snapshot.

## Local scraper

Requirements: Python 3.11+ and a local Gemini API key. The key is read from `GEMINI_API_KEY` in the process environment or root `.env`; it is never used by the browser and must not be committed.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env  # only when you do not already have a local .env
# Add GEMINI_API_KEY to .env locally; never print or commit it.
.\.venv\Scripts\python.exe scraper.py
```

The scraper checks robots.txt before fetching the approved comparison page, selects three configured rows, asks Gemini for schema-constrained terms, validates extracted numeric values against each source row, and writes `docs/bonuses.json` atomically. It runs manually on the owner's machine; Vercel does not run or schedule it.

## JSON contract

`docs/bonuses.json` contains `generated_at` (UTC timestamp), `source_url`, `model`, and a `casinos` array. Each record contains `casino`, `welcome_bonus`, `wagering_requirement_multiplier` (JSON number for one unambiguous multiplier), `minimum_deposit`, and `source_url`. The page reads all records from this array; it does not duplicate the casino data.

The normalizer rejects labelled or multiple multiplier formats instead of flattening them. Do not infer the terms of each part of a bundled promotion from a single headline multiplier.

## Tests and preview

```powershell
# Offline regression tests
.\.venv\Scripts\python.exe -m pytest -q -k "not synthetic"

# Opt-in live synthetic Gemini request (requires local key and available quota)
.\.venv\Scripts\python.exe -m pytest -q tests/test_gemini.py -k synthetic

# Serve the static page over HTTP (do not use file://)
python -m http.server 8000 -d docs
```

Open `http://localhost:8000/`. With a configured key, an unfiltered `pytest` run also executes the live synthetic diagnostic.

## Source limitations

The data is a timestamped snapshot from [BetProof's South African casino-bonus comparison](https://betproof.co.za/casino-bonuses-south-africa/). Listings and operator terms can change. Springbok Casino's row bundles a no-deposit and multi-deposit offer; Thunderbolt Casino's row mentions multiple coupons. The source page provides one headline multiplier for each row but does not establish every component's conditions. The reported minimum deposit may not apply to every part of a bundle. Disallowed `/go/` click-through links are not followed. This is an informational technical demonstration, not an endorsement or gambling recommendation.

## Hosting boundary

Vercel is configured for static output from `docs/` (`vercel.json`). GitHub contains source, tests, documentation, and the generated JSON. Vercel serves only the static page, assets, and committed JSON; it has no backend, function, scheduled scraper, or Gemini secret. Do not deploy until the deployment gate is explicitly approved.

Screening work remains separate from any future portfolio enhancements. See `docs/process/` for objective decisions, execution evidence, and validation results.
