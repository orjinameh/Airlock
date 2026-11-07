"""Irreversibility classifier: which tool calls a staged copy cannot contain.

A copy of the workspace contains file changes inside the workspace. Everything else a command can
do (talk to the network, install software, write elsewhere on the machine) really happens, so the
plugin holds those calls for explicit approval and labels them "not contained".
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import Iterable, List, Optional

LABEL = "NOT CONTAINED"

_SEPARATORS = re.compile(r"\|\||&&|;|\||\n|&(?!>)")
_REDIRECT = re.compile(r"(?:^|[\s;&|])(?:\d?>>?|&>>?)\s*(\S+)")

_INSTALL = {
    "pip": {"install"}, "pip3": {"install"}, "pipx": {"install", "upgrade"},
    "npm": {"install", "i", "add", "ci", "update", "link"}, "pnpm": {"install", "i", "add", "update"},
    "yarn": {"install", "add", "upgrade"}, "bun": {"install", "add", "i"},
    "apt": {"install", "upgrade", "dist-upgrade"}, "apt-get": {"install", "upgrade", "dist-upgrade"},
    "dnf": {"install", "upgrade"}, "yum": {"install", "update"}, "brew": {"install", "upgrade"},
    "apk": {"add"}, "pacman": {"-S", "-Syu"}, "cargo": {"install", "add"}, "gem": {"install"},
    "go": {"install", "get"}, "poetry": {"add", "install"}, "uv": {"add", "sync"}, "conda": {"install"},
    "composer": {"require", "install"}, "nix-env": {"-i", "-iA"},
}
_NET_WRITE_TOOLS = {"scp", "sftp", "ftp", "nc", "ncat", "netcat", "telnet", "rsync", "ssh", "mosh"}
_WRITERS = {"rm", "rmdir", "mv", "cp", "touch", "mkdir", "chmod", "chown", "ln", "tee", "truncate", "install",
            "shred", "unlink"}
_SAFE_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/zero"}


@dataclass(frozen=True)
class Finding:
    category: str     # network, install, push, outside_write, outside_delete, privilege
    detail: str

    def message(self) -> str:
        return f"{LABEL}: {self.detail}. Sluice only contains file changes inside the workspace."


def _words(segment: str) -> List[str]:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _expand(path: str, home: str) -> str:
    if path.startswith("~"):
        path = home + path[1:]
    path = path.replace("${HOME}", home).replace("$HOME", home)
    return path


def _outside(path: str, root: str, home: str, allow: Iterable[str]) -> bool:
    if not path or path in _SAFE_SINKS or path.startswith("-"):
        return False
    if "$" in path or "`" in path:
        return True   # computed path: cannot prove it stays inside
    p = _expand(path, home)
    p = p if os.path.isabs(p) else os.path.join(root, p)
    p = os.path.normpath(p)
    r = os.path.normpath(root)
    if p == r or p.startswith(r + os.sep):
        return False
    return not any(p == a or p.startswith(os.path.normpath(a) + os.sep) for a in allow)


def classify_command(command: str, root: str, allow: Iterable[str] = (), home: Optional[str] = None) -> List[Finding]:
    home = home or os.path.expanduser("~")
    found: List[Finding] = []

    def add(cat: str, detail: str) -> None:
        f = Finding(cat, detail)
        if f not in found:
            found.append(f)

    for m in _REDIRECT.finditer(command):
        tgt = m.group(1).strip("'\"")
        if _outside(tgt, root, home, allow):
            add("outside_write", f"redirects output to {tgt}, outside the workspace")

    for seg in _SEPARATORS.split(command):
        w = _words(seg)
        while w and (re.fullmatch(r"[A-Za-z_]\w*=.*", w[0]) or w[0] in ("env", "command", "builtin", "nohup", "time")):
            w = w[1:]
        if not w:
            continue
        cmd = os.path.basename(w[0])
        args = w[1:]
        if cmd == "sudo" or cmd == "su" or cmd == "doas":
            add("privilege", "runs with elevated privileges")
            w = args
            if not w:
                continue
            cmd, args = os.path.basename(w[0]), w[1:]
        if cmd in ("bash", "sh", "zsh") and "-c" in args:
            i = args.index("-c")
            if i + 1 < len(args):
                for f in classify_command(args[i + 1], root, allow, home):
                    add(f.category, f.detail)
        if cmd == "eval":
            for f in classify_command(" ".join(args), root, allow, home):
                add(f.category, f.detail)
        # git
        if cmd == "git":
            sub, skip = "", False
            for a in args:
                if skip:
                    skip = False
                elif a in ("-C", "-c", "--git-dir", "--work-tree"):
                    skip = True
                elif not a.startswith("-"):
                    sub = a
                    break
            if sub == "push":
                add("push", "runs git push, which publishes commits to a remote")
        # network writes
        if cmd in ("curl", "wget", "http", "https", "xh"):
            joined = " ".join(args)
            if re.search(r"(?:^|\s)(-X\s*(POST|PUT|PATCH|DELETE)|--request\s+(POST|PUT|PATCH|DELETE))", joined, re.I) \
               or re.search(r"(?:^|\s)(-d|--data\S*|-F|--form|-T|--upload-file|--post-\S+|--json)(?:\s|=|$)", joined) \
               or (cmd in ("http", "https", "xh") and re.search(r"(?:^|\s)(POST|PUT|PATCH|DELETE)\s", joined)):
                add("network", f"sends data with {cmd}")
        if cmd in _NET_WRITE_TOOLS:
            add("network", f"uses {cmd}, which sends data off this machine")
        if cmd == "gh":
            sub = " ".join(a for a in args if not a.startswith("-"))[:40]
            if re.match(r"(pr|issue|release|repo|gist|workflow)\s+(create|merge|close|delete|edit|comment|run)", sub) \
               or (sub.startswith("api") and re.search(r"-X\s*(POST|PUT|PATCH|DELETE)|--method\s+(POST|PUT|PATCH|DELETE)|-f\s|-F\s", " ".join(args))):
                add("network", f"changes GitHub state with gh {sub}")
        # installs
        verbs = _INSTALL.get(cmd)
        if cmd == "python" or cmd == "python3":
            if args[:2] == ["-m", "pip"] and any(a in ("install", "uninstall") for a in args[2:3]):
                add("install", "installs Python packages")
        elif cmd == "uv" and args[:1] == ["pip"] and args[1:2] == ["install"]:
            add("install", "installs Python packages")
        elif verbs:
            sub = next((a for a in args if not a.startswith("-") or a in verbs), "")
            if sub in verbs or any(a in verbs for a in args[:2]):
                add("install", f"installs software with {cmd}")
        if cmd in ("npx", "pipx", "bunx", "uvx", "dlx") and cmd != "pipx":
            add("install", f"downloads and runs code with {cmd}")
        # writes outside the workspace
        if cmd in _WRITERS:
            targets = [a for a in args if not a.startswith("-")]
            if cmd in ("rm", "rmdir", "shred", "unlink"):
                for t in targets:
                    if _outside(t, root, home, allow):
                        add("outside_delete", f"deletes {t}, outside the workspace")
            else:
                for t in targets:
                    if _outside(t, root, home, allow):
                        add("outside_write", f"{cmd} touches {t}, outside the workspace")
        if cmd == "sed" and any(a == "-i" or a.startswith("-i") and not a.startswith("--") for a in args):
            for t in [a for a in args if not a.startswith("-")][1:]:
                if _outside(t, root, home, allow):
                    add("outside_write", f"edits {t} in place, outside the workspace")
        if cmd == "dd":
            for a in args:
                if a.startswith("of=") and _outside(a[3:], root, home, allow):
                    add("outside_write", f"dd writes {a[3:]}, outside the workspace")
    return found


def classify_tool(tool_name: str, args: dict, root: str, allow: Iterable[str] = ()) -> List[Finding]:
    """Findings for one tool call. Only terminal commands and file tools are inspected."""
    if not isinstance(args, dict):
        return []
    if tool_name in ("terminal", "execute_code", "bash", "shell"):
        cmd = args.get("command") or args.get("code") or ""
        return classify_command(cmd, root, allow) if isinstance(cmd, str) else []
    if tool_name in ("write_file", "patch", "edit_file", "delete_file"):
        path = args.get("path") or args.get("file_path") or ""
        if isinstance(path, str) and _outside(path, root, os.path.expanduser("~"), allow):
            return [Finding("outside_write", f"writes {path}, outside the workspace")]
    return []
