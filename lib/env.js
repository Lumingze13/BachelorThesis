/*
 * lib/env.js — load .env exactly once, before anything reads process.env.
 *
 * ESM hoists imports, so modules that read process.env at evaluation time (e.g.
 * lib/db.js) run BEFORE a later `dotenv.config()` call in server.js. Importing
 * this module first (it is side-effecting and module-cached, so it runs once)
 * guarantees the environment is populated before any consumer reads it.
 * `override: true` keeps .env authoritative over stale shell vars.
 */
import dotenv from 'dotenv';
dotenv.config({ override: true });
