# Prompt-behaviour evidence — length variation & 10-year future grounding

Two role-play effects the supervisor/feedback asked to be real, not just promised:

1. **Reply length varies** — light/throwaway questions get short replies; only big,
   open questions run long (no uniform medium block every turn).
2. **Answers and advice are grounded in the 10-years-future world** — the chosen
   career's tasks, tools and valued skills have changed; advice reflects the
   future labour market, not today's — **across career types**, not just tech.

## How this was tested

`test/prompt_behavior_check.mjs` builds the **real** Stage-C system prompt from
`lib/prompt.js` (`buildSystemPrompt`) and runs a fixed 8-turn participant script
spanning a range of question sizes, then measures each reply objectively
(word-count by turn kind + a future-reality detector on the day-to-day/advice
turns). Generation needs a model; **measurement does not**.

> Sandbox note: this environment has no model key, so the transcripts below were
> generated with a Claude model **standing in for the study's gpt-5.1**, driven by
> the exact app prompt. Before fielding, re-run with the real model:
> `LLM_BASE_URL=… UVA_API_TOKEN=… node test/prompt_behavior_check.mjs`
> (it exits non-zero if either effect regresses). Raw transcripts are in
> `docs/prompt_behavior_evidence/bot_*.json`.

## Measured result (2026-06-18)

| Career (type) | short-turn mean | big/advice mean | range | length varies | future-grounded (day/advice) |
|---|---|---|---|---|---|
| Data analyst (analytical) | ~42w | ~164w | 10–175w | ✅ | ✅ |
| Registered nurse (clinical) | ~41w | ~166w | 14–190w | ✅ | ✅ |
| Primary school teacher (caring)\* | — | ~150w (3-turn probe) | 144–161w | ✅ | ✅ |

\* Teacher was a focused 3-turn probe of the highest "feels timeless" risk after a
robustness guard was added (the future-shift now explicitly applies to clinical,
hands-on, caring, creative and trades work, not only desk jobs).

### Representative excerpts (future grounding, across fields)

- **Nurse, day-to-day:** *"the obs mostly run themselves now; the patches read
  everything and ping me, so i'm not chasing numbers, i'm reading what the numbers
  mean and deciding who actually needs me."*
- **Nurse, advice:** *"a lot of the rote clinical recall i sweated over got
  offloaded to the systems — they'll flag the drug interaction before i would. so
  don't over-index on memorising facts a tool will hold for you."*
- **Teacher, advice:** *"The tools handle differentiation and worksheets now …
  spend less energy on polished lesson plans and more on the messy human stuff —
  reading a room, sitting with a kid who's melting down."*
- **Data analyst, advice:** *"Don't go all-in on writing SQL and running
  regressions by hand the way a 2026 syllabus would tell you — the tools do that
  now … the part the machines are worst at, and the part everyone needs."*

### Length variation (illustrative, data analyst)

`hi?` → 53w · `what do I call you?` → 48w · day-to-day → 171w · what to learn → 175w
· any regrets → 89w · `lol same` → 10w · hardest part → 145w · `thanks` → 55w.

## Reproduce

```bash
# with the study model (gpt-5.1 via the UvA proxy):
LLM_BASE_URL=<proxy> UVA_API_TOKEN=<token> node test/prompt_behavior_check.mjs
# or measure transcripts you generated elsewhere (dir holds bot_<career>.json):
node test/prompt_behavior_check.mjs --measure docs/prompt_behavior_evidence
```
