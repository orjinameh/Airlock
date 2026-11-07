# Submission pack

PR: https://github.com/NousResearch/hermes-agent/pull/150739
Repo: https://github.com/orjinameh/airlock
Deadline: 5 PM EST, Nov 11, 2026 (11 PM Lagos).

## 1. Demo setup (once)

```bash
bash demo/setup.sh                       # makes ~/demo-repo with a local remote, so git push is harmless
hermes config set terminal.cwd ~/demo-repo
hermes config set terminal.backend sluice
```

Run `bash demo/setup.sh` again before every take; it resets the demo.
Record at 1080p with a large terminal font (at least 18 pt) and a dark theme. Hide anything private (tokens, other tabs).

Check before recording: in `~/demo-repo`, `git status` is clean and `python3 -m pytest -q tests` shows 2 passed.

## 2. Demo script (target 80 seconds, hard limit 90)

Narrate over the recording or add captions. Keep the sentences short. Do 3 takes; use the best.

| Time | Shot | Say or caption |
|---|---|---|
| 0:00 to 0:06 | Title card: **Sluice**, "an airlock for your agent's changes". Cut to the Hermes chat. | "Agents change your files first. You find out after. Sluice flips that." |
| 0:06 to 0:18 | Type in Hermes: `Clean up and refactor this repo: remove duplicate and dead code, add docstrings, and add notes.md. Then run git push.` Let it work (speed up if slow). | "The agent works in a staged copy of the repo." |
| 0:18 to 0:28 | The approval prompt for `git push` appears with **NOT CONTAINED**. Pause on it, then deny. | "A push can't be undone, so Sluice holds it and says so." |
| 0:28 to 0:36 | Second terminal in `~/demo-repo`: run `git status`. It shows clean. | "The agent says it is done. My real repo: untouched." |
| 0:36 to 0:52 | In Hermes type `/sluice diff`. Scroll slowly through the numbered hunks. | "Every change, per file and hunk. I decide what lands." |
| 0:52 to 1:04 | Type `/sluice apply 1,2,4 --discard-rest` (use the numbers on your screen: approve some, skip at least one). Show the "applied N change(s)" and "Discarded the rest" lines. | "Approve some. Drop the rest." |
| 1:04 to 1:16 | Terminal: `git diff --stat`, then `python3 -m pytest -q tests`. | "The real repo has exactly what I approved, and the tests pass." |
| 1:16 to 1:24 | End card: **Sluice**, Hermes plugin, github.com/orjinameh/airlock, @NousResearch. | "Sluice. Review what your agent did before it touches your files." |

If the agent does not try `git push` on its own, send a second message in the same chat: `Now run git push origin main.` The held prompt is the point of shot 3.
If it asks to `pip install` something instead, that works too: it is held the same way.
Do not edit the video to hide anything. Honest framing wins: the on-screen NOT CONTAINED label is a feature.

## 3. X post

Post the video as a native upload (not a link), and tag @NousResearch. The text is under 280 characters (X counts each link as 23).

```
Agents edit your files first. You find out after.

Sluice, my @NousResearch Hermes plugin, flips it: the agent works in a staged copy, you review it hunk by hunk, and only what you approve lands.

PR: https://github.com/NousResearch/hermes-agent/pull/150739
Code: https://github.com/orjinameh/airlock
```

## 4. Typeform answers

I could not read the form's fields from outside, so these cover the usual ones. Paste what matches.

**Project name:** Sluice (the repo is named Airlock)

**One line:** A Hermes terminal backend that runs the agent's work in a staged copy of your workspace, so you review the diff hunk by hunk and apply only what you approve.

**PR link:** https://github.com/NousResearch/hermes-agent/pull/150739

**Demo video link:** (paste the X post link after you post)

**Repo link:** https://github.com/orjinameh/airlock

**What does it do? (short description)**
Sluice replaces where Hermes runs commands. The agent's shell commands and file tools (read_file, write_file, patch, search_files) run in a staged copy of the workspace, so the real files stay untouched. In chat or on the command line the user reads a numbered diff, applies everything, selected hunks or one file, or discards it. Calls a copy cannot contain (git push, package installs, network writes, deploys, writes outside the workspace) are sent to Hermes's own approval prompt and labelled NOT CONTAINED.

**Why is it useful?**
Agents change files and run commands directly on your machine, and you learn what changed after it happened. Sluice reviews before changes land instead of undoing after. It works from chat, so a person can supervise an agent without babysitting each step.

**Why is it more than a prompt or a skill?**
It is a terminal backend plugin: it changes where every command and file tool runs, adds a `pre_tool_call` hook, a `/sluice` slash command, a `hermes sluice` CLI command and a system prompt section. No prompt could make the real files wait for approval.

**How is it reliable?**
119 tests run against real Hermes code (the real file tools, registry and CLI): created, deleted, renamed, binary, symlink and mode changes; ignore rules with and without git; symlink escapes; large directories; apply conflicts when the real workspace changed meanwhile; failed writes; two applies at once. A file you edited yourself is never overwritten. `hermes plugins validate` passes on the pinned commit.

**What is polished or creative?**
The model keeps seeing your real paths while everything runs in the copy. Apply is hunk level, by number, range or file name, and refused unless you have just looked at the diff. The gate says plainly what a copy cannot contain, and the README states the limit: it is not an OS sandbox.

**Tech used:** Python standard library and git, Hermes terminal environment provider API, `pre_tool_call` hook, slash and CLI commands.

**Honest limits:** Commands still run on the host. The gate reads command text, so a command that builds its path at run time can get past it. Tested on Linux, not on macOS.

**Team:** Peter Stephen (solo). Built with Claude.

**X handle, email, Discord name:** fill in yours.
