"""The review surface: `/sluice` in chat and `hermes sluice` on the command line share this."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Set

from . import applying, diffing, stage as stage_mod

HELP = (
    "Sluice reviews what the agent changed before it touches your real files.\n"
    "  /sluice            status\n"
    "  /sluice diff [path]   show the changes, numbered\n"
    "  /sluice apply all     apply everything shown\n"
    "  /sluice apply 1,3-5   apply only those numbered changes\n"
    "  /sluice apply src/a.py   apply every change in that file\n"
    "  /sluice apply 1,3 --discard-rest   apply those, drop the others\n"
    "  /sluice discard       throw the staged copy away\n"
    "  /sluice log           commands run and actions held as not contained"
)
MAX_CHARS = 3800
MAX_HUNK_LINES = 30


def _parse_selection(text: str, valid: Set[int], d: Optional[diffing.Diff] = None) -> Set[int]:
    chosen: Set[int] = set()
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        if d is not None and part in d.files:
            chosen.update(u.id for u in d.units if u.path == part)   # a file name selects all its changes
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"cannot read {part!r}; use numbers like 1,3-5, a changed file name, or all")
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        for n in range(lo, hi + 1):
            if n not in valid:
                raise ValueError(f"there is no change number {n}")
            chosen.add(n)
    return chosen


def _held(st: stage_mod.Stage) -> List[dict]:
    return [r for r in st.read_log() if r.get("held")]


def render_status(st: stage_mod.Stage, d: diffing.Diff) -> str:
    cmds = [r for r in st.read_log() if "cmd" in r]
    held = _held(st)
    if d.units:
        head = f"Sluice: {len(d.units)} changes in {len(d.files)} files, not yet in your workspace."
    else:
        head = "Sluice: no pending changes."
    lines = [head, f"Workspace: {st.root}", f"Commands run in the stage: {len(cmds)}"]
    if held:
        lines.append(f"Held as not contained: {len(held)} (see /sluice log)")
    if st.skipped:
        lines.append(f"Not copied into the stage: {len(st.skipped)} (large files or outside symlinks)")
    moved = stage_mod.drift(st)
    if moved:
        lines.append(f"Changed in your workspace since the stage was taken: {len(moved)} file(s). "
                     "Applying a change to one of those may conflict.")
    if d.units:
        lines.append("Run /sluice diff to review.")
    return "\n".join(lines)


def render_diff(st: stage_mod.Stage, d: diffing.Diff, only: Optional[str] = None) -> str:
    if not d.units:
        return "Sluice: no pending changes."
    out: List[str] = [f"Sluice: {len(d.units)} changes in {len(d.files)} files (not applied yet)"]
    cut = False
    for path in d.files:
        if only and path != only:
            continue
        us = [u for u in d.units if u.path == path]
        out.append(f"\n{path}")
        for u in us:
            if u.kind == "hunk":
                out.append(f"[{u.id}] {u.summary}  +{u.added} -{u.removed}")
                body = u.body if only else u.body[:MAX_HUNK_LINES]
                out += ["    " + b for b in body]
                if len(u.body) > len(body):
                    out.append(f"    ... {len(u.body) - len(body)} more lines")
            else:
                out.append(f"[{u.id}] {u.kind.upper()}: {u.summary}")
                if u.kind == "create" and u.body:
                    shown = u.body if only else u.body[:8]
                    out += ["    " + b for b in shown]
                    if len(u.body) > len(shown):
                        out.append(f"    ... {len(u.body) - len(shown)} more lines")
        if sum(len(x) + 1 for x in out) > MAX_CHARS and not only:
            cut = True
            break
    if cut:
        out.append("\n(output cut for chat; use /sluice diff <path> for one file)")
    held = _held(st)
    if held:
        out.append(f"\n{len(held)} action(s) were held as NOT CONTAINED; see /sluice log.")
    out.append("\nApply with /sluice apply all, or /sluice apply 1,3-5. Reject with /sluice discard.")
    st.last_rev = d.rev
    st.save()
    return "\n".join(out)


def render_log(st: stage_mod.Stage) -> str:
    rows = st.read_log()
    if not rows:
        return "Sluice: nothing logged yet."
    out = ["Sluice log (commands run in the stage, and actions held as NOT CONTAINED):"]
    for r in rows[-40:]:
        if r.get("held"):
            out.append(f"  HELD  [{r.get('category')}] {r.get('detail')}  ({r.get('tool')})")
        else:
            out.append(f"  exit {r.get('exit')!s:>3}  {str(r.get('cmd'))[:160]}")
    return "\n".join(out)


def handle(raw: str = "") -> str:
    words = (raw or "").strip().split(None, 1)
    sub = words[0].lower() if words else "status"
    rest = words[1].strip() if len(words) > 1 else ""
    if sub in ("help", "-h", "--help"):
        return HELP
    st = stage_mod.current()
    if st is None:
        return ("Sluice: no staged work yet. It starts when the agent runs its first command with "
                "`terminal.backend: sluice`.")
    if sub == "discard":
        stage_mod.discard(st)
        return "Sluice: discarded the staged copy. Your workspace was not changed."
    if sub == "log":
        return render_log(st)
    d = diffing.compute(st)
    if sub in ("status", ""):
        return render_status(st, d)
    if sub == "diff":
        only = rest or None
        if only and only not in d.files:
            return f"Sluice: no changes in {only}."
        return render_diff(st, d, only)
    if sub == "apply":
        discard_rest = "--discard-rest" in rest
        sel_text = rest.replace("--discard-rest", "").strip()
        if not sel_text:
            return "Sluice: say what to apply: /sluice apply all, or /sluice apply 1,3-5"
        if not d.units:
            return "Sluice: no pending changes."
        if not st.last_rev:
            return "Sluice: review first. Run /sluice diff, then apply what you saw."
        if st.last_rev != d.rev:
            return ("Sluice: the staged changes moved since you last looked. Run /sluice diff again, "
                    "then apply what you see.")
        try:
            chosen = {u.id for u in d.units} if sel_text.lower() == "all" else \
                _parse_selection(sel_text, {u.id for u in d.units}, d)
        except ValueError as exc:
            return f"Sluice: {exc}"
        with stage_mod.locked(st):
            if not os.path.isdir(st.root):
                return f"Sluice: the workspace {st.root} no longer exists. Nothing was applied."
            res = applying.apply(st, d, chosen)
        lines = [f"Sluice: applied {len(res.applied)} change(s) to {len(res.files_changed)} file(s)."]
        for path, why in res.conflicts:
            lines.append(f"CONFLICT {path}: {why}. Left unchanged.")
        if discard_rest:
            stage_mod.discard(st)
            lines.append("Discarded the rest.")
        elif res.conflicts:
            lines.append("Conflicted files are still staged. Run /sluice diff to review them again.")
        return "\n".join(lines)
    return "Sluice: unknown command.\n" + HELP


def cli_setup(parser) -> None:
    parser.add_argument("args", nargs="*", help="status | diff [path] | apply <all|1,3-5> | discard | log")


def cli_handler(args) -> None:
    print(handle(" ".join(getattr(args, "args", []) or [])))
