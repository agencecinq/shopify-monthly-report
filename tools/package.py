#!/usr/bin/env python3
"""
Builds the plugin archive a merchant uploads in Claude Desktop or claude.ai
(Customize > Plugins > Upload plugin).

Only what the plugin needs at run time goes in: the manifest, the skill, the
licence and the READMEs. Tests, examples, screenshots and tooling stay out.

    python3 tools/package.py            # writes dist/trente-<version>.zip
"""

import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCLUDE = [".claude-plugin/plugin.json", "skills", "LICENSE", "README.md",
           "README.fr.md"]
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_EXT = {".pyc", ".pptx"}


def files():
    for entry in INCLUDE:
        path = os.path.join(ROOT, entry)
        if os.path.isfile(path):
            yield entry
            continue
        for base, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(names):
                if os.path.splitext(name)[1] in SKIP_EXT or name.startswith("."):
                    continue
                yield os.path.relpath(os.path.join(base, name), ROOT)


def main():
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{manifest['name']}-{manifest['version']}.zip")
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files():
            z.write(os.path.join(ROOT, rel), rel)
            count += 1
    size = os.path.getsize(out)
    print(f"{out}: {count} files, {size / 1024:.0f} KB")
    if any(name.startswith("bin/") for name in zipfile.ZipFile(out).namelist()):
        sys.exit("a top-level bin/ directory prevents installation outside Claude Code")


if __name__ == "__main__":
    main()
