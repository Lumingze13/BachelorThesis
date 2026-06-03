# STUDY_PLATFORM_SPEC — DB persistence + management dashboard for the future-self study

> Full build spec. The short build goal references this file; read it end-to-end before coding. **Never break the existing participant-facing chatbot UX.**

## What to build
Turn the existing future-self chatbot prototype into a small **study platform**:
1. **Persist every session** (profile, surveys, both transcripts, scores, condition) to **Postgres** instead of in-memory + manual JSON download.
2. A **management dashboard** (admin UI) to: start/list/open/delete sessions, view a session's transcripts + survey answers + scores, filter by condition/status, export.
3. A mechanism to **start separate sessions and remember them** (server-generated session ids; shareable participant links; resume by id).
4. **Manage eval-pipeline runs** from the same dashboard: trigger a run over stored sessions, store its results, list runs, view metrics + the HTML report.

## Existing architecture — read first, do not break
- Backend `server.js`: Node **ESM**, Express, `@anthropic-ai/sdk` (model `claude-sonnet-4-6`), API key from `.env` (`ANTHROPIC_API_KEY`). Today sessions live in an **in-memory `Map`**; endpoints: `POST /api/phase-b/session`, `POST /api/phase-c/session`, `POST /api/chat`, `POST /api/regenerate`; serves the static frontend; permissive CORS.
- Frontend: **no-build React** (`.jsx` loaded as plain scripts; `app.jsx`, `chat.jsx`, `phaseb.jsx`, `survey.jsx`, `screens.jsx`). Flow: landing → consent → avatar → pre-survey → phaseB (career pick) → phaseC (role-play) → post-survey → **Closure** (builds a `study` object, downloads JSON). Condition (`main|baseline`) from `?condition=`.
- The `study` object (in `app.jsx` Closure) is the canonical record: `{ meta{condition,version,completedAt}, profile, preSurvey, scores{bigFive,riasec,values}, phaseB{career,familiarity,interestStrength,transcript[]}, phaseC{transcript[],durationSec,turnCount}, postSurvey }`. Survey field ids live in `survey.jsx`.
- `eval_pipeline/` (Python) already exists and consumes exactly that `study` JSON schema (loader, persona-replication, metrics, HTML report). **Reuse it — do not rebuild the metrics.**

## Hard rules / stack
- Keep the participant flow and look identical; persistence is additive.
- Postgres via **`pg`** (node-postgres), connection from **`DATABASE_URL`** (Railway provides it); SSL as Railway requires. Keep live LLM message history in memory for an active conversation, but write a **durable session record** to Postgres.
- Admin UI: same no-build React style, served by the same Express app under `/admin`.
- **Admin auth**: gate all `/api/admin/*` routes and the `/admin` UI behind a shared secret from env (`ADMIN_TOKEN`) — simple bearer/cookie check, not full user accounts (flag as minimal). Never expose `ANTHROPIC_API_KEY` or `ADMIN_TOKEN` to the client.
- Schema via a checked-in migration (`db/schema.sql`) + idempotent init on boot. Provide **local dev** via `docker-compose` Postgres (or document a local `DATABASE_URL`).
- Do not commit secrets; extend `.env.example` with the new vars.

## Data model (Postgres)
- `sessions`: `id` (uuid), `condition`, `status` (`started|in_progress|completed|abandoned`), `created_at`, `completed_at`, `version`, JSONB columns mirroring the `study` object — `profile`, `pre_survey`, `scores`, `phase_b`, `phase_c`, `post_survey` — so the eval loader can reconstruct the identical `study` JSON. Optional `notes` text.
- `messages` (queryable transcripts): `id`, `session_id` (fk), `phase` (`b|c`), `idx`, `role` (`user|assistant`), `text`, `created_at`.
- `eval_runs`: `id`, `created_at`, `status` (`queued|running|done|failed`), `config` JSONB (`{depths, prompt_structures, n_runs, model, use_real}`), `summary` JSONB (headline metrics), `report_path`/`report_html`, `error`.

