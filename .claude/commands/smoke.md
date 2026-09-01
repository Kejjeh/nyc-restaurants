# Smoke check — run after ANY change, before saying you're done

```
python -m pytest -q tests/
python src/export_site_data.py --check --quiet
python src/export_venues.py --check --quiet
node --check docs/app.js
node --check docs/venues.js
git ls-files | grep -i '\.pdf$'   # MUST print nothing
```

All green + no PDFs = safe. Windows note: a `PermissionError ... pytest-current`
line AFTER "N passed" is temp-dir cleanup noise; trust the exit code.

If you changed docs/*.js: also bump the `?v=N` cache-buster on that script/css
tag in docs/index.html or docs/restaurant-week.html.
If you changed exporters or the DB schema: regenerate payloads
(`python src/build_venues.py --quiet && python src/resolve_venues.py &&
python src/export_venues.py --quiet` and/or `python src/export_site_data.py`)
and commit them, or CI's staleness guard will fail the PR.
