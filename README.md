# Thesis — Future-Self Career Chatbot + Study Platform

A no-build React frontend + Express backend that lets university
students converse with a 10-year **future self**, wrapped in a small **study
platform**: every session is persisted to Postgres, a gated **admin dashboard**
manages sessions and exports, and the **evaluation pipeline** (`eval_pipeline/`,
LLM-judge ↔ human agreement) can be launched, stored, and viewed from the same UI.

Persistence is **additive** — with no `DATABASE_URL` the app runs exactly as
before (in-memory sessions, JSON download at the end).

---

## Architecture

```
Browser (no-build React .jsx)                Express (server.js, ESM)
  app/chat/phaseb/survey/screens   ──HTTP──▶  /api/phase-b|c/session, /api/chat   → UvA proxy (gpt-5.1, default) | Anthropic (fallback)
                                              /api/sessions (POST/GET/PATCH)       → Postgres (lib/sessions.js)
  admin/index.html (dashboard)     ──HTTP──▶  /admin (gated), /api/admin/*         → Postgres
                                              /api/admin/eval-runs                 → spawns Python (lib/eval_runner.js)
                                                                                       │
eval_pipeline/ (Python, offline-capable) ◀── exported session JSON (temp dir) ──────┘
  run_eval.py → loader → persona/ssr → metrics → report.html (self-contained)
```

**Node owns all DB I/O.** For a DB-source eval run, Node exports the stored
sessions to a temp dir of `<sessionId>.json` files (the exact shape the existing
loader reads) and points Python at it — so Python needs no database driver and
the metrics code is reused unchanged.

### Data model (`db/schema.sql`, idempotent on boot)
- **`sessions`** — one row per participant run. JSONB columns (`profile`,
  `pre_survey`, `scores`, `phase_b`, `phase_c`, `post_survey`) mirror the app's
  `study` object so `reconstructStudy()` rebuilds it 1:1 for the eval loader.
- **`messages`** — flattened transcript turns (`phase` b/c, `idx`, `role`, `text`).
- **`eval_runs`** — one row per pipeline run (`config`, `summary`, `report_html`).
- **`simulations`** — one row per silicon-participant bot↔bot run (`persona`,
  `config`, `transcript`); powers the "real vs simulated" comparison on `/results`.

---

## Environment variables (`.env`; see `.env.example`)

| Var | Required | Purpose |
|-----|----------|---------|
| `LLM_BASE_URL` + `UVA_API_TOKEN` | study default (chat) | OpenAI-compatible proxy for the participant chat (UvA: `https://llmproxy.uva.nl/v1`, model `gpt-5.1`); both set → proxy is used |
| `MODEL_ID` | optional | Override the chat model id (default `gpt-5.1` on the proxy, `claude-sonnet-4-6` on the fallback) |
| `ANTHROPIC_API_KEY` | fallback chat + eval | Used for chat only when the proxy vars are unset; always used by the eval pipeline / silicon runs |
| `DATABASE_URL` | optional | Postgres. Unset → in-memory mode, admin disabled |
| `ADMIN_TOKEN` | optional | Shared secret gating `/admin`. Unset → admin disabled (503) |
| `RESULTS_TOKEN` | optional | Read-only share link for `/results` (anonymized). Unset → `/results` falls back to `ADMIN_TOKEN` |
| `PORT` | optional | Default 3000 |
| `DATABASE_SSL` | optional | `disable` to force-off SSL (remote DBs use SSL automatically) |
| `PYTHON_BIN` | optional | Interpreter for eval runs (default `python3`) |

Secrets live only in `.env` (git-ignored). The client never receives
`ANTHROPIC_API_KEY` or `ADMIN_TOKEN`.

---

## Local development

```bash
npm install                 # node deps (incl. pg)
pip install -r eval_pipeline/requirements.txt   # numpy, scipy, matplotlib, scikit-learn

npm run db:up               # start local Postgres (docker compose, host port 5433)
# .env already points DATABASE_URL at postgresql://postgres:postgres@localhost:5433/thesis
npm start                   # http://localhost:3000  (schema auto-applies on boot)
```

- **Participant app:** `/` — condition axes from the URL:
  `?study=kangzhi|andrea&rec=guide|reflective|direct&cond=main|baseline&pid=K017`
  (plus `?session=<id>` for admin-minted links and `?test=1` for the researcher launcher).
- **Admin dashboard:** `/admin` → enter `ADMIN_TOKEN`.

> Local Postgres uses host port **5433** to avoid clashing with a system Postgres
> on 5432. Stop the DB with `npm run db:down`.

### Migrations
`db/schema.sql` is idempotent (`CREATE … IF NOT EXISTS`) and runs automatically on
every boot via `initSchema()`. To apply manually:
`psql "$DATABASE_URL" -f db/schema.sql`.

---

## Admin dashboard (`/admin`, gated by `ADMIN_TOKEN`)
- **Sessions:** list (filter by condition/status), open (profile + scores + both
  transcripts + pre/post answers + raw JSON), delete, **New session** (returns a
  participant link `/?session=<id>&condition=<…>`), **Export all** / **Export
  de-identified** JSON.
- **Eval runs:** launch a run (data source synthetic | DB, depths, prompt
  structures, k, fake/real LLM), watch status, open the HTML report.

Auth is a single shared secret (Bearer header, httpOnly `admin_token` cookie set
by `/admin/login`, or `?token=`). **Minimal by design** — no user accounts.
- **Simulations:** launch a silicon-participant run (pick a completed session +
  number of turns); a persona built from that profile chats with the same
  future-self bot, and the transcript is stored for `/results`.

