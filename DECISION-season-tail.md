# Decision needed: what to publish for the tail of Summer 2026

**Status:** open, waiting on the owner. Nothing in this file has been acted on.
**Written:** 2026-09-17, against Actions run logs, not against the handoff.
**Scope:** one decision, three options, a recommendation, and one cheap fact
worth having before you choose.

The site currently publishes the **10 August** snapshot: 636 participants, of a
season that ran 20 July – 6 September. Since this branch, both pages say so in
those words rather than calling it a full-season archive. So nothing is
misleading anyone while this sits open — the cost of leaving it is that the
archive stops on 10 August, not that it lies.

---

## What actually happened, corrected

`HANDOFF.md` (2026-09-01) describes three failed runs and concludes that
publishing the tail needs **both** `min_rows` lowered **and** `--allow-shrink`.
Two more runs have happened since it was written, and they change that
conclusion. From the workflow logs:

| Run | Where it stopped | Numbers |
|---|---|---|
| Aug 10 | succeeded | **636 published — this is what the site still shows** |
| Aug 17 | `export_site_data` | 636 → 459 (72%) |
| Aug 24 | `export_site_data` | 636 → 440 (69%) |
| Aug 31 | `fetch_listing` | 308 unique records vs. floor 400 |
| Sep 7 | `export_site_data` | 636 → **406** (64%) |
| Sep 14 | `export_site_data` | 636 → **406** (64%) |

Three things follow, and the first two contradict the handoff:

1. **`min_rows` is not blocking.** It fired once, on 31 August. Both September
   runs cleared the 400 floor and got all the way to the exporter. Lowering
   `min_rows` would change nothing today.
2. **Only the shrink guard is refusing.** So the override under discussion is
   one flag, `--allow-shrink`, not two — a materially smaller decision than the
   handoff describes.
3. **The listing is stable, not draining.** 406 on 7 September and 406 again on
   14 September: the same number twice, eleven days after the programme closed.
   The Aug 31 dip to 308 was transient.

## The fact worth having first

Point 3 raises a question nobody has answered: **what are those 406 rows?**

The handoff's model is "the season is ending, so participants are genuinely
leaving the listing". That model predicts a number still falling on 14
September. It was flat instead, a week after the programme ended, which the
model does not explain. Two possibilities, with very different consequences:

- **Summer leftovers.** The listing keeps ended restaurants rather than
  removing them, and 406 is roughly what stayed. Then publishing it replaces a
  636-row mid-season truth with a 406-row post-season one, and neither is "the
  full season".
- **A winter 2027 season starting to populate.** Then those rows are not srw26
  at all, `--allow-shrink` would publish *next* season's restaurants under
  *this* season's code and dates, and the srw26 archive would be destroyed by
  something that is not even the same programme.

**This costs one request to settle** and does not touch menus, Places, or
anything billed:

```bash
python src/fetch_listing.py            # one listing pull, 1 req/sec, no menus
python - <<'PY'
import json, collections, pathlib
# The season code is the S3 prefix in menuFileUrl, which is what
# config/season.json's `code` must match:
#   https://nyc-tourism-public.s3.amazonaws.com/srw26/menus/20975-BlueFin-menu.pdf
#                                               ^^^^^ index 3
d = json.loads(pathlib.Path("data/raw/listing/latest.json").read_text(encoding="utf-8"))
print(collections.Counter(
    (r.get("menuFileUrl") or "//x/no-menu").split("/")[3] for r in d["items"]))
PY
```

Run against the committed 10 August listing it prints
`{'srw26': 461, 'no-menu': 175}`, so that is the shape of a summer answer and
the baseline to compare against.

If the fresh pull is still overwhelmingly `srw26`, it is option A's world. If a
winter code appears, **do not pass `--allow-shrink` at all** — that is a season
changeover, and the README's 9-step runbook is the right procedure.

`fetch_listing.py` overwrites `data/raw/listing/latest.json`. That is safe
here: the dated snapshots beside it — `snapshot-2026-07-31.json`,
`-08-03.json`, `-08-10.json` — are tracked in git, so the summer pull is
preserved whatever the fresh one returns.

---

## The options

### A. Keep 10 August as the final published snapshot *(recommended)*

Change nothing about the data. The archive is the last snapshot taken while the
season was demonstrably running and fully crawled, and both pages now say
exactly that, with the date and the 27-day gap.

- **For:** the 636 rows are internally consistent — menus, prices, windows and
  grades all belong to one crawl of a live season. Costs nothing and risks
  nothing. Survives the "what are the 406 rows?" question either way.
- **Against:** restaurants that joined after 10 August never appear; the
  archive is 27 days short of the programme it describes.

### B. Publish the tail: one run with `--allow-shrink`

Run the refresh by hand (`workflow_dispatch`, or `/weekly-refresh` locally) and
pass `--allow-shrink` to the exporter.

- **For:** the published set becomes the set that finished the season.
- **Against — and this is the part that is easy to miss:** it does **not**
  just drop 230 rows.
  - The 636-row payload is replaced permanently. There is no second copy: the
    legacy file is a byte-identical duplicate of the same payload.
  - **Every surviving row is re-graded.** The rubric's window component is
    measured from `scoring_day()`, which clamps to `program_end` — so a
    post-season export is reproducible against other post-season exports, but
    not against a mid-season one. Measured today: window component mean
    **21.7 → 2.1**, rubric mean **35.3 → 33.1**. The ranking on the dashboard
    is not the ranking anyone saw during the season.
  - It disables a guard that has caught a real upstream failure before. Do it
    once, deliberately, with the number read first — never by putting the flag
    in the workflow.
- **Do not** also lower `min_rows`. It is not firing, and lowering a floor that
  is not blocking only removes cover for the next real collapse.

### C. Keep both: archive 10 August, publish the tail beside it

`docs/data/seasons/` and the registry already support more than one entry per
season file, and `switchSeason()` in `app.js` is written and dormant purely
because the registry has one entry.

- **For:** nothing is lost; the mid-season picture and the final set are both
  real and both interesting.
- **Against:** the most work of the three, and it needs a ruling on something
  currently undefined — two payloads for one `code`. Probably a second entry
  (`srw26-final`), which touches the registry contract, the switcher's labels,
  and `test_seasons_registry.py`. Not hard, but it is a design decision, not a
  flag.

---

## Recommendation

**A, unless the one-request check says the 406 rows are still srw26 and you
want the final set more than you want the mid-season one.** In that case B is
defensible — but read the shrink number in the run output before confirming,
and know that the grades move.

If the check turns up a winter code, none of the above applies: go to the
README's season changeover runbook, and leave the srw26 archive alone.

Whatever you choose, the roster (1,420 venues) is unaffected. It is the
year-round product; Restaurant Week is one nullable column on it, and that
column is now correctly written in the past tense.

---

## What this branch already did, so you are not deciding under pressure

- Neither page claims completeness it does not have. The dashboard names the
  as-of date and the 27-day gap; the roster says the programme ended.
- `docs/data/seasons.json` says `archived`, corrected through the pipeline
  (`export_site_data.py --registry-only`) with the payloads byte-identical.
- The Monday cron is **staged** paused on this branch — schedule commented out,
  `workflow_dispatch` kept — so the weekly failure stops without removing the
  ability to run the close-out by hand. It is not paused on GitHub; merging
  this branch is what would pause it.

None of that pre-empts the decision. All of it is reversible, and none of it
touches the 636 rows.
