#!/usr/bin/env -S uv run --quiet --no-project --with pytest pytest
"""Tests for bin/ccfix, driving the real CLI via subprocess.

Every expected output is written by hand from the rendering rules, never
captured from ccfix.  The clipboard tests put a FAKE pbpaste/pbcopy on PATH
(backed by a temp file), so the suite never touches the real clipboard.

Run any of:
    ./test_ccfix.py
    ccfix test
"""

import os
import subprocess
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parent
SCRIPT = BIN / "ccfix"


def run(text: str, *args: str) -> str:
    """Tests with short lines pass --width to simulate a narrow terminal."""
    r = subprocess.run([str(SCRIPT), *args, "--stdin", "--print"], input=text,
                       capture_output=True, text=True, check=True)
    assert r.stdout.endswith("\n")
    return r.stdout[:-1]


# --- prose -------------------------------------------------------------------

TREVOR_SAMPLE = """\
  ▎ Mechanically, the app worked exactly as envisioned: over 400 prizes were delivered by email on
  ▎ Saturday afternoon, and players found it easy to use.  Where it fell short was uptake, which
  ▎ I'll get to below.
"""


def test_quoted_paragraph_joins_to_one_line():
    # Stripped lengths: 94, 92, 18 -> width 94.
    # 94+1+len("Saturday") > 94 and 92+1+len("I'll") = 96 > 94: both are wraps.
    assert run(TREVOR_SAMPLE) == (
        "Mechanically, the app worked exactly as envisioned: over 400 prizes were delivered "
        "by email on Saturday afternoon, and players found it easy to use.  Where it fell "
        "short was uptake, which I'll get to below."
    )


def test_quoted_paragraphs_keep_blank_line_between():
    text = ("  ▎ The first paragraph is long enough to\n"   # 39
            "  ▎ wrap once.\n"
            "  ▎\n"
            "  ▎ Second one.\n")
    assert run(text, "--width", "39") == "The first paragraph is long enough to wrap once.\n\nSecond one."


def test_wrap_after_period_gets_two_spaces():
    text = ("  ▎ This line ends a sentence right here.\n"   # 40 = width
            "  ▎ Then more.\n")
    assert run(text, "--width", "40") == "This line ends a sentence right here.  Then more."


def test_short_line_is_a_real_newline():
    # "Hi." (3) + 1 + len("This") = 8 <= 40: it would have fit, so the break is real.
    text = ("  ▎ Hi.\n"
            "  ▎ This line is the widest one in here ok.\n")
    assert run(text, "--width", "40") == "Hi.\nThis line is the widest one in here ok."


def test_cc_bullet_and_indent_stripped():
    text = ("⏺ Done.  The build is green and the tests\n"   # 43 incl. bullet
            "  pass.\n")
    assert run(text, "--width", "43") == "Done.  The build is green and the tests pass."


def test_list_items_not_joined():
    text = ("  - first item that runs right to the edge\n"
            "  - second\n")
    assert run(text, "prose", "--width", "41") == "- first item that runs right to the edge\n- second"


def test_wrapped_list_item_continuation_joins():
    text = ("  - first item that runs right to the edge\n"   # 41
            "    of the screen.\n"
            "  - second\n")
    assert run(text, "prose", "--width", "41") == "- first item that runs right to the edge of the screen.\n- second"


# --- commands ----------------------------------------------------------------

def test_wrapped_command_joins_with_inferred_width():
    # 66 chars, over the 60 floor, so the inferred width is 66 and the break is a wrap.
    text = ("  git-safe log --oneline --graph --decorate --since=2026-09-01 --all\n"
            "  --author=trevor\n")
    assert run(text) == ("git-safe log --oneline --graph --decorate --since=2026-09-01 --all "
                         "--author=trevor")


def test_width_env_var():
    # 49 + 1 + len("--all") = 55 <= floor 60: a real newline unless the width is 49.
    text = ("  git-safe log --oneline --graph --since=2026-09-01\n"
            "  --all\n")
    assert run(text) == "git-safe log --oneline --graph --since=2026-09-01\n--all"
    r = subprocess.run([str(SCRIPT), "--stdin", "--print"], input=text, capture_output=True,
                       text=True, check=True, env={**os.environ, "CCFIX_WIDTH": "49"})
    assert r.stdout == "git-safe log --oneline --graph --since=2026-09-01 --all\n"


def test_separate_short_commands_stay_separate():
    assert run("  ls -la\n  pwd\n") == "ls -la\npwd"


def test_backslash_continuation_preserved():
    text = ("  curl -sSL https://example.com/a/long/path \\\n"
            "    -o out.json\n")
    assert run(text, "--width", "44") == "curl -sSL https://example.com/a/long/path \\\n  -o out.json"


def test_curly_quotes_straightened_in_cmd():
    assert run("  echo “hi” ‘there’\n", "cmd") == "echo \"hi\" 'there'"


def test_long_token_split_mid_token_is_glued():
    # The URL line is the widest (40) and has no space: the renderer cut it mid-token.
    text = ("  open https://x.io/\n"
            "  https://example.com/aaaaaaaaaaaaaaaaaaaa\n"
            "  bbbb\n")
    assert run(text, "cmd", "--width", "40") == "open https://x.io/ https://example.com/aaaaaaaaaaaaaaaaaaaabbbb"


def test_no_trailing_blank_lines():
    assert run("  ls\n\n\n") == "ls"


# --- clipboard + undo ----------------------------------------------------------

@pytest.fixture
def fakeclip(tmp_path):
    clip = tmp_path / "clip"
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    (fakebin / "pbpaste").write_text(f"#!/bin/sh\ncat '{clip}'\n")
    (fakebin / "pbcopy").write_text(f"#!/bin/sh\ncat > '{clip}'\n")
    for f in fakebin.iterdir():
        f.chmod(0o755)
    env = {**os.environ, "PATH": f"{fakebin}:{os.environ['PATH']}",
           "CCFIX_CACHE": str(tmp_path / "cache")}
    return clip, env


def test_clipboard_fixed_in_place_and_undo_restores(fakeclip):
    clip, env = fakeclip
    clip.write_text("  ls -la\n  pwd\n")
    subprocess.run([str(SCRIPT)], env=env, check=True, capture_output=True)
    assert clip.read_text() == "ls -la\npwd"
    subprocess.run([str(SCRIPT), "undo"], env=env, check=True, capture_output=True)
    assert clip.read_text() == "  ls -la\n  pwd\n"


def test_undo_with_nothing_saved_fails(fakeclip):
    _, env = fakeclip
    r = subprocess.run([str(SCRIPT), "undo"], env=env, capture_output=True, text=True)
    assert r.returncode == 1
