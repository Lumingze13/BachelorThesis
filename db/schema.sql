-- db/schema.sql — study-platform schema (idempotent; safe to re-run on every boot)
--
-- Three tables:
--   sessions   — one row per participant run; JSONB columns mirror the app's
--                `study` object so eval_pipeline's loader reconstructs it 1:1.
--   messages   — flattened, queryable transcript turns (phase b + c).
--   eval_runs  — one row per evaluation-pipeline run launched from the dashboard.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

CREATE TABLE IF NOT EXISTS sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  condition     text NOT NULL DEFAULT 'main'    CHECK (condition IN ('main','baseline')),
  status        text NOT NULL DEFAULT 'started' CHECK (status IN ('started','in_progress','completed','abandoned')),
  version       text,
  profile       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- { demographics, bigFive, values, riasec, year, ... }
  pre_survey    jsonb NOT NULL DEFAULT '{}'::jsonb,  -- raw pre-survey answers (study.preSurvey)
  scores        jsonb NOT NULL DEFAULT '{}'::jsonb,  -- { bigFive, riasec, values }
  phase_b       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- { career, familiarity, interestStrength, transcript[] }
  phase_c       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- { transcript[], durationSec, turnCount }
  post_survey   jsonb NOT NULL DEFAULT '{}'::jsonb,  -- raw post-survey answers (study.postSurvey)
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz
);

CREATE INDEX IF NOT EXISTS sessions_status_idx    ON sessions (status);
CREATE INDEX IF NOT EXISTS sessions_condition_idx ON sessions (condition);
CREATE INDEX IF NOT EXISTS sessions_created_idx   ON sessions (created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id  uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  phase       text NOT NULL CHECK (phase IN ('b','c')),
  idx         int  NOT NULL,
  role        text NOT NULL CHECK (role IN ('user','assistant')),
  text        text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_session_idx ON messages (session_id, phase, idx);

CREATE TABLE IF NOT EXISTS eval_runs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at   timestamptz NOT NULL DEFAULT now(),
  status       text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
  config       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- { source, depths, prompt_structures, n_runs, model, use_real }
  summary      jsonb,                                -- headline metrics (D0/D2 spearman per outcome, etc.)
  report_path  text,
  report_html  text,
  error        text
);

CREATE INDEX IF NOT EXISTS eval_runs_created_idx ON eval_runs (created_at DESC);
