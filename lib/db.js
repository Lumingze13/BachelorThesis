/*
 * lib/db.js — Postgres connection + idempotent schema init.
 *
 * Persistence is OPTIONAL: if DATABASE_URL is unset the app still runs in the
 * original in-memory mode (participant flow works, admin shows a notice).
 * `dbEnabled` lets callers degrade gracefully instead of crashing.
 *
 * SSL: Railway/remote Postgres needs SSL (self-signed proxy → rejectUnauthorized
 * false); local docker / localhost does not. Override with DATABASE_SSL=disable.
 */

import './env.js'; // populate process.env before reading DATABASE_URL below
import pg from 'pg';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const url = process.env.DATABASE_URL || '';
export const dbEnabled = Boolean(url);

function sslConfig(u) {
  if (!u) return false;
  if (process.env.DATABASE_SSL === 'disable') return false;
  const isLocal = /@(localhost|127\.0\.0\.1|\[::1\])[:\/]/.test(u);
  if (isLocal) return false;
  return { rejectUnauthorized: false }; // managed proxies present self-signed certs
}

export const pool = dbEnabled
  ? new pg.Pool({ connectionString: url, ssl: sslConfig(url), max: 5, idleTimeoutMillis: 30000 })
  : null;

if (pool) {
  pool.on('error', (err) => console.error('[db] idle client error:', err?.message || err));
}

export async function query(text, params) {
  if (!pool) throw new Error('DATABASE_URL not set — persistence disabled');
  return pool.query(text, params);
}

/** Run db/schema.sql (idempotent). Returns true on success, false if no DB. */
export async function initSchema() {
  if (!pool) return false;
  const sqlPath = path.join(__dirname, '..', 'db', 'schema.sql');
  const sql = fs.readFileSync(sqlPath, 'utf8');
  await pool.query(sql);
  return true;
}

export async function closePool() {
  if (pool) await pool.end();
}
