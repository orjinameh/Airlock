"""Stage store: copy a workspace, remember its baseline, scan trees.

Pure standard library plus the `git` binary (optional). Nothing here imports Hermes except
`state_root`, which asks Hermes where its home is.
"""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_IGNORE_DIRS = frozenset({
    "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".gradle",
})
GIT_DIR = ".git"
DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024


class StageError(RuntimeError):
    """A stage could not be created or used. The message is user facing."""


@dataclass(frozen=True)
class Entry:
    kind: str          # "file" or "link"
    mode: int = 0
    sha: str = ""      # sha256 of file bytes, empty for links
    target: str = ""   # link target, empty for files

    def to_json(self) -> dict:
        return {"kind": self.kind, "mode": self.mode, "sha": self.sha, "target": self.target}

    @staticmethod
    def from_json(d: dict) -> "Entry":
        return Entry(d["kind"], d.get("mode", 0), d.get("sha", ""), d.get("target", ""))


Manifest = Dict[str, Entry]


def state_root() -> Path:
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home()) / "plugin-data" / "sluice"


def stage_id_for(root: str) -> str:
    return hashlib.sha1(os.path.realpath(root).encode("utf-8", "surrogateescape")).hexdigest()[:12]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entry_for(path: str) -> Optional[Entry]:
    """Entry for a path on disk, or None if it is missing or not a regular file or symlink."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode):
        return Entry("link", 0, "", os.readlink(path))
    if stat.S_ISREG(st.st_mode):
        return Entry("file", stat.S_IMODE(st.st_mode), sha256_file(path))
    return None


# ---------------------------------------------------------------- listing

def _gitignore_matcher(root: str):
    """Fallback matcher for trees that are not git repositories: root .gitignore, simple patterns."""
    patterns: List[str] = []
    try:
        with open(os.path.join(root, ".gitignore"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("!"):
                    patterns.append(line)
    except OSError:
        pass

    def ignored(rel: str, is_dir: bool) -> bool:
        parts = rel.split("/")
        for pat in patterns:
            dir_only = pat.endswith("/")
            p = pat.strip("/")
            if not p:
                continue
            if pat.startswith("/") or "/" in p:
                if fnmatch.fnmatch(rel, p) or rel.startswith(p + "/"):
                    return True
                continue
            for i, part in enumerate(parts):
                last = i == len(parts) - 1
                if dir_only and last and not is_dir:
                    continue
                if fnmatch.fnmatch(part, p):
                    return True
        return False

    return ignored


def _git_listing(root: str) -> Optional[List[str]]:
    if not os.path.isdir(os.path.join(root, GIT_DIR)) or not shutil.which("git"):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", root, "-c", "core.quotepath=off", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, timeout=60, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p]


def list_files(root: str) -> List[str]:
    """Relative paths of the files and symlinks that belong to the workspace, sorted.

    Respects ignore rules: through `git ls-files` for a git checkout, else the root .gitignore
    plus a default list of dependency and cache directories. `.git` is never listed.
    """
    listed = _git_listing(root)
    found: List[str] = []
    if listed is not None:
        for rel in listed:
            if rel.split("/")[0] == GIT_DIR or any(p in DEFAULT_IGNORE_DIRS for p in rel.split("/")[:-1]):
                continue
            full = os.path.join(root, rel)
            if os.path.islink(full) or os.path.isfile(full):
                found.append(rel)
        return sorted(set(found))
    ignored = _gitignore_matcher(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        reldir = os.path.relpath(dirpath, root)
        reldir = "" if reldir == "." else reldir.replace(os.sep, "/")
        keep = []
        for d in dirnames:
            rel = f"{reldir}/{d}" if reldir else d
            if d == GIT_DIR or d in DEFAULT_IGNORE_DIRS or ignored(rel, True):
                continue
            if os.path.islink(os.path.join(dirpath, d)):
                found.append(rel)  # a symlink to a directory is listed as a link
                continue
            keep.append(d)
        dirnames[:] = sorted(keep)
        for f in filenames:
            rel = f"{reldir}/{f}" if reldir else f
            if not ignored(rel, False):
                found.append(rel)
    return sorted(set(found))


def scan(root: str) -> Manifest:
    man: Manifest = {}
    for rel in list_files(root):
        e = entry_for(os.path.join(root, rel))
        if e is not None:
            man[rel] = e
    return man


# ---------------------------------------------------------------- the stage

@dataclass
class Stage:
    root: str                      # the real workspace
    dir: Path                      # <state>/<id>
    manifest: Manifest = field(default_factory=dict)   # baseline entries
    skipped: List[str] = field(default_factory=list)
    created: float = 0.0
    last_rev: str = ""

    @property
    def stage_path(self) -> str:
        return str(self.dir / "stage")

    @property
    def base_path(self) -> str:
        return str(self.dir / "base")

    @property
    def meta_path(self) -> Path:
        return self.dir / "meta.json"

    @property
    def log_path(self) -> Path:
        return self.dir / "log.jsonl"

    def save(self) -> None:
        data = {
            "root": self.root, "created": self.created, "skipped": self.skipped, "last_rev": self.last_rev,
            "manifest": {k: v.to_json() for k, v in self.manifest.items()},
        }
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.meta_path)

    def log(self, command: str, cwd: str, returncode) -> None:
        rec = {"t": round(time.time(), 3), "cmd": command, "cwd": cwd, "exit": returncode}
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def log_event(self, **fields) -> None:
        rec = {"t": round(time.time(), 3), **fields}
        try:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    def read_log(self) -> List[dict]:
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out


def _link_stays_inside(root: str, rel: str, target: str) -> bool:
    if os.path.isabs(target):
        return False
    resolved = os.path.normpath(os.path.join(os.path.dirname(os.path.join(root, rel)), target))
    root_n = os.path.normpath(root)
    return resolved == root_n or resolved.startswith(root_n + os.sep)


def _copy_one(src: str, dst: str, e: Entry) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if e.kind == "link":
        os.symlink(e.target, dst)
    else:
        shutil.copy2(src, dst)


def create(root: str, *, copy_git: bool = True, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
           max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES) -> Stage:
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        raise StageError(f"workspace {root} is not a directory")
    sdir = state_root() / stage_id_for(root)
    if sdir.exists():
        shutil.rmtree(sdir)
    (sdir / "stage").mkdir(parents=True)
    (sdir / "base").mkdir()
    st = Stage(root=root, dir=sdir, created=time.time())
    total = 0
    try:
        for rel in list_files(root):
            src = os.path.join(root, rel)
            e = entry_for(src)
            if e is None:
                continue
            if e.kind == "link":
                if not _link_stays_inside(root, rel, e.target):
                    st.skipped.append(f"{rel}: symlink points outside the workspace")
                    continue
            else:
                size = os.path.getsize(src)
                if size > max_file_bytes:
                    st.skipped.append(f"{rel}: larger than {max_file_bytes // (1024 * 1024)} MB")
                    continue
                total += size
                if total > max_total_bytes:
                    raise StageError(
                        f"workspace is larger than {max_total_bytes // (1024 * 1024)} MB; point terminal.cwd at a "
                        "smaller project directory or raise plugins.entries.sluice.settings.max_workspace_mb")
            _copy_one(src, os.path.join(st.base_path, rel), e)
            _copy_one(src, os.path.join(st.stage_path, rel), e)
            st.manifest[rel] = e
        if copy_git and os.path.isdir(os.path.join(root, GIT_DIR)):
            shutil.copytree(os.path.join(root, GIT_DIR), os.path.join(st.stage_path, GIT_DIR), symlinks=True)
        st.save()
        _write_current(sdir.name)
    except BaseException:
        shutil.rmtree(sdir, ignore_errors=True)
        raise
    return st


def load(root: str) -> Optional[Stage]:
    sdir = state_root() / stage_id_for(root)
    return _load_dir(sdir)


def _load_dir(sdir: Path) -> Optional[Stage]:
    try:
        data = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (sdir / "stage").is_dir() or not (sdir / "base").is_dir():
        return None
    return Stage(
        root=data["root"], dir=sdir, created=data.get("created", 0.0), skipped=data.get("skipped", []),
        last_rev=data.get("last_rev", ""),
        manifest={k: Entry.from_json(v) for k, v in data.get("manifest", {}).items()},
    )


def _write_current(stage_id: str) -> None:
    root = state_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "current").write_text(stage_id, encoding="utf-8")


def current() -> Optional[Stage]:
    try:
        sid = (state_root() / "current").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return _load_dir(state_root() / sid) if sid else None


def mark_current(st: Stage) -> None:
    _write_current(st.dir.name)


def discard(st: Stage) -> None:
    shutil.rmtree(st.dir, ignore_errors=True)
    cur = state_root() / "current"
    try:
        if cur.read_text(encoding="utf-8").strip() == st.dir.name:
            cur.unlink()
    except OSError:
        pass


STALE_DAYS = 14


def prune_stale(keep: Optional[str] = None, days: int = STALE_DAYS) -> int:
    """Remove stages nobody has touched for `days` days. Returns how many were removed."""
    base = state_root()
    removed = 0
    cutoff = time.time() - days * 86400
    try:
        entries = list(base.iterdir())
    except OSError:
        return 0
    for d in entries:
        if not d.is_dir() or d.name == keep:
            continue
        try:
            newest = max([d.stat().st_mtime] + [p.stat().st_mtime for p in (d / "meta.json", d / "log.jsonl") if p.exists()])
        except OSError:
            continue
        if newest < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


@contextlib.contextmanager
def locked(st: Stage):
    """Exclusive lock on a stage so two applies (two sessions) cannot interleave."""
    try:
        import fcntl
    except ImportError:   # not posix: no locking available
        yield
        return
    fd = os.open(str(st.dir / ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def drift(st: Stage) -> List[str]:
    """Files whose real copy no longer matches the baseline (you or something else changed them since)."""
    out = []
    for rel, e in st.manifest.items():
        cur = entry_for(os.path.join(st.root, rel))
        if cur is None or cur.kind != e.kind or cur.sha != e.sha or cur.target != e.target:
            out.append(rel)
    return out


def open_or_create(root: str, **kw) -> Stage:
    """Reuse the stage for this workspace if one is pending, else take a fresh copy."""
    st = load(root)
    if st is not None and os.path.realpath(st.root) == os.path.realpath(root):
        mark_current(st)
        prune_stale(keep=st.dir.name)
        return st
    st = create(root, **kw)
    prune_stale(keep=st.dir.name)
    return st
