"""Load the plugin directory as the package `sluice_plugin`, as the Hermes loader does, and give each
test its own HERMES_HOME so nothing touches a real ~/.hermes. Needs hermes-agent importable."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PACKAGE = "sluice_plugin"
_ROOT = Path(__file__).resolve().parents[1] / "sluice"


def _load():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(PACKAGE, _ROOT / "__init__.py",
                                                  submodule_search_locations=[str(_ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = mod
    spec.loader.exec_module(mod)
    return mod


_load()


@pytest.fixture(autouse=True)
def _isolated_hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    import hermes_constants

    monkeypatch.setattr(hermes_constants, "_PINNED_PROCESS_HERMES_HOME", None, raising=False)


@pytest.fixture
def ws(tmp_path):
    """A small real workspace."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("".join(f"line {i}\n" for i in range(1, 41)))
    (root / "README.md").write_text("# demo\n")
    (root / "notes.txt").write_text("keep\n")
    return root


@pytest.fixture
def mods():
    import importlib

    return {n: importlib.import_module(f"{PACKAGE}.{n}") for n in
            ("stage", "diffing", "applying", "review", "classify", "env")}
