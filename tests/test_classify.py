import pytest

ROOT = "/work/proj"


@pytest.mark.parametrize("cmd,cat", [
    ("git push origin main", "push"),
    ("git -C . push --force", "push"),
    ("pip install requests", "install"),
    ("python3 -m pip install -r r.txt", "install"),
    ("npm install left-pad", "install"),
    ("pnpm add zod", "install"),
    ("sudo apt-get install -y jq", "install"),
    ("cargo install ripgrep", "install"),
    ("curl -X POST https://x.io -d '{}'", "network"),
    ("curl --data @f https://x.io", "network"),
    ("wget --post-data=a=b https://x.io", "network"),
    ("scp f user@host:/tmp", "network"),
    ("gh pr create --fill", "network"),
    ("echo hi > /etc/motd", "outside_write"),
    ("echo hi >> ~/.bashrc", "outside_write"),
    ("cp a.txt /usr/local/bin/a", "outside_write"),
    ("rm -rf ../other", "outside_delete"),
    ("rm ~/important.txt", "outside_delete"),
    ("sed -i 's/a/b/' /etc/hosts", "outside_write"),
    ("cat x | tee /var/log/x", "outside_write"),
    ("bash -c 'git push'", "push"),
    ("cd src && git push", "push"),
    ("echo a > $HOME/x", "outside_write"),
])
def test_held(mods, cmd, cat):
    cats = {f.category for f in mods["classify"].classify_command(cmd, ROOT, home="/home/u")}
    assert cat in cats, (cmd, cats)


@pytest.mark.parametrize("cmd", [
    "ls -la", "git status", "git diff", "git commit -m x", "git log --oneline",
    "pytest -q", "python script.py", "npm test", "npm run build", "pip list", "pip --version",
    "echo hi > out.txt", "echo hi > ./sub/out.txt", "cat a > /dev/null", "rm -rf build", "rm src/old.py",
    "curl https://example.com/file.txt", "curl -I https://x.io", "wget https://x.io/a.tgz",
    "cp a b", "mv a.txt sub/a.txt", f"echo hi > {ROOT}/x", "mkdir -p out/dir", "sed -i 's/a/b/' src/a.py",
    "grep -r foo . | sort | head", "make test 2>&1 | tail", "echo 'git push is a command'",
])
def test_not_held(mods, cmd):
    assert mods["classify"].classify_command(cmd, ROOT, home="/home/u") == [], cmd


def test_allow_paths(mods):
    assert mods["classify"].classify_command("echo a > /tmp/x", ROOT, allow=["/tmp"], home="/h") == []
    assert mods["classify"].classify_command("echo a > /tmp/x", ROOT, home="/h")


def test_file_tools(mods):
    c = mods["classify"]
    assert c.classify_tool("write_file", {"path": "/etc/passwd", "content": "x"}, ROOT)
    assert not c.classify_tool("write_file", {"path": "src/a.py", "content": "x"}, ROOT)
    assert c.classify_tool("terminal", {"command": "git push"}, ROOT)
    assert not c.classify_tool("read_file", {"path": "/etc/passwd"}, ROOT)


def test_message_says_not_contained(mods):
    f = mods["classify"].classify_command("git push", ROOT)[0]
    assert "NOT CONTAINED" in f.message()
