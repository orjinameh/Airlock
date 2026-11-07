"""Sluice: a Hermes terminal backend that stages the agent's changes for review.

    hermes plugins enable sluice
    hermes config set terminal.backend sluice

The agent's commands and file tools run in a staged copy of the workspace. `/sluice diff` shows what
changed, `/sluice apply` lands the changes you approve. Calls a copy cannot contain are held for
approval and labelled not contained. See README.md.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Callable, Dict, Optional, Tuple

from agent.terminal_env_provider import TerminalEnvironmentProvider

logger = logging.getLogger(__name__)

BACKEND_NAME = "sluice"
SETTING_KEYS = ("copy_git", "max_file_mb", "max_workspace_mb", "allow_paths")
_PLACEHOLDERS = frozenset({"", ".", "auto", "cwd"})


def _terminal_env(name: str, default: str = "") -> str:
    from tools.terminal_scope import terminal_env

    return terminal_env(name, default)


def workspace_root() -> str:
    """The real workspace: terminal.cwd, else the directory Hermes runs in."""
    value = _terminal_env("TERMINAL_CWD", "").strip()
    root = os.getcwd() if value in _PLACEHOLDERS else os.path.abspath(os.path.expanduser(value))
    root = os.path.realpath(root)
    home = os.path.realpath(os.path.expanduser("~"))
    if root in (os.sep, home):
        from .stage import StageError

        raise StageError(
            "Sluice will not copy your whole home directory or the filesystem root. "
            "Set terminal.cwd to a project directory: hermes config set terminal.cwd /path/to/project")
    return root


class SluiceProvider(TerminalEnvironmentProvider):
    """`terminal.backend: sluice`. Commands run on this machine, in a staged copy of the workspace."""

    name = BACKEND_NAME
    display_name = "Sluice"
    # Commands run on this host, so Hermes keeps its host hints and dangerous-command prompts.
    is_remote = False
    is_container = False

    def __init__(self, get_config: Optional[Callable[..., Any]] = None) -> None:
        self._get_config = get_config

    @property
    def description(self) -> str:
        return "Run commands in a staged copy of the workspace and review the diff before it lands."

    @property
    def env_description(self) -> str:
        return "this machine, in a Sluice staged copy of the workspace"

    @property
    def default_cwd(self) -> Optional[str]:
        try:
            return workspace_root()
        except Exception:
            return None

    def settings(self) -> Dict[str, Any]:
        if self._get_config is None:
            return {}
        out = {}
        for key in SETTING_KEYS:
            try:
                out[key] = self._get_config(key, None)
            except Exception:
                out[key] = None
        return out

    def is_available(self) -> bool:
        return not sys.platform.startswith("win")

    def probe(self) -> Tuple[str, str]:
        return ("ready", "") if self.is_available() else ("unavailable", "Sluice supports Linux and macOS.")

    def setup_instructions(self):
        return [
            "Commands and file edits run in a staged copy of terminal.cwd.",
            "Review with /sluice diff, land with /sluice apply, reject with /sluice discard.",
            "Set terminal.cwd to the project directory: hermes config set terminal.cwd /path/to/project",
        ]

    def create_environment(self, *, cwd: str, timeout: int, task_id: str = "default", image: Optional[str] = None,
                           container_config: Optional[dict] = None, **kwargs: Any):
        from . import stage as stage_mod
        from .env import SluiceEnvironment

        cfg = self.settings()
        mb = 1024 * 1024
        opts = {
            "copy_git": True if cfg.get("copy_git") is None else bool(cfg["copy_git"]),
            "max_file_bytes": int(cfg.get("max_file_mb") or stage_mod.DEFAULT_MAX_FILE_BYTES // mb) * mb,
            "max_total_bytes": int(cfg.get("max_workspace_mb") or stage_mod.DEFAULT_MAX_TOTAL_BYTES // mb) * mb,
        }
        st = stage_mod.open_or_create(workspace_root(), **opts)
        return SluiceEnvironment(stage=st, cwd=cwd, timeout=timeout)

    def prompt_note(self, _session_info: Any = None) -> str:
        if (_terminal_env("TERMINAL_ENV", "local") or "local").strip().lower() != BACKEND_NAME:
            return ""
        return (
            "Terminal backend: Sluice. Your commands and file edits run in a staged copy of the workspace, at "
            "the same paths you see. The user reviews the diff and decides what lands in the real files, so "
            "do the work normally and do not ask them to apply anything yourself. Installing packages, "
            "network writes, git push and writes outside the workspace are not contained by the copy and "
            "need the user's approval; avoid them unless the task requires them. When you finish, tell the "
            "user to run /sluice diff to review your changes."
        )


def _make_hook(get_config: Callable[..., Any]):
    def pre_tool_call(tool_name: str = "", args: Optional[dict] = None, **_kw: Any):
        try:
            if (_terminal_env("TERMINAL_ENV", "local") or "local").strip().lower() != BACKEND_NAME:
                return None
            from . import classify, stage as stage_mod

            st = stage_mod.current()
            root = st.root if st is not None else workspace_root()
            allow = get_config("allow_paths", None) or []
            findings = classify.classify_tool(tool_name, args or {}, root, allow)
            if not findings:
                return None
            if st is not None:
                for f in findings:
                    st.log_event(held=True, tool=tool_name, category=f.category, detail=f.detail)
            return {"action": "approve", "message": "\n".join(f.message() for f in findings)}
        except Exception:
            logger.debug("sluice pre_tool_call failed", exc_info=True)
            return None

    return pre_tool_call


def register(ctx) -> None:
    """Plugin entry point."""
    from . import review

    provider = SluiceProvider(get_config=ctx.get_config)
    ctx.register_terminal_environment_provider(provider)
    ctx.register_hook("pre_tool_call", _make_hook(ctx.get_config))
    ctx.register_command("sluice", review.handle, description="Review, apply or discard the agent's staged changes",
                         args_hint="[status|diff|apply|discard|log]")
    ctx.register_cli_command("sluice", "Review what the agent changed before it lands", review.cli_setup,
                             review.cli_handler)
    ctx.register_system_prompt_section("sluice-backend", provider.prompt_note)


__all__ = ["SluiceProvider", "register", "workspace_root"]
