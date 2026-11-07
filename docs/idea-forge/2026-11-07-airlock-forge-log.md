# Idea Forge Log: Hermes Agent Plugin Hackathon (Nous Research)

Intermediate artifact. The deliverable is the brief (`2026-11-07-airlock-brief.md`) and the Sonnet 5.5 build prompt (`2026-11-07-airlock-sonnet-prompt.md`).

Run settings: model `claude-sonnet-5-5` (below the kit's `top` tier, builder's choice). Risk appetite `novel-wow`. Skills (from earlier in this session): Solidity + Foundry, TypeScript / Next.js / React. Capacity: a Claude Code Sonnet 5.5 session driving the kit's build pipeline, plus the builder.

## Research limit (read this first)

The Hermes developer guide, user guide, marketplace pages, GitHub docs and news pages were all blocked from this session ("not on the allowlist"). I could not read the plugin API, the manifest format, the hook list, the catalog PR requirements or the existing plugins. So:
- Buildability verdicts below are **provisional**, built only from the announcement text.
- **No catalog dedupe was possible.** Creativity scores are weak evidence.
- The first task in the build prompt is a day-one spike that verifies the API and checks the catalog for duplicates, with a fallback ladder if it fails.

Known only from the announcement and search-result titles: plugins can change the model Hermes runs on, where it stores memory, where it runs commands, which messaging apps it works in, and what Hermes Desktop shows. Existing plugins include phone control and photo to printable 3D model. Doc pages exist titled "Build a Hermes Plugin", "Model Provider Plugins", "Plugins" and "Built-in Plugins". A news headline cites 4 official and 96 community plugins in the catalog (unverified).

## Step 1 inputs

1. Event: Hermes Agent Plugin Hackathon, 7 days, $20,000+ prizes. Due **5PM EST, Nov 11, 2026** (22:00 UTC, 11PM in Lagos).
2. Tracks: none, every plugin kind is eligible.
3. Capacity: Claude Code Sonnet 5.5 session + builder.
4. Skills: as above (plugin language not verified; likely Python for backends, TypeScript for Desktop UI).
5. Risk: novel-wow.
6. Prior art: not retrievable beyond the two examples above.

## Published criteria and rubric adaptation

Judges score **usefulness, reliability, polish and creativity** and favor plugins that do more than a prompt or a skill. Entry requires: a PR adding the plugin to the Hermes plugin catalog, a demo video on X under 90 seconds tagging @NousResearch, and the Typeform submission (the form can be sent as soon as the PR is open; catalog checks run once a maintainer starts them).

| Kit axis | Remapped to | Weight |
|---|---|:-:|
| Intrinsic buildability | Reachable in under 5 days with no blocker (includes reliability) | 35 |
| Demo WOW + story | 90 second demo and polish | 25 |
| Theme + track fit | Usefulness, and does more than a prompt or skill | 20 |
| Novelty | Creativity | 20 |

## Step 2: Diverge (full field, unranked)

Seeds: the five extension surfaces in the announcement (model, memory, command execution, messaging, Desktop UI) crossed with common agent pain points (safety, cost, trust, recovery, reach).

