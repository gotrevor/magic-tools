#!/usr/bin/env -S uv run --quiet --no-project --with pytest --with tomlkit pytest
"""Tests for bin/tickler, driving the real CLI via subprocess.

Every run gets a temp items.toml, a temp export dir and a pinned clock
($TICKLER_TODAY = 2026-10-05), so expected dates below are worked out by hand
from that fixed "today", not captured from the tool.

Run any of:
    ./test_tickler.py
    tickler test
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import tomlkit

TOOL = Path(__file__).resolve().with_name("tickler")
TODAY = "2026-10-05"

SEED = '''
base = "/base"

[[item]]
id = "overdue"
due = 2026-10-02
title = "Overdue thing"
detail = "notes/overdue.md"

[[item]]
id = "future"
due = 2026-10-20
title = "Future thing"

[[item]]
id = "silent-yes"
due = 2026-10-04
title = "Check that will fire"
check = "exit 0"

[[item]]
id = "silent-no"
due = 2026-10-05
title = "Check that will not fire yet"
check = "exit 1"
recheck_days = 3

[[item]]
id = "silent-broken"
due = 2026-10-01
title = "Check that is broken"
check = "exit 7"

[[item]]
id = "silent-later"
due = 2026-10-09
title = "Check not due yet"
check = "exit 0"
'''


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "items.toml"
    data.write_text(SEED)
    e = dict(os.environ, TICKLER_FILE=str(data), TICKLER_EXPORT=str(tmp_path / "out"),
             TICKLER_TODAY=TODAY)
    return e, data, tmp_path / "out" / "items.json"


def run(e, *args):
    r = subprocess.run([str(TOOL), *args], env=e, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def item(data, item_id):
    return next(i for i in tomlkit.parse(data.read_text())["item"] if i["id"] == item_id)


def test_list_shows_only_due_plain_items(env):
    e, _, _ = env
    out = run(e, "list")
    assert "overdue" in out and "3d over" in out          # 10-05 minus 10-02
    for hidden in ("future", "silent-yes", "silent-no", "silent-later"):
        assert hidden not in out
    assert "silent-broken" not in out                     # not broken until a check says so


def test_list_all_shows_everything(env):
    e, _, _ = env
    out = run(e, "list", "--all")
    for i in ("overdue", "future", "silent-yes", "silent-no", "silent-broken", "silent-later"):
        assert i in out
    assert "in 15d" in out                                # 10-20 minus 10-05


def test_snooze_default_moves_one_day_from_today_when_overdue(env):
    e, data, _ = env
    run(e, "snooze", "overdue")
    assert str(item(data, "overdue")["due"]) == "2026-10-06"
    assert item(data, "overdue")["log"][-1] == "2026-10-05 snoozed +1d"


def test_snooze_days_from_future_due(env):
    e, data, _ = env
    run(e, "snooze", "future", "2")
    assert str(item(data, "future")["due"]) == "2026-10-22"


def test_snooze_to_date(env):
    e, data, _ = env
    run(e, "snooze", "overdue", "2026-11-01")
    assert str(item(data, "overdue")["due"]) == "2026-11-01"


def test_check_semantics(env):
    e, data, export = env
    out = run(e, "check")
    assert "fired   silent-yes" in out
    assert "waiting silent-no -> 2026-10-08" in out       # 10-05 + recheck_days 3
    assert "BROKEN  silent-broken exit 7" in out
    assert "silent-later" not in out                      # due 10-09, not run yet
    assert item(data, "silent-yes")["fired"] is True
    assert item(data, "silent-broken")["broken"] is True
    listed = run(e, "list")
    assert "silent-yes" in listed and "silent-broken" in listed and "silent-no" not in listed
    ids = [r["id"] for r in json.loads(export.read_text())["items"]]
    assert ids == ["silent-broken", "overdue", "silent-yes", "future"]


def test_export_shape(env):
    e, _, export = env
    run(e, "export")
    payload = json.loads(export.read_text())
    assert payload["cli"] == str(TOOL)
    assert payload["generated"] == TODAY
    rows = {r["id"]: r for r in payload["items"]}
    assert set(rows) == {"overdue", "future"}             # silent items stay out until fired
    assert rows["overdue"]["path"] == "/base/notes/overdue.md"
    assert rows["future"]["path"].endswith("items.toml")  # no detail -> open the data file


def test_done_archives(env):
    e, data, export = env
    run(e, "done", "overdue")
    ids = [i["id"] for i in tomlkit.parse(data.read_text())["item"]]
    assert "overdue" not in ids and len(ids) == 5
    archived = tomlkit.parse(data.with_name("done.toml").read_text())["item"]
    assert archived[0]["id"] == "overdue" and archived[0]["log"][-1] == "2026-10-05 done"
    assert "overdue" not in export.read_text()


def test_add(env):
    e, data, _ = env
    run(e, "add", "new-one", "2026-10-05", "A new thing", "--owner", "agent")
    assert item(data, "new-one")["owner"] == "agent"
    assert "new-one" in run(e, "list") and "🤖" in run(e, "list")


def test_relative_detail_defaults_to_data_dir(env):
    e, data, export = env
    data.write_text(SEED.replace('base = "/base"', ""))
    run(e, "export")
    row = next(r for r in json.loads(export.read_text())["items"] if r["id"] == "overdue")
    assert row["path"] == str(data.parent / "notes/overdue.md")


def test_unknown_id_fails(env):
    e, _, _ = env
    r = subprocess.run([str(TOOL), "snooze", "nope"], env=e, capture_output=True, text=True)
    assert r.returncode != 0 and "no item 'nope'" in r.stderr
