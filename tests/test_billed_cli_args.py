"""Every script that can bill Google Places rejects arguments it does not know.

`python src/fetch_google_ratings.py --dry-run` once made a real, billed Text
Search: the script read `sys.argv` by hand, had no `--dry-run`, and ignored the
flag it did not recognise. The fix is argparse everywhere a key can be spent,
so an unknown or mistyped flag exits 2 BEFORE the key is read or a request is
built, plus a real `--dry-run` that needs neither.

Each test wires the key loader, the HTTP helper and `urlopen` to fail loudly,
so a regression shows up as "tried to read the key" rather than as a bill.
"""
import json
import urllib.request

import pytest

import fetch_google_ratings as g
import places_cli
import refresh
import resolve_venues


class Tripwire(AssertionError):
    pass


@pytest.fixture
def no_spend(monkeypatch):
    """Any key read or HTTP call in the billed scripts raises and is recorded."""
    calls = []

    def trip(what):
        def _f(*a, **k):
            calls.append(what)
            raise Tripwire(f"{what} was called")
        return _f

    monkeypatch.delenv("GOOGLE_PLACES_KEY", raising=False)
    for mod in (g, resolve_venues, places_cli):
        monkeypatch.setattr(mod, "api_key", trip("api_key"))
        monkeypatch.setattr(mod, "get", trip("get"))
    monkeypatch.setattr(urllib.request, "urlopen", trip("urlopen"))
    return calls


# ---- unknown arguments ----------------------------------------------------

@pytest.mark.parametrize("main, argv", [
    (g.main, ["--dry-runn"]),
    (g.main, ["--bogus"]),
    (g.main, ["--shard", "4/4"]),          # would silently select nothing
    (g.main, ["--shard", "x"]),
    (resolve_venues.main, ["--fetch", "--bogus"]),
    (resolve_venues.main, ["--fetchh"]),
    (resolve_venues.main, ["--limit", "ten"]),
    (places_cli.main, ["add", "Le Bernardin", "155 W 51st St", "--bogus"]),
    (places_cli.main, ["add", "Le Bernardin", "hint", "surplus"]),
    (places_cli.main, ["list", "--bogus"]),
    (refresh.main, ["--dryrun"]),
])
def test_an_unknown_argument_exits_nonzero_before_any_key_or_network(
        main, argv, no_spend, monkeypatch, capsys):
    runs = []
    monkeypatch.setattr(refresh.subprocess, "run", lambda *a, **k: runs.append(a))
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 2
    assert no_spend == [] and runs == []
    assert "usage:" in capsys.readouterr().err


def test_valid_invocations_parse_to_the_old_defaults():
    a = g.parse_args([])
    assert (a.shard, a.force, a.report, a.dry_run) == ((0, 1), False, False, False)
    assert g.parse_args(["--shard", "1/4", "--force"]).shard == (1, 4)
    r = resolve_venues.parse_args(["--fetch", "--limit", "30"])
    assert (r.fetch, r.limit, r.force, r.dry_run) == (True, 30, False, False)
    assert places_cli.parse_args([]).cmd is None          # bare = list
    p = places_cli.parse_args(["add", "Le Bernardin", "155 W 51st St"])
    assert (p.name, p.hint, p.dry_run) == ("Le Bernardin", "155 W 51st St", False)
    assert refresh.parse_args(["--force-menus"]).force_menus is True


# ---- dry runs ------------------------------------------------------------

def test_ratings_dry_run_prints_count_and_cost_without_key_or_network(
        no_spend, monkeypatch, tmp_path, capsys):
    out = tmp_path / "google"
    out.mkdir()
    (out / "cached.json").write_text("{}", encoding="utf-8")
    overrides = tmp_path / "ids.json"
    overrides.write_text(json.dumps({"place_ids": {"pinned": "ChIJpin"}}),
                         encoding="utf-8")
    monkeypatch.setattr(g, "OUT", out)
    monkeypatch.setattr(g, "OVERRIDES", overrides)
    monkeypatch.setattr(g, "targets", lambda: [
        ("cached", "Cached", "Soho", "Manhattan", 40.7, -74.0),
        ("new-one", "New One", "Chelsea", "Manhattan", 40.7, -74.0),
        ("pinned", "Pinned", "Tribeca", "Manhattan", 40.7, -74.0),
    ])
    g.main(["--dry-run"])
    text = capsys.readouterr().out
    assert "2 would be fetched" in text
    assert "1 by Text Search, 1 by Details" in text
    assert "estimated cost: $0.06" in text
    # The preview shows the very string the billed run would send.
    assert g.query_for("New One", "Chelsea", "Manhattan") in text
    assert no_spend == []
    assert sorted(p.name for p in out.iterdir()) == ["cached.json"]


def test_ratings_dry_run_with_force_counts_cached_rows_too(
        no_spend, monkeypatch, tmp_path, capsys):
    out = tmp_path / "google"
    out.mkdir()
    (out / "a.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(g, "OUT", out)
    monkeypatch.setattr(g, "OVERRIDES", tmp_path / "absent.json")
    monkeypatch.setattr(g, "targets", lambda: [
        ("a", "A", None, None, None, None), ("b", "B", None, None, None, None)])
    g.main(["--dry-run", "--force"])
    assert "2 would be fetched" in capsys.readouterr().out
    assert no_spend == []


def test_resolve_venues_dry_run_spends_nothing(no_spend, capsys):
    resolve_venues.main(["--dry-run", "--limit", "3"])
    text = capsys.readouterr().out
    assert "venues would be looked up" in text and "estimated cost: $" in text
    assert no_spend == []


def test_places_add_dry_run_spends_and_writes_nothing(no_spend, monkeypatch, capsys):
    monkeypatch.setattr(places_cli, "load_places", lambda: {"places": []})
    monkeypatch.setattr(places_cli, "roster_slugs", lambda: set())
    monkeypatch.setattr(places_cli, "save_places", lambda *a, **k: pytest.fail("wrote"))
    monkeypatch.setattr(places_cli, "cache_record", lambda *a, **k: pytest.fail("wrote"))
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("prompted"))
    places_cli.main(["add", "Le Bernardin", "155 W 51st St", "--dry-run"])
    text = capsys.readouterr().out
    assert "1 Text Search would be sent" in text
    assert places_cli.query_for("Le Bernardin", "155 W 51st St") in text
    assert "estimated cost: $0.032" in text
    assert no_spend == []


def test_refresh_dry_run_runs_only_the_ratings_preview(no_spend, monkeypatch):
    runs = []
    monkeypatch.setattr(refresh, "run", lambda *a: runs.append(a))
    refresh.main(["--dry-run"])
    assert runs == [("fetch_google_ratings.py", "--dry-run")]
    assert no_spend == []
