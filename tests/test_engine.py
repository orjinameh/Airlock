import os
import stat

import pytest

import subprocess


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def stage_of(mods, root, **kw):
    return mods["stage"].create(str(root), **kw)


def edit_stage(st, rel, text):
    p = os.path.join(st.stage_path, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def test_stage_is_a_copy_and_real_workspace_untouched(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "src/app.py", "changed\n")
    assert (ws / "src" / "app.py").read_text().startswith("line 1")
    assert (st.dir / "base" / "src" / "app.py").read_text().startswith("line 1")


def test_ignore_rules_without_git(mods, ws):
    (ws / ".gitignore").write_text("*.log\nbuild/\n")
    (ws / "a.log").write_text("x")
    (ws / "build").mkdir()
    (ws / "build" / "o.bin").write_text("x")
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "m.js").write_text("x")
    names = mods["stage"].list_files(str(ws))
    assert "a.log" not in names and "build/o.bin" not in names and "node_modules/m.js" not in names
    assert "src/app.py" in names


def test_ignore_rules_with_git(mods, ws):
    sh("git", "init", "-q", cwd=ws)
    (ws / ".gitignore").write_text(".env\ndist/\n")
    (ws / ".env").write_text("SECRET=1\n")
    (ws / "dist").mkdir()
    (ws / "dist" / "x.js").write_text("x")
    st = stage_of(mods, ws)
    assert not os.path.exists(os.path.join(st.stage_path, ".env"))
    assert not os.path.exists(os.path.join(st.stage_path, "dist"))
    assert os.path.isdir(os.path.join(st.stage_path, ".git"))
    # a file the agent creates that is ignored never shows up in the diff
    edit_stage(st, "dist/new.js", "x")
    edit_stage(st, ".env", "NEW=1\n")
    assert mods["diffing"].compute(st).units == []


def test_diff_kinds(mods, ws):
    (ws / "bin.dat").write_bytes(b"\0\1\2\3")
    (ws / "old.txt").write_text("rename me\nplease\n")
    os.symlink("README.md", ws / "link")
    st = stage_of(mods, ws)
    sp = st.stage_path
    edit_stage(st, "src/app.py", open(os.path.join(sp, "src/app.py")).read().replace("line 5\n", "FIVE\n"))
    edit_stage(st, "new/dir/n.txt", "hello\n")
    os.remove(os.path.join(sp, "notes.txt"))
    os.rename(os.path.join(sp, "old.txt"), os.path.join(sp, "renamed.txt"))
    with open(os.path.join(sp, "bin.dat"), "wb") as fh:
        fh.write(b"\0\x09\x09")
    os.remove(os.path.join(sp, "link"))
    os.symlink("notes.txt", os.path.join(sp, "link"))
    os.chmod(os.path.join(sp, "README.md"), 0o755)
    d = mods["diffing"].compute(st)
    kinds = sorted((u.kind, u.path) for u in d.units)
    assert ("hunk", "src/app.py") in kinds
    assert ("create", "new/dir/n.txt") in kinds
    assert ("delete", "notes.txt") in kinds
    assert ("rename", "renamed.txt") in kinds
    assert ("replace", "bin.dat") in kinds
    assert ("replace", "link") in kinds
    assert ("mode", "README.md") in kinds
    assert [u.id for u in d.units] == list(range(1, len(d.units) + 1))


def test_apply_all_and_rebase(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "src/app.py", open(os.path.join(st.stage_path, "src/app.py")).read().replace("line 5\n", "FIVE\n"))
    edit_stage(st, "added.txt", "new\n")
    os.remove(os.path.join(st.stage_path, "notes.txt"))
    d = mods["diffing"].compute(st)
    res = mods["applying"].apply(st, d)
    assert not res.conflicts and len(res.applied) == len(d.units)
    assert "FIVE" in (ws / "src/app.py").read_text()
    assert (ws / "added.txt").read_text() == "new\n"
    assert not (ws / "notes.txt").exists()
    assert mods["diffing"].compute(st).units == []   # baseline caught up


def test_apply_selected_hunks_only(mods, ws):
    st = stage_of(mods, ws)
    text = open(os.path.join(st.stage_path, "src/app.py")).read()
    text = text.replace("line 3\n", "THREE\n").replace("line 35\n", "THIRTY-FIVE\n")
    edit_stage(st, "src/app.py", text)
    d = mods["diffing"].compute(st)
    hunks = [u for u in d.units if u.kind == "hunk"]
    assert len(hunks) == 2
    res = mods["applying"].apply(st, d, {hunks[0].id})
    real = (ws / "src/app.py").read_text()
    assert "THREE" in real and "THIRTY-FIVE" not in real and "line 35" in real
    left = mods["diffing"].compute(st)
    assert [u.kind for u in left.units] == ["hunk"] and "THIRTY-FIVE" in "".join(left.units[0].new_lines)


def test_conflict_when_real_file_changed(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "notes.txt", "agent version\n")
    edit_stage(st, "README.md", "# agent\n")
    (ws / "notes.txt").write_text("human edited meanwhile\n")
    d = mods["diffing"].compute(st)
    res = mods["applying"].apply(st, d)
    assert [p for p, _ in res.conflicts] == ["notes.txt"]
    assert (ws / "notes.txt").read_text() == "human edited meanwhile\n"   # never overwritten
    assert (ws / "README.md").read_text() == "# agent\n"