## Session lifecycle + API
- `POST /api/sessions` → create a session record (`status=started`, condition from body/query or balanced assignment), return `{ id }`. Frontend calls this at the start of a run and keeps the id.
- Frontend reads optional `?session=<id>` (admin-created link) and `?condition=`; if no session id, auto-create one (walk-in). Persist progress: write phaseB on completion, append phaseC turns (autosave each turn if feasible, else at closure), write surveys; set `status=completed` + `completed_at` at Closure. Keep the JSON download as a bonus.
- `GET /api/sessions/:id` (resume/load), `GET /api/admin/sessions` (list + filters), `GET /api/admin/sessions/:id` (full record + messages), `DELETE /api/admin/sessions/:id`, `GET /api/admin/sessions/export` (JSON array for the eval pipeline).

## Management dashboard (`/admin`, gated)
- **Sessions list**: table (id, condition, status, created, completed, #phaseC turns), filters, open/delete, "Export all (JSON)".
- **Session detail**: profile + computed scores; both transcripts rendered as chat; all survey answers (pre/post) in a readable grid; raw JSON view/download.
- **New session**: creates a session and shows a **participant link** (`/?session=<id>&condition=<...>`), plus condition assignment.
- **Eval runs**: a form to launch a run (pick depths / prompt structures / k / model / fake-vs-real); a list of runs with status + headline metrics; open a run to view its HTML report.

## Eval integration
- Add a DB-backed source for `eval_pipeline`: a small loader that pulls session rows from Postgres and reconstructs the `study` JSON the existing loader expects (metrics code untouched). Keep `data/raw/` drop-in as an alternative.
- Triggering a run from the dashboard: the Node backend inserts an `eval_runs` row (`queued`) and runs the Python pipeline (e.g. `child_process.spawn('python', ['-m','eval_pipeline.run_eval','--from-db','--run-id',id])`); Python pulls sessions, computes metrics, writes `summary` + report back to the `eval_runs` row (and an HTML file). Dashboard polls run status.
- **Deployment note (handle + document):** needs both Node and Python at runtime. Either one Railway service with Node+Python (nixpacks), or a separate Python worker service sharing `DATABASE_URL`. State which you chose and why.

## Privacy / ethics (do not skip)
- Transcripts + the post-survey `contact` email + open-ended answers are **PII**. Admin area must be auth-gated; never log full transcripts; add an admin action to export a **de-identified** copy (strip contact/email; flag names/places). Note in the README that real-participant use needs the team's ethics clearance and a retention/deletion policy.

## Phases (build + verify incrementally)
1. **Persistence**: `pg` + `DATABASE_URL` + `db/schema.sql` + session create/save/finalize; participant flow still works end-to-end and now lands in Postgres. Local docker-compose Postgres.
2. **Dashboard**: gated `/admin` — list/detail/start/delete/export.
3. **Eval mgmt**: DB loader for `eval_pipeline`; trigger/list/view runs.
4. **Docs/dev**: README (setup, env, migrations, local dev, Railway deploy, Node+Python note), updated `.env.example`, basic tests (session create→persist→fetch; admin auth gate; DB→study reconstruction matches the export schema).

## Acceptance — iterate until all hold, then report
1. Participant flow unchanged in UX and now persists a complete `sessions` row + `messages` on completion.
2. Admin (with `ADMIN_TOKEN`) can list, open (transcripts + surveys + scores), start (get a participant link), delete, and export sessions; unauthenticated access is blocked.
3. A reconstructed `study` JSON from the DB is schema-compatible with what `eval_pipeline`'s loader expects.
4. An eval run can be launched from the dashboard, reads sessions from the DB, and shows headline metrics + the HTML report.
5. Migrations + env + local dev + Railway deploy documented; no secrets committed; existing API keys stay server-side.

Report back: the migration/schema, the new endpoints, how to run locally (docker-compose + commands), the Railway deploy approach for Node+Python, and any limitations. Don't claim a step works without running it.