| ID | Candidate: problem, solution, demo moment |
|---|---|
| P1 | **Airlock.** Agents change files and run commands with no review. An execution backend that runs work in an isolated copy, then shows a diff to approve by hunk. Demo: messy refactor, approve 9 of 12 hunks from chat. |
| P2 | **Time Machine.** Per-turn snapshots with rewind. Demo: agent wrecks a repo, one command restores. |
| P3 | **Seatbelt.** Policy and approval engine over messaging. Demo: risky call blocked, approved from phone. |
| P4 | **Secrets broker.** Credentials injected at execution, never in model context. Demo: prompt injection tries to exfiltrate a key and gets nothing. |
| P5 | **Injection firewall.** Quarantines untrusted web or email content. Demo: malicious page blocked. |
| P6 | **Flight Recorder.** Record runs, replay against new prompts, assert behavior. Demo: behavior diff across 10 tasks. |
| P7 | **Git-backed memory.** Every memory write is a commit, with revert and branches. Demo: revert a wrong memory. |
| P8 | **Memory provenance.** Memories carry source, confidence and expiry. Demo: "why do you believe this?" cites the source. |
| P9 | **Cost router.** Route each turn to the cheapest capable model. Demo: bill drop. |
| P10 | **Offline failover.** Switch to a local model when the network drops. Demo: pull Wi-Fi, agent continues. |
| P11 | **Mission Control.** Desktop panel for tool calls, costs, approvals. |
| P12 | **LoRa mesh gateway.** Off-grid messaging. |
| P13 | **SMS gateway via Twilio.** |
| P14 | **WhatsApp gateway.** |
| P15 | **Voice gateway.** Local speech in and out. |
| P16 | **Email gateway.** Hermes over IMAP and SMTP. |
| P17 | **Teach by demonstration.** Record the user, generate a skill. |
| P18 | **Budget governor.** Spend caps per session. |
| P19 | **Gmail and Calendar connectors.** |
| P20 | **Daily standup digest.** Summary of agent activity. |
| P21 | **Browser inspection bridge.** DevTools-level page data. |
| P22 | **Document pipeline.** PDFs to structured data. |
| P23 | **Memory spaces.** Isolated work and personal memory. |
| P24 | **Remote ephemeral cloud terminal.** Run commands on a rented box. |

### Bolder-pass (8 most generic rewritten, both versions kept)

| ID | From | Bolder rewrite |
|---|---|---|
| B3 | P3 | Score every tool call for blast radius (reversible or not); prompt only on the risky ones, approval over messaging. |
| B9 | P9 | Router that shadow-runs the cheap model on 5% of turns and reports the measured quality loss. |
| B11 | P11 | Run timeline you can scrub like video, with state diffs per step. |
| B15 | P15 | Voice gateway that speaks diffs and confirms risky actions aloud. |
| B16 | P16 | Email gateway where the agent drafts and sends only after you reply "ok". |
| B18 | P18 | Budget governor that downshifts the model mid-task instead of stopping. |
| B20 | P20 | Hash-chained, tamper-evident receipts of every agent action. |
| B21 | P21 | Browser bridge that returns page diffs, not full snapshots, to save tokens. |

## Step 3a: Buildability gate (knockouts, never scored)

| ID | Why out |
|---|---|
| P12 | Needs LoRa hardware the builder does not have. |
| P13 | Needs a paid Twilio account and number. |
| P14 | Needs WhatsApp Business approval, a third-party gate. |
| P19 | Needs OAuth app verification for Gmail and Calendar. |
| P24 | Needs a rented cloud account and balance for the demo. |

Low-scored rather than knocked out (unknown API or heavy lift, not external blockers): P2, P6, P9, P10, P11, P17.

## Step 3b: Weighted score

Creativity is the weakest column because the catalog could not be read.

| Rank | ID | Candidate | Build | Demo+polish | Useful, beyond a skill | Creativity | Score |
|---|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | P1 | Airlock: sandbox-first execution backend with diff and apply | 3 | 5 | 5 | 4 | 410 |
| 2 | B3 | Blast-radius seatbelt: score every call, prompt only the risky | 3 | 4 | 5 | 4 | 385 |
| 3 | P7 | Git-backed memory with revert and branches | 4 | 4 | 3 | 4 | 380 |
| 4 | P8 | Memory provenance: why do you believe this | 4 | 4 | 4 | 3 | 380 |
| 5 | P4 | Secrets broker: model never sees credentials | 3 | 4 | 5 | 3 | 365 |
| 6 | B16 | Email gateway with approve by reply | 4 | 4 | 3 | 3 | 360 |
| 7 | P5 | Injection firewall for untrusted tool output | 3 | 5 | 4 | 2 | 350 |
| 8 | P10 | Offline failover provider with local model | 3 | 5 | 4 | 2 | 350 |
| 9 | B11 | Scrubbable run timeline | 3 | 5 | 3 | 3 | 350 |
| 10 | P2 | Time Machine: per-turn snapshot and rewind backend | 3 | 4 | 4 | 3 | 345 |
| 11 | P6 | Flight Recorder: record, replay, regression tests for agents | 3 | 3 | 4 | 4 | 340 |
| 12 | P3 | Seatbelt: policy and approval engine over messaging | 4 | 3 | 4 | 2 | 335 |
| 13 | P23 | Memory spaces with isolation | 4 | 3 | 3 | 3 | 335 |
| 14 | B20 | Hash-chained action receipts | 4 | 3 | 3 | 3 | 335 |
| 15 | B9 | Self-testing router with shadow runs | 2 | 4 | 4 | 4 | 330 |
| 16 | B15 | Voice gateway with spoken diffs | 3 | 4 | 3 | 3 | 325 |
| 17 | B21 | Browser bridge that returns page diffs | 3 | 3 | 4 | 3 | 320 |
| 18 | P16 | Email gateway | 4 | 3 | 3 | 2 | 315 |
| 19 | B18 | Budget governor with mid-task downshift | 4 | 3 | 3 | 2 | 315 |
| 20 | P17 | Teach by demonstration, skill generator | 2 | 4 | 4 | 3 | 310 |
| 21 | P11 | Mission Control desktop panel | 3 | 4 | 3 | 2 | 305 |
| 22 | P15 | Voice gateway, local speech | 3 | 4 | 3 | 2 | 305 |
| 23 | P20 | Daily standup digest | 5 | 2 | 2 | 1 | 285 |
| 24 | P21 | Browser inspection bridge | 3 | 3 | 3 | 2 | 280 |
| 25 | P18 | Budget governor | 4 | 2 | 3 | 1 | 270 |
| 26 | P9 | Cost router provider | 2 | 3 | 4 | 2 | 265 |
| 27 | P22 | Document to structured data pipeline | 4 | 2 | 2 | 1 | 250 |


