# ccfix fixture corpus

Real pastes from the Claude Code console, one case per pair:

- `NAME.in.txt` - the raw clipboard, exactly as copied (`ccfix capture NAME` writes it)
- `NAME.out.txt` - the correct result, **written by hand**, no trailing newline

`test_ccfix.py` runs every pair through the real CLI.  An `.in` without its `.out` fails the suite
on purpose: a captured case isn't done until someone says what right looks like.  Never produce an
`.out` by running ccfix - that only proves the tool agrees with itself.

Optional first line of an `.in`: `# ccfix-args: cmd --width 120` to pin the mode or width that the
case was rendered at (the line is stripped before the paste is fed in).
