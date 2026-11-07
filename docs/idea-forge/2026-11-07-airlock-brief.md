# Idea Forge Brief: Airlock, an execution backend that lets you review what your agent did before it touches your real files

Working title "Airlock" is provisional. This is the single source of truth for the architect. It fixes what and why, not how. Full field, gate, scores and pressure-test: `2026-11-07-airlock-forge-log.md`.

**Research limit:** the Hermes developer guide and catalog were not readable from the session that wrote this brief. Plugin API facts below are NOT verified. The first build task is a spike that verifies them.

## Event and constraints

- **Hackathon:** Hermes Agent Plugin Hackathon (Nous Research), 7 days, $20,000+ in cash: 1st $10,000, 2nd $5,000, 3rd $2,500, 4th $1,500, 5th $1,000, five runners up with merch and credits.
- **Due:** 5PM EST, Nov 11, 2026 (22:00 UTC, 11PM Lagos). Inert calendar fact for idea-forge; the architect scopes to it.
- **Entry (all three required):** a pull request adding the plugin to the Hermes plugin catalog (path: developer guide at hermes-agent.nousresearch.com/docs/developer-guide/plugins); a demo video on X under 90 seconds tagging @NousResearch; both links submitted in the Typeform at form.typeform.com/to/FwJLvOln. The form can be sent as soon as the PR is open. Catalog checks run only when a maintainer starts them, and entries are reviewed every few days.
- **Judging (published):** usefulness, reliability, polish, creativity. Judges favor plugins that do more than a prompt or a skill. The entry is the plugin itself.
- **Team:** Claude Code Sonnet 5.5 session + builder. Risk: novel-wow.

## Problem

Agents edit files and run commands directly on your machine. You find out what changed after it already happened, and undoing a bad run is manual. People either babysit every step or accept the risk.

## Solution (one line)

A Hermes execution-backend plugin that runs the agent's file changes and commands in an isolated copy of your workspace, then presents the result as a reviewable diff you approve or reject hunk by hunk, with anything that cannot be contained (network writes, installs, writes outside the workspace) flagged as irreversible and held for explicit approval.

## Must-have demo features

1. **Airlock backend:** the agent's commands and file writes run in an isolated copy of the workspace (respecting ignore rules); every command and its exit status is logged; the real workspace is untouched until apply.
2. **Review and apply:** a diff presented per file and hunk, in whatever surface Hermes supports (chat message and CLI at minimum); commands to apply all, apply selected hunks, or discard; clean handling of created, deleted, renamed and binary files.
3. **Irreversibility gate:** classify commands and tool calls that cannot be contained (network writes, `git push`, package installs, writes outside the workspace, deletes beyond the workspace) and hold them for explicit approval, with a plain "not contained" label.
4. **Reliability suite and submission pack:** automated tests for the scenarios above (plus symlinks, large directories, and apply conflicts when the real workspace changed meanwhile), a README, the catalog PR, and a 60 to 90 second demo script.

## Target

No tracks. Scored on usefulness, reliability, polish, creativity. This brief targets all four: review-before-change is a real pain point, the test suite is the reliability evidence, the hunk-by-hunk review is the polish, and "execution backend with a reviewable diff" is the creative angle.

## Why it wins

Honest limit first: the catalog and existing plugins could not be read, so no duplicate check was done. Prior art from general knowledge, unverified here: checkpoint features in coding assistants, container sandboxes, approval prompts in agent frameworks. White space (to confirm in the spike): none of those that I know of combine an execution backend, hunk-level review and a reversibility gate for a messaging-first general agent. Edge on the published criteria: on **beyond a prompt or skill**, it replaces where commands run; on **usefulness**, it reviews before changes land rather than undoing after. If the spike finds an equivalent plugin already in the catalog, switch to the fallback ladder in the log.

## Demo money shot

In chat, ask Hermes to clean up and refactor a messy repo. It replies that the work ran in the Airlock: 14 files changed, 3 actions held as irreversible. You open the diff, approve 9 of 12 hunks, discard the rest, and show the real repo containing exactly the approved changes. About 20 seconds inside a 60 to 90 second video that also shows the blocked irreversible action.

## Out of scope (explicit)

- Container or VM isolation, network sandboxing, Windows support (unless the builder is on Windows), multi-user sharing, a Desktop UI panel (stretch only), memory or model plugins.
- Any claim that it makes unsafe commands safe. It contains workspace file changes only and says so.

## Feasibility notes (primitives, not design)

Known from the announcement only: plugins can change the model Hermes runs on, where it stores memory, where it runs commands, which messaging apps it works in and what Hermes Desktop shows. All plugin API details are unverified.

**Day-0 spike (first task, before any planning):** read the developer guide at hermes-agent.nousresearch.com/docs/developer-guide/plugins and the Model Provider Plugins page as the structural template, and the user-guide Plugins page. If pages cannot be fetched, ask the builder to paste them. Answer in a one-page note, committed to the repo:
1. Is there an execution or terminal backend plugin kind, and can it wrap the local backend?
2. Do file edit and write tools go through that backend, or do they bypass it?
3. What is the manifest and entry-point format, and how are plugins tested?
4. What does the catalog PR require (path, metadata, checks)?
5. Does an equivalent plugin already exist in the marketplace?
If 1 and 2 fail, use the fallback ladder (memory provenance, then blast-radius seatbelt).

## Architect kickoff block

See `2026-11-07-airlock-sonnet-prompt.md` (paste into a fresh Sonnet 5.5 Claude Code session).
