#!/usr/bin/env python3
"""
select_cohort.py — pick the N participants that best match our study frame
(young Economics & Business / Business-Analytics-leaning undergraduates) from the
open-source Holland Code (RIASEC) dataset (openpsychometrics / Kaggle).

WHY: the dataset has no "business analytics student" field. We approximate the
frame with hard filters (undergrad age + business/econ/analytics-ish free-text
major + data-quality screen) and then rank the survivors by closeness to a
Business-Analytics RIASEC archetype (high Enterprising / Conventional /
Investigative). The output is a clean, persona-ready CSV.

INPUT: the dataset's data.csv (TAB- or comma-delimited; auto-detected). Expected
columns (openpsychometrics RIASEC schema):
  R1..R8 I1..I8 A1..A8 S1..S8 E1..E8 C1..C8   (48 interest items, 1-5)
  TIPI1..TIPI10                               (Ten-Item Personality, 1-7 -> Big Five)
  VCL1..VCL16                                 (vocab check; 3 are fake words = quality screen)
  education urban gender engnat age ... major country   (demographics)

OUTPUT: <out> CSV with one row per selected person:
  pid, age, gender, country, education, major,
  big5_O..big5_N (1-5),  riasec_R..riasec_C (1-5),  fit_rank, fit_score
This is exactly the shape the persona generator (lib/personas.js) consumes.

USAGE:
  python3 scripts/select_cohort.py --in data/riasec.csv --out data/cohort_100.csv --n 100
"""

import argparse
import re
import sys
import pandas as pd
import numpy as np

RIASEC = ["R", "I", "A", "S", "E", "C"]
# Business-Analytics archetype in RIASEC z-space (relative to the filtered pool):
# pull toward Enterprising/Conventional/Investigative, away from Realistic/Artistic/Social.
ARCHETYPE_Z = {"R": -0.7, "I": 1.0, "A": -0.7, "S": -0.3, "E": 1.0, "C": 1.0}

MAJOR_RE = re.compile(
    r"(?:business|analyt|econom|finance|financ|account|management|commerc|"
    r"marketing|data\s*scien|statistic|information system|administration|"
    r"entrepreneur|supply chain|operations)",
    re.IGNORECASE,
)
# openpsychometrics VCL fake words (endorsing them = careless responding)
FAKE_VCL = ["VCL6", "VCL9", "VCL12"]

GENDER_MAP = {1: "Male", 2: "Female", 3: "Other", 0: "unknown"}
EDU_MAP = {1: "Less than high school", 2: "High school", 3: "University degree",
           4: "Graduate degree", 0: "unknown"}


def find_cols(df, prefix, n):
    """Return [prefix1..prefixN] matched case-insensitively, else []."""
    low = {c.lower(): c for c in df.columns}
    out = []
    for i in range(1, n + 1):
        key = f"{prefix}{i}".lower()
        if key not in low:
            return []
        out.append(low[key])
    return out


def col(df, name):
    low = {c.lower(): c for c in df.columns}
    return low.get(name.lower())


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def tipi_big_five(df):
    """TIPI (1-7) -> Big Five on a 1-5 scale to match the app's bigFive."""
    t = find_cols(df, "TIPI", 10)
    if not t:
        return None
    T = {i + 1: to_num(df[t[i]]) for i in range(10)}
    rev = lambda x: 8 - x  # 1-7 reverse
    ext = (T[1] + rev(T[6])) / 2
    agr = (rev(T[2]) + T[7]) / 2
    con = (T[3] + rev(T[8])) / 2
    est = (rev(T[4]) + T[9]) / 2          # emotional stability
    opn = (T[5] + rev(T[10])) / 2
    neu = 8 - est                          # neuroticism = reverse of stability
    rescale = lambda v7: 1 + (v7 - 1) * (4.0 / 6.0)   # 1-7 -> 1-5
    return pd.DataFrame({
        "big5_O": rescale(opn), "big5_C": rescale(con), "big5_E": rescale(ext),
        "big5_A": rescale(agr), "big5_N": rescale(neu),
    })


