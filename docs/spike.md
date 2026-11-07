# Day-0 spike: can Airlock be built as a Hermes plugin?

Date: Nov 7, 2026. Sources: the Hermes developer guide (plugins, terminal environment plugins, catalog submission), plus the hermes-agent source at commit a8b0bc1 and the official hermes-official-plugins repo (bubblewrap plugin), both read directly. Nothing below is from memory.

## Verdict

GO. Fallback ladder not needed. One forced change: the name "airlock" is already taken in the catalog (see Q5).

## The five questions

**1. Is there an execution backend plugin kind, and can it wrap the local backend?**
Yes. Kind is `backend`. A plugin subclasses `TerminalEnvironmentProvider` (`agent.terminal_env_provider`) and calls `ctx.register_terminal_environment_provider(provider)` inside `register(ctx)`. Users select it with `hermes plugins enable <name>` then `hermes config set terminal.backend <name>`. The backend name must match `[a-z0-9_]` and cannot be a built-in like `local`, so a plugin cannot replace the local backend. It can wrap it: `create_environment()` may return a subclass of `LocalEnvironment` (this is how the official bubblewrap plugin works). Airlock will do that, with `is_remote = False` and `is_container = False`, which keeps Hermes dangerous-command approval prompts switched on (`skip_container_guards` defaults to `is_container`).

**2. Do file tools go through the backend or bypass it?**
They go through it when the environment sets `uses_host_filesystem = False` (default for everything except the built-in `LocalEnvironment`, which sets True). Then `read_file`, `write_file`, `patch` and `search_files` all call the environment's `execute()`. Core has a test that proves it (`tests/tools/test_file_tools_confined_backend.py`) and it shows the exact pattern Airlock needs: the model uses one path (the "view", here the real workspace path), the environment rewrites it to another real directory (here the staged copy) inside `execute()`. So the agent believes it edits the real project while every byte lands in the copy.

**3. Manifest, entry point, testing?**
`plugin.yaml` with `name`, `version`, `description`, `kind: backend`, `manifest_version: 2`, `requires_hermes`, `platforms`, `config_schema`, `capabilities`. Entry point is `__init__.py` exposing `register(ctx)`. Tests: plain pytest (the bubblewrap plugin loads itself as a package and points `HERMES_HOME` at a temp dir), plus `hermes plugins doctor <path>` and `hermes plugins validate <path> --install-deps`, which is the catalog CI gate. I installed real Hermes in the sandbox, so both commands run here.
Other surfaces I confirmed in source, all public: `ctx.register_command(name, handler)` for `/slash` commands, `ctx.register_cli_command` for `hermes <name> ...`, `ctx.register_tool(...)`, `ctx.register_hook(...)`, `ctx.register_system_prompt_section(...)`. The `pre_tool_call` hook can return `{"action": "block", "message": ...}` or `{"action": "approve", "message": ...}`, and "approve" sends any tool call to Hermes's own human approval gate. That is the clean way to hold irreversible actions without bypassing approvals (catalog rule 12).

**4. What does the catalog PR require?**
The plugin lives in its own public repo. The PR to `NousResearch/hermes-agent` adds exactly one file: `plugin-catalog/<name>.yaml` with `repo`, `subdir`, a full 40 character `sha`, quoted `version`, `requires_hermes`, `description` (including a disclosure of network, file, shell and process behavior), `maintainer`, `tier: community`, `category`, `capabilities`, `image`, `screenshots`. CI clones the repo at the pinned SHA and runs `hermes plugins validate --install-deps`. A maintainer then reviews and merges. Rules that bite us: exact SHA pin (so our repo must be pushed first), no core overrides or monkey patching, declared capabilities must equal what `register()` does, no self updating code, approvals respected, risky behavior disclosed, no compiled files.
Consequence for deliveries: the PR pack is one YAML file, and the SHA comes from the commit you push to your airlock repo.

**5. Does an equivalent plugin already exist?**
No equivalent, but one name clash. I read all 1,065 catalog entries by name and read the closest ones:
- `airlock` (otsoa-dubief): a prompt injection guardrail built on hooks. Different product, same name. We must not submit under `airlock`.
- `bubblewrap`, `singularity`, `cloudflare-sandbox`, `hermes-wslc-sandbox`: sandbox backends. None stage a copy, show hunks, or apply back.
- `undo-effects`, `git-autosave`: snapshot then restore after the fact. They run on the real files.
- `git-review`, `hermes-session-diff` (Desktop panes), `diff-review` (lint a diff): look at changes after they already landed.
None combines an isolated copy, hunk review and a reversibility gate. White space holds.

## Decisions taken from this

- **Name:** `sluice` for the plugin id, backend name and catalog file. Display line: "Sluice, an airlock for agent changes". The repo can stay named airlock. Tell me if you want another name; it must be unique and `[a-z0-9_]`.
- **Honest limit:** the staged copy contains file changes only. Commands still execute on the host, so an `rm ~/x` or `pip install` is not physically prevented by the copy. Containment of those comes from the classifier in `pre_tool_call` plus Hermes's approval gate. We say "not contained" on screen and in the README and never claim otherwise.

## Build plan (delivery B)

1. `SluiceProvider(TerminalEnvironmentProvider)` and `SluiceEnvironment(LocalEnvironment)` with `uses_host_filesystem = False` and the view to stage path mapping from the core test.
2. Stage creation: copy the workspace honoring `.gitignore` and a default ignore list, record a baseline manifest (path, mode, sha256, symlink target). Python standard library and `git` only.
3. Diff engine: baseline vs stage per file (created, modified, deleted, renamed by content match, binary, symlink), unified hunks with stable ids.
4. Apply engine: all, selected hunks, or discard, with a three way check against the real workspace so a file that changed meanwhile is reported as a conflict, never overwritten.
5. Surfaces: `/sluice` slash command (works in chat), `hermes sluice` CLI, one command log (command, exit status) per stage.
6. Irreversibility classifier in `pre_tool_call`: network writes, `git push`, package installs, writes outside the workspace, deletes beyond it. Returns `approve` or `block` with a plain "not contained" label.

## What I cannot test here

- A live Hermes session with a real model, a messaging gateway, or the chat approval flow. I can run real Hermes code (file tools, registry, `plugins validate`), not an LLM turn. Your machine is where the demo runs.
- macOS and Windows behavior. Linux only in the sandbox. The code is standard library plus git, so I expect macOS to work; Windows is out of scope.
