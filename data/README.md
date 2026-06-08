# data/ — drop the open dataset here

This folder holds the open-source dataset we use to **seed realistic personas**
(real human Big Five + RIASEC + demographics). Raw data is git-ignored — keep it
out of the repo.

## What to download
**Holland Code (RIASEC) — Open-Source Psychometrics Project** (one file gives
Big Five via TIPI + RIASEC + demographics):
- openpsychometrics raw data: https://openpsychometrics.org/_rawdata/  → the RIASEC `.zip`
- or Kaggle: https://www.kaggle.com/datasets/lucasgreenwell/holland-code-riasec-test-responses

Unzip it and place the `data.csv` here as:

```
data/riasec.csv
```

(The file is TAB-delimited despite the `.csv` name — the selector auto-detects that.)

## Then select the cohort
```
python3 scripts/select_cohort.py --in data/riasec.csv --out data/cohort_100.csv --n 100
```

This applies our frame — undergrad age (17–24) + business/economics/analytics-ish
free-text `major` + a data-quality screen — then ranks survivors by closeness to a
Business-Analytics RIASEC archetype (high Enterprising / Conventional /
Investigative). Output `data/cohort_100.csv` is persona-ready (one row per
participant: age, gender, country, education, major, `riasec_*`, `big5_*` on a
1–5 scale, `fit_rank`, `fit_score`).

> Note: "business analytics" is not a field in the dataset (free-text major), so
> this is an *approximation* of our frame, not an exact filter. The personas it
> seeds drive the silicon-cohort simulation; the conversation and the outcome
> ratings are AI-generated (the simulated, not-human part).
