"""The Sluice execution environment: LocalEnvironment pointed at a staged copy of the workspace.

The model keeps seeing the real workspace paths. Every command and every file tool call is rewritten
to the staged copy on the way in, and the staged path is rewritten back to the real one in the
output, so nothing under the real workspace changes until the user applies a reviewed diff.
This is path rewriting, not an operating system sandbox: see README for what it does not contain.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from tools.environments.local import LocalEnvironment

from .stage import Stage

_BEFORE = r"(?<![\w./~$\-])"
_AFTER = r"(?![\w.\-])"


def _forms(root: str) -> List[str]:
    """Every way a command may spell the workspace root."""
    forms = {root, os.path.realpath(root), os.path.abspath(root)}
    home = os.path.expanduser("~")
    for r in list(forms):
        if home and home != os.sep and (r == home or r.startswith(home + os.sep)):
            rest = r[len(home):]
            forms.update({"~" + rest, "$HOME" + rest, "${HOME}" + rest})
    return sorted(forms, key=len, reverse=True)


def _compile(forms: List[str]) -> "re.Pattern[str]":
    return re.compile(_BEFORE + "(?:" + "|".join(re.escape(f) for f in forms) + ")" + _AFTER)


class SluiceEnvironment(LocalEnvironment):
    uses_host_filesystem = False   # file tools go through execute(), so they see the stage

    def __init__(self, *, stage: Stage, cwd: str = "", timeout: int = 60, persistent: bool = True):
        self._sluice_stage = stage
        self._sluice_root = stage.root
        self._sluice_path = stage.stage_path
        self._to_stage_re = _compile(_forms(stage.root))
        self._to_real_re = _compile([stage.stage_path])
        self._sluice_cwd = stage.stage_path
        super().__init__(cwd=self._map_cwd(cwd), timeout=timeout, persistent=persistent)

    # -- paths ------------------------------------------------------------
    def _to_stage(self, text: str) -> str:
        return self._to_stage_re.sub(lambda _m: self._sluice_path, text)

    def _to_real(self, text: str) -> str:
        return self._to_real_re.sub(lambda _m: self._sluice_root, text)

    def _under_stage(self, path: str) -> bool:
        p = os.path.normpath(path)
        return p == self._sluice_path or p.startswith(self._sluice_path + os.sep)

    def _map_cwd(self, value: str) -> str:
        """Any cwd Hermes hands us, as a directory inside the stage. A real workspace path is
        translated; a path outside both falls back to the stage root, never to the real tree."""
        if not value:
            return self._sluice_path
        mapped = self._to_stage(value)
        if self._under_stage(mapped) and os.path.isdir(mapped):
            return mapped
        return self._sluice_path

    @property
    def cwd(self) -> str:
        return self._sluice_cwd

    @cwd.setter
    def cwd(self, value: str) -> None:
        # Hermes assigns the real workspace path here (session cwd records, project switching).
        # Popen would run in it, so it is mapped into the stage first.
        self._sluice_cwd = self._map_cwd(value) if value else self._sluice_path

    # -- execution --------------------------------------------------------
    def execute(self, command: str, cwd: str = "", **kwargs):
        run_cwd = self._map_cwd(cwd) if cwd else ""
        result = super().execute(self._to_stage(command), cwd=run_cwd, **kwargs)
        if isinstance(result, dict) and isinstance(result.get("output"), str):
            result["output"] = self._to_real(result["output"])
        if isinstance(result, dict) and isinstance(result.get("cwd"), str):
            result["cwd"] = self._to_real(result["cwd"])   # Hermes records this as the session cwd
        try:
            self._sluice_stage.log(command, self._to_real(run_cwd or self._sluice_cwd),
                                   result.get("returncode", result.get("exit_code")))
        except OSError:
            pass
        return result
