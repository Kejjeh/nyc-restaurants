"""Loading the Places key shadowed the standard library, and hid its own errors.

`api_key()` in `src/fetch_google_ratings.py` was:

    sys.path.insert(0, str(ROOT / "config"))
    try:
        from secrets import GOOGLE_PLACES_KEY
        return GOOGLE_PLACES_KEY
    except Exception:
        raise SystemExit("No API key. Set GOOGLE_PLACES_KEY, or copy ...")

Two defects, and the loader is shared — `resolve_venues.py` and
`places_cli.py` both import this exact function, and both spend money.

**It shadowed `secrets`.** The insert put `config/` ahead of the standard
library on `sys.path` for the remainder of the process, and `secrets` is a
stdlib module (`token_urlsafe`, `compare_digest`). After one call, any later
`import secrets` anywhere in the process — ours, or a dependency's — would get
the key file. Nothing here imports it today, which is luck rather than design:
the symptom would appear far from the cause, and the insert also never got
removed.

**It reported every failure as "no key".** `except Exception` caught a
`SyntaxError` in secrets.py, a file that raises at import, and a file that
spells `GOOGLE_PLACES_KEY` wrong — and answered all three with advice to create
the file that already exists.

These tests use a real temporary file rather than mocks, because the defect was
in the import machinery itself and a mock would have reproduced neither half.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetch_google_ratings as g  # noqa: E402


@pytest.fixture(autouse=True)
def no_env_key(monkeypatch):
    """The env var short-circuits everything below it."""
    monkeypatch.delenv("GOOGLE_PLACES_KEY", raising=False)


def point_at(monkeypatch, tmp_path, body):
    f = tmp_path / "secrets.py"
    f.write_text(body, encoding="utf-8")
    monkeypatch.setattr(g, "SECRETS_FILE", f)
    return f


# ------------------------------------------------- the stdlib-shadowing half

def test_the_config_dir_is_not_put_on_sys_path(monkeypatch, tmp_path):
    before = list(sys.path)
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY = "k"\n')
    g.api_key()
    assert sys.path == before, "api_key() must not mutate sys.path"


def test_stdlib_secrets_still_resolves_to_the_stdlib(monkeypatch, tmp_path):
    """The actual consequence: after loading the key, `import secrets` must
    still be Python's."""
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY = "k"\n')
    g.api_key()
    sys.modules.pop("secrets", None)
    import secrets
    assert hasattr(secrets, "token_urlsafe"), (
        "config/secrets.py has been loaded in place of the standard library")


def test_the_key_file_is_not_registered_as_an_importable_module(monkeypatch, tmp_path):
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY = "k"\n')
    sys.modules.pop("secrets", None)
    g.api_key()
    assert "secrets" not in sys.modules or hasattr(
        sys.modules["secrets"], "token_urlsafe")


def test_the_source_no_longer_imports_a_module_named_secrets():
    """Parsed, not grepped: the docstring above quotes the old code verbatim,
    and a text match cannot tell the record of a defect from the defect."""
    import ast
    tree = ast.parse((ROOT / "src" / "fetch_google_ratings.py")
                     .read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "secrets", "line %d imports from secrets" % node.lineno
        if isinstance(node, ast.Import):
            assert all(a.name != "secrets" for a in node.names)


def test_nothing_inserts_the_config_dir_onto_sys_path():
    import ast
    tree = ast.parse((ROOT / "src" / "fetch_google_ratings.py")
                     .read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "insert"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "path"):
            raise AssertionError(f"sys.path.insert at line {node.lineno}")


# ------------------------------------------------------ the swallowed-error half

def test_a_missing_file_still_reads_as_no_key(monkeypatch, tmp_path):
    monkeypatch.setattr(g, "SECRETS_FILE", tmp_path / "nope.py")
    with pytest.raises(SystemExit) as e:
        g.api_key()
    assert "No API key" in str(e.value)


def test_a_broken_file_does_not_read_as_no_key(monkeypatch, tmp_path):
    """The defect: a syntax error advised you to create the file you had."""
    point_at(monkeypatch, tmp_path, "GOOGLE_PLACES_KEY = = =\n")
    with pytest.raises(SystemExit) as e:
        g.api_key()
    msg = str(e.value)
    assert "could not be loaded" in msg
    assert "SyntaxError" in msg
    assert "No API key" not in msg


def test_a_file_that_raises_says_so(monkeypatch, tmp_path):
    point_at(monkeypatch, tmp_path, 'raise RuntimeError("vault is locked")\n')
    with pytest.raises(SystemExit) as e:
        g.api_key()
    assert "RuntimeError" in str(e.value)
    assert "vault is locked" in str(e.value)


def test_a_misspelled_name_is_its_own_message(monkeypatch, tmp_path):
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY_ = "k"\n')
    with pytest.raises(SystemExit) as e:
        g.api_key()
    assert "missing or empty" in str(e.value)


def test_an_empty_key_is_not_a_key(monkeypatch, tmp_path):
    """config/secrets.example.py ships `GOOGLE_PLACES_KEY = ""`, so a copy that
    was never filled in is the likeliest shape of all."""
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY = ""\n')
    with pytest.raises(SystemExit) as e:
        g.api_key()
    assert "missing or empty" in str(e.value)


# -------------------------------------------------------------- the happy paths

def test_the_environment_wins_and_the_file_is_not_read(monkeypatch, tmp_path):
    point_at(monkeypatch, tmp_path, 'raise AssertionError("must not be read")\n')
    monkeypatch.setenv("GOOGLE_PLACES_KEY", "from-env")
    assert g.api_key() == "from-env"


def test_the_file_is_read_when_the_environment_is_empty(monkeypatch, tmp_path):
    point_at(monkeypatch, tmp_path, 'GOOGLE_PLACES_KEY = "from-file"\n')
    assert g.api_key() == "from-file"


def test_no_error_message_contains_the_key(monkeypatch, tmp_path):
    """A key reaching a traceback is a key reaching a CI log."""
    point_at(monkeypatch, tmp_path,
             'GOOGLE_PLACES_KEY = "AIzaSECRET"\nraise RuntimeError("boom")\n')
    with pytest.raises(SystemExit) as e:
        g.api_key()
    assert "AIzaSECRET" not in str(e.value)


def test_the_shared_loader_is_the_one_the_spenders_use():
    """resolve_venues and places_cli import this function, and both bill."""
    for mod in ("resolve_venues", "places_cli"):
        src = (ROOT / "src" / f"{mod}.py").read_text(encoding="utf-8")
        assert "from fetch_google_ratings import" in src
        assert "api_key" in src
