#!/usr/bin/env python3
"""Idempotently merge templates/settings.json into a Claude Code settings file.

  merge_settings.py [--check] [--target FILE] [--brain DIR]

Union semantics: permission strings and hook commands already present are not
added again; existing keys (model, effortLevel, ...) are never overridden.
<BRAIN_DIR> in the template is replaced by the brain path. Prints "no changes"
when the target already satisfies the template. --check writes nothing and
exits 1 on drift. Before the first change a one-time backup <target>.brain-bak is made.
"""
import argparse, json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except FileNotFoundError:
        return {}


def merge(cur, tpl):
    out = json.loads(json.dumps(cur))
    for k, v in tpl.items():
        if k == "permissions":
            perms = out.setdefault("permissions", {})
            for kind, items in v.items():
                have = perms.setdefault(kind, [])
                have.extend(i for i in items if i not in have)
        elif k == "hooks":
            hooks = out.setdefault("hooks", {})
            for event, groups in v.items():
                have = hooks.setdefault(event, [])
                cmds = {h.get("command") for g in have for h in g.get("hooks", [])}
                for g in groups:
                    if not all(h.get("command") in cmds for h in g.get("hooks", [])):
                        have.append(g)
                        cmds |= {h.get("command") for h in g.get("hooks", [])}
        else:
            out.setdefault(k, v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--brain", default=str(HERE.parent))
    a = ap.parse_args()
    tpl = json.loads((Path(a.brain) / "templates" / "settings.json").read_text()
                     .replace("<BRAIN_DIR>", a.brain))
    target = Path(a.target)
    cur = load(target)
    new = merge(cur, tpl)
    if new == cur:
        print("no changes")
        return 0
    if a.check:
        print(f"drift: {target} lacks entries from templates/settings.json (run scripts/install.sh)")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    bak = target.with_name(target.name + ".brain-bak")
    if target.exists() and not bak.exists():
        shutil.copy2(target, bak)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(new, indent=2) + "\n")
    tmp.replace(target)
    print(f"merged template into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
