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


def test_bullet_first_line_is_not_a_midline_fragment():
    # The ⏺ bullet sits at column 0 but stands in for CC's indent, so the
    # short "Run this:" line is a whole line, not a partial selection.
    assert run("⏺ Run this:\n  ls -la\n") == "Run this:\nls -la"


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


def test_flush_backslash_line_above_indented_continuation_stays_split():
    # A flush line ending in a backslash is a whole command, not a fragment.
    assert run("curl -sS \\\n    -o out.json\n") == "curl -sS \\\n    -o out.json"


def test_curly_quotes_straightened_in_cmd():
    assert run("  echo “hi” ‘there’\n", "cmd") == "echo \"hi\" 'there'"


def test_long_token_split_mid_token_is_glued():
    # The URL line is the widest (40) and has no space: the renderer cut it mid-token.
    text = ("  open https://x.io/\n"
            "  https://example.com/aaaaaaaaaaaaaaaaaaaa\n"
            "  bbbb\n")
    assert run(text, "cmd", "--width", "40") == "open https://x.io/ https://example.com/aaaaaaaaaaaaaaaaaaaabbbb"


def test_url_wrapped_at_query_mark_is_glued():
    # Stripped lengths 31, 8; at width 35, 31+1+8 = 40 > 35 is a wrap.  The line
    # ends in a URL's `?`, so no space goes in.
    text = ("  see https://example.com/search?\n"
            "  q=lean+4\n")
    assert run(text, "cmd", "--width", "35") == "see https://example.com/search?q=lean+4"


def test_path_split_before_slash_at_margin_is_glued():
    # Line 1 is 30 = width.  Its last token `/tmp/abc` (8) + `/def/ghij/klmnop/qrstuv` (23)
    # = 31 > 30: no line could hold that token, so the renderer split it and no space goes in.
    text = ("  cp -r /aaaaaaaaaaaaaa /tmp/abc\n"
            "  /def/ghij/klmnop/qrstuv\n")
    assert run(text, "cmd", "--width", "30") == "cp -r /aaaaaaaaaaaaaa /tmp/abc/def/ghij/klmnop/qrstuv"


def test_two_paths_word_wrapped_keep_their_space():
    # Line 1 is 22, width 30: 22+1+len("/dst/file.txt") = 36 > 30 is a wrap, but
    # `/src/a.txt` (10) + `/dst/file.txt` (13) = 23 fits a line, so it was a word-wrap.
    text = ("  cp --preserve /src/a.txt\n"
            "  /dst/file.txt\n")
    assert run(text, "cmd", "--width", "30") == "cp --preserve /src/a.txt /dst/file.txt"


def test_short_line_before_long_token_line_keeps_its_space():
    # 9+1+31 > 30 is a wrap, and `/tmp` + the 31-char token can't share a line, but
    # "run: /tmp" stops well short of the margin, so the renderer did not cut a token there.
    text = ("  run: /tmp\n"
            "  /aaaaaaaaaa/bbbbbbbbbb/cccccccc\n")
    assert run(text, "cmd", "--width", "30") == "run: /tmp /aaaaaaaaaa/bbbbbbbbbb/cccccccc"


def test_path_ending_in_slash_in_prose_keeps_its_space():
    # `src/` has no host, so it is not a URL: a wrap after it is an ordinary space.
    text = ("  ▎ The tool lives in the directory src/\n"   # 39
            "  ▎ under the repo root.\n")
    assert run(text, "--width", "39") == "The tool lives in the directory src/ under the repo root."


def test_no_trailing_blank_lines():
    assert run("  ls\n\n\n") == "ls"


# --- real-paste corpus (tests/ccfix/*.in.txt + hand-written *.out.txt) ---------------

FIXTURES = BIN / "tests" / "ccfix"
CASES = sorted(p.name[: -len(".in.txt")] for p in FIXTURES.glob("*.in.txt"))


@pytest.mark.parametrize("name", CASES)
def test_fixture(name):
    src = (FIXTURES / f"{name}.in.txt").read_text()
    expected = FIXTURES / f"{name}.out.txt"
    assert expected.exists(), f"write {expected.name} by hand (see tests/ccfix/README.md)"
    args: list[str] = []
    first, _, rest = src.partition("\n")
    if first.startswith("# ccfix-args:"):
        args, src = first.split(":", 1)[1].split(), rest
    assert run(src, *args) == expected.read_text()


def test_corpus_is_not_empty():
    assert CASES, "the fixture corpus vanished"


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


def test_capture_saves_clipboard_as_fixture_input(fakeclip, tmp_path):
    clip, env = fakeclip
    clip.write_text("  ▎ raw paste\n")
    # Run a COPY of ccfix so capture writes into a temp tests/ccfix, not the real corpus.
    (tmp_path / "ccfix").write_bytes(SCRIPT.read_bytes())
    (tmp_path / "ccfix").chmod(0o755)
    r = subprocess.run([str(tmp_path / "ccfix"), "capture", "my-case"], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "tests" / "ccfix" / "my-case.in.txt").read_text() == "  ▎ raw paste\n"
    again = subprocess.run([str(tmp_path / "ccfix"), "capture", "my-case"], env=env,
                           capture_output=True, text=True)
    assert again.returncode == 1  # never clobbers an existing case


def test_capture_rejects_bad_name(fakeclip):
    _, env = fakeclip
    r = subprocess.run([str(SCRIPT), "capture", "../escape"], env=env, capture_output=True)
    assert r.returncode == 2
