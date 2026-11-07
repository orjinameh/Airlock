"""Apply approved units from a stage to the real workspace.

Every file is all or nothing. A file that changed in the real workspace since the stage was
taken is reported as a conflict and left alone; nothing is ever overwritten blindly.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .diffing import Diff, Unit, read_text
from .stage import Entry, Stage, entry_for


@dataclass
class Result:
    applied: List[int] = field(default_factory=list)
    conflicts: List[Tuple[str, str]] = field(default_factory=list)   # (path, reason)
    files_changed: List[str] = field(default_factory=list)


class Conflict(Exception):
    pass


def _inside(root: str, path: str) -> bool:
    root = os.path.realpath(root)
    parent = os.path.realpath(os.path.dirname(path) or ".")
    return parent == root or parent.startswith(root + os.sep)


def _target(root: str, rel: str) -> str:
    if os.path.isabs(rel) or ".." in rel.split("/"):
        raise Conflict("unsafe path")
    full = os.path.join(root, rel)
    # Walk up to the nearest existing ancestor and make sure it resolves inside the workspace.
    anc = os.path.dirname(full)
    while not os.path.exists(anc) and anc != root:
        anc = os.path.dirname(anc)
    real_anc = os.path.realpath(anc)
    r = os.path.realpath(root)
    if not (real_anc == r or real_anc.startswith(r + os.sep)):
        raise Conflict("path leaves the workspace through a symlink")
    return full


def _atomic_write(dst: str, data: bytes, mode: Optional[int]) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dst), prefix=".sluice-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _copy_entry(src: str, dst: str, e: Entry) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if e.kind == "link":
        tmp = dst + ".sluice-link"
        if os.path.lexists(tmp):
            os.unlink(tmp)
        os.symlink(e.target, tmp)
        os.replace(tmp, dst)
    else:
        with open(src, "rb") as fh:
            _atomic_write(dst, fh.read(), e.mode)


def _prune_empty_parents(root: str, path: str) -> None:
    d = os.path.dirname(path)
    root = os.path.realpath(root)
    while os.path.realpath(d) != root and d.startswith(root):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)


def _apply_hunks(root: str, st: Stage, path: str, units: List[Unit]) -> None:
    real = _target(root, path)
    if not os.path.lexists(real):
        raise Conflict("file no longer exists in the workspace")
    if os.path.islink(real):
        raise Conflict("path is now a symlink in the workspace")
    lines = read_text(real)
    if lines is None:
        raise Conflict("file is no longer plain text in the workspace")
    cursor = 0
    offset = 0
    out = list(lines)
    for u in sorted(units, key=lambda x: x.i1):
        old, new = u.old_lines, u.new_lines
        want = u.i1 + offset
        pos = -1
        if not old:
            if out:
                raise Conflict("file changed in the workspace since the stage was taken")
            pos = 0
        else:
            n = len(old)
            if want >= cursor and out[want:want + n] == old:
                pos = want
            else:
                best = None
                for i in range(cursor, len(out) - n + 1):
                    if out[i:i + n] == old and (best is None or abs(i - want) < abs(best - want)):
                        best = i
                if best is None:
                    raise Conflict(f"context for {u.summary} changed in the workspace")
                pos = best
        out[pos:pos + len(old)] = new
        offset += len(new) - len(old)
        cursor = pos + len(new)
    mode = stat.S_IMODE(os.lstat(real).st_mode)
    _atomic_write(real, "".join(out).encode("utf-8"), mode)


def _expect_base(real: str, base: Entry) -> None:
    cur = entry_for(real)
    if cur is None:
        raise Conflict("file no longer exists in the workspace")
    if cur.kind != base.kind or cur.sha != base.sha or cur.target != base.target:
        raise Conflict("file changed in the workspace since the stage was taken")


def apply(st: Stage, diff: Diff, selected: Optional[Iterable[int]] = None) -> Result:
    root = st.root
    chosen: Set[int] = {u.id for u in diff.units} if selected is None else set(selected)
    res = Result()
    by_path: Dict[str, List[Unit]] = {}
    for u in diff.units:
        if u.id in chosen:
            by_path.setdefault(u.path, []).append(u)
    touched: List[str] = []
    removed_paths: List[str] = []
    for path, units in by_path.items():
        try:
            kinds = {u.kind for u in units}
            hunks = [u for u in units if u.kind == "hunk"]
            src = os.path.join(st.stage_path, path)
            real = _target(root, path)
            if "create" in kinds or "rename" in kinds:
                new = diff.stage_manifest[path]
                cur = entry_for(real)
                same = cur is not None and cur.kind == new.kind and cur.sha == new.sha and cur.target == new.target
                if cur is not None and not same:
                    raise Conflict("a different file already exists in the workspace")
                if "rename" in kinds:
                    old_rel = units[0].old_path
                    old_real = _target(root, old_rel)
                    _expect_base(old_real, st.manifest[old_rel])
                if not same:
                    _copy_entry(src, real, new)
                if "rename" in kinds:
                    os.unlink(old_real)
                    _prune_empty_parents(root, old_real)
                    removed_paths.append(old_rel)
            elif "delete" in kinds:
                cur = entry_for(real)
                if cur is not None:
                    _expect_base(real, st.manifest[path])
                    os.unlink(real)
                    _prune_empty_parents(root, real)
                removed_paths.append(path)
            elif "replace" in kinds:
                new = diff.stage_manifest[path]
                cur = entry_for(real)
                if not (cur is not None and cur.kind == new.kind and cur.sha == new.sha and cur.target == new.target):
                    _expect_base(real, st.manifest[path])
                    _copy_entry(src, real, new)
            else:
                if hunks:
                    _apply_hunks(root, st, path, hunks)
                if "mode" in kinds:
                    new = diff.stage_manifest[path]
                    if os.path.isfile(real) and not os.path.islink(real):
                        os.chmod(real, new.mode)
            touched.append(path)
            res.applied += [u.id for u in units]
            res.files_changed.append(path)
        except Conflict as exc:
            res.conflicts.append((path, str(exc)))
    _rebase(st, touched, removed_paths)
    return res


def _rebase(st: Stage, touched: List[str], removed: List[str]) -> None:
    """Make the baseline match the real workspace for every file we just wrote."""
    for rel in removed:
        st.manifest.pop(rel, None)
        try:
            os.unlink(os.path.join(st.base_path, rel))
        except OSError:
            pass
    for rel in touched:
        real = os.path.join(st.root, rel)
        e = entry_for(real)
        base = os.path.join(st.base_path, rel)
        if e is None:
            st.manifest.pop(rel, None)
            if os.path.lexists(base):
                os.unlink(base)
            continue
        if os.path.lexists(base):
            os.unlink(base)
        _copy_entry(real, base, e)
        st.manifest[rel] = e
    st.last_rev = ""
    st.save()
