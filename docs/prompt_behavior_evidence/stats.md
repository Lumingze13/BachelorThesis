# Prompt-behaviour statistics (gpt-5.1)

N=8 personas across career types, each at a random temperature in 0.7–1.0 (2026-06-18).

| type | career | T | short | big/adv | max | varies | brief | future | B future/5 |
|---|---|---|---|---|---|---|---|---|---|
| analytical | Data analyst | 0.89 | 34 | 154 | 167 | ✅ | ✅ | ✅ | 4/5 |
| clinical | Registered nurse | 0.88 | 45 | 171 | 179 | ✅ | ✅ | ✅ | 4/5 |
| caring | Primary school teacher | 0.78 | 46 | 145 | 155 | ✅ | ✅ | ✅ | 5/5 |
| tech | Software engineer | 0.71 | 44 | 129 | 144 | ✅ | ✅ | ✅ | 5/5 |
| creative | Graphic designer | 0.83 | 47 | 175 | 205 | ✅ | ✅ | ✅ | 3/5 |
| professional | Corporate lawyer | 0.73 | 43 | 162 | 182 | ✅ | ✅ | ✅ | 5/5 |
| trades | Electrician | 0.82 | 33 | 281 | 401 | ✅ | ❌ | ✅ | 5/5 |
| business | Marketing manager | 0.81 | 39 | 214 | 250 | ✅ | ❌ | ✅ | 2/5 |

**Aggregate** — Stage-C varies 8/8, not-verbose 6/8, future-grounded 8/8; Stage-B concise 8/8, mean future-aware 4.1/5.

Pooled word-counts by turn kind:

- light: mean 55w, sd 7, range 43–69
- trivial: mean 43w, sd 9, range 25–55
- big: mean 180w, sd 66, range 115–401
- advice: mean 177w, sd 44, range 144–284
- medium: mean 149w, sd 30, range 117–213
- throwaway: mean 29w, sd 9, range 12–39
- closing: mean 38w, sd 8, range 27–47
