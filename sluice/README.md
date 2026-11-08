# Sluice

**An airlock for agent changes.** A Hermes execution backend that runs the agent's commands and file
edits in a staged copy of your workspace, then lets you approve or reject the result hunk by hunk. Anything a
copy cannot contain is held for your approval and labelled **NOT CONTAINED**.

Agents edit files and run commands directly on your machine, and you find out what changed after it happened.
Sluice flips that: the real workspace is untouched until you apply a reviewed diff.

```
You:    clean up and refactor this repo
Agent:  Done. Work ran in Sluice: 14 files changed, 3 actions held as not contained.
You:    /sluice diff
        ... numbered hunks per file ...
You:    /sluice apply 1-9,11 --discard-rest
Sluice: applied 10 change(s) to 8 file(s). Discarded the rest.
```

## Install

Requires Hermes 0.22.6 or newer, Linux or macOS.

```bash
hermes plugins install sluice
hermes plugins enable sluice
hermes config set terminal.cwd /path/to/your/project
hermes config set terminal.backend sluice
```

Set `terminal.cwd` to a project directory. Sluice refuses to stage your home directory or `/`.

## Use

Ask the agent to work as usual. Then, in chat or in a terminal (`hermes sluice ...`):

| Command | What it does |
|---|---|
| `/sluice` | status: pending changes, commands run, held actions, workspace drift |
| `/sluice diff [path]` | numbered changes, per file and hunk |
| `/sluice apply all` | apply everything shown |
| `/sluice apply 1,3-5` | apply only those numbered changes |
| `/sluice apply src/a.py` | apply every change in one file |
| `/sluice apply 1,3 --discard-rest` | apply those, drop the others |
| `/sluice discard` | throw the staged copy away; the workspace was never touched |
| `/sluice log` | every command run in the stage with exit status, and every action held |

You must run `diff` before `apply`, and apply is refused if the staged changes moved since you looked, so you
never apply something you have not seen.

## What it does

* **Isolated run.** The workspace is copied (honoring `.gitignore`, so `.env` and build output stay out) to
  `~/.hermes/plugin-data/sluice/`. Commands and the file tools (`read_file`, `write_file`, `patch`,
  `search_files`) all run in the copy. The model keeps seeing your real paths; Sluice rewrites them.
  `.git` is copied too, so `git status`, `git diff` and `git commit` work in the stage and never touch your real history.
* **Hunk review.** Edits to text files are split into hunks. Created, deleted, renamed, binary, symlink and mode
  changes are each one unit. Select by number, range or file name.
* **Safe apply.** Per file, all or nothing, written atomically. A file you changed yourself after the stage was
  taken is a conflict and is never overwritten. If your edit was elsewhere in the file the hunk still lands.
  A path that would leave the workspace through a symlink is refused. A failed write is reported and retryable.
* **Irreversibility gate.** Before each tool call, Sluice reads the command. `git push`, package installs,
  network writes, deploys and publishes, `curl | sh`, `sudo`, and writes or deletes outside the workspace are sent
  to Hermes's own approval prompt with a plain NOT CONTAINED message. In unattended runs the prompt fails
  closed, as Hermes intends. Held actions are logged and shown in `/sluice` and `/sluice log`.

## What it does not do

Sluice is **not an operating system sandbox**. Commands still run on your machine as you.

* The copy contains file changes inside the workspace only. If you approve an install, a push or an outside write, it really happens.
* The gate reads the command text. Python run through `execute_code`, or a command that builds its target path at run time, can write outside the workspace without being held.
* Empty directories are not tracked. Submodules are treated as plain directories.
* Files over 25 MB, and symlinks pointing outside the workspace, are not copied; they are listed in `/sluice`.
* The stage is a full copy (twice, with the baseline). Workspaces over 1 GB are refused; raise `max_workspace_mb`.

## Settings

`hermes config set plugins.entries.sluice.settings.<key> <value>`

| Key | Default | Meaning |
|---|---|---|
| `copy_git` | `true` | copy `.git` into the stage |
| `max_file_mb` | `25` | largest file copied |
| `max_workspace_mb` | `1024` | largest workspace staged |
| `allow_paths` | `[]` | outside paths that never need approval, e.g. `["/tmp"]` |

## Disclosure

* **Network:** none. The plugin makes no network calls and runs no background process.
* **Files read:** your workspace (to copy and compare it) and its `.gitignore`. It never reads `.env`, `auth.json` or other credential files.
* **Files written:** its own data under `<HERMES_HOME>/plugin-data/sluice/` (copy, baseline, command log), and, only when you run `apply`, the approved changes inside the workspace (including new symlinks). Stages untouched for 14 days are deleted.
* **Commands run:** the shell commands the agent issues, in the staged copy; and `git ls-files` to list workspace files.
* **Hooks:** `pre_tool_call`, to hold calls the copy cannot contain. It only holds; it never approves.
* **Not touched:** Hermes core. No monkey patching; public `register_*` APIs only.

## Reliability

`tests/` holds 119 tests, run against a real Hermes checkout: the real file tools and registry, and the real `hermes sluice` CLI.
They cover created, deleted, renamed, binary, symlink and mode changes; ignore rules with and without git;
symlink escapes; large directories; apply conflicts when the workspace changed meanwhile; failed writes; two
applies at once; CRLF and missing final newlines; odd file names; and a classifier corpus of commands that must and must not be held.

```bash
pip install pytest        # hermes-agent must be importable
python -m pytest tests -q
hermes plugins validate sluice
```

## Layout

```
sluice/plugin.yaml   manifest
sluice/__init__.py   provider, hook, /sluice and CLI registration
sluice/env.py        the environment: path rewriting into the stage
sluice/stage.py      copy, baseline, ignore rules, locking
sluice/diffing.py    changes and hunks
sluice/applying.py   conflict-safe apply
sluice/classify.py   irreversibility classifier
sluice/review.py     the /sluice surface
```

MIT licensed.
