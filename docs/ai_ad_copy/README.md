# AI Ad Copy Generator

An explainable, data-grounded Responsive Search Ad (RSA) generator built **inside**
the Google Ads Intelligence Platform. The user searches a campus; the system
auto-detects the landing page, mines historical performance + keyword data, and
generates production-ready RSAs where **every asset carries a data-derived reason**.

It behaves like a Google Ads strategist, not a generic chatbot: an LLM (optional)
only rephrases within the data it is given, and the deterministic engine runs when
no LLM key is configured — so the module always works.

---

## Architecture

Follows the platform's standard 4-layer flow (route → service → repository → model).
New code is isolated in two packages so it can grow into a suite of AI agents:

```
app/ai_clients/            # external LLM client (cached, tenacity retries, typed errors)
  llm_client.py            #   LLMClient / get_llm_client()  — Anthropic Claude
  exceptions.py
app/services/ai/           # the engine (one responsibility per service)
  campus_config.py         #   curated campus briefs (facts only)
  campus_service.py        #   Step 1 discovery + Step 2 Final-URL ranking
  landing_page_service.py  #   Step 3 landing-page extraction (facts only)
  historical_intelligence_service.py  # Step 4 warehouse mining
  keyword_research_service.py          # Step 5 pluggable providers (planner + historical)
  intent_classifier.py     #   Step 6 rule-based intent
  keyword_scorer.py        #   Step 7 weighted scoring
  rsa_validator.py         #   Step 10 validation + Ad Strength prediction
  ad_copy_service.py       #   orchestrator (Steps 1-11) + persistence
  ad_copy_export.py        #   Excel / CSV / JSON export
app/models/ad_copy.py      # AdCopyGeneration (history table, JSONB payloads)
app/repositories/ad_copy.py
app/schemas/ad_copy.py
app/api/v1/ad_copy.py      # /ai/ad-copy/* endpoints
frontend/src/pages/AiAdCopyGeneratorPage.tsx
```

## Data flow

```
campus query
  └─ CampusService.search ............... autocomplete from curated briefs + warehouse stats
selected campus
  └─ CampusService.discover_final_url ... rank historical ad URLs by spend→clicks→CTR
                                          (+ confidence, manual override, homepage fallback)
  └─ LandingPageService.analyze ......... fetch + parse the URL (facts only, SSRF-guarded)
  └─ HistoricalIntelligenceService ...... best historical headlines/descriptions + themes
  └─ KeywordResearchService.collect ..... Keyword Planner → historical fallback (merged)
       └─ IntentClassifier + KeywordScorer  intent + weighted 0-100 score per keyword
  └─ AdCopyService generation ........... hybrid LLM (constrained) OR deterministic template
       └─ per-asset reasoning
  └─ RsaValidator ....................... char limits, policy, diversity → Ad Strength
  └─ persist (AdCopyGeneration) ......... JSONB assets + scores + reasoning
  └─ export ............................. Excel / CSV / JSON
```

## Decision flow (key branches)

- **Engine:** `LLMClient.available()` (enabled + `ANTHROPIC_API_KEY` + package) →
  hybrid LLM; else deterministic template. LLM output is validated and back-filled
  from the template generator if it under-delivers.
- **Final URL:** manual override (conf 1.0) > historical ad URLs (conf ~0.55–0.98 by
  spend share) > official homepage (conf 0.25).
- **Keyword provider:** Keyword Planner first (if `KEYWORD_PLANNER_ENABLED` and the
  dev token has Standard access); always merged with the historical provider, which
  is the reliable fallback.
- **Campus:** curated brief if matched; otherwise a generic brief built from the typed
  name (so every university works without redesign).

## Database schema — `ad_copy_generations`

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| created_at / updated_at | timestamptz | TimestampMixin |
| actor | varchar(320) | X-Actor header |
| campus | varchar(255) | indexed |
| account_id / campaign_id | FK (nullable) | SET NULL |
| final_url / url_source / url_confidence | text / varchar / numeric | discovery result |
| backend | varchar(16) | `llm` or `template` |
| historical_features_used | JSONB | features fed to generation |
| keyword_snapshot | JSONB | scored keywords used |
| generated_assets | JSONB | headlines/descriptions/extensions |
| scores | JSONB | quality prediction |
| reasoning | JSONB | per-asset reasons |

Migration: `alembic/versions/0003_ai_ad_copy.py` (`alembic upgrade head`).

## API reference (`/api/v1/ai/ad-copy`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/campus/search?q=&limit=` | Autocomplete campuses (with history stats) |
| GET | `/campus/final-url?campus=&override=` | Ranked Final-URL candidates |
| POST | `/generate` | Full generation (body: `AdCopyGenerateRequest`) |
| GET | `/history?campus=&limit=` | Recent generations |
| GET | `/{id}/export?format=excel\|csv\|json` | Download a saved generation |

`POST /generate` is guarded by `require_api_key` (enforced only when `API_KEY` is
set) and reads the actor from the `X-Actor` header.

## Configuration (`.env`)

```
ANTHROPIC_API_KEY=            # optional; blank → deterministic engine
AD_COPY_LLM_MODEL=claude-sonnet-5
AD_COPY_LLM_ENABLED=true
KEYWORD_PLANNER_ENABLED=true  # auto-falls back to historical if token lacks access
LANDING_PAGE_TIMEOUT_SECONDS=12
```

## Developer / deployment notes

- **Dependencies:** `anthropic`, `beautifulsoup4` added (`httpx`, `openpyxl` already
  present). `anthropic` is optional at runtime — the engine degrades gracefully.
- **Tests:** `pytest tests/test_ai_ad_copy.py` — pure-logic, Final-URL ranking, landing
  parser, and API smoke (deterministic backend, network stubbed).
- **No network in tests:** the API test monkeypatches `LandingPageService.analyze`.
- **Safety:** landing-page fetch is http(s)-only, refuses private/loopback hosts, and
  caps the response body. Copy never fabricates rankings/fees/placement numbers — only
  on-page facts and historical data are used.
- **Extensibility (future agents):** add a keyword provider by implementing the
  `KeywordProvider` protocol; swap the LLM provider behind `LLMClient.complete`; the
  same services back a future AI Campaign Creator / Keyword Generator.

## Phase B (not yet built)

Live Keyword Planner verification, Google Ads Editor export format, competitor SERP +
Google Trends providers, impression-share + asset-level performance sync, per-day ad
copy versioning.
