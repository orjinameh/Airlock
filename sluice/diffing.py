"""Compare a stage with its baseline and split the result into approvable units.

A unit is the smallest thing the user can approve or reject: one hunk of a modified text file,
or one whole file for created, deleted, renamed, binary, symlink and mode changes.
"""

from __future__ import annotations

import difflib
import hashlib
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .stage import Entry, Manifest, Stage, scan, sha256_file

MAX_TEXT_BYTES = 2 * 1024 * 1024
CONTEXT = 3


@dataclass
class Unit:
    id: int
    path: str
    kind: str              # hunk, create, delete, rename, replace, mode
    summary: str
    old_path: str = ""
    i1: int = 0
    i2: int = 0
    j1: int = 0
    j2: int = 0
    old_lines: List[str] = field(default_factory=list)
    new_lines: List[str] = field(default_factory=list)
    body: List[str] = field(default_factory=list)   # rendered diff lines
    added: int = 0
    removed: int = 0


@dataclass
class Diff:
    units: List[Unit]
    rev: str
    stage_manifest: Manifest

    @property
    def files(self) -> List[str]:
        seen: List[str] = []
        for u in self.units:
            if u.path not in seen:
                seen.append(u.path)
        return seen

    def by_id(self, uid: int) -> Optional[Unit]:
        for u in self.units:
            if u.id == uid:
                return u
        return None


def read_text(path: str) -> Optional[List[str]]:
    """Lines (with endings) if the file is text, else None."""
    try:
        if os.path.getsize(path) > MAX_TEXT_BYTES:
            return None
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\0" in raw:
        return None
    try:
        return raw.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def _render(a: List[str], b: List[str], group) -> List[str]:
    out: List[str] = []
    for tag, i1, i2, j1, j2 in group:
        if tag == "equal":
            out += [" " + x.rstrip("\n") for x in a[i1:i2]]
        else:
            if tag in ("replace", "delete"):
                out += ["-" + x.rstrip("\n") for x in a[i1:i2]]
            if tag in ("replace", "insert"):
                out += ["+" + x.rstrip("\n") for x in b[j1:j2]]
    return out


def _hunks(path: str, a: List[str], b: List[str], next_id: int) -> List[Unit]:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    units: List[Unit] = []
    for group in sm.get_grouped_opcodes(CONTEXT):
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        added = sum(j2_ - j1_ for t, _, _, j1_, j2_ in group if t in ("replace", "insert"))
        removed = sum(i2_ - i1_ for t, i1_, i2_, _, _ in group if t in ("replace", "delete"))
        units.append(Unit(
            id=next_id + len(units), path=path, kind="hunk",
            summary=f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@",
            i1=i1, i2=i2, j1=j1, j2=j2, old_lines=a[i1:i2], new_lines=b[j1:j2],
            body=_render(a, b, group), added=added, removed=removed,
        ))
    return units


def _same(a: Entry, b: Entry) -> bool:
    return a.kind == b.kind and a.sha == b.sha and a.target == b.target


def compute(st: Stage) -> Diff:
    base = st.manifest
    now = scan(st.stage_path)
    created = sorted(set(now) - set(base))
    deleted = sorted(set(base) - set(now))
    units: List[Unit] = []
    empty = hashlib.sha256(b"").hexdigest()

    renames: Dict[str, str] = {}   # new path -> old path
    by_sha: Dict[str, List[str]] = {}
    for p in deleted:
        e = base[p]
        if e.kind == "file" and e.sha != empty:
            by_sha.setdefault(e.sha, []).append(p)
    for p in created:
        e = now[p]
        if e.kind == "file" and by_sha.get(e.sha):
            renames[p] = by_sha[e.sha].pop(0)
    renamed_old = set(renames.values())

    def add(kind: str, path: str, summary: str, **kw) -> None:
        units.append(Unit(id=0, path=path, kind=kind, summary=summary, **kw))

    paths = sorted(set(created) | set(deleted) | {p for p in base if p in now})
    for p in paths:
        if p in renames:
            add("rename", p, f"renamed from {renames[p]}", old_path=renames[p])
            continue
        if p in renamed_old:
            continue
        if p in created:
            e = now[p]
            text = read_text(os.path.join(st.stage_path, p)) if e.kind == "file" else None
            if e.kind == "link":
                add("create", p, f"new symlink -> {e.target}")
            elif text is None:
                add("create", p, "new binary file")
            else:
                add("create", p, f"new file, {len(text)} lines", new_lines=text,
                    body=["+" + x.rstrip("\n") for x in text], added=len(text))
            continue
        if p in deleted:
            e = base[p]
            add("delete", p, "deleted file" if e.kind == "file" else "deleted symlink")
            continue
        b_e, s_e = base[p], now[p]
        if _same(b_e, s_e):
            if b_e.kind == "file" and b_e.mode != s_e.mode:
                add("mode", p, f"mode {b_e.mode:o} -> {s_e.mode:o}")
            continue
        if b_e.kind == "file" and s_e.kind == "file":
            a = read_text(os.path.join(st.base_path, p))
            b = read_text(os.path.join(st.stage_path, p))
            if a is None or b is None:
                add("replace", p, "binary or very large file changed")
            else:
                hs = _hunks(p, a, b, 0)
                if hs:
                    units.extend(hs)
            if b_e.mode != s_e.mode:
                add("mode", p, f"mode {b_e.mode:o} -> {s_e.mode:o}")
            continue
        add("replace", p, "type changed" if b_e.kind != s_e.kind else f"symlink now -> {s_e.target}")

    for i, u in enumerate(units, 1):
        u.id = i
    h = hashlib.sha1()
    for u in units:
        h.update(f"{u.kind}|{u.path}|{u.old_path}|{u.i1}:{u.i2}|".encode("utf-8", "surrogateescape"))
        h.update("".join(u.new_lines).encode("utf-8", "surrogateescape"))
        e = now.get(u.path)
        if e is not None:
            h.update(f"{e.sha}{e.target}{e.mode}".encode())
    return Diff(units=units, rev=h.hexdigest()[:8], stage_manifest=now)
