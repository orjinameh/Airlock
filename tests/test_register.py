import sluice_plugin as plugin


class Ctx:
    def __init__(self):
        self.calls = []

    def get_config(self, k, d=None):
        return d

    def __getattr__(self, name):
        def rec(*a, **k):
            self.calls.append((name, a, k))
        return rec


def test_register_surfaces():
    ctx = Ctx()
    plugin.register(ctx)
    names = [c[0] for c in ctx.calls]
    assert "register_terminal_environment_provider" in names
    hook = [c for c in ctx.calls if c[0] == "register_hook"]
    assert [h[1][0] for h in hook] == ["pre_tool_call"]
    assert [c[1][0] for c in ctx.calls if c[0] == "register_command"] == ["sluice"]


def test_provider_flags_keep_hermes_approvals_on():
    p = plugin.SluiceProvider()
    assert p.name == "sluice" and p.is_container is False and p.is_remote is False
    assert p.skip_container_guards is False


def test_hook_inactive_on_other_backends(monkeypatch, tmp_path):
    ctx = Ctx()
    hook = plugin._make_hook(ctx.get_config)
    monkeypatch.setenv("TERMINAL_ENV", "local")
    assert hook(tool_name="terminal", args={"command": "git push"}) is None


def test_hook_holds_when_active(monkeypatch, ws):
    ctx = Ctx()
    hook = plugin._make_hook(ctx.get_config)
    monkeypatch.setenv("TERMINAL_ENV", "sluice")
    monkeypatch.setenv("TERMINAL_CWD", str(ws))
    out = hook(tool_name="terminal", args={"command": "git push origin main"})
    assert out["action"] == "approve" and "NOT CONTAINED" in out["message"]
    assert hook(tool_name="terminal", args={"command": "ls"}) is None
