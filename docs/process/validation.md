# Validation record

## Pre-implementation evidence

- Workspace was empty before Pass 0R; this repository is newly initialized in the owner-approved location.
- GitHub CLI authentication succeeded for `Terinit-Technologies-Development`; the requested repository name was not already present.
- Vercel CLI authentication succeeded. The sole available Vercel team is `terinit-technologies-projects`; deployment context reports plan `hobby`.
- Official Google model documentation lists `gemini-3.5-flash-lite` as stable and supports structured outputs. Public documentation does not establish this owner's project quota.
- `GEMINI_API_KEY` was not present and `.env` did not exist at the check. The live synthetic test is expected to skip until the owner configures a local key.
- Pass 0 source inspection found direct HTML and table candidates PlayaBets, Betway South Africa, and Supabets. Betway and Supabets have distinct wagering categories that must not be merged.
- Current comparison rows observed in Pass 0: PlayaBets (`100% up to R3,000`, `6x`, `R10`); Betway South Africa (`R1,000 sports (3x) + R2,000 casino (30x)`, `R5`); Supabets (`R50 free bet + 100 spins + 100% up to R2,000`, `5x free bet / 10x spins & deposit`, `R10`). These are evidence notes, not a production JSON file.
- Google model page identifies `gemini-3.5-flash-lite` as stable and structured-output capable (model page last updated 2026-07-30 UTC). Project-specific access/quota remains unverified without the owner's API key.

## Pass 0R verification

- Environment: Python 3.11.15 virtual environment; `google-genai==2.30.1`, Requests, BeautifulSoup, python-dotenv, and pytest installed from `requirements.txt`.
- Unit tests: `python -m pytest -q` → **8 passed, 1 skipped**. The skipped test is the live synthetic Gemini diagnostic because no key is configured.
- Live Gemini diagnostic: pending owner-provided local key and quota verification.
- Secret exclusion / Git ignore: `.env` absent; `GEMINI_API_KEY` absent; `.env` ignored; `.env.example` not ignored and contains an empty placeholder; tracked-key-pattern scan had no matches. Vercel project environment-variable list is empty.
- GitHub: public repository verified anonymously (HTTP 200, `private: false`), default branch `main`, feature branch pushed. Main commit `80a8aeeabdc77a8ccfbf6890faea50213d11b4d6`; feature commit `fa9bc2cf1fdfb443fa0961919b859d575eb358c3`.
- Vercel: Hobby plan verified; project `prj_1osuoVrHNkRr38wvaxKh2PasagPS` linked to GitHub. Readback confirms framework `null`, build/install command `null`, output directory `docs`, preview deployments disabled, production branch `main`, SSO protection `null`.
- Deployments: zero. Domain `casino-bonus-scraper-screening.vercel.app` is reserved and verified. No deployment was started, so HTTPS service response is not yet testable; Vercel-managed HTTPS applies when a real deployment is made.
- Runtime boundary: scraper/Gemini invocation remains local and manual; generated JSON is intended to be committed to GitHub; Vercel's sole role is static hosting from `docs/`. No Vercel functions, backend, or scheduler are configured.
- No scraper, frontend, production JSON, or deployment is part of this pass.
