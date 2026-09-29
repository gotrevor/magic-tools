# magic-tools 🧙‍♂️

My useful tools - small, general-purpose CLIs, one executable per tool at the repo root.

- Each tool is a self-contained uv-shebang script (`#!/usr/bin/env -S uv run --quiet python3`); run it directly, no install step.
- Each tool has a pytest suite, `test_<tool>.py`, that drives the real CLI via subprocess; `<tool> test` runs it.  Fixtures live in `tests/<tool>/`.
- Expected outputs in fixtures are written by hand, never captured from the tool.
- This repo is public: nothing private, nothing from an employer, in code, fixtures or commit messages.