---

## Results page (`/results`, read-only, gated by `RESULTS_TOKEN`)
A supervisor-facing, **anonymized** surface — share the link without granting
admin powers. Names are replaced with labels (P01, P02…); it can only read.
- **Overview** — sessions collected so far (by condition/career) and mean pre→post
  Δ per IBM outcome (continuity / vividness / closeness). Descriptive pilot only.
- **RQ results** — judge↔human agreement (MAE / Spearman ρ / QWK / ICC / inter-run
  SD per outcome × depth × structure) from stored eval runs, correctly labeled.
- **Real vs simulated** — each simulated Phase-C transcript beside the matched
  real one (illustrative face validity, not a measured result).
- **Browse sessions** — every completed session, anonymized, with scores, both
  transcripts, and pre→post answers.

Auth: `RESULTS_TOKEN` (or `ADMIN_TOKEN`) via `?token=` → httpOnly `results_token`
cookie. All `/api/results/*` payloads are de-identified + name-stripped.

---

## Silicon cohort (simulated participants)
Run the RQ pipeline on **simulated** participants seeded from real open-data
profiles (Big Five + RIASEC + demographics), for method validation before human
data exists. Participant model (Opus) ≠ judge model (Sonnet) to avoid trivial
self-agreement. Pick the cohort with `scripts/select_cohort.py`, then
`node run_silicon_cohort.mjs --n 1 --skip-eval` to eyeball one, then scale. This
is **method validation (LLM↔LLM), not human ground truth** — see
[`SILICON_COHORT.md`](SILICON_COHORT.md).

## Evaluation runs
- **Synthetic** (offline, deterministic): generates planted-truth sessions and a
  `FakeLLM`, reproducing the agreement gradient (D0 near-chance → D2 good → D3
  inflated/leakage; observable manip-checks highest). Good for demo/methodology.
- **DB sessions**: evaluates stored sessions. Use **Real LLM** (`ANTHROPIC_API_KEY`)
  for meaningful numbers; *Fake on real sessions is a smoke test* (no planted
  truth → near-degenerate metrics) that still proves the full DB→pipeline→report loop.

CLI (what the dashboard runs):
```bash
python -m eval_pipeline.run_eval --synthetic --n 24 --depths D0,D2,D3 \
  --structures structured --n-runs 5 --out-dir out --summary-json out/summary.json
python -m eval_pipeline.run_eval --sessions-dir <dir> ... [--use-real]
```

---

## Deployment (Railway) — Node + Python on ONE service

**Chosen approach: a single service running both runtimes.** The Node server
spawns the Python pipeline via `child_process`, so they must share a container; a
separate Python worker would require a job queue + shared DB writer, unnecessary
at this scale.

1. **Build:** the root `requirements.txt` + `package.json` let Railway's builder
   (Railpack auto-detects both; or Nixpacks via the included `nixpacks.toml`)
   install Node deps **and** the Python eval deps. Start command: `node server.js`.
2. **Postgres:** add a Railway Postgres plugin and set the service variable
   `DATABASE_URL = ${{Postgres.DATABASE_URL}}` (private network; SSL handled
   automatically for remote hosts).
3. **Env:** set `LLM_BASE_URL` + `UVA_API_TOKEN` (+ `MODEL_ID=gpt-5.1`) for the
   study chat — or `ANTHROPIC_API_KEY` as the fallback (also needed for eval
   runs); `ADMIN_TOKEN` (long random), `RESULTS_TOKEN` (long random, distinct —
   the read-only supervisor link), and optionally `PYTHON_BIN=python3`. Do
   **not** set `PORT` (Railway injects it). Verify `/healthz` after deploy.
4. Deploys are triggered by pushing to the connected GitHub repo; the schema
   (incl. the new `simulations` table) applies itself on boot.

> **Rotate any previously-exposed secrets** (`ANTHROPIC_API_KEY`, the Postgres
> password in `DATABASE_URL`, `ADMIN_TOKEN`) and set a fresh `RESULTS_TOKEN`.
> Secrets belong only in Railway env vars, never in the repo.

---

## Privacy / ethics
Transcripts, open-ended answers, and the post-survey **contact email** are PII.
The admin area is auth-gated; full transcripts are never logged. **Export
de-identified** strips `contact` and redacts email addresses in free text and
transcripts (name/place redaction is best-effort and flagged — manual review
required). The `/results` page serves only de-identified, name-stripped data
(`P01…` labels) and is read-only, so it can be shared with supervisors without
exposing PII; manual review of transcripts is still advised before any external
sharing. Real-participant use requires the team's ethics clearance and a defined
retention/deletion policy.

---

## Testing
```bash
npm test            # flow (UX + persistence) + reconstruct/de-id + admin gate + DB roundtrip
                    # DB/admin DB tests skip cleanly if DATABASE_URL/ADMIN_TOKEN are unset
PYTHONHASHSEED=0 python -m pytest eval_pipeline/tests -q   # 87 pipeline tests
```

## Limitations
- Single shared-secret admin (no roles/audit).
- Eval runs execute in-process (fire-and-forget) — no queue; fine for a few
  concurrent runs, not high throughput.
- `judge-model selection` as an eval IV depends on multiple models being
  available; the bundled pipeline is single-judge by default (see
  `RESEARCH_PLAN_eval_pipeline.md`).