def test_hunk_applies_when_human_edited_elsewhere(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "src/app.py", open(os.path.join(st.stage_path, "src/app.py")).read().replace("line 30\n", "THIRTY\n"))
    p = ws / "src/app.py"
    p.write_text("inserted by human\n" + p.read_text())          # shifts every line by one
    d = mods["diffing"].compute(st)
    res = mods["applying"].apply(st, d)
    assert not res.conflicts
    text = p.read_text()
    assert text.startswith("inserted by human") and "THIRTY" in text and "line 30" not in text


def test_hunk_conflicts_when_context_changed(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "src/app.py", open(os.path.join(st.stage_path, "src/app.py")).read().replace("line 30\n", "THIRTY\n"))
    p = ws / "src/app.py"
    p.write_text(p.read_text().replace("line 30\n", "human thirty\n"))
    res = mods["applying"].apply(st, mods["diffing"].compute(st))
    assert res.conflicts and "human thirty" in p.read_text()


def test_created_file_conflicts_with_existing_different_file(mods, ws):
    st = stage_of(mods, ws)
    edit_stage(st, "new.txt", "agent\n")
    (ws / "new.txt").write_text("human\n")
    res = mods["applying"].apply(st, mods["diffing"].compute(st))
    assert res.conflicts and (ws / "new.txt").read_text() == "human\n"


def test_deleted_file_conflicts_if_human_changed_it(mods, ws):
    st = stage_of(mods, ws)
    os.remove(os.path.join(st.stage_path, "notes.txt"))
    (ws / "notes.txt").write_text("changed\n")
    res = mods["applying"].apply(st, mods["diffing"].compute(st))
    assert res.conflicts and (ws / "notes.txt").exists()


def test_rename_applies(mods, ws):
    st = stage_of(mods, ws)
    os.makedirs(os.path.join(st.stage_path, "moved"))
    os.rename(os.path.join(st.stage_path, "notes.txt"), os.path.join(st.stage_path, "moved/notes2.txt"))
    d = mods["diffing"].compute(st)
    assert [u.kind for u in d.units] == ["rename"]
    assert not mods["applying"].apply(st, d).conflicts
    assert not (ws / "notes.txt").exists() and (ws / "moved/notes2.txt").read_text() == "keep\n"


def test_binary_and_mode_and_symlink_apply(mods, ws):
    (ws / "bin.dat").write_bytes(b"\0\1")
    os.symlink("README.md", ws / "link")
    st = stage_of(mods, ws)
    with open(os.path.join(st.stage_path, "bin.dat"), "wb") as fh:
        fh.write(b"\0\2\2")
    os.remove(os.path.join(st.stage_path, "link"))
    os.symlink("notes.txt", os.path.join(st.stage_path, "link"))
    os.chmod(os.path.join(st.stage_path, "README.md"), 0o755)
    res = mods["applying"].apply(st, mods["diffing"].compute(st))
    assert not res.conflicts
    assert (ws / "bin.dat").read_bytes() == b"\0\2\2"
    assert os.readlink(ws / "link") == "notes.txt"
    assert stat.S_IMODE(os.stat(ws / "README.md").st_mode) == 0o755


def test_symlinks_that_escape_are_not_staged(mods, ws, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("top secret")
    os.symlink(str(outside), ws / "abs_link")
    os.symlink("../secret.txt", ws / "rel_link")
    st = stage_of(mods, ws)
    assert not os.path.lexists(os.path.join(st.stage_path, "abs_link"))
    assert not os.path.lexists(os.path.join(st.stage_path, "rel_link"))
    assert len(st.skipped) == 2


def test_apply_refuses_path_leaving_workspace_through_symlink(mods, ws, tmp_path):
    st = stage_of(mods, ws)
    edit_stage(st, "evil/x.txt", "pwn\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), ws / "evil")        # appeared in the real workspace after staging
    res = mods["applying"].apply(st, mods["diffing"].compute(st))
    assert res.conflicts and not (outside / "x.txt").exists()


def test_large_files_skipped_and_size_cap(mods, ws):
    (ws / "big.bin").write_bytes(b"x" * 3000)
    st = stage_of(mods, ws, max_file_bytes=1000)
    assert any("big.bin" in s for s in st.skipped)
    with pytest.raises(mods["stage"].StageError):
        mods["stage"].create(str(ws), max_total_bytes=100)


def test_large_directory(mods, tmp_path):
    root = tmp_path / "big"
    for d in range(30):
        (root / f"d{d}").mkdir(parents=True)
        for f in range(60):
            (root / f"d{d}" / f"f{f}.txt").write_text(f"{d}-{f}\n")
    st = stage_of(mods, root)
    assert len(st.manifest) == 1800
    os.remove(os.path.join(st.stage_path, "d3/f3.txt"))
    d = mods["diffing"].compute(st)
    assert [u.path for u in d.units] == ["d3/f3.txt"]


def test_empty_diff_and_rev_changes(mods, ws):
    st = stage_of(mods, ws)
    d0 = mods["diffing"].compute(st)
    assert d0.units == []
    edit_stage(st, "notes.txt", "a\n")
    r1 = mods["diffing"].compute(st).rev
    edit_stage(st, "notes.txt", "b\n")
    assert mods["diffing"].compute(st).rev != r1
