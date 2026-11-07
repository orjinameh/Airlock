"""The backend against real Hermes code: commands, file tools and the registry."""

import json
import os

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="posix only")


@pytest.fixture
def backend(mods, ws, monkeypatch):
    import sluice_plugin as plugin
    from tools import terminal_tool
    from tools.file_tools import clear_file_ops_cache

    monkeypatch.setenv("TERMINAL_CWD", str(ws))
    provider = plugin.SluiceProvider(get_config=lambda k, d=None: d)
    env = provider.create_environment(cwd=str(ws), timeout=30, task_id="t1")
    task = "sluice-test"
    monkeypatch.setitem(terminal_tool._active_environments, terminal_tool._resolve_container_task_id(task), env)
    yield env, ws, task
    clear_file_ops_cache()
    env.cleanup()


def dispatch(name, task, **args):
    from tools.registry import registry

    return json.loads(registry.dispatch(name, args, task_id=task))


def test_commands_run_in_stage_and_see_real_paths(backend):
    env, ws, _ = backend
    r = env.execute(f"cd {ws} && pwd && echo hi > created.txt && printf 'x' >> README.md && ls")
    assert str(ws) in r["output"] and env._sluice_path not in r["output"]
    assert not (ws / "created.txt").exists()
    assert (ws / "README.md").read_text() == "# demo\n"
    assert os.path.exists(os.path.join(env._sluice_path, "created.txt"))


def test_result_cwd_is_the_real_path(backend):
    env, ws, _ = backend
    r = env.execute("cd src && pwd")
    assert r["cwd"] == str(ws / "src") and r["output"].strip() == str(ws / "src")
    r2 = env.execute("pwd", cwd=r["cwd"])      # Hermes passes the recorded cwd back
    assert r2["output"].strip() == str(ws / "src")


def test_relative_and_home_forms_do_not_leak(backend, monkeypatch, tmp_path):
    env, ws, _ = backend
    env.execute("echo rel > rel.txt")
    env.execute(f"echo abs > {ws}/abs.txt")
    env.execute(f"echo abs2 > {ws}/src/../abs2.txt")
    env.execute("cd src && echo nested > n.txt")
    for name in ("rel.txt", "abs.txt", "abs2.txt", "src/n.txt"):
        assert not (ws / name).exists(), name
        assert os.path.exists(os.path.join(env._sluice_path, name)), name


def test_sibling_directory_with_same_prefix_is_not_rewritten(backend, tmp_path):
    env, ws, _ = backend
    sibling = str(ws) + "2"
    os.makedirs(sibling)
    env.execute(f"echo ok > {sibling}/f.txt")
    assert os.path.exists(os.path.join(sibling, "f.txt"))   # outside paths are untouched (and uncontained)


def test_cd_persists_and_cwd_setter_cannot_escape(backend):
    env, ws, _ = backend
    env.execute("cd src")
    assert env.cwd == os.path.join(env._sluice_path, "src")
    env.cwd = str(ws)               # what Hermes does with a session cwd record
    assert env.cwd == env._sluice_path
    env.cwd = "/root"               # unusable container style default
    assert env.cwd == env._sluice_path
    assert env._under_stage(env.cwd)


def test_file_tools_never_touch_the_real_workspace(backend):
    env, ws, task = backend
    read = dispatch("read_file", task, path=str(ws / "README.md"))
    assert "demo" in json.dumps(read)
    w = dispatch("write_file", task, path=str(ws / "b.txt"), content="gamma\n")
    assert "error" not in w, w
    p = dispatch("patch", task, path=str(ws / "notes.txt"), old_string="keep", new_string="changed")
    assert "error" not in p, p
    found = dispatch("search_files", task, pattern="changed", path=str(ws))
    assert [m["path"] for m in found.get("matches", [])] == [str(ws / "notes.txt")], found
    assert not (ws / "b.txt").exists()
    assert (ws / "notes.txt").read_text() == "keep\n"
    assert open(os.path.join(env._sluice_path, "b.txt")).read() == "gamma\n"


def test_command_log_and_review_roundtrip(backend, mods):
    env, ws, task = backend
    env.execute("false")
    dispatch("write_file", task, path=str(ws / "new.txt"), content="hello\n")
    review = mods["review"]
    status = review.handle("status")
    assert "1 changes in 1 files" in status and "Commands run in the stage" in status
    assert "exit   1" in review.handle("log")
    # apply without looking first is refused, and after a stage change it asks to look again
    assert "review first" in review.handle("apply all").lower()
    shown = review.handle("diff")
    assert "new.txt" in shown and "[1]" in shown
    dispatch("write_file", task, path=str(ws / "new2.txt"), content="more\n")
    assert "moved since" in review.handle("apply all")
    review.handle("diff")
    out = review.handle("apply all")
    assert "applied 2" in out
    assert (ws / "new.txt").read_text() == "hello\n" and (ws / "new2.txt").exists()


def test_discard_leaves_real_workspace_exactly_as_it_was(backend, mods):
    env, ws, task = backend
    before = sorted(p.name for p in ws.rglob("*"))
    env.execute("rm -rf src && echo x > a && echo y > README.md")
    mods["review"].handle("diff")
    assert "discarded" in mods["review"].handle("discard")
    assert sorted(p.name for p in ws.rglob("*")) == before
    assert (ws / "README.md").read_text() == "# demo\n"
    assert mods["stage"].current() is None


def test_stage_is_reused_across_environment_recreation(backend, mods):
    env, ws, task = backend
    env.execute("echo kept > kept.txt")
    import sluice_plugin as plugin

    env2 = plugin.SluiceProvider().create_environment(cwd=str(ws), timeout=30)
    try:
        assert os.path.exists(os.path.join(env2._sluice_path, "kept.txt"))
    finally:
        env2.cleanup()


def test_refuses_home_directory_and_root(mods, monkeypatch):
    import sluice_plugin as plugin

    monkeypatch.setenv("TERMINAL_CWD", os.path.expanduser("~"))
    with pytest.raises(mods["stage"].StageError):
        plugin.workspace_root()
    monkeypatch.setenv("TERMINAL_CWD", "/")
    with pytest.raises(mods["stage"].StageError):
        plugin.workspace_root()