## Step 3c: Judge's-eye head-to-head (top 3)

Prior art used is from general knowledge, not verified this run: editor checkpoint features in coding assistants, git auto-commit tools, container sandboxes, policy and approval prompts in agent frameworks, memory services such as mem0.

| Candidate | vs strongest prior art | Verdict |
|---|---|---|
| P1 Airlock | vs coding-assistant checkpoints and container sandboxes. Wins on **does more than a prompt or skill**: it replaces where commands run, an official plugin surface. Wins on **demo**: approve by hunk from a chat message in 20 seconds. Wins on **usefulness**: review before changes, not undo after. Ties on creativity (checkpoints exist for editors, not for a messaging-first general agent). No clear loss found. | Advances |
| B3 Blast-radius seatbelt | vs approval prompts in existing frameworks. Edge: scoring by reversibility. Loses on demo: a prompt dialog is less visual. Weakly depends on hook coverage. | Runner-up, and folded into Airlock as the irreversible-action gate |
| P7 Git-backed memory | vs memory services. Wins on creativity, loses on usefulness (a nicety, not a pain point) and on the "does more than a skill" test. | Third |

## Step 3d: Pressure-test the top 3 for hidden blockers

**P1 Airlock**
- Unknown plugin API: whether an execution-backend plugin kind exists and can wrap the local backend (the announcement says plugins can change "where it runs commands", which suggests yes). Unverified. Day-0 spike.
- File tools: if Hermes file edits bypass the command backend, Airlock must also intercept them. Unverified. Day-0 spike.
- Containment honesty: a copied workspace contains file changes only. Package installs, writes outside the workspace, network writes and `git push` are not contained. Resolution: classify these as irreversible and block or prompt, and say so on screen. This is a scope limit, not a blocker.
- Environment: Hermes install and a model key for the demo; builder-controlled.
- Platform: use Python standard library and git only; builder OS to be confirmed.
- PR and catalog checks: format unknown. Open the PR early, since checks wait on a maintainer.
- Verdict: no uncontrollable blocker visible, but Build is 3, not 4, because the API is unread.

**B3** depends on hook coverage across tool calls, unverified.

**P7** depends on the memory backend plugin API, unverified, and is the least useful.

## Step 3e: Sensitivity and fallback ladder

Airlock leads by 25 points over B3 and 30 over P7 and P8, so ranking is stable on these weights. But every score rests on an unread API. Fallback ladder if the Day-0 spike fails or the catalog already holds an equivalent:
1. **Airlock** (execution backend).
2. **Memory provenance** (P8) if only a memory backend kind is usable.
3. **Blast-radius seatbelt** (B3) if only hooks are usable.

## Step 4: Commit

Winner: **P1 Airlock**. See `2026-11-07-airlock-brief.md`.