def riasec_scores(df):
    """Mean of the 8 items per interest dimension (already 1-5)."""
    out = {}
    for L in RIASEC:
        cols = find_cols(df, L, 8)
        if not cols:
            return None
        out[f"riasec_{L}"] = pd.concat([to_num(df[c]) for c in cols], axis=1).mean(axis=1)
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="path to RIASEC data.csv")
    ap.add_argument("--out", dest="out", required=True, help="output cohort CSV")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--age-min", type=int, default=17)
    ap.add_argument("--age-max", type=int, default=24)
    args = ap.parse_args()

    # auto-detect delimiter (openpsychometrics data.csv is TAB-delimited despite .csv)
    df = pd.read_csv(args.inp, sep=None, engine="python", encoding="utf-8",
                     on_bad_lines="skip")
    n0 = len(df)
    print(f"[load] {n0} rows, {len(df.columns)} columns")

    bf = tipi_big_five(df)
    ria = riasec_scores(df)
    if bf is None:
        print("[warn] TIPI columns not found — Big Five will be blank", file=sys.stderr)
    if ria is None:
        sys.exit("[fatal] RIASEC item columns (R1..C8) not found — wrong file?")

    work = pd.DataFrame(index=df.index)
    age_c = col(df, "age")
    work["age"] = to_num(df[age_c]) if age_c else np.nan
    gen_c = col(df, "gender")
    work["gender"] = to_num(df[gen_c]) if gen_c else 0
    edu_c = col(df, "education")
    work["education"] = to_num(df[edu_c]) if edu_c else 0
    maj_c = col(df, "major")
    work["major"] = df[maj_c].astype(str) if maj_c else ""
    ctry_c = col(df, "country")
    work["country"] = df[ctry_c].astype(str) if ctry_c else ""
    work = pd.concat([work, ria, bf if bf is not None else pd.DataFrame()], axis=1)

    # --- data-quality screen ------------------------------------------------
    mask = pd.Series(True, index=df.index)
    fake = [col(df, v) for v in FAKE_VCL if col(df, v)]
    if fake:
        endorsed = pd.concat([to_num(df[f]).fillna(0) for f in fake], axis=1).sum(axis=1)
        mask &= endorsed < 2          # endorsing >=2 fake words = careless
    # implausible / non-undergrad age
    mask &= work["age"].between(args.age_min, args.age_max)
    # complete RIASEC
    mask &= ria.notna().all(axis=1)
    pool = work[mask].copy()
    print(f"[filter] after age {args.age_min}-{args.age_max} + quality: {len(pool)} rows")

    # --- major match (soft tier) -------------------------------------------
    pool["major_match"] = pool["major"].fillna("").str.contains(MAJOR_RE)
    biz = pool[pool["major_match"]]
    print(f"[filter] business/econ/analytics-ish major: {len(biz)} rows")

    # --- rank by RIASEC archetype closeness (z-space within the pool) -------
    def rank_by_archetype(frame, ref):
        if frame.empty:
            return frame.assign(fit_score=[])
        z = frame.copy()
        for L in RIASEC:
            c = f"riasec_{L}"
            mu, sd = ref[c].mean(), ref[c].std(ddof=0) or 1.0
            z[c + "_z"] = (frame[c] - mu) / sd
        dist = np.sqrt(sum((z[f"riasec_{L}_z"] - ARCHETYPE_Z[L]) ** 2 for L in RIASEC))
        return frame.assign(fit_score=(-dist))

    # primary: business-major pool, ranked by archetype; fill from age-pool if short
    primary = rank_by_archetype(biz, pool).sort_values("fit_score", ascending=False)
    chosen = primary.head(args.n)
    if len(chosen) < args.n:
        need = args.n - len(chosen)
        rest = pool.drop(chosen.index)
        filler = rank_by_archetype(rest, pool).sort_values("fit_score", ascending=False).head(need)
        chosen = pd.concat([chosen, filler])
        print(f"[rank] only {len(primary)} business-major matches; filled {need} by archetype+age")

    chosen = chosen.head(args.n).reset_index(drop=True)

    # --- write clean persona-ready CSV -------------------------------------
    out = pd.DataFrame()
    out["pid"] = [f"PID{str(i+1).zfill(3)}" for i in range(len(chosen))]
    out["age"] = chosen["age"].astype("Int64")
    out["gender"] = chosen["gender"].round().map(GENDER_MAP).fillna("unknown")
    out["country"] = chosen["country"].fillna("")
    out["education"] = chosen["education"].round().map(EDU_MAP).fillna("unknown")
    out["major"] = chosen["major"].fillna("").str.slice(0, 60)
    for L in RIASEC:
        out[f"riasec_{L}"] = chosen[f"riasec_{L}"].round(2)
    if bf is not None:
        for t in ["O", "C", "E", "A", "N"]:
            out[f"big5_{t}"] = chosen[f"big5_{t}"].round(2)
    out["fit_rank"] = range(1, len(out) + 1)
    out["fit_score"] = chosen["fit_score"].round(3)

    out.to_csv(args.out, index=False)
    print(f"[done] wrote {len(out)} participants -> {args.out}")
    # quick profile of the selection
    print("\n[selection summary]")
    print(f"  age:    {out['age'].min()}–{out['age'].max()}  (mean {out['age'].dropna().mean():.1f})")
    print(f"  gender: " + ", ".join(f"{k}:{v}" for k, v in out['gender'].value_counts().items()))
    print("  RIASEC means: " + "  ".join(f"{L}={out[f'riasec_{L}'].mean():.2f}" for L in RIASEC))
    if bf is not None:
        print("  BigFive means(1-5): " + "  ".join(f"{t}={out[f'big5_{t}'].mean():.2f}" for t in ["O", "C", "E", "A", "N"]))
    print("  top majors: " + ", ".join(f"{m!r}" for m in out['major'][out['major'].str.len() > 0].head(8)))


if __name__ == "__main__":
    main()
