# Sluice (Airlock)

A Hermes execution backend that lets you review what your agent did before it touches your real files.

The agent runs its commands and file edits in a staged copy of your workspace. You then read the result
hunk by hunk and apply only what you approve. Anything a copy cannot contain (network writes, `git push`,
package installs, writes outside the workspace) is held for your approval and labelled **NOT CONTAINED**.

Status: working vertical slice (isolated run, diff, apply, hold). Full README and reliability notes land with the final build.

## Install for development

The plugin lives in `sluice/`. Copy it into your Hermes home and switch the backend on:

```bash
cp -r sluice ~/.hermes/plugins/sluice
hermes plugins enable sluice
hermes config set terminal.cwd /path/to/your/project
hermes config set terminal.backend sluice
```

Set `terminal.cwd` to a project directory. Sluice refuses to stage your home directory or `/`.

## Use

Ask the agent to work as usual. Then, in chat or on the command line:

| Command | What it does |
|---|---|
| `/sluice` | status |
| `/sluice diff [path]` | numbered changes, per file and hunk |
| `/sluice apply all` | apply everything shown |
| `/sluice apply 1,3-5` | apply only those changes |
| `/sluice apply 1,3 --discard-rest` | apply those and drop the others |
| `/sluice discard` | throw the staged copy away, workspace untouched |
| `/sluice log` | commands run, and actions held as not contained |

`hermes sluice <same arguments>` does the same from a terminal. You must run `diff` before `apply`, and apply
is refused if the staged changes moved since you looked.

## What it does

* Copies the workspace honoring `.gitignore` (so `.env` and build output are not copied) into
  `~/.hermes/plugin-data/sluice/`. The model keeps seeing your real paths; Sluice rewrites them to the copy.
* File tools (`read_file`, `write_file`, `patch`, `search_files`) go through the same backend, so they also land in the copy.
* Created, deleted, renamed, binary, symlink and mode changes are each one approvable unit. Edits to text files are split into hunks.
* Apply is per file and all or nothing. A file you edited yourself after the stage was taken is reported as a
  conflict and never overwritten. If your edit was elsewhere in the file, the hunk still lands.
* Symlinks that point outside the workspace are not copied. Files over 25 MB are not copied and are listed.

## What it does not do

It is not an operating system sandbox. Commands still run on your machine as you.

* The copy contains file changes inside the workspace only.
* Commands that install packages, write over the network, `git push`, or write outside the workspace really happen
  if you approve them. Sluice detects them by reading the command and asks first through Hermes's own approval prompt.
  A command that builds its target path at run time can get past that reading.
* Empty directories are not tracked.

## Test

```bash
pip install pytest   # plus a hermes-agent checkout importable
python -m pytest tests -q
hermes plugins validate sluice
```
