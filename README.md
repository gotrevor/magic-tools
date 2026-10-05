# magic-tools 🧙‍♂️

My useful tools.  Clone it and put the repo on your `PATH`; each tool is a single
[uv](https://docs.astral.sh/uv/) script, so there is no install step.

```sh
git clone https://github.com/gotrevor/magic-tools.git
export PATH="$PWD/magic-tools:$PATH"
```

| Tool | What it does |
|---|---|
| `ccfix` | Un-mangles text copied out of the Claude Code console (quote bars, bullets, indent, hard wraps) and fixes the clipboard in place.  `ccfix --help` for details. |
| `tickler` | Dated reminders as a TOML file: snooze / done / add from the CLI, a JSON export for a glanceable viewer, and "has X happened yet?" items whose check command a scheduled job runs.  `tickler --help` for details. |

Apache 2.0.
