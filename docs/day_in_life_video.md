# "Day in the life" video stimulus (optional, Phase B→C)

A first-person POV glimpse — morning, afternoon, evening of one ordinary weekday ten years on — generated from the chosen career, the location, and what the participant told the recommendation guide. It appears at the Phase B→C handoff, after the career is locked in and before the role-play.

**It is OFF by default.** The fielded study and the automated flow test are unchanged unless it is explicitly enabled. Turn it on only with the team's agreement — it is a new pre-chat stimulus and, for a study with ethics approval, adding it is a protocol change that could confound the manipulation.

## How it works

- When the participant locks in a career (end of Phase B), the frontend POSTs to `/api/day-in-life`. If the feature is enabled, the server starts generation immediately, so the clips render during the B→C pause text.
- Claude writes three short POV scene descriptions; each is wrapped in fixed shot/style scaffolding and sent to **Google Veo** (Gemini API). Generation is **fresh per participant** (no caching) — every session renders new clips.
- The browser polls `/api/day-in-life/:jobId` until the clips are ready, then plays them in order (morning → afternoon → evening) with a label overlay. The bytes are streamed through `/api/day-in-life/:jobId/:seg` (the Veo file URIs need the API key, so they can't be fetched client-side).
- It is always **skippable**, and any error or timeout falls straight through to the conversation — it never traps the participant.

## Enabling it (Railway env)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `VIDEO_ENABLED` | yes | _(off)_ | Set to `1`/`true` to turn the feature on. |
| `GEMINI_API_KEY` | yes | — | Google AI Studio key (or `GOOGLE_API_KEY`). Feature stays off if absent. |
| `VEO_MODEL` | no | `veo-3.1-fast-generate-preview` | e.g. `veo-3.1-generate-preview` for higher quality. |
| `VEO_ASPECT` | no | `16:9` | `16:9` or `9:16`. |
| `VEO_RESOLUTION` | no | `720p` | `720p` / `1080p`. |
| `VEO_DURATION` | no | `8` | Seconds per clip (`4`/`6`/`8`). |
| `VEO_POLL_MS` | no | `10000` | How often the server polls Veo. |
| `VEO_TIMEOUT_MS` | no | `360000` | Per-clip generation timeout. |
| `VEO_JOB_TTL_MS` | no | `1800000` | When the job + temp files are cleaned up. |

Both `VIDEO_ENABLED` truthy **and** a key must be present, or `/api/day-in-life` returns `{enabled:false}` and the flow behaves exactly as before.

## Cost & latency

Each participant triggers **three** Veo generations. Veo clips take roughly 1–5 minutes each (run in parallel) and cost real money per clip — budget accordingly before fielding. To cut this, set `VEO_MODEL` to a `fast`/`lite` variant (the default is already `fast`) or shorten `VEO_DURATION`.

## Testing with a key

1. Set `VIDEO_ENABLED=1` and `GEMINI_API_KEY=…` in the environment.
2. Run the study to the end of Phase B and lock in a career.
3. The B→C handoff shows a loader, then the three POV clips, then "Step into the conversation".

Code: `lib/video.js` (job store, Veo calls, polling, download), `lib/prompt.js` (`buildDayInLifeScenePrompt`), `server.js` (`/api/day-in-life*`), `dayinlife.jsx` (player), `app.jsx` (wiring at `pause_bc`).
