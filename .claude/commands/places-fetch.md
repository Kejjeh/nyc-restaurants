# Google Places fetch — SPENDS REAL MONEY. Follow exactly; skip no step.

Key: env `GOOGLE_PLACES_KEY` or local `config/secrets.py` (gitignored).
NEVER write the key into any file, log, or commit. Commit the CACHE, not the key.

```
python src/resolve_venues.py --dry-run     # 1. what it would send + cost. No key, no network.
python src/resolve_venues.py --fetch --limit 30   # 2. spend ~a dollar; READ the 30 answers
python src/resolve_venues.py --fetch       # 3. the rest. Resumable — cached slugs are skipped, an interrupted run costs nothing twice.
python src/resolve_venues.py               # 4. apply cache to roster
python src/export_venues.py --quiet        # 5. re-export
```

Then the smoke check (/smoke). Stop and ask the user between steps 1→2 and 2→3:
they are the spend decisions, not yours.
