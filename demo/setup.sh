#!/usr/bin/env bash
# Creates a small messy repo for the Sluice demo at ~/demo-repo, with a local bare remote so
# `git push` is harmless. Run it again any time to reset the demo.
set -euo pipefail
D="${1:-$HOME/demo-repo}"
rm -rf "$D" "$D.remote.git"
git init -q --bare "$D.remote.git"
mkdir -p "$D/shop" "$D/tests"
cd "$D"
git init -q

cat > shop/cart.py <<'PY'
import os, sys, json
import random
from datetime import datetime

def calc(a, b, c):
    x = 0
    for i in a:
        x = x + i * b
    if c == True:
        x = x - x * 0.1
    print("total is", x)
    return x

def calc2(a, b, c):
    x = 0
    for i in a:
        x = x + i * b
    if c == True:
        x = x - x * 0.1
    return x

def fmt(n):
    return "$" + str(round(n, 2))

def unused_helper():
    pass
PY

cat > shop/orders.py <<'PY'
import json
from shop.cart import calc2, fmt

def make_order(items, qty, vip):
    t = calc2(items, qty, vip)
    o = {"total": t, "pretty": fmt(t)}
    print("order made", o)
    return o

def save(o, path):
    f = open(path, "w")
    f.write(json.dumps(o))
    f.close()

def load(path):
    f = open(path)
    d = json.loads(f.read())
    f.close()
    return d
PY

cat > shop/notes.py <<'PY'
# TODO: clean this file up
def x(q):
    r = []
    for z in q:
        if z != None:
            r.append(z)
    return r

def y(q):
    r = []
    for z in q:
        if z != None:
            r.append(z)
    return r
PY

cat > tests/test_cart.py <<'PY'
from shop.cart import calc2

def test_total():
    assert calc2([10, 20], 2, False) == 60

def test_vip_discount():
    assert round(calc2([10, 20], 2, True), 2) == 54.0
PY

printf '# shop\n\nA tiny shopping cart.\n' > README.md
touch shop/__init__.py
printf '.env\n__pycache__/\n' > .gitignore
git add -A
git -c user.name=demo -c user.email=demo@example.com commit -qm "initial messy version"
git branch -M main
git remote add origin "$D.remote.git"
git push -q -u origin main 2>/dev/null
echo "Demo repo ready at $D"
