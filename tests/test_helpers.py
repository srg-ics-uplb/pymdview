"""Tests for small helpers and for keeping docs in sync with the code."""

import os
import re
from pathlib import Path

from pymdview import shortcuts
from pymdview.util import js_str, pretty_path

ROOT = Path(__file__).resolve().parent.parent


def test_js_str_escapes():
    assert js_str('a"b\\c\nd') == '"a\\"b\\\\c\\nd"'


def test_pretty_path(monkeypatch):
    monkeypatch.setenv("HOME", "/home/u")
    assert pretty_path("/home/u") == "~"
    assert pretty_path("/home/u/docs") == "~" + os.sep + "docs"
    assert pretty_path("/home/user2/docs") == "/home/user2/docs"  # not a prefix match
    assert pretty_path(None) is None


def test_detailed_name():
    assert shortcuts.detailed_name("open") == "win.open"
    assert shortcuts.detailed_name("app.quit") == "app.quit"


def test_every_shortcut_is_documented_in_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [label for _n, _k, label in shortcuts.SHORTCUTS if label not in readme]
    assert not missing, f"Add these to the README shortcut table: {missing}"


def test_version_is_semver():
    import pymdview

    assert re.fullmatch(r"\d+\.\d+\.\d+", pymdview.VERSION)


def test_changelog_mentions_current_version():
    import pymdview

    assert f"[{pymdview.VERSION}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
